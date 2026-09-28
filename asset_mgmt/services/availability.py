from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from django.utils import timezone


def merge_downtime_intervals(events, period_start: datetime, period_end: datetime):
    intervals = []
    for event in events:
        start = max(event.started_at, period_start)
        end = min(event.ended_at, period_end)
        if end > start:
            intervals.append((start, end))
    intervals.sort(key=lambda value: value[0])
    merged = []
    for start, end in intervals:
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        elif end > merged[-1][1]:
            merged[-1][1] = end
    return merged


def calculate_asset_availability(asset, period_start: datetime, period_end: datetime):
    if timezone.is_naive(period_start):
        period_start = timezone.make_aware(period_start)
    if timezone.is_naive(period_end):
        period_end = timezone.make_aware(period_end)
    if period_end <= period_start:
        return {'scheduled_hours': 0.0, 'downtime_hours': 0.0, 'availability_percent': 0.0}

    events = asset.downtime_events.filter(started_at__lt=period_end, ended_at__gt=period_start).only('started_at', 'ended_at')
    intervals = merge_downtime_intervals(events, period_start, period_end)
    downtime_hours = sum((end - start).total_seconds() for start, end in intervals) / 3600
    period_days = Decimal(str((period_end - period_start).total_seconds())) / Decimal('86400')
    scheduled_hours = float(period_days * asset.scheduled_hours_per_day)
    unavailable = min(downtime_hours, scheduled_hours)
    availability = ((scheduled_hours - unavailable) / scheduled_hours * 100) if scheduled_hours else 0
    return {
        'scheduled_hours': round(scheduled_hours, 2),
        'downtime_hours': round(downtime_hours, 2),
        'availability_percent': round(max(0, min(100, availability)), 2),
    }
