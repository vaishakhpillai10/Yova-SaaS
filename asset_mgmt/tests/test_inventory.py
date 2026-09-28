from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from asset_mgmt.models import GoodsReceipt, MaterialIssue, PurchaseOrder, StockTransaction
from asset_mgmt.services.inventory import post_goods_receipt, post_material_issue
from asset_mgmt.services.workflows import approve_purchase_request, submit_purchase_request

from .helpers import EngineeringDataMixin


class InventoryPostingTests(EngineeringDataMixin, TestCase):
    def test_material_issue_prevents_negative_stock(self):
        issue = MaterialIssue.objects.create(
            plant=self.plant, item=self.item, source_location=self.location_store,
            quantity_issued=Decimal('11'), work_order=self.wo
        )
        with self.assertRaises(ValidationError):
            post_material_issue(issue, self.store_user)
        self.balance.refresh_from_db()
        issue.refresh_from_db()
        self.assertEqual(self.balance.quantity, Decimal('10'))
        self.assertEqual(issue.status, 'DRAFT')
        self.assertFalse(StockTransaction.objects.filter(reference_no=issue.issue_no).exists())

    def test_goods_receipt_updates_stock_and_blocks_over_receipt(self):
        pr = self.make_pr(quantity=Decimal('5'))
        submit_purchase_request(pr, self.engineer)
        approve_purchase_request(pr, self.hod, 'Approved')
        po = PurchaseOrder.objects.create(
            plant=self.plant, purchase_request=pr, item=self.item, vendor='Vendor A',
            quantity=Decimal('5'), unit_rate=Decimal('100'), created_by=self.purchase_user,
            status='RELEASED'
        )
        first = GoodsReceipt.objects.create(
            plant=self.plant, purchase_order=po, item=self.item,
            received_location=self.location_store, quantity_received=Decimal('3')
        )
        post_goods_receipt(first, self.store_user)
        po.refresh_from_db()
        self.assertEqual(po.status, 'PARTIAL_RECEIVED')
        second = GoodsReceipt.objects.create(
            plant=self.plant, purchase_order=po, item=self.item,
            received_location=self.location_store, quantity_received=Decimal('3')
        )
        with self.assertRaises(ValidationError):
            post_goods_receipt(second, self.store_user)
        second.refresh_from_db()
        self.assertEqual(second.status, 'DRAFT')
