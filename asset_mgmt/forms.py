from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model

from .models import (
    Asset, AssetBOM, AssetChangeRequest, AssetConditionAssessment, AssetCriticalityAssessment, AssetDisposalRequest, AssetDocument, AssetImage, AssetMeter, AssetMeterReading, AssetTransferRequest, AssetDowntimeEvent, CalibrationPlan, CalibrationRecord,
    CAPAAction, CAPEXProposal, FishboneCause, FunctionalLocation, GoodsReceipt,
    Department, CostCentre, InspectionPlan, InspectionRecord, LLFObservation, MaintenanceRequest, MaintenanceRequestItem, MaintenanceCatalogCode, MaterialIssue, MeterReading,
    ModificationOrder, PermitToWork, PMPlan, PMTask, PMPlanCounter, PurchaseOrder, PurchaseRequest,
    RCARecord, ShutdownJob, ShutdownPlan, SparePart, StockTransfer, StoreLocation,
    UtilityMeter, VendorInvoice, WorkCentre, WorkOrder, WorkOrderOperation, WorkOrderLabour, WorkOrderSpare, RiskAssessment,
    WorkOrderConfirmation, MaintenanceTaskList, MaintenanceTaskListOperation, MaintenanceTaskListMaterial,
    MaintenanceStrategy, MaintenanceStrategyPackage, PMPlanStrategyPackage, ConditionRule, SettlementRule, ServiceEntrySheet,
)
from .permissions import user_plant_ids

User = get_user_model()


class SecureBootstrapFormMixin:
    """Bootstrap styling, upload size validation and user-scoped foreign keys."""
    MAX_UPLOAD_SIZE = 10 * 1024 * 1024

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class', 'form-check-input')
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault('class', 'form-select')
            else:
                field.widget.attrs.setdefault('class', 'form-control')
        self._scope_foreign_keys()

    def _scope_foreign_keys(self):
        if not self.user:
            return
        plant_ids = user_plant_ids(self.user)
        if plant_ids is None:
            return
        for name, field in self.fields.items():
            if not isinstance(field, forms.ModelChoiceField):
                continue
            model = field.queryset.model
            field_names = {f.name for f in model._meta.get_fields()}
            if model.__name__ == 'User':
                field.queryset = field.queryset.filter(plant_assignments__plant_id__in=plant_ids, plant_assignments__active=True).distinct()
            elif model.__name__ == 'Plant':
                field.queryset = field.queryset.filter(id__in=plant_ids)
            elif 'plant' in field_names:
                field.queryset = field.queryset.filter(plant_id__in=plant_ids)
            elif model.__name__ == 'FunctionalLocation':
                field.queryset = field.queryset.filter(plant_id__in=plant_ids)
            elif model.__name__ == 'Asset':
                field.queryset = field.queryset.filter(plant_id__in=plant_ids)
            elif 'asset' in field_names:
                field.queryset = field.queryset.filter(asset__plant_id__in=plant_ids)
            elif 'task_list' in field_names:
                field.queryset = field.queryset.filter(task_list__plant_id__in=plant_ids)
            elif 'strategy' in field_names:
                field.queryset = field.queryset.filter(strategy__plant_id__in=plant_ids)
            elif 'work_order' in field_names:
                field.queryset = field.queryset.filter(work_order__plant_id__in=plant_ids)
            elif model.__name__ == 'WorkOrder':
                field.queryset = field.queryset.filter(plant_id__in=plant_ids)
            elif model.__name__ == 'PMPlan':
                field.queryset = field.queryset.filter(plant_id__in=plant_ids)
            elif model.__name__ == 'PurchaseRequest':
                field.queryset = field.queryset.filter(plant_id__in=plant_ids)

    def clean(self):
        cleaned = super().clean()
        for name, file in self.files.items():
            if file.size > self.MAX_UPLOAD_SIZE:
                self.add_error(name, 'File size must not exceed 10 MB.')
        return cleaned


class AssetForm(SecureBootstrapFormMixin, forms.ModelForm):
    """Asset Master form aligned to the PDF: grouped in the template, with controlled fields and validation."""
    class Meta:
        model = Asset
        fields = [
            'plant', 'department', 'area', 'functional_location', 'cost_centre', 'business_unit', 'profit_centre',
            'asset_type', 'tag_number', 'name', 'asset_description', 'category', 'subcategory', 'asset_class',
            'parent_asset', 'equipment_position', 'component_type', 'installed_under_parent_on',
            'asset_owner', 'responsible_department', 'maintenance_department', 'user_department', 'responsible_engineer',
            'maintenance_planner', 'custodian', 'escalation_manager',
            'manufacturer', 'model_number', 'serial_number', 'manufacturer_part_number', 'capacity_rating',
            'material_of_construction', 'equipment_rating', 'design_pressure', 'operating_pressure',
            'design_temperature', 'operating_temperature', 'power_rating', 'voltage', 'current', 'speed', 'weight',
            'dimensions', 'protection_class', 'hazardous_area_classification', 'installation_specification',
            'drawing_number', 'datasheet_number',
            'purchase_date', 'purchase_order_reference', 'purchase_request_reference', 'vendor', 'purchase_cost',
            'installation_cost', 'replacement_cost', 'currency', 'capitalisation_date', 'asset_accounting_number',
            'depreciation_method', 'useful_life_years', 'residual_value', 'current_book_value', 'insurance_policy',
            'insurance_expiry_date',
            'commissioning_date', 'decommissioning_date', 'disposal_date', 'lifecycle_status', 'status',
            'status_effective_date', 'status_reason',
            'criticality', 'criticality_score', 'safety_critical', 'safety_function', 'regulatory_requirement',
            'statutory_inspection_required', 'inspection_authority', 'certificate_number', 'certificate_expiry',
            'permit_requirement', 'loto_requirement', 'risk_assessment_required',
            'current_condition', 'condition_score', 'condition_assessment_date', 'condition_remarks', 'recommended_action',
            'next_condition_assessment_date',
            'warranty_start_date', 'warranty_end_date', 'warranty_provider', 'warranty_type', 'warranty_terms',
            'warranty_contact', 'warranty_claim_reference', 'contract_type', 'service_provider', 'contract_number',
            'contract_start_date', 'contract_end_date', 'contract_value', 'included_services', 'excluded_services',
            'response_time', 'visit_frequency', 'service_contact_person', 'renewal_reminder_date',
            'meter_enabled', 'default_meter_type', 'default_meter_unit', 'current_meter_reading', 'initial_meter_reading',
            'reading_frequency', 'meter_rollover_value', 'iot_enabled',
            'scheduled_hours_per_day', 'availability_target', 'qr_active', 'image', 'remarks',
        ]
        widgets = {
            'asset_description': forms.Textarea(attrs={'rows': 3}),
            'installation_specification': forms.Textarea(attrs={'rows': 3}),
            'status_reason': forms.Textarea(attrs={'rows': 2}),
            'safety_function': forms.Textarea(attrs={'rows': 2}),
            'regulatory_requirement': forms.Textarea(attrs={'rows': 2}),
            'condition_remarks': forms.Textarea(attrs={'rows': 2}),
            'recommended_action': forms.Textarea(attrs={'rows': 2}),
            'warranty_terms': forms.Textarea(attrs={'rows': 3}),
            'included_services': forms.Textarea(attrs={'rows': 2}),
            'excluded_services': forms.Textarea(attrs={'rows': 2}),
            'remarks': forms.Textarea(attrs={'rows': 3}),
        }

    DATE_FIELDS = [
        'installed_under_parent_on', 'purchase_date', 'capitalisation_date', 'insurance_expiry_date',
        'commissioning_date', 'decommissioning_date', 'disposal_date', 'status_effective_date',
        'condition_assessment_date', 'next_condition_assessment_date', 'warranty_start_date', 'warranty_end_date',
        'certificate_expiry', 'contract_start_date', 'contract_end_date', 'renewal_reminder_date',
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in self.DATE_FIELDS:
            if name in self.fields:
                self.fields[name].widget = forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
        if self.instance and self.instance.pk and not (self.user and (self.user.is_superuser or self.user.groups.filter(name__in=['Admin', 'HOD', 'Manager']).exists())):
            # Normal engineers should request approval for controlled master changes instead of editing them directly.
            for field in ['plant', 'area', 'functional_location', 'parent_asset', 'category', 'subcategory', 'asset_type', 'tag_number', 'lifecycle_status', 'criticality', 'criticality_score', 'safety_critical', 'purchase_cost']:
                if field in self.fields:
                    self.fields[field].disabled = True

    def clean(self):
        cleaned = super().clean()
        plant = cleaned.get('plant')
        location = cleaned.get('functional_location')
        area = cleaned.get('area')
        category = cleaned.get('category')
        subcategory = cleaned.get('subcategory')
        if plant and location and location.plant_id != plant.id:
            self.add_error('functional_location', 'Functional location must belong to the selected plant.')
        if plant and area and area.plant_id != plant.id:
            self.add_error('area', 'Area must belong to the selected plant.')
        if category and subcategory and subcategory.category_id != category.id:
            self.add_error('subcategory', 'Subcategory must belong to the selected category.')
        return cleaned


class AssetDocumentForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AssetDocument
        fields = ['asset', 'document_number', 'title', 'document_type', 'revision', 'effective_date', 'expiry_date', 'document_owner', 'status', 'file', 'superseded_document', 'notes']
        widgets = {
            'effective_date': forms.DateInput(attrs={'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class AssetImageForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AssetImage
        fields = ['asset', 'image', 'image_type', 'caption', 'primary']


class AssetStatusChangeForm(forms.Form):
    lifecycle_status = forms.ChoiceField(choices=Asset.LIFECYCLE_STATUS_CHOICES, required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    operational_status = forms.ChoiceField(choices=Asset.OPERATIONAL_STATUS_CHOICES, required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    effective_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    reason = forms.CharField(widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}), min_length=5)


class AssetMeterForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AssetMeter
        fields = ['asset', 'meter_type', 'unit', 'initial_reading', 'current_reading', 'reading_frequency', 'rollover_value', 'iot_enabled', 'active']


class AssetMeterReadingForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AssetMeterReading
        fields = ['meter', 'reading', 'reading_date', 'reading_source', 'photograph', 'correction_reason', 'remarks']
        widgets = {'reading_date': forms.DateInput(attrs={'type': 'date'}), 'correction_reason': forms.Textarea(attrs={'rows': 2}), 'remarks': forms.Textarea(attrs={'rows': 2})}


class AssetTransferRequestForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AssetTransferRequest
        fields = ['asset', 'transfer_type', 'destination_plant', 'destination_location', 'destination_department', 'destination_parent', 'transfer_date', 'reason', 'remarks']
        widgets = {'transfer_date': forms.DateInput(attrs={'type': 'date'}), 'reason': forms.Textarea(attrs={'rows': 3}), 'remarks': forms.Textarea(attrs={'rows': 2})}


class AssetChangeRequestForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AssetChangeRequest
        fields = ['asset', 'requested_change', 'current_value', 'proposed_value', 'reason', 'effective_date', 'remarks']
        widgets = {'effective_date': forms.DateInput(attrs={'type': 'date'}), 'current_value': forms.Textarea(attrs={'rows': 2}), 'proposed_value': forms.Textarea(attrs={'rows': 2}), 'reason': forms.Textarea(attrs={'rows': 3}), 'remarks': forms.Textarea(attrs={'rows': 2})}


class AssetConditionAssessmentForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AssetConditionAssessment
        fields = ['asset', 'assessment_date', 'condition', 'score', 'findings', 'recommendation', 'next_assessment_date', 'image']
        widgets = {'assessment_date': forms.DateInput(attrs={'type': 'date'}), 'next_assessment_date': forms.DateInput(attrs={'type': 'date'}), 'findings': forms.Textarea(attrs={'rows': 3}), 'recommendation': forms.Textarea(attrs={'rows': 2})}


class AssetCriticalityAssessmentForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AssetCriticalityAssessment
        fields = ['asset', 'assessment_date', 'next_review_date', 'remarks']
        widgets = {'assessment_date': forms.DateInput(attrs={'type': 'date'}), 'next_review_date': forms.DateInput(attrs={'type': 'date'}), 'remarks': forms.Textarea(attrs={'rows': 3})}


class AssetBOMForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AssetBOM
        fields = ['asset', 'spare_part', 'quantity', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 2})}


class AssetImportForm(forms.Form):
    csv_file = forms.FileField(help_text='Upload the provided CSV/Excel template. Maximum 10 MB.')
    validate_only = forms.BooleanField(required=False, initial=True, help_text='Validate first without saving records.')

    def clean_csv_file(self):
        file = self.cleaned_data['csv_file']
        if file.size > 10 * 1024 * 1024:
            raise forms.ValidationError('Import file must not exceed 10 MB.')
        if not file.name.lower().endswith(('.csv', '.xlsx')):
            raise forms.ValidationError('Only CSV or XLSX files are accepted for secure bulk import.')
        return file


class WorkCentreCapacityForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = WorkCentre
        fields = ['capacity_hours_per_day', 'default_crew_size', 'active']


class MaintenanceRequestForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = MaintenanceRequest
        fields = ['plant', 'asset', 'work_centre', 'reported_department', 'problem_description', 'priority', 'failure_mode', 'safety_issue', 'leakage', 'production_stopped', 'attachment']
        widgets = {'problem_description': forms.Textarea(attrs={'rows': 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Do not expose assets or work centres from every permitted plant before
        # the user chooses a plant. Bound forms and edit forms retain the choices
        # belonging to their submitted/stored plant so validation still works
        # without relying on JavaScript.
        selected_plant_id = None
        if self.is_bound:
            selected_plant_id = self.data.get(self.add_prefix('plant'))
        elif self.initial.get('plant'):
            selected_plant = self.initial['plant']
            selected_plant_id = getattr(selected_plant, 'pk', selected_plant)
        elif self.instance and self.instance.pk:
            selected_plant_id = self.instance.plant_id

        for field_name in ['asset', 'work_centre']:
            queryset = self.fields[field_name].queryset
            try:
                self.fields[field_name].queryset = queryset.filter(plant_id=int(selected_plant_id))
            except (TypeError, ValueError):
                self.fields[field_name].queryset = queryset.none()


class MaintenanceRequestItemForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = MaintenanceRequestItem
        fields = ['sequence', 'object_part', 'damage_code', 'cause_code', 'activity_code', 'description', 'findings']
        widgets = {'description': forms.Textarea(attrs={'rows': 2}), 'findings': forms.Textarea(attrs={'rows': 2})}


class MaintenanceCatalogCodeForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = MaintenanceCatalogCode
        fields = ['plant', 'catalog_type', 'code_group', 'code', 'description', 'active']


class WorkOrderForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = WorkOrder
        fields = [
            'asset', 'work_centre', 'maintenance_request', 'pm_plan', 'shutdown_plan', 'assigned_to', 'supervisor',
            'work_type', 'activity_type', 'shift', 'priority', 'job_description', 'checklist', 'required_tools', 'risk_summary',
            'planned_start', 'planned_end', 'permit_required', 'loto_required', 'estimated_cost',
            'external_service_cost', 'other_cost', 'failure_mode', 'failure_cause', 'failure_action', 'completion_notes',
        ]
        widgets = {
            'planned_start': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'planned_end': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'job_description': forms.Textarea(attrs={'rows': 4}),
            'checklist': forms.Textarea(attrs={'rows': 5}),
            'required_tools': forms.Textarea(attrs={'rows': 3}),
            'risk_summary': forms.Textarea(attrs={'rows': 3}),
            'failure_cause': forms.Textarea(attrs={'rows': 3}),
            'failure_action': forms.Textarea(attrs={'rows': 3}),
            'completion_notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Status is intentionally not editable here. The controlled workflow actions own every status transition.
        if 'maintenance_request' in self.fields:
            self.fields['maintenance_request'].queryset = self.fields['maintenance_request'].queryset.filter(status__in=['ACCEPTED', 'WO_CREATED'])


class WorkOrderOperationForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = WorkOrderOperation
        fields = ['sequence', 'description', 'work_centre', 'assigned_to', 'parent_operation', 'predecessor', 'execution_stage', 'execution_type', 'control_key', 'persons_required', 'planned_hours', 'scheduled_start', 'scheduled_end', 'vendor', 'service_item', 'external_service_description', 'notes']
        widgets = {'description': forms.Textarea(attrs={'rows': 3}), 'scheduled_start': forms.DateTimeInput(attrs={'type':'datetime-local'}), 'scheduled_end': forms.DateTimeInput(attrs={'type':'datetime-local'}), 'external_service_description': forms.Textarea(attrs={'rows':2}), 'notes': forms.Textarea(attrs={'rows': 2})}


class WorkOrderSpareForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = WorkOrderSpare
        fields = ['operation', 'spare_part', 'procurement_type', 'quantity_required', 'remarks']


class WorkOrderLabourForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = WorkOrderLabour
        fields = ['person', 'role', 'started_at', 'ended_at', 'hours', 'hourly_rate', 'remarks']
        widgets = {
            'started_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'ended_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }


class WorkOrderConfirmationForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = WorkOrderConfirmation
        fields = ['operation', 'person', 'confirmation_type', 'started_at', 'ended_at', 'remaining_work_hours', 'confirmation_text']
        widgets = {
            'started_at': forms.DateTimeInput(attrs={'type':'datetime-local'}),
            'ended_at': forms.DateTimeInput(attrs={'type':'datetime-local'}),
            'confirmation_text': forms.Textarea(attrs={'rows':3}),
        }


class SettlementRuleForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = SettlementRule
        fields = ['receiver_type', 'receiver_reference', 'percentage']


class RiskAssessmentForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = RiskAssessment
        fields = ['activity', 'hazard', 'consequence', 'existing_control', 'likelihood', 'severity', 'additional_control']
        widgets = {
            'hazard': forms.Textarea(attrs={'rows': 2}), 'consequence': forms.Textarea(attrs={'rows': 2}),
            'existing_control': forms.Textarea(attrs={'rows': 2}), 'additional_control': forms.Textarea(attrs={'rows': 2}),
        }


class DowntimeForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AssetDowntimeEvent
        fields = ['asset', 'work_order', 'downtime_type', 'started_at', 'ended_at', 'reason', 'production_impact']
        widgets = {'started_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}), 'ended_at': forms.DateTimeInput(attrs={'type': 'datetime-local'})}


class PMPlanForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PMPlan
        fields = ['asset', 'work_centre', 'responsible_user', 'name', 'frequency_value', 'frequency_unit', 'scheduling_mode', 'task_list', 'strategy', 'counter_meter', 'counter_interval', 'last_counter_reading', 'next_counter_due', 'call_horizon_percent', 'estimated_duration_hours', 'permit_required', 'next_due_date', 'last_completed_date', 'auto_generate_work_order', 'active']
        widgets = {'next_due_date': forms.DateInput(attrs={'type': 'date'}), 'last_completed_date': forms.DateInput(attrs={'type': 'date'})}


class PMPlanCounterForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PMPlanCounter
        fields = ['pm_plan', 'meter', 'interval', 'last_completed_reading', 'next_due_reading', 'active']


class MaintenanceTaskListForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = MaintenanceTaskList
        fields = ['plant', 'code', 'name', 'list_type', 'asset', 'functional_location', 'strategy', 'revision', 'active']


class MaintenanceTaskListOperationForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = MaintenanceTaskListOperation
        fields = ['task_list', 'sequence', 'description', 'work_centre', 'execution_stage', 'execution_type', 'planned_hours', 'persons_required', 'required_tools', 'safety_instruction', 'strategy_package', 'vendor', 'service_item', 'external_service_description']
        widgets = {'description': forms.Textarea(attrs={'rows':3}), 'required_tools': forms.Textarea(attrs={'rows':2}), 'safety_instruction': forms.Textarea(attrs={'rows':2}), 'external_service_description': forms.Textarea(attrs={'rows':2})}


class MaintenanceTaskListMaterialForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = MaintenanceTaskListMaterial
        fields = ['task_operation', 'spare_part', 'quantity']


class MaintenanceStrategyForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = MaintenanceStrategy
        fields = ['plant', 'name', 'description', 'active']


class MaintenanceStrategyPackageForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = MaintenanceStrategyPackage
        fields = ['strategy', 'name', 'cycle_value', 'cycle_unit', 'hierarchy']


class ConditionRuleForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ConditionRule
        fields = ['meter', 'name', 'operator', 'threshold', 'priority', 'work_centre', 'auto_create_notification', 'active']


class PMPlanStrategyPackageForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PMPlanStrategyPackage
        fields = ['pm_plan', 'package', 'next_due_date', 'next_due_reading', 'last_completed_date', 'active']
        widgets = {'next_due_date': forms.DateInput(attrs={'type':'date'}), 'last_completed_date': forms.DateInput(attrs={'type':'date'})}


class PMTaskForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PMTask
        fields = ['pm_plan', 'sequence', 'task', 'safety_instruction', 'required_tools', 'expected_result', 'mandatory']
        widgets = {'task': forms.Textarea(attrs={'rows': 3}), 'safety_instruction': forms.Textarea(attrs={'rows': 3})}


class ShutdownPlanForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ShutdownPlan
        fields = ['plant', 'title', 'start_date', 'end_date', 'scope', 'coordinator', 'status', 'remarks']
        widgets = {'start_date': forms.DateInput(attrs={'type': 'date'}), 'end_date': forms.DateInput(attrs={'type': 'date'}), 'scope': forms.Textarea(attrs={'rows': 4})}


class ShutdownJobForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ShutdownJob
        fields = ['shutdown_plan', 'asset', 'work_centre', 'description', 'planned_start', 'planned_end', 'status', 'progress_percent', 'delay_reason']
        widgets = {'planned_start': forms.DateTimeInput(attrs={'type': 'datetime-local'}), 'planned_end': forms.DateTimeInput(attrs={'type': 'datetime-local'}), 'description': forms.Textarea(attrs={'rows': 3})}


class InspectionPlanForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = InspectionPlan
        fields = ['asset', 'assigned_to', 'statutory_equipment', 'statutory_form', 'inspection_type', 'standard_reference', 'frequency_months', 'checklist', 'next_due_date', 'active']
        widgets = {'next_due_date': forms.DateInput(attrs={'type': 'date'}), 'checklist': forms.Textarea(attrs={'rows': 4})}


class InspectionRecordForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = InspectionRecord
        fields = ['plan', 'inspected_on', 'inspector_name', 'result', 'thickness_reading', 'corrosion_observation', 'recommendation', 'certificate', 'next_inspection_date']
        widgets = {
            'inspected_on': forms.DateInput(attrs={'type': 'date'}), 'next_inspection_date': forms.DateInput(attrs={'type': 'date'}),
            'corrosion_observation': forms.Textarea(attrs={'rows': 3}), 'recommendation': forms.Textarea(attrs={'rows': 3}),
        }


class CalibrationPlanForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = CalibrationPlan
        fields = ['asset', 'assigned_to', 'permit_required', 'instrument_range', 'accuracy', 'frequency_months', 'next_due_date', 'active']
        widgets = {'next_due_date': forms.DateInput(attrs={'type': 'date'})}


class CalibrationRecordForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = CalibrationRecord
        fields = ['plan', 'calibrated_on', 'calibrated_by', 'standard_instrument', 'before_reading', 'after_reading', 'error_observed', 'result', 'certificate', 'next_calibration_date']
        widgets = {
            'calibrated_on': forms.DateInput(attrs={'type': 'date'}), 'next_calibration_date': forms.DateInput(attrs={'type': 'date'}),
            'before_reading': forms.Textarea(attrs={'rows': 2}), 'after_reading': forms.Textarea(attrs={'rows': 2}),
        }


class PermitToWorkForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PermitToWork
        fields = ['permit_no', 'work_order', 'permit_type', 'permit_date', 'start_time', 'end_time', 'hazards', 'ppe_required', 'isolation_done', 'gas_test_required', 'gas_test_result', 'loto_applied', 'fire_extinguisher_available', 'area_barricaded', 'valid_from', 'valid_to', 'closure_notes']
        widgets = {'permit_date': forms.DateInput(attrs={'type': 'date'}), 'start_time': forms.TimeInput(attrs={'type': 'time'}), 'end_time': forms.TimeInput(attrs={'type': 'time'}), 'valid_from': forms.DateTimeInput(attrs={'type': 'datetime-local'}), 'valid_to': forms.DateTimeInput(attrs={'type': 'datetime-local'})}


class RCAForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = RCARecord
        fields = ['work_order', 'method', 'failure_mode', 'event_description', 'why_1', 'why_2', 'why_3', 'why_4', 'why_5', 'root_cause', 'responsible_person', 'target_date', 'closed']
        widgets = {name: forms.Textarea(attrs={'rows': 2}) for name in ['event_description', 'why_1', 'why_2', 'why_3', 'why_4', 'why_5', 'root_cause']}


class FishboneCauseForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = FishboneCause
        fields = ['rca', 'category', 'cause', 'verified']
        widgets = {'cause': forms.Textarea(attrs={'rows': 3})}


class CAPAForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = CAPAAction
        fields = ['rca', 'action_type', 'description', 'owner', 'due_date', 'severity', 'probability', 'detectability', 'status', 'completion_evidence', 'effectiveness_review', 'verified_by']
        widgets = {'due_date': forms.DateInput(attrs={'type': 'date'}), 'description': forms.Textarea(attrs={'rows': 3}), 'effectiveness_review': forms.Textarea(attrs={'rows': 3})}


class LLFForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = LLFObservation
        fields = ['asset', 'observed_at', 'sense', 'observation', 'severity', 'photo', 'assigned_work_centre']
        widgets = {'observed_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}), 'observation': forms.Textarea(attrs={'rows': 4})}


class ModificationOrderForm(SecureBootstrapFormMixin, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assigned_approver'].queryset = self.fields['assigned_approver'].queryset.filter(
            plant_assignments__designation__in=['HOD', 'PLANT_HEAD'], plant_assignments__active=True
        ).distinct()

    class Meta:
        model = ModificationOrder
        fields = ['asset', 'work_centre', 'assigned_approver', 'requested_date', 'change_type', 'title', 'current_condition', 'proposed_change', 'reason', 'safety_impact', 'quality_impact', 'environment_impact', 'production_impact', 'risk_assessment', 'implementation_plan', 'rollback_plan', 'validation_plan', 'attachment']
        widgets = {'requested_date': forms.DateInput(attrs={'type': 'date'})}


class SparePartForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = SparePart
        fields = ['plant', 'part_code', 'item_no', 'name', 'item_description', 'item_category', 'item_class', 'unit', 'minimum_stock', 'maximum_stock', 'item_rate', 'tax_code', 'preferred_vendor', 'active']
        widgets = {'item_description': forms.Textarea(attrs={'rows': 3})}


class PurchaseRequestForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PurchaseRequest
        fields = ['plant', 'work_centre', 'work_order', 'item', 'request_date', 'quantity', 'required_date', 'purpose', 'remarks']
        widgets = {'request_date': forms.DateInput(attrs={'type': 'date'}), 'required_date': forms.DateInput(attrs={'type': 'date'}), 'purpose': forms.Textarea(attrs={'rows': 3}), 'remarks': forms.Textarea(attrs={'rows': 2})}


class ApprovalRemarksForm(forms.Form):
    remarks = forms.CharField(widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}), min_length=3)


class RejectionForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}), min_length=5)


class PurchaseOrderForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ['purchase_request', 'vendor', 'order_date', 'quantity', 'unit_rate', 'description', 'remarks']
        widgets = {'order_date': forms.DateInput(attrs={'type': 'date'}), 'description': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['purchase_request'].queryset = self.fields['purchase_request'].queryset.filter(status__in=['APPROVED', 'PROCESSING'])

    def clean(self):
        cleaned = super().clean()
        pr = cleaned.get('purchase_request')
        if pr:
            # Derive system-controlled fields before ModelForm calls model.clean().
            self.instance.purchase_request = pr
            self.instance.plant = pr.plant
            self.instance.item = pr.item
            is_external_service = bool(
                pr.source_operation_id and pr.source_operation.execution_type == 'EXTERNAL'
                and pr.source_operation.service_item_id == pr.item_id
            )
            self.instance.po_type = 'SERVICE' if pr.item.procurement_type == 'SERVICE' or is_external_service else 'MATERIAL'
            self.instance.status = 'DRAFT'
        return cleaned


class GoodsReceiptForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = GoodsReceipt
        fields = ['purchase_order', 'received_date', 'quantity_received', 'received_location', 'migo_reference', 'remarks']
        widgets = {'received_date': forms.DateInput(attrs={'type': 'date'})}

    def clean(self):
        cleaned = super().clean()
        po = cleaned.get('purchase_order')
        if po:
            self.instance.purchase_order = po
            self.instance.plant = po.plant
            self.instance.item = po.item
        return cleaned


class StockTransferForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = StockTransfer
        fields = ['plant', 'item', 'transfer_date', 'from_location', 'to_location', 'quantity', 'remarks']
        widgets = {'transfer_date': forms.DateInput(attrs={'type': 'date'})}


class MaterialIssueForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = MaterialIssue
        fields = ['plant', 'item', 'work_order', 'operation', 'source_location', 'issue_date', 'quantity_issued', 'issued_to', 'remarks']
        widgets = {'issue_date': forms.DateInput(attrs={'type': 'date'})}


class ServiceEntrySheetForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ServiceEntrySheet
        fields = ['purchase_order', 'work_order_operation', 'service_date', 'description', 'quantity', 'amount']
        widgets = {'service_date': forms.DateInput(attrs={'type':'date'}), 'description': forms.Textarea(attrs={'rows':3})}


class VendorInvoiceForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = VendorInvoice
        fields = ['invoice_no', 'purchase_order', 'goods_receipt', 'invoice_date', 'amount']
        widgets = {'invoice_date': forms.DateInput(attrs={'type': 'date'})}


class UtilityMeterForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = UtilityMeter
        fields = ['plant', 'meter_code', 'name', 'utility_type', 'unit', 'location', 'target_per_day', 'active']


class MeterReadingForm(SecureBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = MeterReading
        fields = ['meter', 'reading_date', 'opening_reading', 'closing_reading', 'multiplier', 'remarks']
        widgets = {'reading_date': forms.DateInput(attrs={'type': 'date'})}


class CAPEXProposalForm(SecureBootstrapFormMixin, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assigned_approver'].queryset = self.fields['assigned_approver'].queryset.filter(
            plant_assignments__designation__in=['HOD', 'PLANT_HEAD'], plant_assignments__active=True
        ).distinct()

    class Meta:
        model = CAPEXProposal
        fields = ['plant', 'work_centre', 'budget_year', 'cost_centre', 'title', 'justification', 'business_benefit', 'amount', 'assigned_approver', 'attachment']
        widgets = {'justification': forms.Textarea(attrs={'rows': 4}), 'business_benefit': forms.Textarea(attrs={'rows': 3})}


class AssetDisposalForm(SecureBootstrapFormMixin, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assigned_approver'].queryset = self.fields['assigned_approver'].queryset.filter(
            plant_assignments__designation__in=['HOD', 'PLANT_HEAD'], plant_assignments__active=True
        ).distinct()

    class Meta:
        model = AssetDisposalRequest
        fields = ['asset', 'condition', 'reason', 'estimated_value', 'disposal_method', 'assigned_approver', 'evidence']
        widgets = {'condition': forms.Textarea(attrs={'rows': 3}), 'reason': forms.Textarea(attrs={'rows': 3})}
