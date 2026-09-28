from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.utils import timezone

from asset_mgmt.models import (
    Area, Asset, AssetCategory, Company, FunctionalLocation, InventoryBalance,
    MaintenanceRequest, MeterReading, Plant, PMPlan, PMTask, PurchaseRequest,
    SparePart, StoreLocation, UserAssignment, UtilityMeter, WorkCentre, WorkOrder, WorkOrderOperation, RiskAssessment,
)
from asset_mgmt.roles import ALL_ROLES, ROLE_DEMO_USERS

User = get_user_model()


class Command(BaseCommand):
    help = 'Create secure demo roles, users, organisational hierarchy and sample records.'

    def handle(self, *args, **options):
        groups = {name: Group.objects.get_or_create(name=name)[0] for name in ALL_ROLES}
        users = {}
        for username, config in ROLE_DEMO_USERS.items():
            user, _ = User.objects.get_or_create(username=username)
            user.email = config['email']
            user.first_name = config.get('first_name', '')
            user.last_name = config.get('last_name', '')
            user.is_staff = config.get('is_staff', False)
            user.is_superuser = config.get('is_superuser', False)
            user.is_active = True
            user.set_password(config['password'])
            user.save()
            user.groups.clear()
            user.groups.add(groups[config['role']])
            users[username] = user

        company, _ = Company.objects.get_or_create(code='VAI', defaults={'name': 'Vaisra Demo Industries'})
        plant1, _ = Plant.objects.get_or_create(company=company, code='PL01', defaults={'name': 'Main Manufacturing Plant', 'address': 'Kerala, India'})
        plant2, _ = Plant.objects.get_or_create(company=company, code='PL02', defaults={'name': 'Utilities Plant', 'address': 'Kerala, India'})

        area_prod, _ = Area.objects.get_or_create(plant=plant1, code='PROD', defaults={'name': 'Production Block'})
        area_util, _ = Area.objects.get_or_create(plant=plant2, code='UTIL', defaults={'name': 'Utility Block'})
        fl_pump, _ = FunctionalLocation.objects.get_or_create(
            code='VAI-PL01-PROD-GF-N-PUMPHOUSE',
            defaults={'plant': plant1, 'area': area_prod, 'name': 'Pump House', 'floor': 'GF', 'cardinal_direction': 'N'},
        )
        fl_utility, _ = FunctionalLocation.objects.get_or_create(
            code='VAI-PL02-UTIL-GF-C-UTILITY',
            defaults={'plant': plant2, 'area': area_util, 'name': 'Utility Station', 'floor': 'GF', 'cardinal_direction': 'C'},
        )

        wc_mech, _ = WorkCentre.objects.get_or_create(plant=plant1, code='MECH', defaults={'name': 'Mechanical Maintenance', 'discipline': 'MECHANICAL'})
        wc_elec, _ = WorkCentre.objects.get_or_create(plant=plant1, code='ELEC', defaults={'name': 'Electrical Maintenance', 'discipline': 'ELECTRICAL'})
        WorkCentre.objects.get_or_create(plant=plant1, code='INST', defaults={'name': 'Instrument Maintenance', 'discipline': 'INSTRUMENT'})
        WorkCentre.objects.get_or_create(plant=plant1, code='CIVIL', defaults={'name': 'Civil Maintenance', 'discipline': 'CIVIL'})
        WorkCentre.objects.get_or_create(plant=plant1, code='UTILITY', defaults={'name': 'Utility Maintenance', 'discipline': 'UTILITY'})
        WorkCentre.objects.get_or_create(plant=plant1, code='IT', defaults={'name': 'IT Services', 'discipline': 'IT'})
        WorkCentre.objects.get_or_create(plant=plant1, code='SAFETY', defaults={'name': 'Safety Services', 'discipline': 'SAFETY'})
        wc_store, _ = WorkCentre.objects.get_or_create(plant=plant1, code='STORE', defaults={'name': 'Engineering Store', 'discipline': 'STORE'})
        wc_mm, _ = WorkCentre.objects.get_or_create(plant=plant1, code='MM', defaults={'name': 'Materials Management', 'discipline': 'MM'})
        wc_prod, _ = WorkCentre.objects.get_or_create(plant=plant1, code='PROD', defaults={'name': 'Production', 'discipline': 'PRODUCTION'})
        wc_util, _ = WorkCentre.objects.get_or_create(plant=plant2, code='UTIL', defaults={'name': 'Utility Maintenance', 'discipline': 'UTILITY'})

        assignments = [
            ('asset_admin', plant1, None, 'ASSET_ADMIN', users['manager']),
            ('asset_admin', plant2, None, 'ASSET_ADMIN', users['manager']),
            ('production', plant1, wc_prod, 'PRODUCTION_USER', users['maintenance_hod']),
            ('maintenance_engineer', plant1, wc_mech, 'ENGINEER', users['maintenance_hod']),
            ('maintenance_hod', plant1, wc_mech, 'HOD', users['manager']),
            ('safety', plant1, None, 'SAFETY_USER', users['manager']),
            ('store', plant1, wc_store, 'STORE_USER', users['manager']),
            ('purchase', plant1, wc_mm, 'PURCHASE_USER', users['manager']),
            ('accounts', plant1, None, 'ACCOUNTS_USER', users['manager']),
            ('manager', plant1, None, 'PLANT_HEAD', None),
            ('manager', plant2, None, 'PLANT_HEAD', None),
            ('maintenance_engineer', plant2, wc_util, 'ENGINEER', users['manager']),
        ]
        for username, plant, centre, designation, hod in assignments:
            UserAssignment.objects.update_or_create(
                user=users[username], plant=plant, work_centre=centre,
                defaults={'designation': designation, 'reporting_hod': hod, 'active': True, 'is_primary': username != 'manager'},
            )

        category, _ = AssetCategory.objects.get_or_create(name='Rotating Equipment')
        pump, _ = Asset.objects.get_or_create(
            plant=plant1, tag_number='P-101',
            defaults={'asset_type': 'PUMP', 'name': 'Feed Pump P-101', 'asset_description': 'Critical feed transfer pump', 'category': category, 'functional_location': fl_pump, 'criticality': 'HIGH', 'criticality_score': 90, 'manufacturer': 'Demo Pumps'},
        )
        utility_asset, _ = Asset.objects.get_or_create(
            plant=plant2, tag_number='CH-101',
            defaults={'asset_type': 'UTILITY', 'name': 'Chiller CH-101', 'asset_description': 'Process chilled water package', 'functional_location': fl_utility, 'criticality': 'HIGH', 'criticality_score': 85},
        )

        bearing, _ = SparePart.objects.get_or_create(
            plant=plant1, item_no='100000001',
            defaults={'part_code': 'BRG-6205', 'name': 'Bearing 6205', 'item_description': 'Deep groove ball bearing', 'item_category': 'MECHANICAL', 'item_class': 'CRITICAL', 'unit': 'Nos', 'minimum_stock': 4, 'maximum_stock': 20, 'item_rate': Decimal('850.00')},
        )
        store_loc, _ = StoreLocation.objects.get_or_create(plant=plant1, code='MAIN', bin_code='A-01', defaults={'name': 'Main Engineering Store'})
        InventoryBalance.objects.update_or_create(item=bearing, location=store_loc, defaults={'quantity': Decimal('10')})
        bearing.current_stock = 10
        bearing.save(update_fields=['current_stock', 'updated_at'])

        mr, _ = MaintenanceRequest.objects.get_or_create(
            plant=plant1, asset=pump, problem_description='Abnormal bearing noise and vibration',
            defaults={'work_centre': wc_mech, 'reported_by': users['production'], 'reported_department': 'PRODUCTION', 'priority': 'HIGH', 'failure_mode': 'Bearing noise'},
        )
        wo, _ = WorkOrder.objects.get_or_create(
            plant=plant1, asset=pump, job_description='Inspect pump bearing and replace if required',
            defaults={'work_centre': wc_mech, 'maintenance_request': mr, 'created_by': users['maintenance_hod'], 'assigned_to': users['maintenance_engineer'], 'supervisor': users['maintenance_hod'], 'work_type': 'BREAKDOWN', 'activity_type': 'REPAIR', 'priority': 'HIGH', 'status': 'DRAFT', 'planned_start': timezone.now(), 'planned_end': timezone.now() + timedelta(hours=4)},
        )
        if not wo.supervisor_id:
            wo.supervisor = users['maintenance_hod']
        wo.status = 'DRAFT'
        wo.save(update_fields=['supervisor', 'status', 'updated_at'])
        mr.status = 'WO_CREATED'
        mr.save(update_fields=['status', 'updated_at'])
        WorkOrderOperation.objects.get_or_create(
            work_order=wo, sequence=10,
            defaults={'description': 'Inspect bearing, isolate equipment and replace bearing if required', 'work_centre': wc_mech, 'assigned_to': users['maintenance_engineer'], 'planned_hours': Decimal('4.00')},
        )
        RiskAssessment.objects.get_or_create(
            work_order=wo, activity='Pump bearing inspection and replacement', hazard='Unexpected rotation / stored energy',
            defaults={'consequence': 'Personnel injury', 'existing_control': 'Isolation and LOTO', 'likelihood': 2, 'severity': 3, 'additional_control': 'Verify zero energy before work'},
        )

        pm, _ = PMPlan.objects.get_or_create(
            plant=plant1, asset=pump, name='Monthly Pump Inspection',
            defaults={'work_centre': wc_mech, 'responsible_user': users['maintenance_engineer'], 'frequency_value': 1, 'frequency_unit': 'MONTHS', 'next_due_date': timezone.localdate() + timedelta(days=7)},
        )
        PMTask.objects.get_or_create(pm_plan=pm, sequence=1, defaults={'task': 'Check bearing noise and vibration', 'safety_instruction': 'Apply LOTO before coupling inspection', 'required_tools': 'Vibration meter', 'expected_result': 'Within approved limit'})
        PMTask.objects.get_or_create(pm_plan=pm, sequence=2, defaults={'task': 'Check seal leakage and lubrication', 'required_tools': 'Torch and grease gun', 'expected_result': 'No leakage'})

        PurchaseRequest.objects.get_or_create(
            plant=plant1, item=bearing, requested_by=users['maintenance_engineer'], purpose='Bearing replacement for feed pump',
            defaults={'work_centre': wc_mech, 'work_order': wo, 'assigned_hod': users['maintenance_hod'], 'quantity': 2, 'required_date': timezone.localdate() + timedelta(days=5)},
        )

        meter, _ = UtilityMeter.objects.get_or_create(plant=plant2, meter_code='ELEC-MAIN', defaults={'name': 'Main Electrical Incomer', 'utility_type': 'ELECTRICITY', 'unit': 'kWh', 'location': 'Main Substation', 'target_per_day': 12000})
        MeterReading.objects.get_or_create(meter=meter, reading_date=timezone.localdate(), defaults={'opening_reading': 100000, 'closing_reading': 110500, 'multiplier': 1, 'recorded_by': users['maintenance_engineer']})

        self.stdout.write(self.style.SUCCESS('Demo data created. Use README_DEMO.md for credentials and testing flow.'))
