from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone

from asset_mgmt.models import (
    Area, Asset, AssetCategory, Company, FunctionalLocation, InventoryBalance, MaintenanceRequest,
    Plant, PurchaseRequest, SparePart, StoreLocation, UserAssignment, WorkCentre, WorkOrder,
)
from asset_mgmt.roles import ALL_ROLES

User = get_user_model()


class EngineeringDataMixin:
    @classmethod
    def setUpTestData(cls):
        cls.groups = {name: Group.objects.create(name=name) for name in ALL_ROLES}
        cls.engineer = User.objects.create_user('engineer', password='Test@12345')
        cls.hod = User.objects.create_user('hod', password='Test@12345')
        cls.purchase_user = User.objects.create_user('purchase_user', password='Test@12345')
        cls.store_user = User.objects.create_user('store_user', password='Test@12345')
        cls.outsider = User.objects.create_user('outsider', password='Test@12345')
        cls.engineer.groups.add(cls.groups['Maintenance'])
        cls.hod.groups.add(cls.groups['HOD'])
        cls.purchase_user.groups.add(cls.groups['Purchase'])
        cls.store_user.groups.add(cls.groups['Store'])
        cls.outsider.groups.add(cls.groups['Maintenance'])

        cls.company = Company.objects.create(code='TST', name='Test Industries')
        cls.category = AssetCategory.objects.create(name='Pump', code='PUMP', asset_id_prefix='PUMP')
        cls.plant = Plant.objects.create(company=cls.company, code='P01', name='Plant 01')
        cls.other_plant = Plant.objects.create(company=cls.company, code='P02', name='Plant 02')
        cls.work_centre = WorkCentre.objects.create(
            plant=cls.plant, code='MECH', name='Mechanical', discipline='MECHANICAL'
        )
        cls.other_work_centre = WorkCentre.objects.create(
            plant=cls.other_plant, code='MECH', name='Mechanical', discipline='MECHANICAL'
        )
        UserAssignment.objects.create(
            user=cls.engineer, plant=cls.plant, work_centre=cls.work_centre,
            designation='ENGINEER', reporting_hod=cls.hod, active=True,
        )
        UserAssignment.objects.create(
            user=cls.hod, plant=cls.plant, work_centre=cls.work_centre,
            designation='HOD', active=True,
        )
        UserAssignment.objects.create(
            user=cls.purchase_user, plant=cls.plant, work_centre=cls.work_centre,
            designation='PURCHASE_USER', reporting_hod=cls.hod, active=True,
        )
        UserAssignment.objects.create(
            user=cls.store_user, plant=cls.plant, work_centre=cls.work_centre,
            designation='STORE_USER', reporting_hod=cls.hod, active=True,
        )
        UserAssignment.objects.create(
            user=cls.outsider, plant=cls.other_plant, work_centre=cls.other_work_centre,
            designation='ENGINEER', active=True,
        )

        cls.area = Area.objects.create(plant=cls.plant, code='PROD', name='Production')
        cls.location = FunctionalLocation.objects.create(
            plant=cls.plant, area=cls.area, name='Pump House', floor='GF', cardinal_direction='N'
        )
        cls.asset = Asset.objects.create(
            plant=cls.plant, functional_location=cls.location, asset_type='PUMP',
            tag_number='P-101', name='Feed Pump', criticality='HIGH'
        )
        cls.item = SparePart.objects.create(
            plant=cls.plant, part_code='BRG-01', item_no='10001', name='Bearing',
            item_description='Pump bearing', minimum_stock=Decimal('2'),
            maximum_stock=Decimal('20'), item_rate=Decimal('100')
        )
        cls.location_store = StoreLocation.objects.create(
            plant=cls.plant, code='MAIN', name='Main Store', bin_code='A01'
        )
        cls.balance = InventoryBalance.objects.create(
            item=cls.item, location=cls.location_store, quantity=Decimal('10')
        )
        cls.item.current_stock = Decimal('10')
        cls.item.save(update_fields=['current_stock', 'updated_at'])

        cls.mr = MaintenanceRequest.objects.create(
            plant=cls.plant, asset=cls.asset, work_centre=cls.work_centre,
            reported_by=cls.engineer, reported_department='MAINTENANCE',
            problem_description='Bearing noise', priority='HIGH'
        )
        cls.wo = WorkOrder.objects.create(
            plant=cls.plant, asset=cls.asset, work_centre=cls.work_centre,
            maintenance_request=cls.mr, created_by=cls.hod, assigned_to=cls.engineer,
            work_type='BREAKDOWN', priority='HIGH', job_description='Replace bearing',
            planned_start=timezone.now(), planned_end=timezone.now() + timedelta(hours=4),
            status='RELEASED'
        )

    def make_pr(self, **overrides):
        values = {
            'plant': self.plant,
            'work_centre': self.work_centre,
            'work_order': self.wo,
            'item': self.item,
            'requested_by': self.engineer,
            'assigned_hod': self.hod,
            'quantity': Decimal('2'),
            'purpose': 'Required for pump repair',
        }
        values.update(overrides)
        return PurchaseRequest.objects.create(**values)
