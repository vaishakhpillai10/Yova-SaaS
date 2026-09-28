from __future__ import annotations

from datetime import datetime, time, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from ..models import (
    AssetMeterReading, ConditionRule, InventoryBalance, InventoryReservation,
    MaintenanceRequest, PMPlan, PMPlanCounter, PurchaseRequest, SettlementPosting,
    WorkOrder, WorkOrderConfirmation, WorkOrderOperation, WorkOrderSpare,
)


def _require(condition, message):
    if not condition:
        raise ValidationError(message)


def work_centre_capacity(work_centre, start_date, end_date):
    """Return planned capacity/utilisation for the scheduling board."""
    if end_date < start_date:
        start_date, end_date = end_date, start_date
    days = (end_date - start_date).days + 1
    capacity = Decimal(str(work_centre.capacity_hours_per_day)) * Decimal(work_centre.default_crew_size) * Decimal(days)
    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(datetime.combine(start_date, time.min), tz)
    end_dt = timezone.make_aware(datetime.combine(end_date + timedelta(days=1), time.min), tz)
    scheduled = work_centre.work_order_operations.filter(
        scheduled_start__lt=end_dt,
        scheduled_end__gt=start_dt,
    ).exclude(status='CANCELLED').only('planned_hours', 'persons_required')
    planned = sum((Decimal(op.planned_hours or 0) * Decimal(op.persons_required or 1) for op in scheduled), Decimal('0'))
    utilization = round(float((planned / capacity) * 100), 1) if capacity else 0
    return {'capacity_hours': capacity, 'planned_hours': planned, 'utilization_percent': utilization}


def schedule_work_order(work_order: WorkOrder, user):
    """Capacity-aware scheduling. Operations without dates inherit the WO planning window."""
    _require(work_order.planned_start and work_order.planned_end, 'Planned start/end are required before scheduling.')
    _require(work_order.operations.exists(), 'At least one operation is required before scheduling.')
    cursor = work_order.planned_start
    for op in work_order.operations.order_by('sequence'):
        if op.status == 'CANCELLED':
            continue
        hours = float(op.planned_hours or 0)
        predecessor_end = op.predecessor.scheduled_end if op.predecessor_id else None
        if op.predecessor_id:
            _require(predecessor_end is not None, f'Operation {op.sequence} predecessor {op.predecessor.sequence} must be scheduled first.')
        earliest = max(cursor, predecessor_end) if predecessor_end else cursor
        op.scheduled_start = op.scheduled_start or earliest
        _require(op.scheduled_start >= earliest, f'Operation {op.sequence} cannot start before predecessor completion.')
        op.scheduled_end = op.scheduled_end or (op.scheduled_start + timedelta(hours=hours))
        if op.assigned_to_id:
            conflict = WorkOrderOperation.objects.filter(
                assigned_to_id=op.assigned_to_id,
                scheduled_start__lt=op.scheduled_end,
                scheduled_end__gt=op.scheduled_start,
            ).exclude(pk=op.pk).exclude(status='CANCELLED').exists()
            _require(not conflict, f'{op.assigned_to.username} is already scheduled for another operation in this time window.')
        op.status = 'READY'
        op.full_clean()
        op.save(update_fields=['scheduled_start', 'scheduled_end', 'status', 'updated_at'])
        cursor = max(cursor, op.scheduled_end)
    for wc in {op.work_centre for op in work_order.operations.exclude(status='CANCELLED').select_related('work_centre')}:
        scheduled_ops = work_order.operations.filter(work_centre=wc).exclude(status='CANCELLED')
        first = min((op.scheduled_start.date() for op in scheduled_ops if op.scheduled_start), default=work_order.planned_start.date())
        last = max((op.scheduled_end.date() for op in scheduled_ops if op.scheduled_end), default=work_order.planned_end.date())
        cap = work_centre_capacity(wc, first, last)
        _require(cap['utilization_percent'] <= 100, f'{wc.code} is over capacity ({cap["utilization_percent"]}%). Level or reschedule operations before dispatch.')
    work_order.scheduled_by = user
    work_order.scheduled_at = timezone.now()
    return work_order


def dispatch_work_order(work_order: WorkOrder, user):
    _require(not work_order.operations.filter(scheduled_start__isnull=True).exclude(status='CANCELLED').exists(), 'Schedule every active operation before dispatch.')
    now = timezone.now()
    work_order.operations.exclude(status='CANCELLED').update(status='DISPATCHED', dispatched_at=now)
    work_order.dispatched_by = user
    work_order.dispatched_at = now
    return work_order


def _procurement_approver(work_order, requester):
    approver = work_order.supervisor or work_order.approved_by
    if approver and approver.pk != requester.pk:
        return approver
    from .workflows import choose_hod
    approver = choose_hod(requester, work_order.plant, work_order.work_centre)
    _require(approver.pk != requester.pk, 'Automatic procurement requires an approver different from the requester.')
    return approver


def available_inventory(item, location=None):
    balance_qs = InventoryBalance.objects.filter(item=item)
    if location:
        balance_qs = balance_qs.filter(location=location)
    physical = balance_qs.aggregate(total=Sum('quantity'))['total'] or Decimal('0')
    reservations = InventoryReservation.objects.filter(item=item, status__in=['ACTIVE', 'PARTIAL'])
    if location:
        reservations = reservations.filter(location=location)
    reserved = reservations.aggregate(total=Sum('quantity'))['total'] or Decimal('0')
    return {'physical': physical, 'reserved': reserved, 'available': max(Decimal('0'), physical - reserved)}


@transaction.atomic
def reserve_or_procure_work_order(work_order: WorkOrder, user):
    """Reserve stock components and create draft PRs for shortages/non-stock components/services."""
    for line in work_order.spares_used.select_related('spare_part', 'operation'):
        item = line.spare_part
        required = Decimal(line.quantity_required)
        line.reservations.filter(status__in=['ACTIVE', 'PARTIAL']).delete()
        line.quantity_reserved = Decimal('0')

        should_procure = line.procurement_type == 'NON_STOCK' or item.procurement_type in {'NON_STOCK', 'SERVICE'}
        remaining = required
        if not should_procure:
            balances = InventoryBalance.objects.select_for_update().filter(item=item, quantity__gt=0).select_related('location').order_by('-quantity')
            for balance in balances:
                avail = available_inventory(item, balance.location)['available']
                take = min(avail, remaining)
                if take <= 0:
                    continue
                InventoryReservation.objects.create(
                    work_order_spare=line, item=item, location=balance.location,
                    quantity=take, status='ACTIVE', reserved_by=user,
                )
                line.quantity_reserved += take
                remaining -= take
                if remaining <= 0:
                    break

        if remaining > 0 or should_procure:
            shortage = required if should_procure else remaining
            pr = line.purchase_request
            if not pr or pr.status in {'REJECTED', 'CANCELLED', 'CLOSED'}:
                approver = _procurement_approver(work_order, user)
                pr = PurchaseRequest.objects.create(
                    plant=work_order.plant, work_centre=work_order.work_centre, work_order=work_order,
                    source_operation=line.operation, item=item, requested_by=user, assigned_hod=approver,
                    quantity=shortage, required_date=work_order.planned_start.date() if work_order.planned_start else None,
                    purpose=f'Automatic maintenance requirement for {work_order.wo_number}' + (f' operation {line.operation.sequence}' if line.operation_id else ''),
                    status='DRAFT',
                )
                line.purchase_request = pr
            line.reservation_status = 'PROCUREMENT'
        elif line.quantity_reserved >= required:
            line.reservation_status = 'RESERVED'
        elif line.quantity_reserved > 0:
            line.reservation_status = 'PARTIAL'
        else:
            line.reservation_status = 'UNRESERVED'
        line.save(update_fields=['quantity_reserved', 'reservation_status', 'purchase_request', 'updated_at'])

    # External operations become service PRs using the configured service item.
    for op in work_order.operations.filter(execution_type='EXTERNAL').select_related('service_item'):
        _require(op.service_item_id, f'External operation {op.sequence} requires a service item.')
        if not op.purchase_requests.exclude(status__in=['REJECTED', 'CANCELLED', 'CLOSED']).exists():
            approver = _procurement_approver(work_order, user)
            PurchaseRequest.objects.create(
                plant=work_order.plant, work_centre=op.work_centre, work_order=work_order,
                source_operation=op, item=op.service_item, requested_by=user, assigned_hod=approver,
                quantity=Decimal('1'), required_date=op.scheduled_start.date() if op.scheduled_start else (work_order.planned_start.date() if work_order.planned_start else None),
                purpose=op.external_service_description or f'External service for {work_order.wo_number} operation {op.sequence}',
                status='DRAFT',
            )


def procurement_ready(work_order: WorkOrder):
    for line in work_order.spares_used.select_related('purchase_request'):
        if line.reservation_status in {'RESERVED', 'ISSUED'}:
            continue
        if line.purchase_request_id and line.purchase_request.purchase_orders.filter(status__in=['RECEIVED', 'INVOICED', 'CLOSED']).exists():
            continue
        return False
    for op in work_order.operations.filter(execution_type='EXTERNAL'):
        if not op.purchase_requests.filter(purchase_orders__status__in=['RELEASED', 'PARTIAL_RECEIVED', 'RECEIVED', 'INVOICED', 'CLOSED']).exists():
            return False
    return True


@transaction.atomic
def confirm_operation(operation: WorkOrderOperation, person, confirmation_type, started_at, ended_at, remaining_work_hours=0, text=''):
    confirmation = WorkOrderConfirmation(
        work_order=operation.work_order, operation=operation, person=person,
        confirmation_type=confirmation_type, started_at=started_at, ended_at=ended_at,
        remaining_work_hours=remaining_work_hours, confirmation_text=text,
    )
    confirmation.full_clean()
    confirmation.save()
    return confirmation


def evaluate_condition_rules(reading: AssetMeterReading):
    """Create one open notification per breached condition rule."""
    value = reading.reading
    for rule in reading.meter.condition_rules.filter(active=True, auto_create_notification=True).select_related('work_centre'):
        hit = {
            'GT': value > rule.threshold,
            'GTE': value >= rule.threshold,
            'LT': value < rule.threshold,
            'LTE': value <= rule.threshold,
        }[rule.operator]
        if not hit:
            continue
        recent_cutoff = timezone.now() - timedelta(hours=24)
        exists = MaintenanceRequest.objects.filter(
            asset=reading.meter.asset,
            work_centre=rule.work_centre,
            problem_description__icontains=f'Condition rule: {rule.name}',
            created_at__gte=recent_cutoff,
        ).exclude(status__in=['CLOSED', 'REJECTED', 'CANCELLED']).exists()
        if not exists:
            MaintenanceRequest.objects.create(
                plant=reading.meter.asset.plant, asset=reading.meter.asset, work_centre=rule.work_centre,
                reported_by=reading.entered_by, reported_department='MAINTENANCE', priority=rule.priority,
                problem_description=f'Condition rule: {rule.name}. Reading {value} {reading.meter.unit} breached {rule.get_operator_display()} {rule.threshold}.',
                failure_mode='Condition threshold exceeded', status='REPORTED',
            )
        rule.last_triggered_at = timezone.now()
        rule.save(update_fields=['last_triggered_at', 'updated_at'])


def due_strategy_package_ids(plan: PMPlan, today=None):
    """Return strategy packages whose call horizon has been reached."""
    today = today or timezone.localdate()
    due_ids = []
    horizon = Decimal(plan.call_horizon_percent or 100) / Decimal('100')
    unit_meter_type = {'RUNNING_HOURS':'RUNNING_HOURS', 'KM':'KM', 'CYCLES':'CYCLES'}
    counters = list(plan.counters.filter(active=True).select_related('meter'))
    for link in plan.strategy_packages.filter(active=True).select_related('package'):
        package = link.package
        cycle = Decimal(package.cycle_value)
        if package.cycle_unit in {'DAYS','WEEKS','MONTHS'}:
            if not link.next_due_date:
                continue
            if package.cycle_unit == 'DAYS':
                cycle_days = int(package.cycle_value)
                cycle_start = link.next_due_date - timedelta(days=cycle_days)
            elif package.cycle_unit == 'WEEKS':
                cycle_days = int(package.cycle_value) * 7
                cycle_start = link.next_due_date - timedelta(days=cycle_days)
            else:
                from .pm import add_months
                cycle_start = add_months(link.next_due_date, -int(package.cycle_value))
                cycle_days = max(1, (link.next_due_date - cycle_start).days)
            call_date = cycle_start + timedelta(days=round(cycle_days * float(horizon)))
            if today >= call_date:
                due_ids.append(package.pk)
        else:
            meter_type = unit_meter_type.get(package.cycle_unit)
            meter = None
            if plan.counter_meter_id and plan.counter_meter.meter_type == meter_type:
                meter = plan.counter_meter
            if meter is None:
                counter = next((c for c in counters if c.meter.meter_type == meter_type), None)
                meter = counter.meter if counter else None
            if meter and link.next_due_reading is not None:
                call_reading = link.next_due_reading - (cycle * (Decimal('1') - horizon))
                if meter.current_reading >= call_reading:
                    due_ids.append(package.pk)
    return due_ids


def advance_strategy_packages(plan: PMPlan, completed_date=None):
    completed_date = completed_date or timezone.localdate()
    due_ids = set(due_strategy_package_ids(plan, completed_date))
    if not due_ids:
        return
    from .pm import add_months
    unit_meter_type = {'RUNNING_HOURS':'RUNNING_HOURS', 'KM':'KM', 'CYCLES':'CYCLES'}
    counters = list(plan.counters.filter(active=True).select_related('meter'))
    for link in plan.strategy_packages.filter(active=True, package_id__in=due_ids).select_related('package'):
        package = link.package
        link.last_completed_date = completed_date
        if package.cycle_unit == 'DAYS':
            link.next_due_date = completed_date + timedelta(days=package.cycle_value)
        elif package.cycle_unit == 'WEEKS':
            link.next_due_date = completed_date + timedelta(weeks=package.cycle_value)
        elif package.cycle_unit == 'MONTHS':
            link.next_due_date = add_months(completed_date, package.cycle_value)
        else:
            meter_type = unit_meter_type.get(package.cycle_unit)
            meter = plan.counter_meter if plan.counter_meter_id and plan.counter_meter.meter_type == meter_type else None
            if meter is None:
                counter = next((c for c in counters if c.meter.meter_type == meter_type), None)
                meter = counter.meter if counter else None
            if meter:
                link.next_due_reading = meter.current_reading + Decimal(package.cycle_value)
        link.save(update_fields=['last_completed_date','next_due_date','next_due_reading','updated_at'])


def pm_plan_is_due(plan: PMPlan, today=None):
    """Evaluate calendar, primary counter, multiple counters and strategy package call horizons."""
    today = today or timezone.localdate()
    reasons = []
    horizon = Decimal(plan.call_horizon_percent or 100) / Decimal('100')
    if plan.frequency_unit != 'RUNNING_HOURS' and plan.next_due_date:
        if plan.frequency_unit == 'DAYS':
            cycle_start = plan.next_due_date - timedelta(days=plan.frequency_value)
        elif plan.frequency_unit == 'WEEKS':
            cycle_start = plan.next_due_date - timedelta(weeks=plan.frequency_value)
        else:
            from .pm import add_months
            cycle_start = add_months(plan.next_due_date, -plan.frequency_value)
        cycle_days = max(1, (plan.next_due_date - cycle_start).days)
        call_date = cycle_start + timedelta(days=round(cycle_days * float(horizon)))
        if today >= call_date:
            reasons.append(f'Calendar call horizon reached {call_date} (due {plan.next_due_date})')
    if plan.frequency_unit == 'RUNNING_HOURS' and plan.counter_meter_id and plan.next_counter_due is not None and plan.counter_interval:
        call_reading = plan.next_counter_due - (plan.counter_interval * (Decimal('1') - horizon))
        if plan.counter_meter.current_reading >= call_reading:
            reasons.append(f'Counter call horizon {plan.counter_meter.current_reading} / {plan.next_counter_due}')
    for counter in plan.counters.filter(active=True).select_related('meter'):
        if counter.next_due_reading is not None:
            call_reading = counter.next_due_reading - (counter.interval * (Decimal('1') - horizon))
            if counter.meter.current_reading >= call_reading:
                reasons.append(f'{counter.meter.get_meter_type_display()} call horizon {counter.meter.current_reading} / {counter.next_due_reading}')
    strategy_due = due_strategy_package_ids(plan, today)
    if strategy_due:
        names = list(plan.strategy_packages.filter(package_id__in=strategy_due).values_list('package__name', flat=True))
        reasons.append('Strategy package call: ' + ', '.join(names))
    return bool(reasons), reasons


def advance_pm_counters(plan: PMPlan):
    if plan.counter_meter_id and plan.counter_interval:
        plan.last_counter_reading = plan.counter_meter.current_reading
        plan.next_counter_due = plan.counter_meter.current_reading + plan.counter_interval
        plan.save(update_fields=['last_counter_reading', 'next_counter_due', 'updated_at'])
    for counter in plan.counters.filter(active=True).select_related('meter'):
        counter.last_completed_reading = counter.meter.current_reading
        counter.next_due_reading = counter.meter.current_reading + counter.interval
        counter.save(update_fields=['last_completed_reading', 'next_due_reading', 'updated_at'])
    advance_strategy_packages(plan)


@transaction.atomic
def settle_work_order(work_order: WorkOrder, user):
    total_pct = work_order.settlement_rules.aggregate(total=Sum('percentage'))['total'] or Decimal('0')
    _require(total_pct == Decimal('100'), 'Settlement rules must total exactly 100%.')
    work_order.settlement_postings.all().delete()
    actual = Decimal(work_order.calculated_actual_cost)
    rules = list(work_order.settlement_rules.all())
    allocated = Decimal('0')
    for idx, rule in enumerate(rules):
        amount = actual - allocated if idx == len(rules) - 1 else (actual * rule.percentage / Decimal('100')).quantize(Decimal('0.01'))
        SettlementPosting.objects.create(work_order=work_order, rule=rule, amount=amount, posted_by=user, reference=f'SETTLE-{work_order.wo_number}')
        allocated += amount
    work_order.actual_cost = actual
    work_order.settlement_status = 'SETTLED'
    work_order.save(update_fields=['actual_cost', 'settlement_status', 'updated_at'])
    return work_order
