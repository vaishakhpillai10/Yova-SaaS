from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from asset_mgmt.models import (
    AssetMeter, AssetMeterReading, ConditionRule, InventoryReservation,
    MaintenanceRequest, PMPlan, SettlementRule, WorkOrder, WorkOrderOperation,
    WorkOrderSpare,
)
from asset_mgmt.services.maintenance_workflow import transition_work_order
from asset_mgmt.services.pm import generate_pm_work_order
from asset_mgmt.services.sap_pm import pm_plan_is_due, reserve_or_procure_work_order

from .helpers import EngineeringDataMixin


class SapStylePmEnhancementTests(EngineeringDataMixin, TestCase):
    def _draft_wo(self, work_type='CORRECTIVE'):
        wo = WorkOrder.objects.create(
            plant=self.plant, asset=self.asset, work_centre=self.work_centre,
            created_by=self.engineer, assigned_to=self.engineer, supervisor=self.hod,
            work_type=work_type, priority='MEDIUM', job_description='SAP-style test job',
            planned_start=timezone.now(), planned_end=timezone.now() + timedelta(hours=3),
            estimated_cost=Decimal('100'), status='DRAFT',
        )
        WorkOrderOperation.objects.create(
            work_order=wo, sequence=10, description='Main repair', work_centre=self.work_centre,
            assigned_to=self.engineer, execution_stage='MAIN', planned_hours=2,
        )
        return wo

    def test_scheduling_and_dispatch_are_mandatory_before_release(self):
        wo = self._draft_wo()
        transition_work_order(wo, 'plan', self.engineer)
        transition_work_order(wo, 'submit_approval', self.engineer)
        transition_work_order(wo, 'approve', self.hod, 'Approved')
        transition_work_order(wo, 'prepare', self.engineer)
        transition_work_order(wo, 'ready_schedule', self.engineer)
        transition_work_order(wo, 'schedule', self.engineer)
        self.assertEqual(wo.status, 'SCHEDULED')
        self.assertIsNotNone(wo.operations.get().scheduled_start)
        transition_work_order(wo, 'dispatch', self.engineer)
        self.assertEqual(wo.status, 'DISPATCHED')
        self.assertEqual(wo.operations.get().status, 'DISPATCHED')
        transition_work_order(wo, 'release', self.engineer)
        self.assertEqual(wo.status, 'RELEASED')

    def test_stock_reservation_reduces_available_stock(self):
        wo = self._draft_wo()
        line = WorkOrderSpare.objects.create(
            work_order=wo, operation=wo.operations.get(), spare_part=self.item,
            quantity_required=Decimal('4'), procurement_type='STOCK',
        )
        reserve_or_procure_work_order(wo, self.engineer)
        line.refresh_from_db()
        self.assertEqual(line.quantity_reserved, Decimal('4'))
        self.assertEqual(line.reservation_status, 'RESERVED')
        self.assertEqual(InventoryReservation.objects.filter(work_order_spare=line, status='ACTIVE').count(), 1)
        self.assertEqual(self.item.available_stock, Decimal('6'))

    def test_running_hour_pm_generates_when_counter_reaches_due_reading(self):
        meter = AssetMeter.objects.create(asset=self.asset, meter_type='RUNNING_HOURS', unit='h', current_reading=Decimal('1000'))
        plan = PMPlan.objects.create(
            plant=self.plant, asset=self.asset, work_centre=self.work_centre, responsible_user=self.engineer,
            name='500 hour service', frequency_value=500, frequency_unit='RUNNING_HOURS',
            next_due_date=timezone.localdate() + timedelta(days=365), counter_meter=meter,
            counter_interval=Decimal('500'), last_counter_reading=Decimal('500'), next_counter_due=Decimal('1000'),
        )
        due, _ = pm_plan_is_due(plan)
        self.assertTrue(due)
        wo = generate_pm_work_order(plan, self.engineer)
        self.assertEqual(wo.work_type, 'PREVENTIVE')
        self.assertEqual(wo.pm_plan, plan)

    def test_condition_rule_creates_notification_on_threshold_breach(self):
        meter = AssetMeter.objects.create(asset=self.asset, meter_type='VIBRATION', unit='mm/s', current_reading=Decimal('2'))
        ConditionRule.objects.create(
            meter=meter, name='High vibration', operator='GTE', threshold=Decimal('8'),
            priority='HIGH', work_centre=self.work_centre, auto_create_notification=True,
        )
        AssetMeterReading.objects.create(meter=meter, reading=Decimal('8.5'), entered_by=self.engineer)
        self.assertTrue(MaintenanceRequest.objects.filter(asset=self.asset, problem_description__icontains='High vibration').exists())

    def test_teco_sets_technical_lock_and_cost_settlement_posts_100_percent(self):
        wo = self._draft_wo()
        wo.other_cost = Decimal('50'); wo.save(update_fields=['other_cost', 'updated_at'])
        op = wo.operations.get()
        transition_work_order(wo, 'plan', self.engineer)
        transition_work_order(wo, 'submit_approval', self.engineer)
        transition_work_order(wo, 'approve', self.hod, 'Approved')
        transition_work_order(wo, 'prepare', self.engineer)
        transition_work_order(wo, 'ready_schedule', self.engineer)
        transition_work_order(wo, 'schedule', self.engineer)
        transition_work_order(wo, 'dispatch', self.engineer)
        transition_work_order(wo, 'release', self.engineer)
        transition_work_order(wo, 'start', self.engineer)
        op.status = 'COMPLETED'; op.save(update_fields=['status', 'updated_at'])
        wo.completion_notes = 'Completed and tested'; wo.save(update_fields=['completion_notes', 'updated_at'])
        transition_work_order(wo, 'complete', self.engineer)
        transition_work_order(wo, 'verify', self.hod)
        transition_work_order(wo, 'teco', self.hod)
        self.assertTrue(wo.technical_lock)
        SettlementRule.objects.create(work_order=wo, receiver_type='COST_CENTRE', receiver_reference='MAINT', percentage=Decimal('100'))
        transition_work_order(wo, 'cost_close', self.hod)
        self.assertEqual(wo.settlement_status, 'SETTLED')
        self.assertEqual(wo.settlement_postings.count(), 1)
        transition_work_order(wo, 'close', self.hod)
        self.assertEqual(wo.status, 'CLOSED')
