from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils.html import escape

from asset_mgmt.models import Asset, MaintenanceRequest
from asset_mgmt.views import AssetListView

from .helpers import EngineeringDataMixin


class CoreViewTests(EngineeringDataMixin, TestCase):
    def test_dashboard_renders_with_chart_payloads(self):
        admin = get_user_model().objects.create_superuser('dashboard_admin', 'dash@example.com', 'Test@12345')
        admin.groups.add(self.groups['Admin'])
        self.client.force_login(admin)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('asset_status_json', response.context)
        self.assertContains(response, 'Open work orders')

    def test_role_dashboards_render(self):
        self.client.force_login(self.hod)
        manager = self.client.get(reverse('maintenance_manager_dashboard'))
        self.assertEqual(manager.status_code, 200)
        self.assertIn('manager_pipeline_json', manager.context)
        self.assertIn('manager_capacity_json', manager.context)
        assets = self.client.get(reverse('asset_dashboard'))
        self.assertEqual(assets.status_code, 200)
        self.assertIn('asset_status_json', assets.context)
        self.assertIn('asset_readiness_percent', assets.context)

    def test_sidebar_groups_dashboards_and_maintenance_modules(self):
        self.client.force_login(self.hod)
        response = self.client.get(reverse('maintenance_manager_dashboard'))

        self.assertEqual(response.status_code, 200)
        sections = {section['title']: section['items'] for section in response.context['navigation_sections']}
        main_items = sections['Main']
        self.assertEqual(main_items[0]['label'], 'Dashboard')
        dashboard_group = next(item for item in main_items if item['label'] == 'Dashboards')
        self.assertTrue(dashboard_group['active'])
        self.assertIn('Maintenance Manager', [item['label'] for item in dashboard_group['children']])
        self.assertEqual(
            [item['label'] for item in sections['Maintenance']],
            ['Maintenance Requests', 'Work Orders', 'Maintenance History', 'Downtime'],
        )
        self.assertIn('PM Plans', [item['label'] for item in sections['Preventive & Planned Maintenance']])
        self.assertIn('Reliability Analysis', [item['label'] for item in sections['Reliability']])
        self.assertIn('Permit to Work', [item['label'] for item in sections['Inspection & Compliance']])
        self.assertContains(response, '<details class="nav-dropdown" open>')
        for title in (
            'Asset Management',
            'Maintenance',
            'Preventive & Planned Maintenance',
            'Reliability',
            'Inspection & Compliance',
            'Materials',
            'Utilities & Approvals',
        ):
            self.assertContains(response, f'<span class="nav-text">{escape(title)}</span>')
        self.assertContains(response, 'class="nav-dropdown nav-section-dropdown"', count=7)

    def test_reliability_analysis_sidebar_route_renders(self):
        self.client.force_login(self.hod)
        response = self.client.get(reverse('reliability_analysis'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Maintenance History & Reliability')

    def test_purchase_and_store_dashboard_routing(self):
        self.client.force_login(self.purchase_user)
        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(response, reverse('mm_dashboard'), fetch_redirect_response=False)
        self.client.force_login(self.store_user)
        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(response, reverse('store_dashboard'), fetch_redirect_response=False)

    def test_work_order_list_supports_dashboard_work_type_filter(self):
        self.client.force_login(self.hod)
        response = self.client.get(reverse('work_order_list'), {'work_type': 'PREVENTIVE'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.wo, list(response.context['items']))
        response = self.client.get(reverse('work_order_list'), {'work_type': 'BREAKDOWN'})
        self.assertIn(self.wo, list(response.context['items']))

    def test_asset_pagination_preserves_active_filters(self):
        Asset.objects.create(
            plant=self.plant,
            functional_location=self.location,
            asset_type='PUMP',
            tag_number='P-102',
            name='Backup Pump',
            criticality='HIGH',
        )
        self.client.force_login(self.engineer)
        filters = {
            'plant': str(self.plant.pk),
            'lifecycle': 'ACTIVE',
            'q': 'Pump',
        }

        with patch.object(AssetListView, 'paginate_by', 1):
            response = self.client.get(reverse('asset_list'), filters)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_paginated'])
        expected_query = f'plant={self.plant.pk}&amp;lifecycle=ACTIVE&amp;q=Pump&amp;page=2'
        self.assertContains(response, expected_query)

    def test_outsider_cannot_open_asset_detail(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('asset_detail', args=[self.asset.pk]))
        self.assertEqual(response.status_code, 404)

    def test_pr_approval_endpoint_rejects_get(self):
        pr = self.make_pr()
        self.client.force_login(self.hod)
        response = self.client.get(reverse('purchase_request_approve', args=[pr.pk]))
        self.assertEqual(response.status_code, 405)

    def test_pdf_routes_are_not_shadowed_by_action_route(self):
        # Reverse resolution confirms approval.pdf routes remain distinct from generic action URLs.
        self.assertTrue(reverse('moc_pdf', args=[1]).endswith('/approval.pdf'))
        self.assertTrue(reverse('capex_pdf', args=[1]).endswith('/approval.pdf'))
        self.assertTrue(reverse('disposal_pdf', args=[1]).endswith('/approval.pdf'))

    def test_maintenance_request_create_derives_plant_before_model_validation(self):
        self.client.force_login(self.engineer)
        response = self.client.post(reverse('maintenance_request_create'), {
            'plant': self.plant.pk,
            'asset': self.asset.pk,
            'work_centre': self.work_centre.pk,
            'reported_department': 'MAINTENANCE',
            'problem_description': 'Seal leakage reported from production.',
            'priority': 'HIGH',
        })

        self.assertRedirects(
            response,
            reverse('maintenance_request_list'),
            fetch_redirect_response=False,
        )
        request = MaintenanceRequest.objects.get(
            asset=self.asset,
            problem_description='Seal leakage reported from production.',
        )
        self.assertEqual(request.plant, self.asset.plant)
        self.assertEqual(request.work_centre, self.work_centre)
        self.assertEqual(request.reported_by, self.engineer)

    def test_maintenance_request_form_waits_for_a_plant_before_listing_dependencies(self):
        self.client.force_login(self.engineer)
        response = self.client.get(reverse('maintenance_request_create'))

        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertIn('plant', form.fields)
        self.assertFalse(form.fields['asset'].queryset.exists())
        self.assertFalse(form.fields['work_centre'].queryset.exists())
        self.assertContains(response, 'id_asset_combobox')
        self.assertContains(response, 'asset-combobox-results')
        self.assertContains(response, 'Type asset ID or name')
        self.assertContains(response, 'select.form-select { display: none !important; }')

    def test_maintenance_request_options_are_filtered_by_selected_plant(self):
        self.client.force_login(self.engineer)
        response = self.client.get(
            reverse('maintenance_request_options'),
            {'plant': self.plant.pk},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn(self.asset.pk, [item['id'] for item in payload['assets']])
        self.assertIn(self.work_centre.pk, [item['id'] for item in payload['work_centres']])
        self.assertNotIn(self.other_work_centre.pk, [item['id'] for item in payload['work_centres']])

    def test_maintenance_request_options_reject_an_unassigned_plant(self):
        self.client.force_login(self.engineer)
        response = self.client.get(
            reverse('maintenance_request_options'),
            {'plant': self.other_plant.pk},
        )

        self.assertEqual(response.status_code, 404)
