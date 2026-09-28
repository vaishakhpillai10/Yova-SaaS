from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from asset_mgmt.models import InventoryBalance, StockTransaction


def _balance_for_update(item, location):
    balance, _ = InventoryBalance.objects.select_for_update().get_or_create(
        item=item, location=location, defaults={'quantity': Decimal('0')}
    )
    return balance


def _refresh_item_total(item):
    total = item.balances.aggregate(total=Sum('quantity'))['total'] or Decimal('0')
    item.current_stock = total
    item.save(update_fields=['current_stock', 'updated_at'])


@transaction.atomic
def post_goods_receipt(receipt, user):
    receipt = receipt.__class__.objects.select_for_update().select_related('item', 'received_location', 'purchase_order').get(pk=receipt.pk)
    if receipt.status != 'DRAFT':
        raise ValidationError('Only a draft goods receipt can be posted.')
    purchase_order = receipt.purchase_order.__class__.objects.select_for_update().get(pk=receipt.purchase_order_id)
    already_received = purchase_order.goods_receipts.filter(status='POSTED').aggregate(total=Sum('quantity_received'))['total'] or Decimal('0')
    if already_received + receipt.quantity_received > purchase_order.quantity:
        remaining = purchase_order.quantity - already_received
        raise ValidationError(f'Receipt exceeds PO quantity. Remaining receivable quantity is {remaining}.')
    balance = _balance_for_update(receipt.item, receipt.received_location)
    balance.quantity += receipt.quantity_received
    balance.save(update_fields=['quantity', 'updated_at'])
    StockTransaction.objects.create(
        item=receipt.item, transaction_type='RECEIPT', quantity=receipt.quantity_received,
        to_location=receipt.received_location, reference_type='GoodsReceipt', reference_no=receipt.receipt_no,
        posted_by=user, remarks=receipt.remarks,
    )
    receipt.status = 'POSTED'
    receipt.posted_by = user
    receipt.posted_at = timezone.now()
    receipt.save(update_fields=['status', 'posted_by', 'posted_at', 'updated_at'])
    new_total = already_received + receipt.quantity_received
    purchase_order.status = 'RECEIVED' if new_total == purchase_order.quantity else 'PARTIAL_RECEIVED'
    purchase_order.save(update_fields=['status', 'updated_at'])

    # If this PO was raised for a WO shortage, immediately reserve received stock to that WO.
    pr = purchase_order.purchase_request
    if pr.work_order_id:
        from asset_mgmt.models import InventoryReservation, WorkOrderSpare
        remaining_receipt = Decimal(receipt.quantity_received)
        for line in WorkOrderSpare.objects.select_for_update().filter(purchase_request=pr, spare_part=receipt.item):
            if remaining_receipt <= 0:
                break
            need = max(Decimal('0'), Decimal(line.quantity_required) - Decimal(line.quantity_reserved) - Decimal(line.quantity_used))
            take = min(need, remaining_receipt)
            if take <= 0:
                continue
            reservation = InventoryReservation.objects.filter(
                work_order_spare=line, item=receipt.item, location=receipt.received_location,
                status__in=['ACTIVE', 'PARTIAL'],
            ).first()
            if reservation:
                reservation.quantity += take
                reservation.status = 'ACTIVE'
                reservation.reserved_by = user
                reservation.save(update_fields=['quantity', 'status', 'reserved_by', 'updated_at'])
            else:
                InventoryReservation.objects.create(
                    work_order_spare=line, item=receipt.item, location=receipt.received_location,
                    quantity=take, status='ACTIVE', reserved_by=user,
                )
            line.quantity_reserved += take
            line.reservation_status = 'RESERVED' if line.quantity_reserved + line.quantity_used >= line.quantity_required else 'PARTIAL'
            line.save(update_fields=['quantity_reserved', 'reservation_status', 'updated_at'])
            remaining_receipt -= take

    _refresh_item_total(receipt.item)
    return receipt


@transaction.atomic
def post_material_issue(issue, user):
    issue = issue.__class__.objects.select_for_update().select_related('item', 'source_location').get(pk=issue.pk)
    if issue.status != 'DRAFT':
        raise ValidationError('Only a draft material issue can be posted.')
    if issue.work_order_id:
        if issue.work_order.technical_lock or issue.work_order.status not in {'RELEASED', 'IN_PROGRESS'}:
            raise ValidationError('Material can only be issued to a Released or In Progress work order before TECO.')
        from asset_mgmt.models import WorkOrderSpare
        planned_qs = WorkOrderSpare.objects.filter(work_order_id=issue.work_order_id, spare_part_id=issue.item_id)
        if issue.operation_id:
            planned_qs = planned_qs.filter(operation_id=issue.operation_id)
        elif planned_qs.values('operation_id').distinct().count() > 1:
            raise ValidationError('This spare is planned on multiple operations; select the operation before posting the material issue.')
        planned = planned_qs.first()
        if not planned:
            raise ValidationError('This material is not planned for the selected work order/operation.')
        already_posted = issue.work_order.material_issues.filter(
            item_id=issue.item_id, status='POSTED'
        )
        if issue.operation_id:
            already_posted = already_posted.filter(operation_id=issue.operation_id)
        posted_qty = already_posted.aggregate(total=Sum('quantity_issued'))['total'] or Decimal('0')
        remaining_plan = planned.quantity_required - posted_qty
        if issue.quantity_issued > remaining_plan:
            raise ValidationError(f'Issue exceeds planned requirement. Remaining planned quantity is {remaining_plan}.')
    balance = _balance_for_update(issue.item, issue.source_location)
    from asset_mgmt.models import InventoryReservation
    active_reservations = InventoryReservation.objects.select_for_update().filter(
        item=issue.item, location=issue.source_location, status__in=['ACTIVE', 'PARTIAL']
    )
    own_reserved = Decimal('0')
    if issue.work_order_id:
        own_qs = active_reservations.filter(work_order_spare__work_order_id=issue.work_order_id)
        if issue.operation_id:
            own_qs = own_qs.filter(work_order_spare__operation_id=issue.operation_id)
        own_reserved = own_qs.aggregate(total=Sum('quantity'))['total'] or Decimal('0')
    total_reserved = active_reservations.aggregate(total=Sum('quantity'))['total'] or Decimal('0')
    other_reserved = max(Decimal('0'), total_reserved - own_reserved)
    usable = max(Decimal('0'), balance.quantity - other_reserved)
    if usable < issue.quantity_issued:
        raise ValidationError(f'Insufficient uncommitted stock. Usable quantity is {usable}; {other_reserved} is reserved for other work orders.')
    balance.quantity -= issue.quantity_issued
    balance.save(update_fields=['quantity', 'updated_at'])
    StockTransaction.objects.create(
        item=issue.item, transaction_type='ISSUE', quantity=issue.quantity_issued,
        from_location=issue.source_location, reference_type='MaterialIssue', reference_no=issue.issue_no,
        posted_by=user, remarks=issue.remarks,
    )
    issue.status = 'POSTED'
    issue.posted_by = user
    issue.posted_at = timezone.now()
    issue.save(update_fields=['status', 'posted_by', 'posted_at', 'updated_at'])
    if issue.work_order_id:
        from asset_mgmt.models import InventoryReservation, WorkOrderSpare
        planned_qs = WorkOrderSpare.objects.filter(work_order_id=issue.work_order_id, spare_part_id=issue.item_id)
        if issue.operation_id:
            planned_qs = planned_qs.filter(operation_id=issue.operation_id)
        elif planned_qs.values('operation_id').distinct().count() > 1:
            raise ValidationError('This spare is planned on multiple operations; select the operation before posting the material issue.')
        planned = planned_qs.first()
        if planned:
            planned.quantity_used = planned.quantity_used + issue.quantity_issued
            if planned.quantity_used >= planned.quantity_required:
                planned.reservation_status = 'ISSUED'
            planned.save(update_fields=['quantity_used', 'reservation_status', 'updated_at'])
            remaining = issue.quantity_issued
            for reservation in InventoryReservation.objects.select_for_update().filter(work_order_spare=planned, location=issue.source_location, status__in=['ACTIVE','PARTIAL']).order_by('reserved_at'):
                if remaining <= 0:
                    break
                if reservation.quantity <= remaining:
                    remaining -= reservation.quantity
                    reservation.status = 'ISSUED'
                else:
                    reservation.quantity -= remaining
                    remaining = Decimal('0')
                    reservation.status = 'PARTIAL'
                reservation.save(update_fields=['quantity','status','updated_at'])
    _refresh_item_total(issue.item)
    return issue


@transaction.atomic
def post_stock_transfer(transfer, user):
    transfer = transfer.__class__.objects.select_for_update().select_related('item', 'from_location', 'to_location').get(pk=transfer.pk)
    if transfer.status != 'DRAFT':
        raise ValidationError('Only a draft transfer can be posted.')
    source = _balance_for_update(transfer.item, transfer.from_location)
    destination = _balance_for_update(transfer.item, transfer.to_location)
    from asset_mgmt.models import InventoryReservation
    reserved = InventoryReservation.objects.select_for_update().filter(
        item=transfer.item, location=transfer.from_location, status__in=['ACTIVE', 'PARTIAL']
    ).aggregate(total=Sum('quantity'))['total'] or Decimal('0')
    available = max(Decimal('0'), source.quantity - reserved)
    if available < transfer.quantity:
        raise ValidationError(f'Insufficient unreserved stock. Transferable quantity is {available}; {reserved} is reserved for work orders.')
    source.quantity -= transfer.quantity
    destination.quantity += transfer.quantity
    source.save(update_fields=['quantity', 'updated_at'])
    destination.save(update_fields=['quantity', 'updated_at'])
    common = dict(item=transfer.item, quantity=transfer.quantity, reference_type='StockTransfer', reference_no=transfer.transfer_no, posted_by=user, remarks=transfer.remarks)
    StockTransaction.objects.create(transaction_type='TRANSFER_OUT', from_location=transfer.from_location, **common)
    StockTransaction.objects.create(transaction_type='TRANSFER_IN', to_location=transfer.to_location, **common)
    transfer.status = 'POSTED'
    transfer.posted_by = user
    transfer.posted_at = timezone.now()
    transfer.save(update_fields=['status', 'posted_by', 'posted_at', 'updated_at'])
    _refresh_item_total(transfer.item)
    return transfer
