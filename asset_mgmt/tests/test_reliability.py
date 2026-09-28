from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from asset_mgmt.models import Asset, AssetDowntimeEvent, WorkOrder
from asset_mgmt.services.reliability import calculate_reliability_metrics

from .helpers import EngineeringDataMixin


class ReliabilityMetricTests(EngineeringDataMixin, TestCase):
    def setUp(self):
        # The shared released WO is unrelated to these metric scenarios.
        self.wo.work_type = 'PREVENTIVE'
        self.wo.save(update_fields=['work_type', 'updated_at'])

    def _breakdown_wo(self, start, end, status='COMPLETED'):
        return WorkOrder.objects.create(
            plant=self.plant,
            asset=self.asset,
            work_centre=self.work_centre,
            created_by=self.hod,
            assigned_to=self.engineer,
            work_type='BREAKDOWN',
            priority='HIGH',
            job_description='Repair breakdown',
            actual_start=start,
            actual_end=end,
            status=status,
        )

    def test_mttr_uses_only_completed_breakdown_actual_repair_time(self):
        period_end = timezone.now()
        period_start = period_end - timedelta(hours=24)
        self._breakdown_wo(period_start + timedelta(hours=1), period_start + timedelta(hours=3))
        self._breakdown_wo(period_start + timedelta(hours=5), period_start + timedelta(hours=9), status='VERIFIED')
        WorkOrder.objects.create(
            plant=self.plant, asset=self.asset, work_centre=self.work_centre,
            created_by=self.hod, work_type='PREVENTIVE', priority='MEDIUM',
            job_description='PM task', actual_start=period_start + timedelta(hours=2),
            actual_end=period_start + timedelta(hours=12), status='COMPLETED',
        )

        metrics = calculate_reliability_metrics(
            Asset.objects.filter(pk=self.asset.pk),
            WorkOrder.objects.filter(plant=self.plant),
            AssetDowntimeEvent.objects.filter(asset__plant=self.plant),
            period_start,
            period_end,
        )

        self.assertEqual(metrics['completed_breakdown_repairs'], 2)
        self.assertEqual(metrics['mttr_hours'], 3.0)

    def test_mtbf_uses_scheduled_hours_and_merged_breakdown_downtime(self):
        period_end = timezone.now()
        period_start = period_end - timedelta(hours=24)
        self._breakdown_wo(period_start + timedelta(hours=1), period_start + timedelta(hours=2))
        self._breakdown_wo(period_start + timedelta(hours=10), period_start + timedelta(hours=11))
        AssetDowntimeEvent.objects.create(
            asset=self.asset, downtime_type='BREAKDOWN',
            started_at=period_start + timedelta(hours=2),
            ended_at=period_start + timedelta(hours=6),
            reason='Failure one', recorded_by=self.engineer,
        )
        AssetDowntimeEvent.objects.create(
            asset=self.asset, downtime_type='BREAKDOWN',
            started_at=period_start + timedelta(hours=5),
            ended_at=period_start + timedelta(hours=8),
            reason='Overlapping record', recorded_by=self.engineer,
        )
        AssetDowntimeEvent.objects.create(
            asset=self.asset, downtime_type='PLANNED',
            started_at=period_start + timedelta(hours=12),
            ended_at=period_start + timedelta(hours=16),
            reason='Planned shutdown', recorded_by=self.engineer,
        )

        metrics = calculate_reliability_metrics(
            Asset.objects.filter(pk=self.asset.pk),
            WorkOrder.objects.filter(plant=self.plant),
            AssetDowntimeEvent.objects.filter(asset__plant=self.plant),
            period_start,
            period_end,
        )

        self.assertEqual(metrics['scheduled_hours'], 24.0)
        self.assertEqual(metrics['breakdown_downtime_hours'], 6.0)
        self.assertEqual(metrics['operating_hours'], 18.0)
        self.assertEqual(metrics['breakdown_failures'], 2)
        self.assertEqual(metrics['mtbf_hours'], 9.0)
        self.assertEqual(metrics['availability_percent'], 75.0)
        self.assertEqual(metrics['failure_rate_per_1000_hours'], 111.111)


    def test_breakdown_cannot_be_completed_without_actual_times(self):
        work_order = WorkOrder(
            plant=self.plant, asset=self.asset, work_centre=self.work_centre,
            created_by=self.hod, work_type='BREAKDOWN', priority='HIGH',
            job_description='Incomplete repair record', status='COMPLETED',
        )
        with self.assertRaises(ValidationError) as error:
            work_order.full_clean()
        self.assertIn('actual_start', error.exception.message_dict)
        self.assertIn('actual_end', error.exception.message_dict)

    def test_completed_breakdown_without_actual_times_is_excluded_from_mttr(self):
        period_end = timezone.now()
        period_start = period_end - timedelta(hours=24)
        WorkOrder.objects.create(
            plant=self.plant, asset=self.asset, work_centre=self.work_centre,
            created_by=self.hod, work_type='BREAKDOWN', priority='HIGH',
            job_description='Repair without timestamps', status='COMPLETED',
            actual_end=period_end - timedelta(hours=1),
        )

        metrics = calculate_reliability_metrics(
            Asset.objects.filter(pk=self.asset.pk),
            WorkOrder.objects.filter(plant=self.plant),
            AssetDowntimeEvent.objects.filter(asset__plant=self.plant),
            period_start,
            period_end,
        )

        self.assertIsNone(metrics['mttr_hours'])
        self.assertEqual(metrics['repairs_missing_actual_times'], 1)
        self.assertTrue(any('excluded from MTTR' in warning for warning in metrics['warnings']))

    def test_reliability_accepts_select_related_work_order_queryset(self):
        """Regression: report querysets may preload related fields."""
        period_end = timezone.now()
        period_start = period_end - timedelta(hours=24)
        self._breakdown_wo(
            period_start + timedelta(hours=1),
            period_start + timedelta(hours=3),
        )

        # This mirrors MaintenanceHistoryReliabilityView, which preloads plant,
        # asset, work centre and user relations for the history table.
        report_queryset = WorkOrder.objects.filter(plant=self.plant).select_related(
            'plant', 'asset', 'work_centre', 'assigned_to'
        )

        metrics = calculate_reliability_metrics(
            Asset.objects.filter(pk=self.asset.pk),
            report_queryset,
            AssetDowntimeEvent.objects.filter(asset__plant=self.plant),
            period_start,
            period_end,
        )

        self.assertEqual(metrics['completed_breakdown_repairs'], 1)
        self.assertEqual(metrics['mttr_hours'], 2.0)

