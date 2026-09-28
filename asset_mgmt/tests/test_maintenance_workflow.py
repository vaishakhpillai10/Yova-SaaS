from django.test import TestCase

from asset_mgmt.models import RiskAssessment, WorkOrderOperation
from asset_mgmt.services.maintenance_workflow import transition_maintenance_request, transition_work_order

from .helpers import EngineeringDataMixin


class MaintenanceWorkflowTests(EngineeringDataMixin, TestCase):
    def test_notification_screening_acceptance(self):
        transition_maintenance_request(self.mr, 'start_screening', self.engineer)
        self.assertEqual(self.mr.status, 'SCREENING')
        transition_maintenance_request(self.mr, 'accept', self.hod, 'Valid maintenance requirement')
        self.assertEqual(self.mr.status, 'ACCEPTED')
        self.assertEqual(self.mr.screened_by, self.hod)

    def test_full_work_order_controlled_flow(self):
        wo = self.wo
        wo.status = 'DRAFT'
        wo.supervisor = self.hod
        wo.failure_mode = 'Bearing failure'
        wo.failure_cause = 'Loss of lubrication'
        wo.failure_action = 'Bearing replaced and lubricated'
        wo.completion_notes = 'Repair completed and test run satisfactory.'
        wo.save()
        WorkOrderOperation.objects.create(
            work_order=wo, sequence=10, description='Replace bearing', work_centre=self.work_centre,
            assigned_to=self.engineer, planned_hours=2, status='PENDING',
        )
        RiskAssessment.objects.create(
            work_order=wo, activity='Bearing replacement', hazard='Unexpected rotation',
            consequence='Injury', existing_control='Isolation', likelihood=2, severity=3,
        )

        transition_work_order(wo, 'plan', self.engineer)
        transition_work_order(wo, 'submit_approval', self.engineer)
        transition_work_order(wo, 'approve', self.hod, 'Approved')
        transition_work_order(wo, 'prepare', self.engineer)
        transition_work_order(wo, 'ready_schedule', self.engineer)
        transition_work_order(wo, 'schedule', self.engineer)
        transition_work_order(wo, 'dispatch', self.engineer)
        transition_work_order(wo, 'release', self.engineer)
        transition_work_order(wo, 'start', self.engineer)

        op = wo.operations.get(sequence=10)
        op.status = 'COMPLETED'
        op.actual_hours = 2
        op.save()
        transition_work_order(wo, 'complete', self.engineer)
        transition_work_order(wo, 'verify', self.hod)
        transition_work_order(wo, 'teco', self.hod)
        transition_work_order(wo, 'cost_close', self.hod)
        transition_work_order(wo, 'close', self.hod)

        wo.refresh_from_db()
        self.mr.refresh_from_db()
        self.asset.refresh_from_db()
        self.assertEqual(wo.status, 'CLOSED')
        self.assertEqual(self.mr.status, 'CLOSED')
        self.assertEqual(self.asset.status, 'RUNNING')
        self.assertIsNotNone(wo.actual_start)
        self.assertIsNotNone(wo.actual_end)
        self.assertIsNotNone(wo.teco_at)
        self.assertIsNotNone(wo.cost_closed_at)
