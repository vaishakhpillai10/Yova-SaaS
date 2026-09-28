from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from asset_mgmt.models import AssetDowntimeEvent, PMPlan, PMTask, WorkOrder
from asset_mgmt.services.availability import calculate_asset_availability
from asset_mgmt.services.pm import generate_pm_work_order

from .helpers import EngineeringDataMixin


class PMAndAvailabilityTests(EngineeringDataMixin, TestCase):
    def test_overlapping_downtime_is_not_double_counted(self):
        end = timezone.now()
        start = end - timedelta(hours=24)
        AssetDowntimeEvent.objects.create(
            asset=self.asset, downtime_type='BREAKDOWN', started_at=start + timedelta(hours=2),
            ended_at=start + timedelta(hours=6), reason='Failure one', recorded_by=self.engineer,
        )
        AssetDowntimeEvent.objects.create(
            asset=self.asset, downtime_type='BREAKDOWN', started_at=start + timedelta(hours=5),
            ended_at=start + timedelta(hours=8), reason='Overlapping failure record', recorded_by=self.engineer,
        )
        result = calculate_asset_availability(self.asset, start, end)
        self.assertEqual(result['downtime_hours'], 6.0)
        self.assertEqual(result['availability_percent'], 75.0)

    def test_pm_generation_copies_tasks_and_blocks_duplicate_open_wo(self):
        plan = PMPlan.objects.create(
            plant=self.plant, asset=self.asset, work_centre=self.work_centre,
            responsible_user=self.engineer, name='Weekly inspection', frequency_value=1,
            frequency_unit='WEEKS', next_due_date=timezone.localdate(),
        )
        PMTask.objects.create(pm_plan=plan, sequence=1, task='Check coupling', required_tools='Torch')
        wo = generate_pm_work_order(plan, self.hod)
        self.assertEqual(wo.work_type, 'PREVENTIVE')
        self.assertIn('Check coupling', wo.checklist)
        with self.assertRaises(ValidationError):
            generate_pm_work_order(plan, self.hod)
        self.assertEqual(WorkOrder.objects.filter(pm_plan=plan).count(), 1)
