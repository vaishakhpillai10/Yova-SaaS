from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from asset_mgmt.models import PurchaseOrder, PurchaseRequestApprovalHistory
from asset_mgmt.services.workflows import approve_purchase_request, reject_purchase_request, submit_purchase_request

from .helpers import EngineeringDataMixin


class PurchaseRequestWorkflowTests(EngineeringDataMixin, TestCase):
    def test_requester_submit_and_hod_approve(self):
        pr = self.make_pr()
        submit_purchase_request(pr, self.engineer)
        pr.refresh_from_db()
        self.assertEqual(pr.status, 'SUBMITTED')
        approve_purchase_request(pr, self.hod, 'Approved for urgent repair')
        pr.refresh_from_db()
        self.assertEqual(pr.status, 'APPROVED')
        self.assertEqual(pr.approved_by, self.hod)
        self.assertEqual(PurchaseRequestApprovalHistory.objects.filter(purchase_request=pr).count(), 2)

    def test_requester_cannot_self_approve(self):
        pr = self.make_pr(assigned_hod=self.engineer)
        submit_purchase_request(pr, self.engineer)
        with self.assertRaises(PermissionDenied):
            approve_purchase_request(pr, self.engineer, 'Attempted approval')

    def test_other_plant_user_cannot_approve(self):
        pr = self.make_pr()
        submit_purchase_request(pr, self.engineer)
        with self.assertRaises(PermissionDenied):
            approve_purchase_request(pr, self.outsider, 'Not my plant')

    def test_rejected_pr_can_be_resubmitted(self):
        pr = self.make_pr()
        submit_purchase_request(pr, self.engineer)
        reject_purchase_request(pr, self.hod, 'Need clearer justification')
        pr.refresh_from_db()
        self.assertEqual(pr.status, 'REJECTED')
        submit_purchase_request(pr, self.engineer)
        pr.refresh_from_db()
        self.assertEqual(pr.status, 'SUBMITTED')
        self.assertEqual(pr.rejection_reason, '')

    def test_po_requires_approved_pr_and_exact_quantity(self):
        pr = self.make_pr()
        po = PurchaseOrder(
            plant=self.plant, purchase_request=pr, item=self.item, vendor='Vendor A',
            quantity=Decimal('2'), unit_rate=Decimal('100'), created_by=self.purchase_user,
        )
        with self.assertRaises(ValidationError):
            po.full_clean()
        submit_purchase_request(pr, self.engineer)
        approve_purchase_request(pr, self.hod, 'Approved')
        pr.refresh_from_db()
        po.full_clean()
        po.save()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PurchaseOrder.objects.create(
                    plant=self.plant, purchase_request=pr, item=self.item, vendor='Vendor B',
                    quantity=Decimal('2'), unit_rate=Decimal('100'), created_by=self.purchase_user,
                )
