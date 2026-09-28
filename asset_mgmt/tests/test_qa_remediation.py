from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from asset_mgmt.forms import GoodsReceiptForm, PurchaseOrderForm
from asset_mgmt.models import (
    AssetDowntimeEvent,
    AssetMeter,
    AssetMeterReading,
    GoodsReceipt,
    InventoryReservation,
    MaterialIssue,
    PurchaseOrder,
    ServiceEntrySheet,
    SparePart,
    StockTransfer,
    StoreLocation,
    WorkOrderConfirmation,
    WorkOrderOperation,
    WorkOrderSpare,
)
from asset_mgmt.services.inventory import post_goods_receipt, post_material_issue, post_stock_transfer
from asset_mgmt.services.maintenance_workflow import transition_work_order
from asset_mgmt.services.sap_pm import work_centre_capacity

from .helpers import EngineeringDataMixin


class QARemediationRegressionTests(EngineeringDataMixin, TestCase):
    """Regression coverage for defects found in the formal 2026-08-08 QA audit."""

    def test_work_order_creator_cannot_self_approve(self):
        self.wo.status = 'PENDING_APPROVAL'
        self.wo.created_by = self.hod
        self.wo.save(update_fields=['status', 'created_by', 'updated_at'])
        with self.assertRaises(ValidationError):
            transition_work_order(self.wo, 'approve', self.hod, 'Self approval attempt')

    def test_capacity_uses_person_hours(self):
        now = timezone.now()
        WorkOrderOperation.objects.create(
            work_order=self.wo,
            sequence=10,
            description='Three-person eight-hour operation',
            work_centre=self.work_centre,
            assigned_to=self.engineer,
            persons_required=3,
            planned_hours=Decimal('8'),
            scheduled_start=now,
            scheduled_end=now + timedelta(hours=8),
            status='READY',
        )
        result = work_centre_capacity(self.work_centre, now.date(), now.date())
        self.assertEqual(result['planned_hours'], Decimal('24'))
        self.assertEqual(result['capacity_hours'], Decimal('8'))
        self.assertEqual(result['utilization_percent'], 300.0)

    def test_predecessor_blocks_successor_confirmation(self):
        self.wo.status = 'IN_PROGRESS'
        self.wo.save(update_fields=['status', 'updated_at'])
        predecessor = WorkOrderOperation.objects.create(
            work_order=self.wo, sequence=10, description='Isolate', work_centre=self.work_centre,
            assigned_to=self.engineer, planned_hours=1, status='IN_PROGRESS',
        )
        successor = WorkOrderOperation.objects.create(
            work_order=self.wo, sequence=20, description='Repair', work_centre=self.work_centre,
            assigned_to=self.engineer, predecessor=predecessor, planned_hours=1, status='READY',
        )
        now = timezone.now()
        confirmation = WorkOrderConfirmation(
            work_order=self.wo,
            operation=successor,
            person=self.engineer,
            confirmation_type='FINAL',
            started_at=now,
            ended_at=now + timedelta(hours=1),
        )
        with self.assertRaises(ValidationError):
            confirmation.full_clean()

    def test_reserved_stock_cannot_be_transferred(self):
        destination = StoreLocation.objects.create(
            plant=self.plant, code='SECOND', name='Second Store', bin_code='B01'
        )
        line = WorkOrderSpare.objects.create(
            work_order=self.wo, spare_part=self.item, quantity_required=Decimal('8'),
            quantity_reserved=Decimal('8'), reservation_status='RESERVED',
        )
        InventoryReservation.objects.create(
            work_order_spare=line, item=self.item, location=self.location_store,
            quantity=Decimal('8'), status='ACTIVE', reserved_by=self.engineer,
        )
        transfer = StockTransfer.objects.create(
            plant=self.plant, item=self.item, from_location=self.location_store,
            to_location=destination, quantity=Decimal('3'),
        )
        with self.assertRaises(ValidationError):
            post_stock_transfer(transfer, self.store_user)

    def test_material_issue_requires_execution_phase_and_respects_plan(self):
        line = WorkOrderSpare.objects.create(
            work_order=self.wo, spare_part=self.item, quantity_required=Decimal('2')
        )
        self.wo.status = 'DRAFT'
        self.wo.save(update_fields=['status', 'updated_at'])
        early_issue = MaterialIssue.objects.create(
            plant=self.plant, item=self.item, source_location=self.location_store,
            quantity_issued=Decimal('1'), work_order=self.wo,
        )
        with self.assertRaises(ValidationError):
            post_material_issue(early_issue, self.store_user)

        self.wo.status = 'RELEASED'
        self.wo.save(update_fields=['status', 'updated_at'])
        over_issue = MaterialIssue.objects.create(
            plant=self.plant, item=self.item, source_location=self.location_store,
            quantity_issued=Decimal('3'), work_order=self.wo,
        )
        with self.assertRaises(ValidationError):
            post_material_issue(over_issue, self.store_user)
        line.refresh_from_db()
        self.assertEqual(line.quantity_used, Decimal('0'))

    def test_operation_level_non_stock_material_creates_material_po_type(self):
        self.item.procurement_type = 'NON_STOCK'
        self.item.save(update_fields=['procurement_type', 'updated_at'])
        op = WorkOrderOperation.objects.create(
            work_order=self.wo, sequence=10, description='Replace bearing',
            work_centre=self.work_centre, assigned_to=self.engineer,
            execution_type='INTERNAL', planned_hours=1,
        )
        pr = self.make_pr(source_operation=op, status='APPROVED')
        po = PurchaseOrder.objects.create(
            plant=self.plant,
            purchase_request=pr,
            item=self.item,
            vendor='Vendor A',
            quantity=pr.quantity,
            unit_rate=Decimal('100'),
            created_by=self.purchase_user,
            po_type='SERVICE',
            status='RECEIVED',
        )
        self.assertEqual(po.po_type, 'MATERIAL')
        self.assertEqual(po.status, 'DRAFT')

    def test_service_entry_cannot_exceed_po_quantity_or_value(self):
        service_item = SparePart.objects.create(
            plant=self.plant, part_code='SVC-01', item_no='SVC-01', name='Alignment Service',
            item_description='External alignment', item_category='SERVICE', procurement_type='SERVICE',
        )
        op = WorkOrderOperation.objects.create(
            work_order=self.wo, sequence=10, description='External alignment',
            work_centre=self.work_centre, execution_type='EXTERNAL', service_item=service_item,
            planned_hours=1, vendor='Service Vendor',
        )
        pr = self.make_pr(item=service_item, source_operation=op, quantity=Decimal('2'), status='APPROVED')
        po = PurchaseOrder.objects.create(
            plant=self.plant, purchase_request=pr, item=service_item, vendor='Service Vendor',
            quantity=Decimal('2'), unit_rate=Decimal('100'), created_by=self.purchase_user,
        )
        po.status = 'RELEASED'
        po.save(update_fields=['status', 'updated_at'])
        ServiceEntrySheet.objects.create(
            purchase_order=po, work_order_operation=op, description='First portion',
            quantity=Decimal('1'), amount=Decimal('100'), status='ACCEPTED', created_by=self.engineer,
            accepted_by=self.hod, accepted_at=timezone.now(),
        )
        excessive = ServiceEntrySheet(
            purchase_order=po, work_order_operation=op, description='Excessive portion',
            quantity=Decimal('2'), amount=Decimal('150'), created_by=self.engineer,
        )
        with self.assertRaises(ValidationError):
            excessive.full_clean()

    def test_downward_meter_correction_becomes_current_and_same_day_is_allowed(self):
        meter = AssetMeter.objects.create(
            asset=self.asset, meter_type='RUNNING_HOURS', unit='h', current_reading=Decimal('0')
        )
        today = timezone.localdate()
        AssetMeterReading.objects.create(
            meter=meter, reading=Decimal('100'), reading_date=today,
            entered_by=self.engineer, reading_source='MANUAL',
        )
        correction = AssetMeterReading(
            meter=meter, reading=Decimal('90'), reading_date=today,
            entered_by=self.engineer, reading_source='CORRECTION', correction_reason='Meter entry correction',
        )
        correction.full_clean()
        correction.save()
        meter.refresh_from_db()
        self.assertEqual(meter.current_reading, Decimal('90'))
        self.assertEqual(meter.readings.filter(reading_date=today).count(), 2)

    def test_downtime_is_blocked_after_teco(self):
        self.wo.status = 'TECO'
        self.wo.technical_lock = True
        self.wo.actual_start = timezone.now() - timedelta(hours=2)
        self.wo.actual_end = timezone.now() - timedelta(hours=1)
        self.wo.save(update_fields=['status', 'technical_lock', 'actual_start', 'actual_end', 'updated_at'])
        event = AssetDowntimeEvent(
            asset=self.asset, work_order=self.wo, downtime_type='BREAKDOWN',
            started_at=timezone.now() - timedelta(hours=2), ended_at=timezone.now() - timedelta(hours=1),
            reason='Late entry', recorded_by=self.engineer,
        )
        with self.assertRaises(ValidationError):
            event.full_clean()

    def test_teco_does_not_mark_unused_planned_material_as_issued(self):
        self.wo.status = 'VERIFIED'
        self.wo.actual_start = timezone.now() - timedelta(hours=2)
        self.wo.actual_end = timezone.now() - timedelta(hours=1)
        self.wo.failure_mode = 'Bearing failure'
        self.wo.failure_cause = 'Wear'
        self.wo.completion_notes = 'Completed'
        self.wo.save()
        line = WorkOrderSpare.objects.create(
            work_order=self.wo, spare_part=self.item, quantity_required=Decimal('2'),
            quantity_reserved=Decimal('2'), quantity_used=Decimal('0'), reservation_status='RESERVED',
        )
        InventoryReservation.objects.create(
            work_order_spare=line, item=self.item, location=self.location_store,
            quantity=Decimal('2'), status='ACTIVE', reserved_by=self.engineer,
        )
        transition_work_order(self.wo, 'teco', self.hod)
        line.refresh_from_db()
        self.assertEqual(line.quantity_used, Decimal('0'))
        self.assertEqual(line.quantity_reserved, Decimal('0'))
        self.assertEqual(line.reservation_status, 'UNRESERVED')

    def test_business_close_rejects_open_purchase_request(self):
        self.wo.status = 'COST_CLOSURE'
        self.wo.settlement_status = 'NOT_REQUIRED'
        self.wo.save(update_fields=['status', 'settlement_status', 'updated_at'])
        self.make_pr(status='PO_CREATED')
        with self.assertRaises(ValidationError):
            transition_work_order(self.wo, 'close', self.hod)

    def test_received_work_order_shortage_is_reserved_for_that_work_order(self):
        self.item.procurement_type = 'NON_STOCK'
        self.item.save(update_fields=['procurement_type', 'updated_at'])
        pr = self.make_pr(quantity=Decimal('5'), status='APPROVED')
        line = WorkOrderSpare.objects.create(
            work_order=self.wo, spare_part=self.item, procurement_type='NON_STOCK',
            quantity_required=Decimal('5'), purchase_request=pr, reservation_status='PROCUREMENT',
        )
        po = PurchaseOrder.objects.create(
            plant=self.plant, purchase_request=pr, item=self.item, vendor='Vendor A',
            quantity=Decimal('5'), unit_rate=Decimal('100'), created_by=self.purchase_user,
        )
        po.status = 'RELEASED'
        po.save(update_fields=['status', 'updated_at'])
        receipt = GoodsReceipt.objects.create(
            plant=self.plant, purchase_order=po, item=self.item,
            received_location=self.location_store, quantity_received=Decimal('2'),
        )
        post_goods_receipt(receipt, self.store_user)
        line.refresh_from_db()
        reservation = line.reservations.get(location=self.location_store)
        self.assertEqual(reservation.quantity, Decimal('2'))
        self.assertEqual(reservation.status, 'ACTIVE')
        self.assertEqual(line.quantity_reserved, Decimal('2'))

    def test_service_purchase_order_form_derives_service_type_before_model_validation(self):
        service_item = SparePart.objects.create(
            plant=self.plant, part_code='SVC-FORM', item_no='SVC-FORM', name='Vendor Service',
            item_description='External service item', item_category='SERVICE', procurement_type='SERVICE',
        )
        op = WorkOrderOperation.objects.create(
            work_order=self.wo, sequence=10, description='External service',
            work_centre=self.work_centre, execution_type='EXTERNAL', service_item=service_item,
            planned_hours=1, vendor='Service Vendor',
        )
        pr = self.make_pr(item=service_item, source_operation=op, quantity=Decimal('1'), status='APPROVED')
        form = PurchaseOrderForm(
            data={
                'purchase_request': pr.pk,
                'vendor': 'Service Vendor',
                'order_date': timezone.localdate().isoformat(),
                'quantity': '1',
                'unit_rate': '500',
                'description': 'External service',
                'remarks': '',
            },
            user=self.purchase_user,
        )
        self.assertTrue(form.is_valid(), form.errors.as_json())
        self.assertEqual(form.instance.po_type, 'SERVICE')
        self.assertEqual(form.instance.status, 'DRAFT')
        self.assertEqual(form.instance.plant, self.plant)
        self.assertEqual(form.instance.item, service_item)

    def test_goods_receipt_form_derives_hidden_plant_and_item_before_validation(self):
        pr = self.make_pr(quantity=Decimal('2'), status='APPROVED')
        po = PurchaseOrder.objects.create(
            plant=self.plant, purchase_request=pr, item=self.item, vendor='Vendor A',
            quantity=Decimal('2'), unit_rate=Decimal('100'), created_by=self.purchase_user,
        )
        po.status = 'RELEASED'
        po.save(update_fields=['status', 'updated_at'])
        form = GoodsReceiptForm(
            data={
                'purchase_order': po.pk,
                'received_date': timezone.localdate().isoformat(),
                'quantity_received': '1',
                'received_location': self.location_store.pk,
                'migo_reference': 'MIGO-TEST',
                'remarks': '',
            },
            user=self.store_user,
        )
        self.assertTrue(form.is_valid(), form.errors.as_json())
        self.assertEqual(form.instance.plant, self.plant)
        self.assertEqual(form.instance.item, self.item)

    def test_material_issue_requires_operation_when_same_spare_is_planned_on_multiple_operations(self):
        self.wo.status = 'RELEASED'
        self.wo.save(update_fields=['status', 'updated_at'])
        op1 = WorkOrderOperation.objects.create(
            work_order=self.wo, sequence=10, description='First', work_centre=self.work_centre,
            assigned_to=self.engineer, planned_hours=1,
        )
        op2 = WorkOrderOperation.objects.create(
            work_order=self.wo, sequence=20, description='Second', work_centre=self.work_centre,
            assigned_to=self.engineer, planned_hours=1,
        )
        WorkOrderSpare.objects.create(work_order=self.wo, operation=op1, spare_part=self.item, quantity_required=Decimal('1'))
        WorkOrderSpare.objects.create(work_order=self.wo, operation=op2, spare_part=self.item, quantity_required=Decimal('1'))
        issue = MaterialIssue(
            plant=self.plant, item=self.item, source_location=self.location_store,
            quantity_issued=Decimal('1'), work_order=self.wo,
        )
        with self.assertRaises(ValidationError) as error:
            issue.full_clean()
        self.assertIn('operation', error.exception.message_dict)
