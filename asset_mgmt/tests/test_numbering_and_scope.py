from django.test import TestCase

from asset_mgmt.models import MaintenanceRequest, WorkOrder
from asset_mgmt.permissions import scope_queryset_for_user

from .helpers import EngineeringDataMixin


class NumberingAndScopeTests(EngineeringDataMixin, TestCase):
    def test_mr_and_wo_numbers_are_generated_and_unique(self):
        second_mr = MaintenanceRequest.objects.create(
            plant=self.plant, asset=self.asset, work_centre=self.work_centre,
            reported_by=self.engineer, problem_description='Second request'
        )
        second_wo = WorkOrder.objects.create(
            plant=self.plant, asset=self.asset, work_centre=self.work_centre,
            created_by=self.hod, work_type='CORRECTIVE', job_description='Second work order'
        )
        self.assertTrue(self.mr.request_no.startswith('MR-P01-'))
        self.assertTrue(self.wo.wo_number.startswith('WO-P01-'))
        self.assertNotEqual(self.mr.request_no, second_mr.request_no)
        self.assertNotEqual(self.wo.wo_number, second_wo.wo_number)

    def test_plant_scope_blocks_other_plant_records(self):
        engineer_assets = scope_queryset_for_user(self.asset.__class__.objects.all(), self.engineer)
        outsider_assets = scope_queryset_for_user(self.asset.__class__.objects.all(), self.outsider)
        self.assertIn(self.asset, engineer_assets)
        self.assertNotIn(self.asset, outsider_assets)
