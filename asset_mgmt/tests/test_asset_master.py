from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from asset_mgmt.models import Asset, AssetStatusHistory, AssetTransferRequest
from asset_mgmt.tests.helpers import EngineeringDataMixin


class AssetMasterTests(EngineeringDataMixin, TestCase):
    def test_asset_id_is_generated_and_qr_token_created(self):
        asset = Asset.objects.create(
            plant=self.plant,
            functional_location=self.location,
            asset_type='PUMP',
            tag_number='P-TEST-900',
            name='Test Pump 900',
            category=self.category,
            created_by=self.hod,
        )
        self.assertTrue(asset.asset_id)
        self.assertTrue(asset.qr_token)
        self.assertEqual(asset.area, self.location.area)
        self.assertEqual(asset.company, self.plant.company)

    def test_duplicate_tag_in_same_plant_is_blocked(self):
        Asset.objects.create(plant=self.plant, functional_location=self.location, asset_type='PUMP', tag_number='DUP-001', name='First Duplicate')
        duplicate = Asset(plant=self.plant, functional_location=self.location, asset_type='PUMP', tag_number='DUP-001', name='Second Duplicate')
        with self.assertRaises(Exception):
            duplicate.full_clean()
            duplicate.save()

    def test_circular_parent_is_blocked(self):
        parent = Asset.objects.create(plant=self.plant, functional_location=self.location, asset_type='PUMP', tag_number='TREE-P', name='Parent')
        child = Asset.objects.create(plant=self.plant, functional_location=self.location, asset_type='MOTOR', tag_number='TREE-C', name='Child', parent_asset=parent)
        parent.parent_asset = child
        with self.assertRaises(ValidationError):
            parent.full_clean()

    def test_status_action_records_history(self):
        self.client.force_login(self.hod)
        response = self.client.post(reverse('asset_status_change', args=[self.asset.pk]), {
            'lifecycle_status': 'ACTIVE',
            'operational_status': 'MAINTENANCE',
            'effective_date': date.today().isoformat(),
            'reason': 'Testing controlled status change',
        })
        self.assertEqual(response.status_code, 302)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, 'MAINTENANCE')
        self.assertTrue(AssetStatusHistory.objects.filter(asset=self.asset, new_operational_status='MAINTENANCE').exists())

    def test_transfer_updates_location_only_on_receive(self):
        transfer = AssetTransferRequest.objects.create(
            asset=self.asset,
            current_plant=self.plant,
            current_location=self.location,
            destination_plant=self.plant,
            destination_location=self.location,
            transfer_date=date.today(),
            reason='Testing transfer workflow',
            requested_by=self.hod,
            status='DISPATCHED',
        )
        transfer.complete_transfer(self.hod)
        transfer.refresh_from_db()
        self.assertEqual(transfer.status, 'COMPLETED')
