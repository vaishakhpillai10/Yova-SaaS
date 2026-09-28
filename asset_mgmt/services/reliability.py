from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from .availability import merge_downtime_intervals


COMPLETED_WORK_ORDER_STATUSES = ('COMPLETED', 'VERIFIED', 'TECO', 'COST_CLOSURE', 'CLOSED')
OPERATING_LIFECYCLE_STATUSES = (
    'ACTIVE', 'OPERATIONAL', 'STANDBY', 'TEMP_INACTIVE',
    'UNDER_MAINTENANCE', 'BREAKDOWN',
)


def _aware_start_of_day(value, tz):
    boundary = datetime.combine(value, time.min)
    return timezone.make_aware(boundary, tz) if timezone.is_naive(boundary) else boundary


def _asset_operating_window(asset, period_start, period_end):
    """Return the part of the reporting period in which an asset could operate."""
    tz = timezone.get_current_timezone()
    asset_start = period_start
    asset_end = period_end

    if asset.commissioning_date:
        asset_start = max(asset_start, _aware_start_of_day(asset.commissioning_date, tz))

    retirement_dates = [value for value in (asset.decommissioning_date, asset.disposal_date) if value]
    if retirement_dates:
        asset_end = min(asset_end, _aware_start_of_day(min(retirement_dates), tz))

    if asset_end <= asset_start:
        return None
    return asset_start, asset_end


def calculate_reliability_metrics(assets, work_orders, downtime_events, period_start, period_end):
    """Calculate plant/fleet MTTR and MTBF for a reporting period.

    MTTR = total actual repair hours for completed breakdown work orders
           / completed breakdown repairs with valid actual timestamps.

    MTBF = total scheduled operating hours across eligible assets minus merged
           breakdown downtime / number of breakdown failures.

    A breakdown work order represents one failure. Its actual_start is used as
    the failure date; created_at is used only when actual_start is not recorded.
    """
    if timezone.is_naive(period_start):
        period_start = timezone.make_aware(period_start)
    if timezone.is_naive(period_end):
        period_end = timezone.make_aware(period_end)
    if period_end <= period_start:
        return {
            'mttr_hours': None,
            'mtbf_hours': None,
            'scheduled_hours': 0.0,
            'operating_hours': 0.0,
            'breakdown_downtime_hours': 0.0,
            'breakdown_failures': 0,
            'completed_breakdown_repairs': 0,
            'repairs_missing_actual_times': 0,
            'eligible_asset_count': 0,
            'availability_percent': None,
            'failure_rate_per_1000_hours': None,
            'warnings': ['The reporting period is invalid.'],
        }

    eligible_assets = list(
        assets.filter(is_active=True, lifecycle_status__in=OPERATING_LIFECYCLE_STATUSES)
        .exclude(status='SCRAPPED')
        .only(
            'id', 'scheduled_hours_per_day', 'commissioning_date',
            'decommissioning_date', 'disposal_date',
        )
    )
    asset_ids = [asset.pk for asset in eligible_assets]

    events_by_asset = defaultdict(list)
    if asset_ids:
        breakdown_events = downtime_events.filter(
            asset_id__in=asset_ids,
            downtime_type='BREAKDOWN',
            started_at__lt=period_end,
            ended_at__gt=period_start,
        ).only('asset_id', 'started_at', 'ended_at')
        for event in breakdown_events:
            events_by_asset[event.asset_id].append(event)

    total_scheduled_hours = Decimal('0')
    total_breakdown_downtime_hours = Decimal('0')
    total_operating_hours = Decimal('0')

    for asset in eligible_assets:
        operating_window = _asset_operating_window(asset, period_start, period_end)
        if not operating_window:
            continue
        asset_start, asset_end = operating_window
        period_days = Decimal(str((asset_end - asset_start).total_seconds())) / Decimal('86400')
        scheduled_hours = period_days * asset.scheduled_hours_per_day

        intervals = merge_downtime_intervals(events_by_asset.get(asset.pk, []), asset_start, asset_end)
        downtime_hours = Decimal(str(sum((end - start).total_seconds() for start, end in intervals) / 3600))
        unavailable_hours = min(downtime_hours, scheduled_hours)

        total_scheduled_hours += scheduled_hours
        total_breakdown_downtime_hours += unavailable_hours
        total_operating_hours += max(Decimal('0'), scheduled_hours - unavailable_hours)

    breakdown_orders = work_orders.filter(
        asset_id__in=asset_ids,
        work_type='BREAKDOWN',
    ).exclude(status='CANCELLED')
    failure_period_filter = (
        Q(actual_start__gte=period_start, actual_start__lt=period_end)
        | Q(actual_start__isnull=True, created_at__gte=period_start, created_at__lt=period_end)
    )
    breakdown_failures = breakdown_orders.filter(failure_period_filter).count()

    # The report layer may pass a queryset optimized with select_related().
    # Clear those joins before narrowing columns with only(); otherwise Django
    # raises FieldError when a related FK (for example plant) is deferred while
    # still being traversed by select_related().
    completed_candidates = breakdown_orders.select_related(None).filter(
        status__in=COMPLETED_WORK_ORDER_STATUSES,
        actual_end__gte=period_start,
        actual_end__lt=period_end,
    ).only('id', 'actual_start', 'actual_end')

    total_repair_hours = Decimal('0')
    completed_breakdown_repairs = 0
    repairs_missing_actual_times = 0
    for work_order in completed_candidates:
        if not work_order.actual_start or not work_order.actual_end or work_order.actual_end <= work_order.actual_start:
            repairs_missing_actual_times += 1
            continue
        total_repair_hours += Decimal(str((work_order.actual_end - work_order.actual_start).total_seconds() / 3600))
        completed_breakdown_repairs += 1

    mttr = (
        total_repair_hours / Decimal(completed_breakdown_repairs)
        if completed_breakdown_repairs
        else None
    )
    mtbf = (
        total_operating_hours / Decimal(breakdown_failures)
        if breakdown_failures
        else None
    )
    availability = (
        (total_operating_hours / total_scheduled_hours) * Decimal('100')
        if total_scheduled_hours > 0 else None
    )
    failure_rate = (
        (Decimal(breakdown_failures) / total_operating_hours) * Decimal('1000')
        if total_operating_hours > 0 else None
    )

    warnings = []
    if not eligible_assets:
        warnings.append('No active operating assets are available for the selected scope.')
    if repairs_missing_actual_times:
        warnings.append(
            f'{repairs_missing_actual_times} completed breakdown work order(s) were excluded from MTTR because actual start/end time is missing or invalid.'
        )
    if breakdown_failures == 0:
        warnings.append('MTBF is unavailable because no breakdown failure was recorded in this period.')
    if completed_breakdown_repairs == 0:
        warnings.append('MTTR is unavailable because no completed breakdown repair has valid actual start/end time in this period.')

    return {
        'mttr_hours': round(float(mttr), 2) if mttr is not None else None,
        'mtbf_hours': round(float(mtbf), 2) if mtbf is not None else None,
        'scheduled_hours': round(float(total_scheduled_hours), 2),
        'operating_hours': round(float(total_operating_hours), 2),
        'breakdown_downtime_hours': round(float(total_breakdown_downtime_hours), 2),
        'breakdown_failures': breakdown_failures,
        'completed_breakdown_repairs': completed_breakdown_repairs,
        'repairs_missing_actual_times': repairs_missing_actual_times,
        'eligible_asset_count': len(eligible_assets),
        'availability_percent': round(float(availability), 2) if availability is not None else None,
        'failure_rate_per_1000_hours': round(float(failure_rate), 3) if failure_rate is not None else None,
        'warnings': warnings,
    }


def calculate_maintenance_cost_for_period(work_orders, period_start, period_end):
    """Transaction-period maintenance cost. Avoids attributing an entire WO to a month merely because it started/ended there."""
    from ..models import MaterialIssue, ServiceEntrySheet, WorkOrderLabour
    wo_ids = work_orders.values_list('pk', flat=True)
    material_total = Decimal('0')
    for issue in MaterialIssue.objects.filter(
        work_order_id__in=wo_ids, status='POSTED', posted_at__gte=period_start, posted_at__lt=period_end
    ).select_related('item'):
        material_total += Decimal(issue.quantity_issued) * Decimal(issue.item.item_rate)

    labour_total = Decimal('0')
    labour_rows = WorkOrderLabour.objects.filter(work_order_id__in=wo_ids).filter(
        Q(ended_at__gte=period_start, ended_at__lt=period_end) |
        Q(ended_at__isnull=True, created_at__gte=period_start, created_at__lt=period_end)
    )
    for row in labour_rows:
        labour_total += Decimal(row.cost)

    service_total = ServiceEntrySheet.objects.filter(
        work_order_operation__work_order_id__in=wo_ids, status='ACCEPTED',
        accepted_at__gte=period_start, accepted_at__lt=period_end,
    ).aggregate(total=__import__('django').db.models.Sum('amount'))['total'] or Decimal('0')

    # Other/manual costs have no separate transaction ledger; recognize them when technical cost closure posts.
    other_total = work_orders.filter(
        cost_closed_at__gte=period_start, cost_closed_at__lt=period_end
    ).aggregate(total=__import__('django').db.models.Sum('other_cost'))['total'] or Decimal('0')
    return {
        'material': material_total, 'labour': labour_total, 'external_service': Decimal(service_total),
        'other': Decimal(other_total), 'total': material_total + labour_total + Decimal(service_total) + Decimal(other_total),
    }
