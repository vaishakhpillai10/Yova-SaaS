from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

ROLE_ADMIN = 'Admin'
ROLE_PRODUCTION = 'Production'
ROLE_MAINTENANCE = 'Maintenance'
ROLE_HOD = 'HOD'
ROLE_SAFETY = 'Safety'
ROLE_STORE = 'Store'
ROLE_PURCHASE = 'Purchase'
ROLE_ACCOUNTS = 'Accounts'
ROLE_MANAGER = 'Manager'
ROLE_ASSET_ADMIN = 'Asset Admin'

ALL_ROLES = [ROLE_ADMIN, ROLE_ASSET_ADMIN, ROLE_PRODUCTION, ROLE_MAINTENANCE, ROLE_HOD, ROLE_SAFETY, ROLE_STORE, ROLE_PURCHASE, ROLE_ACCOUNTS, ROLE_MANAGER]

ROLE_LABELS = {
    ROLE_ADMIN: 'System Admin', ROLE_ASSET_ADMIN: 'Asset Admin', ROLE_PRODUCTION: 'Production User', ROLE_MAINTENANCE: 'Maintenance Engineer',
    ROLE_HOD: 'Engineering HOD', ROLE_SAFETY: 'Safety Officer', ROLE_STORE: 'Engineering Store User',
    ROLE_PURCHASE: 'Purchase User', ROLE_ACCOUNTS: 'Accounts User', ROLE_MANAGER: 'Plant Head / Manager',
}

ROLE_DEMO_USERS = {
    'admin': {'role': ROLE_ADMIN, 'password': 'Admin@12345', 'email': 'admin@example.com', 'is_staff': True, 'is_superuser': True, 'first_name': 'System', 'last_name': 'Admin'},
    'asset_admin': {'role': ROLE_ASSET_ADMIN, 'password': 'Asset@12345', 'email': 'asset.admin@example.com', 'first_name': 'Asset', 'last_name': 'Admin'},
    'production': {'role': ROLE_PRODUCTION, 'password': 'Demo@12345', 'email': 'production@example.com', 'first_name': 'Production', 'last_name': 'User'},
    'maintenance_engineer': {'role': ROLE_MAINTENANCE, 'password': 'Demo@12345', 'email': 'engineer@example.com', 'first_name': 'Maintenance', 'last_name': 'Engineer'},
    'maintenance_hod': {'role': ROLE_HOD, 'password': 'Demo@12345', 'email': 'hod@example.com', 'first_name': 'Maintenance', 'last_name': 'HOD'},
    'safety': {'role': ROLE_SAFETY, 'password': 'Demo@12345', 'email': 'safety@example.com', 'first_name': 'Safety', 'last_name': 'Officer'},
    'store': {'role': ROLE_STORE, 'password': 'Demo@12345', 'email': 'store@example.com', 'first_name': 'Engineering', 'last_name': 'Store'},
    'purchase': {'role': ROLE_PURCHASE, 'password': 'Demo@12345', 'email': 'purchase@example.com', 'first_name': 'Purchase', 'last_name': 'User'},
    'accounts': {'role': ROLE_ACCOUNTS, 'password': 'Demo@12345', 'email': 'accounts@example.com', 'first_name': 'Accounts', 'last_name': 'User'},
    'manager': {'role': ROLE_MANAGER, 'password': 'Demo@12345', 'email': 'manager@example.com', 'first_name': 'Plant', 'last_name': 'Head'},
}

# URL access is deliberately explicit. Workflow actions perform extra record-level checks in views.
ROLE_URL_ACCESS = {
    'dashboard': ALL_ROLES, 'asset_dashboard': [ROLE_ADMIN, ROLE_ASSET_ADMIN, ROLE_HOD, ROLE_MANAGER], 'engineering_dashboard': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_MANAGER], 'maintenance_manager_dashboard': [ROLE_ADMIN, ROLE_HOD, ROLE_MANAGER], 'scheduling_board': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_MANAGER], 'work_centre_capacity_update': [ROLE_ADMIN, ROLE_HOD, ROLE_MANAGER],
    'mm_dashboard': [ROLE_ADMIN, ROLE_PURCHASE, ROLE_HOD, ROLE_MANAGER], 'store_dashboard': [ROLE_ADMIN, ROLE_STORE, ROLE_HOD, ROLE_MANAGER],
    'utility_dashboard': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_MANAGER],
    'asset_list': [ROLE_ADMIN, ROLE_ASSET_ADMIN, ROLE_HOD, ROLE_MAINTENANCE, ROLE_MANAGER], 'asset_detail': [ROLE_ADMIN, ROLE_ASSET_ADMIN, ROLE_HOD, ROLE_MAINTENANCE, ROLE_MANAGER], 'asset_create': [ROLE_ADMIN, ROLE_ASSET_ADMIN, ROLE_HOD, ROLE_MAINTENANCE],
    'asset_update': [ROLE_ADMIN, ROLE_ASSET_ADMIN, ROLE_HOD, ROLE_MAINTENANCE], 'asset_import': [ROLE_ADMIN, ROLE_ASSET_ADMIN, ROLE_HOD], 'asset_import_template': [ROLE_ADMIN, ROLE_ASSET_ADMIN, ROLE_HOD, ROLE_MAINTENANCE],

    'asset_bom_create': [ROLE_ADMIN, ROLE_ASSET_ADMIN, ROLE_HOD, ROLE_MAINTENANCE], 'asset_bom_update': [ROLE_ADMIN, ROLE_ASSET_ADMIN, ROLE_HOD, ROLE_MAINTENANCE],
    'asset_condition_assessment_create': [ROLE_ADMIN, ROLE_ASSET_ADMIN, ROLE_HOD, ROLE_MAINTENANCE], 'asset_criticality_assessment_create': [ROLE_ADMIN, ROLE_ASSET_ADMIN, ROLE_HOD],
    'asset_document_upload': [ROLE_ADMIN, ROLE_ASSET_ADMIN, ROLE_HOD, ROLE_MAINTENANCE], 'asset_image_upload': [ROLE_ADMIN, ROLE_ASSET_ADMIN, ROLE_HOD, ROLE_MAINTENANCE],
    'asset_meter_create': [ROLE_ADMIN, ROLE_ASSET_ADMIN, ROLE_HOD, ROLE_MAINTENANCE], 'asset_meter_reading_create': [ROLE_ADMIN, ROLE_ASSET_ADMIN, ROLE_HOD, ROLE_MAINTENANCE],
    'asset_status_change': [ROLE_ADMIN, ROLE_ASSET_ADMIN, ROLE_HOD, ROLE_MAINTENANCE], 'asset_transfer_create': [ROLE_ADMIN, ROLE_ASSET_ADMIN, ROLE_HOD, ROLE_MAINTENANCE],
    'asset_transfer_detail': [ROLE_ADMIN, ROLE_ASSET_ADMIN, ROLE_HOD, ROLE_MAINTENANCE, ROLE_MANAGER], 'asset_transfer_action': [ROLE_ADMIN, ROLE_ASSET_ADMIN, ROLE_HOD, ROLE_MANAGER],
    'asset_change_request_create': [ROLE_ADMIN, ROLE_ASSET_ADMIN, ROLE_HOD, ROLE_MAINTENANCE], 'asset_change_request_action': [ROLE_ADMIN, ROLE_ASSET_ADMIN, ROLE_HOD, ROLE_MANAGER],
    'maintenance_request_list': [ROLE_ADMIN, ROLE_PRODUCTION, ROLE_MAINTENANCE, ROLE_HOD, ROLE_SAFETY, ROLE_MANAGER],
    'maintenance_request_create': [ROLE_ADMIN, ROLE_PRODUCTION, ROLE_MAINTENANCE, ROLE_HOD],
    'maintenance_request_update': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_PRODUCTION],
    'maintenance_request_action': [ROLE_ADMIN, ROLE_PRODUCTION, ROLE_MAINTENANCE, ROLE_HOD, ROLE_MANAGER], 'maintenance_request_item_add': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD], 'maintenance_catalog_list': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_MANAGER], 'maintenance_catalog_create': [ROLE_ADMIN, ROLE_HOD],
    'work_order_list': [ROLE_ADMIN, ROLE_PRODUCTION, ROLE_MAINTENANCE, ROLE_HOD, ROLE_SAFETY, ROLE_STORE, ROLE_ACCOUNTS, ROLE_MANAGER],
    'work_order_detail': [ROLE_ADMIN, ROLE_PRODUCTION, ROLE_MAINTENANCE, ROLE_HOD, ROLE_SAFETY, ROLE_STORE, ROLE_ACCOUNTS, ROLE_MANAGER],
    'work_order_create': [ROLE_ADMIN, ROLE_HOD, ROLE_MAINTENANCE], 'work_order_update': [ROLE_ADMIN, ROLE_HOD, ROLE_MAINTENANCE],
    'work_order_action': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_ACCOUNTS, ROLE_MANAGER],
    'work_order_operation_add': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD], 'work_order_operation_update': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD], 'work_order_operation_action': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD], 'work_order_confirmation_add': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD], 'settlement_rule_add': [ROLE_ADMIN, ROLE_HOD, ROLE_ACCOUNTS, ROLE_MANAGER], 'work_order_spare_add': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD], 'work_order_spare_update': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD],
    'work_order_labour_add': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD], 'work_order_risk_add': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_SAFETY],
    'maintenance_history_reliability': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_SAFETY, ROLE_STORE, ROLE_ACCOUNTS, ROLE_MANAGER], 'reliability_analysis': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_SAFETY, ROLE_STORE, ROLE_ACCOUNTS, ROLE_MANAGER],
    'maintenance_history_excel': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_SAFETY, ROLE_STORE, ROLE_ACCOUNTS, ROLE_MANAGER],
    'maintenance_history_pdf': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_SAFETY, ROLE_STORE, ROLE_ACCOUNTS, ROLE_MANAGER],
    'downtime_list': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_MANAGER], 'downtime_create': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD],
    'pm_plan_list': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_MANAGER], 'pm_plan_detail': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_MANAGER], 'pm_plan_create': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD], 'pm_plan_update': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD],
    'pm_task_create': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD], 'pm_counter_create': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD], 'pm_strategy_call_create': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD], 'pm_generate_wo': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD], 'task_list_list': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_MANAGER], 'task_list_detail': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_MANAGER], 'task_list_create': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD], 'task_list_operation_create': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD], 'task_list_material_create': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD], 'maintenance_strategy_list': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_MANAGER], 'maintenance_strategy_create': [ROLE_ADMIN, ROLE_HOD], 'maintenance_strategy_package_create': [ROLE_ADMIN, ROLE_HOD], 'condition_rule_list': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_MANAGER], 'condition_rule_create': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD],
    'shutdown_list': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_MANAGER], 'shutdown_create': [ROLE_ADMIN, ROLE_HOD], 'shutdown_update': [ROLE_ADMIN, ROLE_HOD], 'shutdown_job_create': [ROLE_ADMIN, ROLE_HOD, ROLE_MAINTENANCE], 'shutdown_job_update': [ROLE_ADMIN, ROLE_HOD, ROLE_MAINTENANCE],
    'inspection_plan_list': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_SAFETY, ROLE_MANAGER], 'inspection_plan_create': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_SAFETY], 'inspection_record_create': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_SAFETY],
    'calibration_plan_list': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_MANAGER], 'calibration_plan_create': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD], 'calibration_record_create': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD],
    'permit_list': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_SAFETY, ROLE_MANAGER], 'permit_create': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_SAFETY], 'permit_action': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_SAFETY],
    'rca_list': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_MANAGER], 'rca_create': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD], 'fishbone_create': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD],
    'capa_list': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_MANAGER], 'capa_create': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD],
    'llf_list': [ROLE_ADMIN, ROLE_PRODUCTION, ROLE_MAINTENANCE, ROLE_HOD, ROLE_MANAGER], 'llf_create': [ROLE_ADMIN, ROLE_PRODUCTION, ROLE_MAINTENANCE, ROLE_HOD], 'llf_convert_mr': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD],
    'moc_list': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_MANAGER], 'moc_create': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD], 'moc_update': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD], 'moc_action': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_MANAGER], 'moc_pdf': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_MANAGER],
    'spare_list': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_STORE, ROLE_PURCHASE, ROLE_MANAGER], 'spare_create': [ROLE_ADMIN, ROLE_STORE], 'spare_update': [ROLE_ADMIN, ROLE_STORE],
    'purchase_request_list': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_STORE, ROLE_PURCHASE, ROLE_MANAGER], 'purchase_request_detail': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_STORE, ROLE_PURCHASE, ROLE_MANAGER],
    'purchase_request_create': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_STORE], 'purchase_request_update': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_STORE],
    'purchase_request_submit': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_STORE], 'purchase_request_approve': [ROLE_ADMIN, ROLE_HOD, ROLE_MANAGER], 'purchase_request_reject': [ROLE_ADMIN, ROLE_HOD, ROLE_MANAGER], 'purchase_request_processing': [ROLE_ADMIN, ROLE_PURCHASE],
    'purchase_order_list': [ROLE_ADMIN, ROLE_PURCHASE, ROLE_HOD, ROLE_MANAGER], 'purchase_order_create': [ROLE_ADMIN, ROLE_PURCHASE], 'purchase_order_action': [ROLE_ADMIN, ROLE_PURCHASE, ROLE_HOD, ROLE_MANAGER], 'service_entry_list': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_PURCHASE, ROLE_ACCOUNTS, ROLE_MANAGER], 'service_entry_create': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_PURCHASE], 'service_entry_action': [ROLE_ADMIN, ROLE_HOD, ROLE_MANAGER],
    'goods_receipt_list': [ROLE_ADMIN, ROLE_STORE, ROLE_PURCHASE, ROLE_HOD, ROLE_MANAGER], 'goods_receipt_create': [ROLE_ADMIN, ROLE_STORE], 'goods_receipt_post': [ROLE_ADMIN, ROLE_STORE],
    'stock_transfer_list': [ROLE_ADMIN, ROLE_STORE, ROLE_HOD, ROLE_MANAGER], 'stock_transfer_create': [ROLE_ADMIN, ROLE_STORE], 'stock_transfer_post': [ROLE_ADMIN, ROLE_STORE],
    'material_issue_list': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_STORE, ROLE_MANAGER], 'material_issue_create': [ROLE_ADMIN, ROLE_STORE], 'material_issue_post': [ROLE_ADMIN, ROLE_STORE],
    'vendor_invoice_list': [ROLE_ADMIN, ROLE_PURCHASE, ROLE_ACCOUNTS, ROLE_HOD, ROLE_MANAGER], 'vendor_invoice_create': [ROLE_ADMIN, ROLE_ACCOUNTS], 'vendor_invoice_action': [ROLE_ADMIN, ROLE_ACCOUNTS],
    'meter_list': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_MANAGER], 'meter_create': [ROLE_ADMIN, ROLE_HOD], 'meter_reading_create': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD],
    'capex_list': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_MANAGER], 'capex_create': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD], 'capex_action': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_MANAGER], 'capex_pdf': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_MANAGER],
    'disposal_list': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_MANAGER], 'disposal_create': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD], 'disposal_action': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_MANAGER], 'disposal_pdf': [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_HOD, ROLE_MANAGER],
    'audit_list': [ROLE_ADMIN, ROLE_MANAGER],
}

NAVIGATION_SECTIONS = [
    {'title': 'Main', 'items': [
        {'label': 'Dashboard', 'url_name': 'dashboard', 'icon': '⌂'},
        {'label': 'Dashboards', 'icon': '▦', 'children': [
            {'label': 'Asset Administration', 'url_name': 'asset_dashboard', 'icon': '◈'},
            {'label': 'Engineering', 'url_name': 'engineering_dashboard', 'icon': '⚙'},
            {'label': 'Maintenance Manager', 'url_name': 'maintenance_manager_dashboard', 'icon': '▦'},
            {'label': 'Materials Management', 'url_name': 'mm_dashboard', 'icon': '◫'},
            {'label': 'Engineering Store', 'url_name': 'store_dashboard', 'icon': '▤'},
            {'label': 'Utilities', 'url_name': 'utility_dashboard', 'icon': '⌁'},
        ]},
    ]},
    {'title': 'Asset Management', 'icon': '▣', 'items': [
        {'label': 'Asset Register', 'url_name': 'asset_list', 'icon': '▣'},
    ]},
    {'title': 'Maintenance', 'icon': '🔧', 'items': [
        {'label': 'Maintenance Requests', 'url_name': 'maintenance_request_list', 'icon': '⚑'},
        {'label': 'Work Orders', 'url_name': 'work_order_list', 'icon': '🔧'},
        {'label': 'Maintenance History', 'url_name': 'maintenance_history_reliability', 'icon': '▥'},
        {'label': 'Downtime', 'url_name': 'downtime_list', 'icon': '⏱'},
    ]},
    {'title': 'Preventive & Planned Maintenance', 'icon': '☑', 'items': [
        {'label': 'PM Plans', 'url_name': 'pm_plan_list', 'icon': '☑'},
        {'label': 'Scheduling Board', 'url_name': 'scheduling_board', 'icon': '▦'},
        {'label': 'Task Lists', 'url_name': 'task_list_list', 'icon': '☷'},
        {'label': 'Maintenance Strategies', 'url_name': 'maintenance_strategy_list', 'icon': '↻'},
        {'label': 'Condition Rules', 'url_name': 'condition_rule_list', 'icon': '⌁'},
        {'label': 'Shutdown Maintenance', 'url_name': 'shutdown_list', 'icon': '▥'},
    ]},
    {'title': 'Reliability', 'icon': '◉', 'items': [
        {'label': 'Failure Catalogs', 'url_name': 'maintenance_catalog_list', 'icon': '⌕'},
        {'label': 'RCA', 'url_name': 'rca_list', 'icon': '⌕'},
        {'label': 'CAPA', 'url_name': 'capa_list', 'icon': '✓'},
        {'label': 'Reliability Analysis', 'url_name': 'reliability_analysis', 'icon': '▥'},
        {'label': 'LLF / TPM', 'url_name': 'llf_list', 'icon': '◉'},
    ]},
    {'title': 'Inspection & Compliance', 'icon': '◎', 'items': [
        {'label': 'Inspection', 'url_name': 'inspection_plan_list', 'icon': '◎'},
        {'label': 'Calibration', 'url_name': 'calibration_plan_list', 'icon': '◌'},
        {'label': 'Permit to Work', 'url_name': 'permit_list', 'icon': '🛡'},
        {'label': 'MOC', 'url_name': 'moc_list', 'icon': '↻'},
    ]},
    {'title': 'Materials', 'icon': '□', 'items': [
        {'label': 'Item Master', 'url_name': 'spare_list', 'icon': '□'}, {'label': 'Purchase Requests', 'url_name': 'purchase_request_list', 'icon': '＋'},
        {'label': 'Purchase Orders', 'url_name': 'purchase_order_list', 'icon': '◫'}, {'label': 'Service Entry', 'url_name': 'service_entry_list', 'icon': '✓'}, {'label': 'MIGO / Receipt', 'url_name': 'goods_receipt_list', 'icon': '⇡'},
        {'label': 'Stock Transfer', 'url_name': 'stock_transfer_list', 'icon': '⇄'}, {'label': 'Material Issue', 'url_name': 'material_issue_list', 'icon': '⇣'},
        {'label': 'Vendor Invoices', 'url_name': 'vendor_invoice_list', 'icon': '₹'},
    ]},
    {'title': 'Utilities & Approvals', 'icon': '⌁', 'items': [
        {'label': 'Utility Meters', 'url_name': 'meter_list', 'icon': '◍'},
        {'label': 'CAPEX Proposals', 'url_name': 'capex_list', 'icon': '₹'}, {'label': 'Asset Disposal', 'url_name': 'disposal_list', 'icon': '♻'},
        {'label': 'Audit Log', 'url_name': 'audit_list', 'icon': '≡'},
    ]},
]


def user_role(user):
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        return ROLE_ADMIN
    for role in ALL_ROLES:
        if user.groups.filter(name=role).exists():
            return role
    return None


def user_role_label(user):
    return ROLE_LABELS.get(user_role(user), 'No Role Assigned')


def role_can_access(user, allowed_roles):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return not allowed_roles or user_role(user) in allowed_roles


def role_can_access_url(user, url_name):
    allowed = ROLE_URL_ACCESS.get(url_name)
    return role_can_access(user, allowed) if allowed is not None else bool(user and user.is_superuser)


def navigation_for_user(user, current_url_name=''):
    role = user_role(user)
    if role == ROLE_ASSET_ADMIN:
        return [
            {'title': 'Main', 'items': [
                {'label': 'Dashboard', 'url_name': 'dashboard', 'icon': '⌂', 'active': current_url_name == 'dashboard'},
                {'label': 'Dashboards', 'icon': '▦', 'active': current_url_name == 'asset_dashboard', 'children': [
                    {'label': 'Asset Administration', 'url_name': 'asset_dashboard', 'icon': '◈', 'active': current_url_name == 'asset_dashboard'},
                ]},
            ]},
            {'title': 'Asset Administration', 'icon': '▣', 'active': current_url_name in {
                'asset_list', 'asset_create', 'asset_import', 'asset_transfer_create',
            }, 'items': [
                {'label': 'Asset Register', 'url_name': 'asset_list', 'icon': '▣', 'active': current_url_name == 'asset_list'},
                {'label': 'Register Asset', 'url_name': 'asset_create', 'icon': '＋', 'active': current_url_name == 'asset_create'},
                {'label': 'Bulk Import', 'url_name': 'asset_import', 'icon': '⇡', 'active': current_url_name == 'asset_import'},
                {'label': 'Transfer Requests', 'url_name': 'asset_transfer_create', 'icon': '⇄', 'active': current_url_name == 'asset_transfer_create'},
            ]},
        ]
    sections = []
    for section in NAVIGATION_SECTIONS:
        items = []
        for item in section['items']:
            if item.get('children'):
                children = []
                for child in item['children']:
                    if role_can_access_url(user, child['url_name']):
                        children.append({**child, 'active': child['url_name'] == current_url_name})
                if children:
                    items.append({**item, 'children': children, 'active': any(child['active'] for child in children)})
            elif role_can_access_url(user, item['url_name']):
                items.append({**item, 'active': item['url_name'] == current_url_name})
        if items:
            sections.append({
                'title': section['title'],
                'icon': section.get('icon', ''),
                'active': any(item['active'] for item in items),
                'items': items,
            })
    return sections


class RoleRequiredMixin(LoginRequiredMixin):
    allowed_roles = None

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        url_name = request.resolver_match.url_name if request.resolver_match else ''
        allowed = ROLE_URL_ACCESS.get(url_name, self.allowed_roles or [])
        if not role_can_access(request.user, allowed):
            messages.error(request, 'Access denied for your login role.')
            if url_name == 'dashboard':
                raise PermissionDenied('Your account does not have a permitted role.')
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
