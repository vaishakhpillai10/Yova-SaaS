from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db.models import F, Sum

from asset_mgmt.models import (
    Asset, GoodsReceipt, InventoryBalance, MaterialIssue, PurchaseOrder, PurchaseRequest,
    SparePart, StockTransaction, StockTransfer, WorkOrder,
)


class Command(BaseCommand):
    help = 'Run data-integrity checks across plant, approval, purchasing and inventory records.'

    def handle(self, *args, **options):
        issues: list[str] = []

        if InventoryBalance.objects.filter(quantity__lt=0).exists():
            issues.append('One or more inventory balances are negative.')

        totals = {
            row['item_id']: row['total'] or Decimal('0')
            for row in InventoryBalance.objects.values('item_id').annotate(total=Sum('quantity'))
        }
        for item in SparePart.objects.only('id', 'item_no', 'current_stock'):
            if item.current_stock != totals.get(item.id, Decimal('0')):
                issues.append(f'Item {item.item_no}: cached stock does not match location balances.')

        cross_plant_checks = [
            ('Asset / functional location', Asset.objects.exclude(plant_id=F('functional_location__plant_id'))),
            ('Work order / asset', WorkOrder.objects.exclude(plant_id=F('asset__plant_id'))),
            ('Work order / work centre', WorkOrder.objects.exclude(plant_id=F('work_centre__plant_id'))),
            ('Purchase request / item', PurchaseRequest.objects.exclude(plant_id=F('item__plant_id'))),
            ('Purchase request / work centre', PurchaseRequest.objects.exclude(plant_id=F('work_centre__plant_id'))),
            ('Purchase order / PR', PurchaseOrder.objects.exclude(plant_id=F('purchase_request__plant_id'))),
            ('Goods receipt / PO', GoodsReceipt.objects.exclude(plant_id=F('purchase_order__plant_id'))),
            ('Stock transfer / item', StockTransfer.objects.exclude(plant_id=F('item__plant_id'))),
            ('Material issue / item', MaterialIssue.objects.exclude(plant_id=F('item__plant_id'))),
        ]
        for label, queryset in cross_plant_checks:
            count = queryset.count()
            if count:
                issues.append(f'{label}: {count} cross-plant record(s).')

        if PurchaseRequest.objects.filter(requested_by_id=F('assigned_hod_id')).exists():
            issues.append('A requester is assigned as their own PR approver.')
        if PurchaseRequest.objects.filter(status='SUBMITTED', assigned_hod__isnull=True).exists():
            issues.append('A submitted PR has no assigned HOD.')
        if PurchaseRequest.objects.filter(status__in=['APPROVED', 'PROCESSING', 'PO_CREATED'], approved_by__isnull=True).exists():
            issues.append('An approved/processed PR is missing approved_by.')
        if PurchaseRequest.objects.filter(status__in=['APPROVED', 'PROCESSING', 'PO_CREATED'], approved_at__isnull=True).exists():
            issues.append('An approved/processed PR is missing approved_at.')

        invalid_po = PurchaseOrder.objects.exclude(purchase_request__status__in=['PO_CREATED', 'CLOSED', 'PROCESSING', 'APPROVED'])
        if invalid_po.exists():
            issues.append(f'{invalid_po.count()} PO(s) reference a PR in an invalid status.')

        posted_checks = [
            ('Goods receipt', GoodsReceipt.objects.filter(status='POSTED'), 'GoodsReceipt'),
            ('Stock transfer', StockTransfer.objects.filter(status='POSTED'), 'StockTransfer'),
            ('Material issue', MaterialIssue.objects.filter(status='POSTED'), 'MaterialIssue'),
        ]
        for label, queryset, reference_type in posted_checks:
            for obj in queryset.only('pk'):
                reference_no = getattr(obj, 'receipt_no', None) or getattr(obj, 'transfer_no', None) or getattr(obj, 'issue_no', None)
                if not StockTransaction.objects.filter(reference_type=reference_type, reference_no=reference_no).exists():
                    issues.append(f'{label} {reference_no} is posted but has no stock-ledger transaction.')

        if issues:
            for issue in issues:
                self.stderr.write(self.style.ERROR(f'FAIL: {issue}'))
            raise CommandError(f'Data-integrity verification failed with {len(issues)} issue(s).')

        self.stdout.write(self.style.SUCCESS('All configured data-integrity checks passed.'))
