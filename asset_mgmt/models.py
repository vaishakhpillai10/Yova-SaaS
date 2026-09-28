from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone


POSITIVE_DECIMAL = [MinValueValidator(Decimal('0.01'))]
NON_NEGATIVE_DECIMAL = [MinValueValidator(Decimal('0.00'))]
DOCUMENT_VALIDATORS = [FileExtensionValidator(['pdf', 'doc', 'docx', 'xls', 'xlsx', 'csv', 'jpg', 'jpeg', 'png'])]
IMAGE_VALIDATORS = [FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp'])]


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Company(TimeStampedModel):
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=20, unique=True)

    class Meta:
        verbose_name_plural = 'Companies'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'


class Plant(TimeStampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name='plants')
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=30)
    address = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['company__code', 'code']
        constraints = [
            models.UniqueConstraint(fields=['company', 'code'], name='uniq_company_plant_code'),
        ]

    def __str__(self):
        return f'{self.company.code}/{self.code} - {self.name}'


class WorkCentre(TimeStampedModel):
    DISCIPLINE_CHOICES = [
        ('MECHANICAL', 'Mechanical'),
        ('ELECTRICAL', 'Electrical'),
        ('INSTRUMENT', 'Instrument'),
        ('CIVIL', 'Civil'),
        ('UTILITY', 'Utility'),
        ('IT', 'IT'),
        ('SAFETY', 'Safety'),
        ('MM', 'Materials Management'),
        ('STORE', 'Engineering Store'),
        ('PRODUCTION', 'Production'),
        ('OTHER', 'Other'),
    ]
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name='work_centres')
    code = models.CharField(max_length=30)
    name = models.CharField(max_length=120)
    discipline = models.CharField(max_length=30, choices=DISCIPLINE_CHOICES)
    capacity_hours_per_day = models.DecimalField(max_digits=8, decimal_places=2, default=8, validators=POSITIVE_DECIMAL)
    default_crew_size = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['plant__code', 'code']
        constraints = [
            models.UniqueConstraint(fields=['plant', 'code'], name='uniq_plant_workcentre_code'),
        ]

    def __str__(self):
        return f'{self.plant.code}/{self.code} - {self.name}'


class UserAssignment(TimeStampedModel):
    DESIGNATION_CHOICES = [
        ('ENGINEER', 'Engineer'),
        ('SENIOR_ENGINEER', 'Senior Engineer'),
        ('HOD', 'Head of Department'),
        ('PLANT_HEAD', 'Plant Head'),
        ('STORE_USER', 'Store User'),
        ('PURCHASE_USER', 'Purchase User'),
        ('ACCOUNTS_USER', 'Accounts User'),
        ('SAFETY_USER', 'Safety User'),
        ('PRODUCTION_USER', 'Production User'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='plant_assignments')
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name='user_assignments')
    work_centre = models.ForeignKey(WorkCentre, on_delete=models.PROTECT, null=True, blank=True, related_name='user_assignments')
    designation = models.CharField(max_length=30, choices=DESIGNATION_CHOICES)
    reporting_hod = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reporting_users',
    )
    is_primary = models.BooleanField(default=False)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['user__username', 'plant__code']
        constraints = [
            models.UniqueConstraint(fields=['user', 'plant', 'work_centre'], name='uniq_user_plant_workcentre'),
        ]

    def clean(self):
        if self.work_centre and self.work_centre.plant_id != self.plant_id:
            raise ValidationError({'work_centre': 'The work centre must belong to the selected plant.'})
        if self.reporting_hod_id == self.user_id:
            raise ValidationError({'reporting_hod': 'A user cannot report to themselves.'})

    def __str__(self):
        centre = self.work_centre.code if self.work_centre else 'ALL'
        return f'{self.user.username} - {self.plant.code}/{centre} ({self.get_designation_display()})'


class DocumentSequence(models.Model):
    DOCUMENT_TYPES = [
        ('ASSET', 'Asset'), ('MR', 'Maintenance Request'), ('WO', 'Work Order'),
        ('PR', 'Purchase Request'), ('PO', 'Purchase Order'), ('GRN', 'Goods Receipt'),
        ('TRANSFER', 'Stock Transfer'), ('ISSUE', 'Material Issue'), ('MOC', 'Management of Change'),
        ('SHUTDOWN', 'Shutdown Plan'), ('CAPEX', 'CAPEX Proposal'), ('DISPOSAL', 'Asset Disposal'),
        ('LLF', 'LLF Observation'), ('RCA', 'RCA'),
    ]
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, null=True, blank=True, related_name='document_sequences')
    year = models.PositiveIntegerField()
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['document_type', 'plant', 'year'], name='uniq_document_sequence'),
        ]



class Department(TimeStampedModel):
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name='departments')
    code = models.CharField(max_length=30)
    name = models.CharField(max_length=150)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['plant__code', 'code']
        constraints = [models.UniqueConstraint(fields=['plant', 'code'], name='uniq_plant_department_code')]

    def __str__(self):
        return f'{self.plant.code}/{self.code} - {self.name}'


class CostCentre(TimeStampedModel):
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name='cost_centres')
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=150)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['plant__code', 'code']
        constraints = [models.UniqueConstraint(fields=['plant', 'code'], name='uniq_plant_costcentre_code')]

    def __str__(self):
        return f'{self.plant.code}/{self.code} - {self.name}'


class Area(TimeStampedModel):
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name='areas')
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=30)

    class Meta:
        ordering = ['plant__code', 'code']
        constraints = [models.UniqueConstraint(fields=['plant', 'code'], name='uniq_plant_area_code')]

    def __str__(self):
        return f'{self.plant.code}/{self.code} - {self.name}'


class FunctionalLocation(TimeStampedModel):
    DIRECTION_CHOICES = [
        ('N', 'North'), ('S', 'South'), ('E', 'East'), ('W', 'West'),
        ('NE', 'North-East'), ('NW', 'North-West'), ('SE', 'South-East'), ('SW', 'South-West'),
        ('C', 'Central'),
    ]
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name='functional_locations')
    area = models.ForeignKey(Area, on_delete=models.PROTECT, related_name='functional_locations')
    parent = models.ForeignKey('self', on_delete=models.PROTECT, null=True, blank=True, related_name='children')
    code = models.CharField(max_length=120, unique=True, blank=True)
    name = models.CharField(max_length=180)
    floor = models.CharField(max_length=20, blank=True, help_text='Example: F01, GF, B1')
    cardinal_direction = models.CharField(max_length=3, choices=DIRECTION_CHOICES, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['code']

    def clean(self):
        if self.area_id and self.area.plant_id != self.plant_id:
            raise ValidationError({'area': 'The area must belong to the selected plant.'})
        if self.parent_id and self.parent.plant_id != self.plant_id:
            raise ValidationError({'parent': 'The parent location must belong to the selected plant.'})

    def save(self, *args, **kwargs):
        if self.area_id:
            self.plant = self.area.plant
        if not self.code:
            name_token = ''.join(ch for ch in self.name.upper() if ch.isalnum())[:12] or 'LOC'
            floor = (self.floor or 'NA').upper()
            direction = self.cardinal_direction or 'C'
            self.code = f'{self.plant.company.code}-{self.plant.code}-{self.area.code}-{floor}-{direction}-{name_token}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.code} - {self.name}'


class AssetCategory(TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=30, unique=True, blank=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey('self', on_delete=models.PROTECT, null=True, blank=True, related_name='children')
    asset_id_prefix = models.CharField(max_length=12, blank=True)
    maintenance_type = models.CharField(max_length=80, blank=True)
    calibration_required = models.BooleanField(default=False)
    inspection_required = models.BooleanField(default=False)
    safety_critical_default = models.BooleanField(default=False)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = 'Asset categories'
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = ''.join(ch for ch in self.name.upper() if ch.isalnum())[:30] or 'CATEGORY'
        if not self.asset_id_prefix:
            self.asset_id_prefix = self.code[:8]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class AssetSubcategory(TimeStampedModel):
    category = models.ForeignKey(AssetCategory, on_delete=models.PROTECT, related_name='subcategories')
    code = models.CharField(max_length=30)
    name = models.CharField(max_length=120)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = 'Asset subcategories'
        ordering = ['category__name', 'name']
        constraints = [models.UniqueConstraint(fields=['category', 'code'], name='uniq_category_subcategory_code')]

    def __str__(self):
        return f'{self.category.name} / {self.name}'


class AssetAttributeDefinition(TimeStampedModel):
    DATA_TYPES = [('TEXT', 'Text'), ('NUMBER', 'Number'), ('DATE', 'Date'), ('BOOLEAN', 'Yes/No'), ('DROPDOWN', 'Dropdown')]
    category = models.ForeignKey(AssetCategory, on_delete=models.CASCADE, related_name='attribute_definitions')
    field_name = models.SlugField(max_length=80)
    field_label = models.CharField(max_length=120)
    data_type = models.CharField(max_length=20, choices=DATA_TYPES, default='TEXT')
    unit = models.CharField(max_length=30, blank=True)
    mandatory = models.BooleanField(default=False)
    minimum_value = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    maximum_value = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    dropdown_options = models.TextField(blank=True, help_text='One option per line for dropdown fields.')
    display_order = models.PositiveIntegerField(default=10)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['category__name', 'display_order', 'field_label']
        constraints = [models.UniqueConstraint(fields=['category', 'field_name'], name='uniq_category_attribute_name')]

    def clean(self):
        if self.minimum_value is not None and self.maximum_value is not None and self.minimum_value > self.maximum_value:
            raise ValidationError({'maximum_value': 'Maximum value must be greater than or equal to minimum value.'})

    def __str__(self):
        return f'{self.category.name} - {self.field_label}'


class Asset(TimeStampedModel):
    LIFECYCLE_STATUS_CHOICES = [
        ('DRAFT', 'Draft'), ('SUBMITTED', 'Submitted'), ('REVIEWED', 'Reviewed'), ('APPROVED', 'Approved'),
        ('ACTIVE', 'Active'), ('REJECTED', 'Rejected'), ('CANCELLED', 'Cancelled'), ('PROPOSED', 'Proposed'),
        ('PURCHASED', 'Purchased'), ('RECEIVED', 'Received'), ('INSTALLED', 'Installed'),
        ('COMMISSIONING', 'Under Commissioning'), ('OPERATIONAL', 'Operational'), ('STANDBY', 'Standby'),
        ('TEMP_INACTIVE', 'Temporarily Inactive'), ('UNDER_MAINTENANCE', 'Under Maintenance'),
        ('BREAKDOWN', 'Breakdown'), ('DECOMMISSIONED', 'Decommissioned'), ('DISPOSED', 'Disposed'),
    ]
    OPERATIONAL_STATUS_CHOICES = [
        ('RUNNING', 'Running'), ('STOPPED', 'Stopped'), ('STANDBY', 'Standby'), ('MAINTENANCE', 'Under Maintenance'),
        ('BREAKDOWN', 'Breakdown'), ('AWAITING_VERIFICATION', 'Awaiting Verification'),
        ('DISPOSAL_PENDING', 'Disposal Pending'), ('SCRAPPED', 'Scrapped'),
    ]
    STATUS_CHOICES = OPERATIONAL_STATUS_CHOICES
    CRITICALITY_CHOICES = [('LOW', 'Low'), ('MEDIUM', 'Medium'), ('HIGH', 'High'), ('CRITICAL', 'Critical')]
    CONDITION_CHOICES = [('EXCELLENT', 'Excellent'), ('GOOD', 'Good'), ('FAIR', 'Fair'), ('POOR', 'Poor'), ('CRITICAL', 'Critical'), ('FAILED', 'Failed')]
    ASSET_CLASS_CHOICES = [('PRODUCTION', 'Production asset'), ('UTILITY', 'Utility asset'), ('SAFETY', 'Safety asset'), ('SUPPORT', 'Support asset'), ('INFRASTRUCTURE', 'Infrastructure asset')]
    ASSET_TYPE_CHOICES = [
        ('REACTOR', 'Reactor'), ('PUMP', 'Pump'), ('TANK', 'Tank'), ('MOTOR', 'Motor'), ('COMPRESSOR', 'Compressor'), ('GEARBOX', 'Gearbox'),
        ('HEAT_EXCHANGER', 'Heat Exchanger'), ('INSTRUMENT', 'Instrument'), ('VALVE', 'Valve'), ('ELECTRICAL', 'Electrical Equipment'),
        ('UTILITY', 'Utility Equipment'), ('SAFETY', 'Safety Equipment'), ('CIVIL', 'Civil Asset'), ('IT', 'IT Equipment'), ('VEHICLE', 'Vehicle'), ('OTHER', 'Other'),
    ]
    TYPE_PREFIX = {
        'REACTOR': 'R', 'PUMP': 'P', 'TANK': 'T', 'MOTOR': 'M', 'COMPRESSOR': 'C', 'GEARBOX': 'GB', 'HEAT_EXCHANGER': 'HX',
        'INSTRUMENT': 'I', 'VALVE': 'V', 'ELECTRICAL': 'E', 'UTILITY': 'U', 'SAFETY': 'S', 'CIVIL': 'CV', 'IT': 'IT', 'VEHICLE': 'VH', 'OTHER': 'A',
    }

    company = models.ForeignKey(Company, on_delete=models.PROTECT, null=True, blank=True, related_name='assets')
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name='assets')
    department = models.ForeignKey(Department, on_delete=models.PROTECT, null=True, blank=True, related_name='assets')
    area = models.ForeignKey(Area, on_delete=models.PROTECT, null=True, blank=True, related_name='assets')
    functional_location = models.ForeignKey(FunctionalLocation, on_delete=models.PROTECT, related_name='assets')
    cost_centre = models.ForeignKey(CostCentre, on_delete=models.PROTECT, null=True, blank=True, related_name='assets')
    business_unit = models.CharField(max_length=120, blank=True)
    profit_centre = models.CharField(max_length=120, blank=True)

    asset_id = models.CharField(max_length=80, unique=True, blank=True)
    asset_type = models.CharField(max_length=30, choices=ASSET_TYPE_CHOICES, default='OTHER')
    tag_number = models.CharField(max_length=80)
    name = models.CharField(max_length=180)
    asset_description = models.TextField(blank=True)
    category = models.ForeignKey(AssetCategory, on_delete=models.PROTECT, null=True, blank=True)
    subcategory = models.ForeignKey(AssetSubcategory, on_delete=models.PROTECT, null=True, blank=True)
    asset_class = models.CharField(max_length=30, choices=ASSET_CLASS_CHOICES, blank=True)
    parent_asset = models.ForeignKey('self', on_delete=models.PROTECT, null=True, blank=True, related_name='sub_assets')
    hierarchy_level = models.PositiveIntegerField(default=0)
    equipment_position = models.CharField(max_length=80, blank=True)
    component_type = models.CharField(max_length=100, blank=True)
    installed_under_parent_on = models.DateField(null=True, blank=True)
    removed_from_parent_on = models.DateField(null=True, blank=True)

    asset_owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='owned_assets')
    responsible_department = models.ForeignKey(Department, on_delete=models.PROTECT, null=True, blank=True, related_name='responsible_assets')
    maintenance_department = models.ForeignKey(Department, on_delete=models.PROTECT, null=True, blank=True, related_name='maintenance_assets')
    user_department = models.ForeignKey(Department, on_delete=models.PROTECT, null=True, blank=True, related_name='user_assets')
    responsible_engineer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='responsible_assets')
    maintenance_planner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='planned_assets')
    custodian = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='custodian_assets')
    escalation_manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='escalated_assets')

    manufacturer = models.CharField(max_length=150, blank=True)
    model_number = models.CharField(max_length=120, blank=True)
    serial_number = models.CharField(max_length=120, blank=True)
    manufacturer_part_number = models.CharField(max_length=120, blank=True)
    capacity_rating = models.CharField(max_length=150, blank=True)
    material_of_construction = models.CharField(max_length=150, blank=True)
    equipment_rating = models.CharField(max_length=150, blank=True)
    design_pressure = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    operating_pressure = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    design_temperature = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    operating_temperature = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    power_rating = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    voltage = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    current = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    speed = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    weight = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    dimensions = models.CharField(max_length=150, blank=True)
    protection_class = models.CharField(max_length=80, blank=True)
    hazardous_area_classification = models.CharField(max_length=100, blank=True)
    installation_specification = models.TextField(blank=True)
    drawing_number = models.CharField(max_length=100, blank=True)
    datasheet_number = models.CharField(max_length=100, blank=True)

    purchase_date = models.DateField(null=True, blank=True)
    purchase_order_reference = models.CharField(max_length=120, blank=True)
    purchase_request_reference = models.CharField(max_length=120, blank=True)
    vendor = models.CharField(max_length=150, blank=True)
    purchase_cost = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, validators=NON_NEGATIVE_DECIMAL)
    installation_cost = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, validators=NON_NEGATIVE_DECIMAL)
    replacement_cost = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, validators=NON_NEGATIVE_DECIMAL)
    currency = models.CharField(max_length=10, default='INR')
    capitalisation_date = models.DateField(null=True, blank=True)
    asset_accounting_number = models.CharField(max_length=100, null=True, blank=True)
    depreciation_method = models.CharField(max_length=80, blank=True)
    useful_life_years = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, validators=POSITIVE_DECIMAL)
    residual_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, validators=NON_NEGATIVE_DECIMAL)
    current_book_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, validators=NON_NEGATIVE_DECIMAL)
    insurance_policy = models.CharField(max_length=120, blank=True)
    insurance_expiry_date = models.DateField(null=True, blank=True)

    commissioning_date = models.DateField(null=True, blank=True)
    decommissioning_date = models.DateField(null=True, blank=True)
    disposal_date = models.DateField(null=True, blank=True)
    lifecycle_status = models.CharField(max_length=30, choices=LIFECYCLE_STATUS_CHOICES, default='ACTIVE')
    status = models.CharField(max_length=30, choices=OPERATIONAL_STATUS_CHOICES, default='RUNNING')
    status_effective_date = models.DateField(null=True, blank=True)
    status_reason = models.TextField(blank=True)
    status_changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='asset_status_changes')

    criticality = models.CharField(max_length=20, choices=CRITICALITY_CHOICES, default='MEDIUM')
    criticality_score = models.PositiveIntegerField(default=50, validators=[MaxValueValidator(100)])
    safety_critical = models.BooleanField(default=False)
    safety_function = models.TextField(blank=True)
    regulatory_requirement = models.TextField(blank=True)
    statutory_inspection_required = models.BooleanField(default=False)
    inspection_authority = models.CharField(max_length=150, blank=True)
    certificate_number = models.CharField(max_length=120, blank=True)
    certificate_expiry = models.DateField(null=True, blank=True)
    permit_requirement = models.BooleanField(default=False)
    loto_requirement = models.BooleanField(default=False)
    risk_assessment_required = models.BooleanField(default=False)

    current_condition = models.CharField(max_length=30, choices=CONDITION_CHOICES, blank=True)
    condition_score = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(100)])
    condition_assessment_date = models.DateField(null=True, blank=True)
    condition_remarks = models.TextField(blank=True)
    recommended_action = models.TextField(blank=True)
    next_condition_assessment_date = models.DateField(null=True, blank=True)

    warranty_start_date = models.DateField(null=True, blank=True)
    warranty_end_date = models.DateField(null=True, blank=True)
    warranty_provider = models.CharField(max_length=150, blank=True)
    warranty_type = models.CharField(max_length=80, blank=True)
    warranty_terms = models.TextField(blank=True)
    warranty_contact = models.CharField(max_length=150, blank=True)
    warranty_claim_reference = models.CharField(max_length=120, blank=True)
    contract_type = models.CharField(max_length=80, blank=True)
    service_provider = models.CharField(max_length=150, blank=True)
    contract_number = models.CharField(max_length=120, blank=True)
    contract_start_date = models.DateField(null=True, blank=True)
    contract_end_date = models.DateField(null=True, blank=True)
    contract_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, validators=NON_NEGATIVE_DECIMAL)
    included_services = models.TextField(blank=True)
    excluded_services = models.TextField(blank=True)
    response_time = models.CharField(max_length=80, blank=True)
    visit_frequency = models.CharField(max_length=80, blank=True)
    service_contact_person = models.CharField(max_length=150, blank=True)
    renewal_reminder_date = models.DateField(null=True, blank=True)

    meter_enabled = models.BooleanField(default=False)
    default_meter_type = models.CharField(max_length=80, blank=True)
    default_meter_unit = models.CharField(max_length=30, blank=True)
    current_meter_reading = models.DecimalField(max_digits=16, decimal_places=3, null=True, blank=True, validators=NON_NEGATIVE_DECIMAL)
    initial_meter_reading = models.DecimalField(max_digits=16, decimal_places=3, null=True, blank=True, validators=NON_NEGATIVE_DECIMAL)
    reading_frequency = models.CharField(max_length=80, blank=True)
    meter_rollover_value = models.DecimalField(max_digits=16, decimal_places=3, null=True, blank=True, validators=NON_NEGATIVE_DECIMAL)
    iot_enabled = models.BooleanField(default=False)

    scheduled_hours_per_day = models.DecimalField(max_digits=5, decimal_places=2, default=24, validators=[MinValueValidator(Decimal('0.01')), MaxValueValidator(Decimal('24.00'))])
    availability_target = models.DecimalField(max_digits=5, decimal_places=2, default=95, validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))])
    qr_token = models.CharField(max_length=150, unique=True, null=True, blank=True)
    qr_code_value = models.CharField(max_length=160, blank=True)
    qr_generated_at = models.DateTimeField(null=True, blank=True)
    qr_generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='generated_asset_qr_codes')
    qr_active = models.BooleanField(default=True)
    qr_last_printed_at = models.DateTimeField(null=True, blank=True)
    image = models.ImageField(upload_to='asset_images/', blank=True, null=True, validators=IMAGE_VALIDATORS)
    remarks = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='assets_created')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='assets_updated')

    class Meta:
        ordering = ['asset_id']
        constraints = [
            models.UniqueConstraint(fields=['plant', 'tag_number'], name='uniq_plant_asset_tag'),
        ]

    def clean(self):
        if self.functional_location_id and self.functional_location.plant_id != self.plant_id:
            raise ValidationError({'functional_location': 'Functional location must belong to the selected plant.'})
        if self.area_id and self.area.plant_id != self.plant_id:
            raise ValidationError({'area': 'Area must belong to the selected plant.'})
        for field_name in ['department', 'responsible_department', 'maintenance_department', 'user_department']:
            department = getattr(self, field_name, None)
            if department and department.plant_id != self.plant_id:
                raise ValidationError({field_name: 'Department must belong to the selected plant.'})
        if self.cost_centre_id and self.cost_centre.plant_id != self.plant_id:
            raise ValidationError({'cost_centre': 'Cost centre must belong to the selected plant.'})
        if self.subcategory_id and self.category_id and self.subcategory.category_id != self.category_id:
            raise ValidationError({'subcategory': 'Subcategory must belong to the selected category.'})
        if self.parent_asset_id:
            if self.parent_asset_id == self.pk:
                raise ValidationError({'parent_asset': 'An asset cannot be its own parent.'})
            if self.parent_asset.plant_id != self.plant_id:
                raise ValidationError({'parent_asset': 'Parent asset must belong to the selected plant.'})
            if self.parent_asset.lifecycle_status in ['DECOMMISSIONED', 'DISPOSED'] or self.parent_asset.status in ['SCRAPPED']:
                raise ValidationError({'parent_asset': 'Disposed or scrapped assets cannot be selected as parent assets.'})
            parent = self.parent_asset
            visited = {self.pk} if self.pk else set()
            while parent:
                if parent.pk in visited:
                    raise ValidationError({'parent_asset': 'Circular asset hierarchy is not allowed.'})
                visited.add(parent.pk)
                parent = parent.parent_asset
        if self.purchase_date and self.commissioning_date and self.purchase_date > self.commissioning_date:
            raise ValidationError({'commissioning_date': 'Commissioning date cannot normally be before purchase date.'})
        if self.warranty_start_date and self.warranty_end_date and self.warranty_end_date < self.warranty_start_date:
            raise ValidationError({'warranty_end_date': 'Warranty end cannot be before warranty start.'})
        if self.disposal_date and self.commissioning_date and self.disposal_date < self.commissioning_date:
            raise ValidationError({'disposal_date': 'Disposal date cannot be before commissioning date.'})
        if self.design_pressure is not None and self.operating_pressure is not None and self.design_pressure < self.operating_pressure:
            raise ValidationError({'design_pressure': 'Design pressure must not be below operating pressure.'})
        if self.design_temperature is not None and self.operating_temperature is not None and self.design_temperature < self.operating_temperature:
            raise ValidationError({'design_temperature': 'Design temperature must not be below operating temperature.'})
        if self.asset_accounting_number and Asset.objects.exclude(pk=self.pk).filter(asset_accounting_number=self.asset_accounting_number).exists():
            raise ValidationError({'asset_accounting_number': 'Another asset already has this asset accounting number.'})

    def save(self, *args, **kwargs):
        if self.functional_location_id:
            self.plant = self.functional_location.plant
            self.area = self.functional_location.area
        if self.plant_id:
            self.company = self.plant.company
        if not self.asset_description:
            self.asset_description = self.name
        if not self.status_effective_date:
            self.status_effective_date = timezone.localdate()
        if not self.asset_id:
            from .services.numbering import next_document_number
            prefix = self.TYPE_PREFIX.get(self.asset_type, '')
            if self.category_id and self.category.asset_id_prefix:
                prefix = self.category.asset_id_prefix
            self.asset_id = next_document_number('ASSET', self.plant, custom_prefix=prefix or 'A')
        if not self.qr_token:
            self.qr_token = f'asset-{self.asset_id}-{timezone.now().timestamp()}'.replace(' ', '-').replace(':', '').replace('.', '')[:150]
        if not self.qr_code_value:
            self.qr_code_value = f'ASSET:{self.asset_id}'
        if not self.qr_generated_at:
            self.qr_generated_at = timezone.now()
        self.is_active = self.lifecycle_status not in ['DISPOSED', 'DECOMMISSIONED', 'CANCELLED'] and self.status != 'SCRAPPED'
        super().save(*args, **kwargs)

    @property
    def warranty_status(self):
        if not self.warranty_start_date and not self.warranty_end_date:
            return 'Not applicable'
        today = timezone.localdate()
        if self.warranty_start_date and today < self.warranty_start_date:
            return 'Not started'
        if self.warranty_end_date and today > self.warranty_end_date:
            return 'Expired'
        if self.warranty_end_date and (self.warranty_end_date - today).days <= 60:
            return 'Expiring soon'
        return 'Active'

    @property
    def total_acquisition_cost(self):
        return (self.purchase_cost or Decimal('0')) + (self.installation_cost or Decimal('0'))

    def __str__(self):
        return f'{self.asset_id} - {self.name}'

    def get_absolute_url(self):
        return reverse('asset_detail', kwargs={'pk': self.pk})


class AssetDocument(TimeStampedModel):
    DOCUMENT_TYPES = [
        ('MANUAL', 'User Manual'), ('MAINT_MANUAL', 'Maintenance Manual'), ('DRAWING', 'Drawing / P&ID'),
        ('DATASHEET', 'Datasheet'), ('CERTIFICATE', 'Certificate'), ('CALIBRATION_CERT', 'Calibration Certificate'),
        ('INSPECTION_CERT', 'Inspection Certificate'), ('WARRANTY_CERT', 'Warranty Certificate'), ('PURCHASE_DOC', 'Purchase Document'),
        ('SOP', 'SOP'), ('SAFETY_DOC', 'Safety Document'), ('PHOTO', 'Photograph'), ('COMMISSIONING', 'Commissioning Report'),
        ('REPORT', 'Report'), ('OTHER', 'Other'),
    ]
    STATUS_CHOICES = [('DRAFT', 'Draft'), ('UNDER_REVIEW', 'Under Review'), ('APPROVED', 'Approved'), ('SUPERSEDED', 'Superseded'), ('ARCHIVED', 'Archived')]
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='documents')
    document_number = models.CharField(max_length=100, blank=True)
    title = models.CharField(max_length=180)
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPES, default='OTHER')
    revision = models.CharField(max_length=40, blank=True)
    effective_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    document_owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='owned_asset_documents')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='approved_asset_documents')
    approval_date = models.DateField(null=True, blank=True)
    file = models.FileField(upload_to='asset_documents/', validators=DOCUMENT_VALIDATORS)
    superseded_document = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='new_revisions')
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['asset__asset_id', 'document_type', '-created_at']

    def clean(self):
        if self.expiry_date and self.effective_date and self.expiry_date < self.effective_date:
            raise ValidationError({'expiry_date': 'Expiry date cannot be before effective date.'})
        if self.superseded_document_id and self.superseded_document.asset_id != self.asset_id:
            raise ValidationError({'superseded_document': 'Superseded document must belong to the same asset.'})

    def __str__(self):
        return f'{self.asset.asset_id} - {self.title}'


class AssetImage(TimeStampedModel):
    IMAGE_TYPES = [('FRONT', 'Front View'), ('NAMEPLATE', 'Nameplate'), ('INSTALLATION', 'Installation View'), ('INTERNAL', 'Internal View'), ('BEFORE', 'Before Maintenance'), ('AFTER', 'After Maintenance'), ('OTHER', 'Other')]
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='asset_gallery/', validators=IMAGE_VALIDATORS)
    image_type = models.CharField(max_length=20, choices=IMAGE_TYPES, default='OTHER')
    caption = models.CharField(max_length=180, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='uploaded_asset_images')
    primary = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if self.primary:
            AssetImage.objects.filter(asset=self.asset, primary=True).exclude(pk=self.pk).update(primary=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.asset.asset_id} - {self.get_image_type_display()}'


class AssetAttributeValue(TimeStampedModel):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='attribute_values')
    definition = models.ForeignKey(AssetAttributeDefinition, on_delete=models.CASCADE, related_name='values')
    value = models.TextField(blank=True)

    class Meta:
        ordering = ['definition__display_order']
        constraints = [models.UniqueConstraint(fields=['asset', 'definition'], name='uniq_asset_attribute_value')]

    def clean(self):
        if self.definition.category_id and self.asset.category_id and self.definition.category_id != self.asset.category_id:
            raise ValidationError({'definition': 'Attribute definition must belong to the selected asset category.'})
        if self.definition.mandatory and not str(self.value).strip():
            raise ValidationError({'value': 'This category-specific attribute is mandatory.'})
        if self.definition.data_type == 'NUMBER' and str(self.value).strip():
            try:
                number = Decimal(str(self.value).strip())
            except InvalidOperation:
                raise ValidationError({'value': 'Enter a valid number.'})
            if self.definition.minimum_value is not None and number < self.definition.minimum_value:
                raise ValidationError({'value': f'Minimum allowed value is {self.definition.minimum_value}.'})
            if self.definition.maximum_value is not None and number > self.definition.maximum_value:
                raise ValidationError({'value': f'Maximum allowed value is {self.definition.maximum_value}.'})

    def __str__(self):
        return f'{self.asset.asset_id} - {self.definition.field_label}'


class AssetStatusHistory(models.Model):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='status_history')
    previous_lifecycle_status = models.CharField(max_length=30, blank=True)
    new_lifecycle_status = models.CharField(max_length=30, blank=True)
    previous_operational_status = models.CharField(max_length=30, blank=True)
    new_operational_status = models.CharField(max_length=30, blank=True)
    effective_date = models.DateField(default=timezone.localdate)
    reason = models.TextField()
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='asset_status_history')
    reference = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.asset.asset_id} status change on {self.effective_date}'


class AssetConditionAssessment(TimeStampedModel):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='condition_assessments')
    assessment_date = models.DateField(default=timezone.localdate)
    condition = models.CharField(max_length=30, choices=Asset.CONDITION_CHOICES)
    score = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(100)])
    findings = models.TextField()
    recommendation = models.TextField(blank=True)
    assessor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='asset_condition_assessments')
    next_assessment_date = models.DateField(null=True, blank=True)
    image = models.ImageField(upload_to='asset_condition/', blank=True, null=True, validators=IMAGE_VALIDATORS)

    class Meta:
        ordering = ['-assessment_date']

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        Asset.objects.filter(pk=self.asset_id).update(
            current_condition=self.condition,
            condition_score=self.score,
            condition_assessment_date=self.assessment_date,
            condition_remarks=self.findings,
            recommended_action=self.recommendation,
            next_condition_assessment_date=self.next_assessment_date,
        )


class AssetMeter(TimeStampedModel):
    METER_TYPES = [('RUNNING_HOURS', 'Running Hours'), ('KM', 'Kilometres'), ('CYCLES', 'Production Cycles'), ('STARTS', 'Number of Starts'), ('ENERGY', 'Energy Consumption'), ('FLOW', 'Flow Totaliser'), ('VIBRATION', 'Vibration'), ('TEMPERATURE', 'Temperature'), ('PRESSURE', 'Pressure'), ('CURRENT', 'Electrical Current'), ('OTHER', 'Other')]
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='asset_meters')
    meter_type = models.CharField(max_length=30, choices=METER_TYPES)
    unit = models.CharField(max_length=30)
    current_reading = models.DecimalField(max_digits=16, decimal_places=3, default=0, validators=NON_NEGATIVE_DECIMAL)
    initial_reading = models.DecimalField(max_digits=16, decimal_places=3, default=0, validators=NON_NEGATIVE_DECIMAL)
    reading_frequency = models.CharField(max_length=80, blank=True)
    rollover_value = models.DecimalField(max_digits=16, decimal_places=3, null=True, blank=True, validators=NON_NEGATIVE_DECIMAL)
    iot_enabled = models.BooleanField(default=False)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['asset', 'meter_type', 'unit'], name='uniq_asset_meter_type_unit')]

    def __str__(self):
        return f'{self.asset.asset_id} - {self.get_meter_type_display()}'


class AssetMeterReading(TimeStampedModel):
    SOURCE_CHOICES = [('MANUAL', 'Manual'), ('IOT', 'IoT'), ('IMPORT', 'Import'), ('CORRECTION', 'Correction')]
    meter = models.ForeignKey(AssetMeter, on_delete=models.CASCADE, related_name='readings')
    reading = models.DecimalField(max_digits=16, decimal_places=3, validators=NON_NEGATIVE_DECIMAL)
    reading_date = models.DateField(default=timezone.localdate)
    entered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='asset_meter_readings')
    reading_source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='MANUAL')
    photograph = models.ImageField(upload_to='asset_meter_readings/', blank=True, null=True, validators=IMAGE_VALIDATORS)
    correction_reason = models.TextField(blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ['-reading_date', '-created_at']
        indexes = [models.Index(fields=['meter', 'reading_date'], name='idx_asset_meter_reading_date')]

    def clean(self):
        latest = self.meter.readings.exclude(pk=self.pk).order_by('-reading_date', '-created_at').first() if self.meter_id else None
        if latest and self.reading < latest.reading and not self.correction_reason and not self.meter.rollover_value:
            raise ValidationError({'reading': 'Reading is lower than previous reading. Enter correction reason or configure rollover.'})
        if self.reading_source == 'CORRECTION' and self.reading < (latest.reading if latest else self.meter.current_reading) and not self.correction_reason:
            raise ValidationError({'correction_reason': 'A reason is required when correcting a meter reading downward.'})

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Multiple readings per day are allowed. The newest chronological record, not the maximum value,
        # is the authoritative current reading so a documented downward correction works correctly.
        latest = self.meter.readings.order_by('-reading_date', '-created_at').first()
        if latest:
            self.meter.current_reading = latest.reading
            self.meter.save(update_fields=['current_reading', 'updated_at'])
            Asset.objects.filter(pk=self.meter.asset_id).update(current_meter_reading=latest.reading, meter_enabled=True)
        from .services.sap_pm import evaluate_condition_rules
        evaluate_condition_rules(self)


class ConditionRule(TimeStampedModel):
    OPERATORS = [('GT', '>'), ('GTE', '>='), ('LT', '<'), ('LTE', '<=')]
    meter = models.ForeignKey(AssetMeter, on_delete=models.CASCADE, related_name='condition_rules')
    name = models.CharField(max_length=150)
    operator = models.CharField(max_length=5, choices=OPERATORS, default='GTE')
    threshold = models.DecimalField(max_digits=16, decimal_places=3)
    priority = models.CharField(max_length=20, choices=[('LOW','Low'),('MEDIUM','Medium'),('HIGH','High'),('URGENT','Urgent')], default='HIGH')
    work_centre = models.ForeignKey(WorkCentre, on_delete=models.PROTECT, related_name='condition_rules')
    auto_create_notification = models.BooleanField(default=True)
    active = models.BooleanField(default=True)
    last_triggered_at = models.DateTimeField(null=True, blank=True)

    def clean(self):
        if self.work_centre_id and self.meter_id and self.work_centre.plant_id != self.meter.asset.plant_id:
            raise ValidationError({'work_centre': 'Work centre must belong to the meter asset plant.'})

    def __str__(self):
        return f'{self.meter} - {self.name}'


class AssetCriticalityAssessment(TimeStampedModel):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='criticality_assessments')
    assessment_date = models.DateField(default=timezone.localdate)
    assessed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='asset_criticality_assessments')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='approved_asset_criticalities')
    total_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    criticality_class = models.CharField(max_length=20, choices=Asset.CRITICALITY_CHOICES, default='MEDIUM')
    next_review_date = models.DateField(null=True, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ['-assessment_date']

    def recalculate(self):
        total = sum(line.weighted_score for line in self.lines.all())
        self.total_score = total
        if total >= 76:
            self.criticality_class = 'CRITICAL'
        elif total >= 51:
            self.criticality_class = 'HIGH'
        elif total >= 26:
            self.criticality_class = 'MEDIUM'
        else:
            self.criticality_class = 'LOW'
        self.save(update_fields=['total_score', 'criticality_class', 'updated_at'])
        Asset.objects.filter(pk=self.asset_id).update(criticality_score=min(int(total), 100), criticality=self.criticality_class)


class AssetCriticalityAssessmentLine(TimeStampedModel):
    FACTORS = [('SAFETY', 'Safety Impact'), ('ENVIRONMENT', 'Environmental Impact'), ('PRODUCTION', 'Production Impact'), ('QUALITY', 'Quality Impact'), ('MAINT_COST', 'Maintenance Cost'), ('LEAD_TIME', 'Replacement Lead Time'), ('STANDBY', 'Availability of Standby'), ('FAILURE_FREQ', 'Failure Frequency'), ('REGULATORY', 'Regulatory Impact')]
    assessment = models.ForeignKey(AssetCriticalityAssessment, on_delete=models.CASCADE, related_name='lines')
    factor = models.CharField(max_length=30, choices=FACTORS)
    score = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    weight = models.DecimalField(max_digits=6, decimal_places=2, default=1, validators=POSITIVE_DECIMAL)
    comment = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['assessment', 'factor'], name='uniq_criticality_factor')]

    @property
    def weighted_score(self):
        return Decimal(self.score) * self.weight


class AssetTransferRequest(TimeStampedModel):
    TRANSFER_TYPES = [('LOCATION', 'Location Change'), ('DEPARTMENT', 'Department Change'), ('PLANT', 'Plant Transfer'), ('PARENT', 'Parent Asset Change'), ('WORKSHOP', 'Repair Workshop'), ('VENDOR', 'External Vendor')]
    STATUS_CHOICES = [('DRAFT', 'Draft'), ('SUBMITTED', 'Submitted'), ('APPROVED', 'Approved'), ('DISPATCHED', 'Dispatched'), ('RECEIVED', 'Received'), ('COMPLETED', 'Completed'), ('REJECTED', 'Rejected'), ('CANCELLED', 'Cancelled')]
    transfer_no = models.CharField(max_length=80, unique=True, blank=True)
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name='transfer_requests')
    transfer_type = models.CharField(max_length=20, choices=TRANSFER_TYPES, default='LOCATION')
    current_plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name='asset_transfers_from')
    current_location = models.ForeignKey(FunctionalLocation, on_delete=models.PROTECT, related_name='asset_transfers_from')
    destination_plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name='asset_transfers_to')
    destination_location = models.ForeignKey(FunctionalLocation, on_delete=models.PROTECT, related_name='asset_transfers_to')
    current_department = models.ForeignKey(Department, on_delete=models.PROTECT, null=True, blank=True, related_name='asset_transfers_from')
    destination_department = models.ForeignKey(Department, on_delete=models.PROTECT, null=True, blank=True, related_name='asset_transfers_to')
    destination_parent = models.ForeignKey(Asset, on_delete=models.PROTECT, null=True, blank=True, related_name='incoming_transfer_children')
    transfer_date = models.DateField(default=timezone.localdate)
    reason = models.TextField()
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='requested_asset_transfers')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='approved_asset_transfers')
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='received_asset_transfers')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def clean(self):
        if self.asset_id:
            if self.asset.lifecycle_status in ['DISPOSED']:
                raise ValidationError({'asset': 'Disposed assets cannot be transferred.'})
        if self.destination_location_id and self.destination_location.plant_id != self.destination_plant_id:
            raise ValidationError({'destination_location': 'Destination location must belong to destination plant.'})
        if self.destination_department_id and self.destination_department.plant_id != self.destination_plant_id:
            raise ValidationError({'destination_department': 'Destination department must belong to destination plant.'})
        if self.destination_parent_id and self.destination_parent.plant_id != self.destination_plant_id:
            raise ValidationError({'destination_parent': 'Destination parent must belong to destination plant.'})

    def save(self, *args, **kwargs):
        if self.asset_id and not self.current_plant_id:
            self.current_plant = self.asset.plant
        if self.asset_id and not self.current_location_id:
            self.current_location = self.asset.functional_location
        if not self.transfer_no:
            from .services.numbering import next_document_number
            self.transfer_no = next_document_number('TRANSFER', self.asset.plant if self.asset_id else None)
        super().save(*args, **kwargs)

    def complete_transfer(self, user):
        self.asset.functional_location = self.destination_location
        self.asset.plant = self.destination_plant
        self.asset.area = self.destination_location.area
        self.asset.department = self.destination_department
        self.asset.parent_asset = self.destination_parent
        self.asset.updated_by = user
        self.asset.full_clean()
        self.asset.save()
        self.received_by = user
        self.status = 'COMPLETED'
        self.save(update_fields=['received_by', 'status', 'updated_at'])


class AssetChangeRequest(TimeStampedModel):
    STATUS_CHOICES = [('DRAFT', 'Draft'), ('SUBMITTED', 'Submitted'), ('APPROVED', 'Approved'), ('REJECTED', 'Rejected'), ('APPLIED', 'Applied')]
    FIELD_CHOICES = [('PLANT', 'Plant'), ('LOCATION', 'Location'), ('PARENT_ASSET', 'Parent Asset'), ('CATEGORY', 'Asset Category'), ('TAG_NUMBER', 'Tag Number'), ('LIFECYCLE_STATUS', 'Lifecycle Status'), ('PURCHASE_VALUE', 'Purchase Value'), ('CRITICALITY', 'Criticality'), ('SAFETY_CRITICAL', 'Safety Critical')]
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name='change_requests')
    requested_change = models.CharField(max_length=40, choices=FIELD_CHOICES)
    current_value = models.TextField(blank=True)
    proposed_value = models.TextField()
    reason = models.TextField()
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='requested_asset_changes')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='approved_asset_changes')
    effective_date = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.asset.asset_id} - {self.get_requested_change_display()}'

class MaintenanceRequest(TimeStampedModel):
    PRIORITY_CHOICES = [('LOW', 'Low'), ('MEDIUM', 'Medium'), ('HIGH', 'High'), ('URGENT', 'Urgent')]
    STATUS_CHOICES = [
        ('REPORTED', 'Reported'), ('SCREENING', 'Screening'), ('NEED_INFO', 'Need More Information'),
        ('ACCEPTED', 'Accepted'), ('REJECTED', 'Rejected'), ('WO_CREATED', 'Work Order Created'),
        ('IN_PROGRESS', 'In Progress'), ('COMPLETED', 'Completed'), ('CLOSED', 'Closed'), ('CANCELLED', 'Cancelled'),
    ]
    REPORTED_DEPARTMENT_CHOICES = [
        ('PRODUCTION', 'Production'), ('MAINTENANCE', 'Maintenance'), ('SAFETY', 'Safety'), ('OTHER', 'Other'),
    ]
    request_no = models.CharField(max_length=80, unique=True, blank=True)
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name='maintenance_requests')
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name='maintenance_requests')
    work_centre = models.ForeignKey(WorkCentre, on_delete=models.PROTECT, related_name='maintenance_requests')
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='reported_maintenance_requests')
    reported_department = models.CharField(max_length=30, choices=REPORTED_DEPARTMENT_CHOICES, default='PRODUCTION')
    problem_description = models.TextField()
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='MEDIUM')
    failure_mode = models.CharField(max_length=150, blank=True)
    safety_issue = models.BooleanField(default=False)
    leakage = models.BooleanField(default=False)
    production_stopped = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='REPORTED')
    screening_notes = models.TextField(blank=True)
    screened_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='screened_maintenance_requests')
    screened_at = models.DateTimeField(null=True, blank=True)
    attachment = models.FileField(upload_to='maintenance_requests/', blank=True, null=True, validators=DOCUMENT_VALIDATORS)

    class Meta:
        ordering = ['-created_at']

    def clean(self):
        # The plant selected on the request must agree with both dependent
        # selections. Keep the fallback assignment for programmatic callers that
        # create a request directly from an asset without first setting a plant.
        if self.asset_id:
            asset_plant_id = self.asset.plant_id
            if self.plant_id and asset_plant_id != self.plant_id:
                raise ValidationError({'asset': 'Asset must belong to the selected plant.'})
            if not self.plant_id:
                self.plant = self.asset.plant

        if self.work_centre_id and self.plant_id and self.work_centre.plant_id != self.plant_id:
            raise ValidationError({'work_centre': 'Work centre must belong to the same plant as the selected asset.'})

    def save(self, *args, **kwargs):
        if self.asset_id:
            self.plant = self.asset.plant
        if not self.request_no:
            from .services.numbering import next_document_number
            self.request_no = next_document_number('MR', self.plant)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.request_no} - {self.asset.asset_id}'


class MaintenanceCatalogCode(TimeStampedModel):
    CATALOG_TYPES = [
        ('OBJECT_PART', 'Object Part'), ('DAMAGE', 'Damage'), ('CAUSE', 'Cause'),
        ('ACTIVITY', 'Activity'), ('TASK', 'Task / Action'),
    ]
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name='maintenance_catalog_codes')
    catalog_type = models.CharField(max_length=20, choices=CATALOG_TYPES)
    code_group = models.CharField(max_length=40, default='GENERAL')
    code = models.CharField(max_length=40)
    description = models.CharField(max_length=180)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['plant__code', 'catalog_type', 'code_group', 'code']
        constraints = [models.UniqueConstraint(fields=['plant', 'catalog_type', 'code_group', 'code'], name='uniq_pm_catalog_code')]

    def __str__(self):
        return f'{self.get_catalog_type_display()} {self.code} - {self.description}'


class MaintenanceRequestItem(TimeStampedModel):
    maintenance_request = models.ForeignKey(MaintenanceRequest, on_delete=models.CASCADE, related_name='items')
    sequence = models.PositiveIntegerField(default=10)
    object_part = models.ForeignKey(MaintenanceCatalogCode, on_delete=models.PROTECT, null=True, blank=True, related_name='notification_object_parts')
    damage_code = models.ForeignKey(MaintenanceCatalogCode, on_delete=models.PROTECT, null=True, blank=True, related_name='notification_damage_codes')
    cause_code = models.ForeignKey(MaintenanceCatalogCode, on_delete=models.PROTECT, null=True, blank=True, related_name='notification_cause_codes')
    activity_code = models.ForeignKey(MaintenanceCatalogCode, on_delete=models.PROTECT, null=True, blank=True, related_name='notification_activity_codes')
    description = models.TextField(blank=True)
    findings = models.TextField(blank=True)

    class Meta:
        ordering = ['maintenance_request', 'sequence']
        constraints = [models.UniqueConstraint(fields=['maintenance_request', 'sequence'], name='uniq_notification_item_sequence')]

    def clean(self):
        for field_name in ['object_part', 'damage_code', 'cause_code', 'activity_code']:
            obj = getattr(self, field_name, None)
            if obj and obj.plant_id != self.maintenance_request.plant_id:
                raise ValidationError({field_name: 'Catalog code must belong to the notification plant.'})

    def __str__(self):
        return f'{self.maintenance_request.request_no} / {self.sequence}'


class ShutdownPlan(TimeStampedModel):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'), ('PLANNED', 'Planned'), ('APPROVED', 'Approved'),
        ('IN_PROGRESS', 'In Progress'), ('COMPLETED', 'Completed'), ('CLOSED', 'Closed'), ('CANCELLED', 'Cancelled'),
    ]
    plan_no = models.CharField(max_length=80, unique=True, blank=True)
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name='shutdown_plans')
    title = models.CharField(max_length=180)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    scope = models.TextField()
    coordinator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='coordinated_shutdowns')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='approved_shutdowns')
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ['-start_date']

    def clean(self):
        if self.end_date < self.start_date:
            raise ValidationError({'end_date': 'End date cannot be earlier than start date.'})

    def save(self, *args, **kwargs):
        if not self.plan_no:
            from .services.numbering import next_document_number
            self.plan_no = next_document_number('SHUTDOWN', self.plant)
        super().save(*args, **kwargs)

    @property
    def completion_percent(self):
        total = self.jobs.count()
        if not total:
            return 0
        done = self.jobs.filter(status__in=['COMPLETED', 'CLOSED']).count()
        return round((done / total) * 100, 1)

    def __str__(self):
        return f'{self.plan_no} - {self.title}'


class MaintenanceStrategy(TimeStampedModel):
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name='maintenance_strategies')
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['plant', 'name'], name='uniq_maintenance_strategy_name')]

    def __str__(self):
        return f'{self.plant.code} - {self.name}'


class MaintenanceStrategyPackage(TimeStampedModel):
    UNIT_CHOICES = [('DAYS', 'Days'), ('WEEKS', 'Weeks'), ('MONTHS', 'Months'), ('RUNNING_HOURS', 'Running Hours'), ('KM', 'Kilometres'), ('CYCLES', 'Cycles')]
    strategy = models.ForeignKey(MaintenanceStrategy, on_delete=models.CASCADE, related_name='packages')
    name = models.CharField(max_length=100)
    cycle_value = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    cycle_unit = models.CharField(max_length=20, choices=UNIT_CHOICES)
    hierarchy = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['strategy', 'hierarchy', 'cycle_value']

    def __str__(self):
        return f'{self.strategy.name} - {self.name}'


class MaintenanceTaskList(TimeStampedModel):
    LIST_TYPES = [('GENERAL', 'General'), ('EQUIPMENT', 'Equipment'), ('FUNCTIONAL_LOCATION', 'Functional Location')]
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name='maintenance_task_lists')
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=180)
    list_type = models.CharField(max_length=30, choices=LIST_TYPES, default='GENERAL')
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, null=True, blank=True, related_name='maintenance_task_lists')
    functional_location = models.ForeignKey(FunctionalLocation, on_delete=models.PROTECT, null=True, blank=True, related_name='maintenance_task_lists')
    strategy = models.ForeignKey(MaintenanceStrategy, on_delete=models.PROTECT, null=True, blank=True, related_name='task_lists')
    revision = models.CharField(max_length=20, default='1')
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['plant', 'code', 'revision'], name='uniq_task_list_revision')]

    def clean(self):
        if self.list_type == 'EQUIPMENT' and not self.asset_id:
            raise ValidationError({'asset': 'Equipment task lists require an asset.'})
        if self.list_type == 'FUNCTIONAL_LOCATION' and not self.functional_location_id:
            raise ValidationError({'functional_location': 'Functional-location task lists require a functional location.'})
        if self.asset_id and self.asset.plant_id != self.plant_id:
            raise ValidationError({'asset': 'Task-list asset must belong to the selected plant.'})
        if self.functional_location_id and self.functional_location.plant_id != self.plant_id:
            raise ValidationError({'functional_location': 'Task-list functional location must belong to the selected plant.'})
        if self.strategy_id and self.strategy.plant_id != self.plant_id:
            raise ValidationError({'strategy': 'Task-list strategy must belong to the selected plant.'})

    def __str__(self):
        return f'{self.code} - {self.name} (Rev {self.revision})'


class MaintenanceTaskListOperation(TimeStampedModel):
    EXECUTION_STAGES = [('PRE', 'Preliminary'), ('MAIN', 'Main Work'), ('POST', 'Post / Restoration')]
    EXECUTION_TYPES = [('INTERNAL', 'Internal'), ('EXTERNAL', 'External Service')]
    task_list = models.ForeignKey(MaintenanceTaskList, on_delete=models.CASCADE, related_name='operations')
    sequence = models.PositiveIntegerField(default=10)
    description = models.TextField()
    work_centre = models.ForeignKey(WorkCentre, on_delete=models.PROTECT, related_name='task_list_operations')
    execution_stage = models.CharField(max_length=10, choices=EXECUTION_STAGES, default='MAIN')
    execution_type = models.CharField(max_length=10, choices=EXECUTION_TYPES, default='INTERNAL')
    planned_hours = models.DecimalField(max_digits=8, decimal_places=2, default=1, validators=NON_NEGATIVE_DECIMAL)
    persons_required = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    required_tools = models.TextField(blank=True)
    safety_instruction = models.TextField(blank=True)
    strategy_package = models.ForeignKey(MaintenanceStrategyPackage, on_delete=models.PROTECT, null=True, blank=True, related_name='task_operations')
    vendor = models.CharField(max_length=180, blank=True)
    service_item = models.ForeignKey('SparePart', on_delete=models.PROTECT, null=True, blank=True, related_name='task_list_service_operations')
    external_service_description = models.TextField(blank=True)

    class Meta:
        ordering = ['task_list', 'sequence']
        constraints = [models.UniqueConstraint(fields=['task_list', 'sequence'], name='uniq_task_list_operation_sequence')]

    def clean(self):
        if self.work_centre_id and self.task_list_id and self.work_centre.plant_id != self.task_list.plant_id:
            raise ValidationError({'work_centre': 'Task-list work centre must belong to the task-list plant.'})
        if self.strategy_package_id and self.task_list.strategy_id != self.strategy_package.strategy_id:
            raise ValidationError({'strategy_package': 'The package must belong to the task-list strategy.'})
        if self.execution_type == 'EXTERNAL' and not self.service_item_id:
            raise ValidationError({'service_item': 'External task-list operations require a service item.'})
        if self.service_item_id and self.service_item.plant_id != self.task_list.plant_id:
            raise ValidationError({'service_item': 'Service item must belong to the task-list plant.'})

    def __str__(self):
        return f'{self.task_list.code} / {self.sequence}'


class MaintenanceTaskListMaterial(TimeStampedModel):
    task_operation = models.ForeignKey(MaintenanceTaskListOperation, on_delete=models.CASCADE, related_name='materials')
    spare_part = models.ForeignKey('SparePart', on_delete=models.PROTECT, related_name='task_list_materials')
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=1, validators=POSITIVE_DECIMAL)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['task_operation', 'spare_part'], name='uniq_task_operation_material')]


class PMPlan(TimeStampedModel):
    FREQUENCY_UNITS = [('DAYS', 'Days'), ('WEEKS', 'Weeks'), ('MONTHS', 'Months'), ('RUNNING_HOURS', 'Running Hours')]
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name='pm_plans')
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name='pm_plans')
    work_centre = models.ForeignKey(WorkCentre, on_delete=models.PROTECT, related_name='pm_plans')
    responsible_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='responsible_pm_plans')
    name = models.CharField(max_length=180)
    frequency_value = models.PositiveIntegerField(default=30, validators=[MinValueValidator(1)])
    frequency_unit = models.CharField(max_length=20, choices=FREQUENCY_UNITS, default='DAYS')
    estimated_duration_hours = models.DecimalField(max_digits=8, decimal_places=2, default=1, validators=POSITIVE_DECIMAL)
    permit_required = models.BooleanField(default=False)
    next_due_date = models.DateField(null=True, blank=True)
    last_completed_date = models.DateField(null=True, blank=True)
    auto_generate_work_order = models.BooleanField(default=True)
    SCHEDULING_MODES = [('FIXED', 'Fixed Cycle'), ('COMPLETION', 'Completion Based')]
    scheduling_mode = models.CharField(max_length=20, choices=SCHEDULING_MODES, default='FIXED')
    task_list = models.ForeignKey(MaintenanceTaskList, on_delete=models.PROTECT, null=True, blank=True, related_name='pm_plans')
    strategy = models.ForeignKey(MaintenanceStrategy, on_delete=models.PROTECT, null=True, blank=True, related_name='pm_plans')
    counter_meter = models.ForeignKey(AssetMeter, on_delete=models.PROTECT, null=True, blank=True, related_name='pm_plans')
    counter_interval = models.DecimalField(max_digits=16, decimal_places=3, null=True, blank=True, validators=POSITIVE_DECIMAL)
    last_counter_reading = models.DecimalField(max_digits=16, decimal_places=3, null=True, blank=True, validators=NON_NEGATIVE_DECIMAL)
    next_counter_due = models.DecimalField(max_digits=16, decimal_places=3, null=True, blank=True, validators=NON_NEGATIVE_DECIMAL)
    call_horizon_percent = models.PositiveIntegerField(default=100, validators=[MinValueValidator(1), MaxValueValidator(100)])
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['next_due_date']

    def clean(self):
        if self.asset_id and self.work_centre_id and self.asset.plant_id != self.work_centre.plant_id:
            raise ValidationError({'work_centre': 'PM work centre must belong to the asset plant.'})
        if self.task_list_id and self.asset_id and self.task_list.plant_id != self.asset.plant_id:
            raise ValidationError({'task_list': 'Task list must belong to the asset plant.'})
        if self.strategy_id and self.asset_id and self.strategy.plant_id != self.asset.plant_id:
            raise ValidationError({'strategy': 'Maintenance strategy must belong to the asset plant.'})
        if self.task_list_id and self.strategy_id and self.task_list.strategy_id and self.task_list.strategy_id != self.strategy_id:
            raise ValidationError({'task_list': 'Task-list strategy must match the PM plan strategy.'})
        if self.counter_meter_id and self.counter_meter.asset_id != self.asset_id:
            raise ValidationError({'counter_meter': 'Counter meter must belong to the PM plan asset.'})
        if self.frequency_unit == 'RUNNING_HOURS':
            if not self.counter_meter_id:
                raise ValidationError({'counter_meter': 'Running-hours plans require a counter meter.'})
            if not self.counter_interval:
                raise ValidationError({'counter_interval': 'Running-hours plans require a counter interval.'})
        elif not self.next_due_date:
            raise ValidationError({'next_due_date': 'Calendar PM plans require a next due date.'})

    def save(self, *args, **kwargs):
        if self.asset_id:
            self.plant = self.asset.plant
        if self.frequency_unit == 'RUNNING_HOURS' and self.counter_meter_id and self.counter_interval and self.next_counter_due is None:
            base = self.last_counter_reading if self.last_counter_reading is not None else self.counter_meter.current_reading
            self.next_counter_due = base + self.counter_interval
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.name} - {self.asset.asset_id}'


class PMCall(TimeStampedModel):
    """Durable preventive-maintenance call/history record used for compliance reporting."""
    TRIGGER_CHOICES = [
        ('CALENDAR', 'Calendar'), ('COUNTER', 'Primary Counter'),
        ('MULTI_COUNTER', 'Multiple Counter'), ('STRATEGY', 'Strategy Package'),
    ]
    STATUS_CHOICES = [
        ('DUE', 'Due / Not Generated'), ('GENERATED', 'Work Order Generated'),
        ('COMPLETED', 'Completed'), ('MISSED', 'Missed'), ('CANCELLED', 'Cancelled'),
    ]
    pm_plan = models.ForeignKey(PMPlan, on_delete=models.PROTECT, related_name='calls')
    call_key = models.CharField(max_length=180, unique=True)
    trigger_type = models.CharField(max_length=20, choices=TRIGGER_CHOICES, default='CALENDAR')
    call_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField(null=True, blank=True)
    due_reading = models.DecimalField(max_digits=16, decimal_places=3, null=True, blank=True, validators=NON_NEGATIVE_DECIMAL)
    reason = models.TextField(blank=True)
    work_order = models.OneToOneField('WorkOrder', on_delete=models.SET_NULL, null=True, blank=True, related_name='pm_call')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DUE')
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-call_date', '-created_at']
        indexes = [models.Index(fields=['pm_plan', 'call_date', 'status'], name='idx_pm_call_plan_date')]

    def __str__(self):
        return f'{self.pm_plan.name} / {self.call_date} / {self.get_status_display()}'


class PMTask(TimeStampedModel):
    pm_plan = models.ForeignKey(PMPlan, on_delete=models.CASCADE, related_name='tasks')
    sequence = models.PositiveIntegerField(default=1)
    task = models.TextField()
    safety_instruction = models.TextField(blank=True)
    required_tools = models.CharField(max_length=250, blank=True)
    expected_result = models.CharField(max_length=250, blank=True)
    mandatory = models.BooleanField(default=True)

    class Meta:
        ordering = ['pm_plan', 'sequence']
        constraints = [models.UniqueConstraint(fields=['pm_plan', 'sequence'], name='uniq_pm_task_sequence')]

    def __str__(self):
        return f'{self.pm_plan} / {self.sequence}'


class PMPlanCounter(TimeStampedModel):
    pm_plan = models.ForeignKey(PMPlan, on_delete=models.CASCADE, related_name='counters')
    meter = models.ForeignKey(AssetMeter, on_delete=models.PROTECT, related_name='pm_counter_links')
    interval = models.DecimalField(max_digits=16, decimal_places=3, validators=POSITIVE_DECIMAL)
    last_completed_reading = models.DecimalField(max_digits=16, decimal_places=3, null=True, blank=True, validators=NON_NEGATIVE_DECIMAL)
    next_due_reading = models.DecimalField(max_digits=16, decimal_places=3, null=True, blank=True, validators=NON_NEGATIVE_DECIMAL)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['pm_plan', 'meter'], name='uniq_pm_plan_meter_counter')]

    def clean(self):
        if self.meter_id and self.pm_plan_id and self.meter.asset_id != self.pm_plan.asset_id:
            raise ValidationError({'meter': 'Counter meter must belong to the PM plan asset.'})

    def save(self, *args, **kwargs):
        if self.next_due_reading is None and self.meter_id:
            base = self.last_completed_reading if self.last_completed_reading is not None else self.meter.current_reading
            self.next_due_reading = base + self.interval
        super().save(*args, **kwargs)


class PMPlanStrategyPackage(TimeStampedModel):
    pm_plan = models.ForeignKey(PMPlan, on_delete=models.CASCADE, related_name='strategy_packages')
    package = models.ForeignKey(MaintenanceStrategyPackage, on_delete=models.PROTECT, related_name='plan_calls')
    next_due_date = models.DateField(null=True, blank=True)
    next_due_reading = models.DecimalField(max_digits=16, decimal_places=3, null=True, blank=True, validators=NON_NEGATIVE_DECIMAL)
    last_completed_date = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['pm_plan', 'package'], name='uniq_pm_plan_strategy_package')]

    def clean(self):
        if self.pm_plan_id and self.package_id and self.pm_plan.strategy_id != self.package.strategy_id:
            raise ValidationError({'package': 'Strategy package must belong to the PM plan strategy.'})
        if self.package_id and self.package.cycle_unit in {'RUNNING_HOURS','KM','CYCLES'} and self.next_due_reading is None:
            raise ValidationError({'next_due_reading': 'Counter-based strategy packages require a next due reading.'})
        if self.package_id and self.package.cycle_unit in {'DAYS','WEEKS','MONTHS'} and not self.next_due_date:
            raise ValidationError({'next_due_date': 'Calendar strategy packages require a next due date.'})

    def __str__(self):
        return f'{self.pm_plan} / {self.package.name}'


class WorkOrder(TimeStampedModel):
    WORK_TYPES = [
        ('BREAKDOWN', 'Breakdown Maintenance'), ('PREVENTIVE', 'Preventive Maintenance'),
        ('CORRECTIVE', 'Corrective Maintenance'), ('INSPECTION', 'Inspection'),
        ('CALIBRATION', 'Calibration'), ('SHUTDOWN', 'Shutdown Maintenance'),
        ('SAFETY', 'Safety Work'), ('MODIFICATION', 'Modification Order'), ('PROJECT', 'Project Work'),
    ]
    ACTIVITY_TYPES = [
        ('REPAIR', 'Repair'), ('REPLACEMENT', 'Replacement'), ('TESTING', 'Testing'),
        ('OIL_CHANGE', 'Oil Change'), ('GREASING', 'Greasing / Lubrication'), ('ROUTINE', 'Routine Job'),
        ('CONDITION_MONITORING', 'Condition Monitoring'), ('ALIGNMENT', 'Alignment'),
        ('CLEANING', 'Cleaning'), ('OVERHAUL', 'Overhaul'), ('OTHER', 'Other'),
    ]
    SHIFT_CHOICES = [('G', 'General'), ('A', 'A Shift'), ('B', 'B Shift'), ('C', 'C Shift')]
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'), ('PLANNED', 'Planned'), ('PENDING_APPROVAL', 'Pending Approval'),
        ('APPROVED', 'Approved'), ('PREPARATION', 'Preparation'), ('READY_TO_SCHEDULE', 'Ready to Schedule'),
        ('SCHEDULED', 'Scheduled'), ('DISPATCHED', 'Dispatched'), ('RELEASED', 'Released'),
        ('IN_PROGRESS', 'In Progress'), ('COMPLETED', 'Completed'), ('VERIFIED', 'Verified'),
        ('TECO', 'Technically Completed (TECO)'), ('COST_CLOSURE', 'Cost Closure'),
        ('CLOSED', 'Closed'), ('CANCELLED', 'Cancelled'),
    ]
    wo_number = models.CharField(max_length=80, unique=True, blank=True)
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name='work_orders')
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name='work_orders')
    work_centre = models.ForeignKey(WorkCentre, on_delete=models.PROTECT, related_name='work_orders')
    maintenance_request = models.ForeignKey(MaintenanceRequest, on_delete=models.PROTECT, null=True, blank=True, related_name='work_orders')
    pm_plan = models.ForeignKey(PMPlan, on_delete=models.PROTECT, null=True, blank=True, related_name='work_orders')
    shutdown_plan = models.ForeignKey(ShutdownPlan, on_delete=models.PROTECT, null=True, blank=True, related_name='work_orders')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_work_orders')
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='assigned_work_orders')
    supervisor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='supervised_work_orders')
    work_type = models.CharField(max_length=20, choices=WORK_TYPES)
    activity_type = models.CharField(max_length=30, choices=ACTIVITY_TYPES, default='OTHER')
    shift = models.CharField(max_length=2, choices=SHIFT_CHOICES, default='G')
    priority = models.CharField(max_length=20, choices=MaintenanceRequest.PRIORITY_CHOICES, default='MEDIUM')
    job_description = models.TextField()
    checklist = models.TextField(blank=True)
    required_tools = models.TextField(blank=True)
    risk_summary = models.TextField(blank=True)
    failure_mode = models.CharField(max_length=180, blank=True)
    failure_cause = models.TextField(blank=True)
    failure_action = models.TextField(blank=True)
    planned_start = models.DateTimeField(null=True, blank=True)
    planned_end = models.DateTimeField(null=True, blank=True)
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_end = models.DateTimeField(null=True, blank=True)
    permit_required = models.BooleanField(default=False)
    loto_required = models.BooleanField(default=False)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='DRAFT')
    estimated_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=NON_NEGATIVE_DECIMAL)
    actual_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=NON_NEGATIVE_DECIMAL)
    external_service_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=NON_NEGATIVE_DECIMAL)
    other_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=NON_NEGATIVE_DECIMAL)
    completion_notes = models.TextField(blank=True)
    approval_notes = models.TextField(blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='approved_work_orders')
    approved_at = models.DateTimeField(null=True, blank=True)
    prepared_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='prepared_work_orders')
    prepared_at = models.DateTimeField(null=True, blank=True)
    ready_to_schedule_at = models.DateTimeField(null=True, blank=True)
    scheduled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='scheduled_work_orders')
    scheduled_at = models.DateTimeField(null=True, blank=True)
    dispatched_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='dispatched_work_orders')
    dispatched_at = models.DateTimeField(null=True, blank=True)
    released_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='released_work_orders')
    released_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='completed_work_orders')
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='verified_work_orders')
    verified_at = models.DateTimeField(null=True, blank=True)
    teco_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='teco_work_orders')
    teco_at = models.DateTimeField(null=True, blank=True)
    cost_closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='cost_closed_work_orders')
    cost_closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='closed_work_orders')
    closed_at = models.DateTimeField(null=True, blank=True)
    baseline_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=NON_NEGATIVE_DECIMAL)
    planned_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=NON_NEGATIVE_DECIMAL)
    technical_lock = models.BooleanField(default=False)
    settlement_status = models.CharField(max_length=20, choices=[('NOT_REQUIRED','Not Required'),('PENDING','Pending'),('SETTLED','Settled')], default='PENDING')
    business_completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='business_completed_work_orders')
    business_completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def clean(self):
        if self.asset_id and self.asset.plant_id != self.plant_id:
            raise ValidationError({'asset': 'Asset must belong to the selected plant.'})
        if self.work_centre_id and self.work_centre.plant_id != self.plant_id:
            raise ValidationError({'work_centre': 'Work centre must belong to the selected plant.'})
        if self.planned_start and self.planned_end and self.planned_end < self.planned_start:
            raise ValidationError({'planned_end': 'Planned end cannot be earlier than planned start.'})
        if self.actual_start and self.actual_end and self.actual_end < self.actual_start:
            raise ValidationError({'actual_end': 'Actual end cannot be earlier than actual start.'})
        if self.work_type == 'BREAKDOWN' and self.status in ['COMPLETED', 'VERIFIED', 'TECO', 'COST_CLOSURE', 'CLOSED']:
            errors = {}
            if not self.actual_start:
                errors['actual_start'] = 'Actual start is required before completing a breakdown work order.'
            if not self.actual_end:
                errors['actual_end'] = 'Actual end is required before completing a breakdown work order.'
            if errors:
                raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.asset_id:
            self.plant = self.asset.plant
        if not self.wo_number:
            from .services.numbering import next_document_number
            self.wo_number = next_document_number('WO', self.plant)
        if self.pm_plan_id and not self.checklist:
            self.checklist = '\n'.join(task.task for task in self.pm_plan.tasks.all())
        super().save(*args, **kwargs)

    @property
    def repair_hours(self):
        if self.actual_start and self.actual_end and self.actual_end > self.actual_start:
            return round((self.actual_end - self.actual_start).total_seconds() / 3600, 2)
        return None

    @property
    def material_cost(self):
        total = Decimal('0')
        for issue in self.material_issues.filter(status='POSTED').select_related('item'):
            total += issue.quantity_issued * issue.item.item_rate
        return total

    @property
    def labour_cost(self):
        return sum((line.cost for line in self.labour_entries.all()), Decimal('0'))

    @property
    def external_procurement_cost(self):
        service_total = self.purchase_requests.filter(
            source_operation__execution_type='EXTERNAL',
            purchase_orders__service_entries__status='ACCEPTED',
        ).aggregate(total=models.Sum('purchase_orders__service_entries__amount'))['total'] or Decimal('0')
        if service_total:
            return service_total
        invoice_total = self.purchase_requests.filter(
            source_operation__execution_type='EXTERNAL',
            purchase_orders__vendor_invoices__accounts_clearance_status='CLEARED',
        ).aggregate(total=models.Sum('purchase_orders__vendor_invoices__amount'))['total'] or Decimal('0')
        return invoice_total

    @property
    def calculated_actual_cost(self):
        external = self.external_procurement_cost or self.external_service_cost
        return self.material_cost + self.labour_cost + external + self.other_cost

    def __str__(self):
        return f'{self.wo_number} - {self.asset.asset_id}'

    def get_absolute_url(self):
        return reverse('work_order_detail', kwargs={'pk': self.pk})


class WorkOrderOperation(TimeStampedModel):
    STATUS_CHOICES = [('PENDING', 'Pending'), ('READY', 'Ready'), ('DISPATCHED', 'Dispatched'), ('IN_PROGRESS', 'In Progress'), ('PAUSED', 'Paused'), ('WORK_FINISHED', 'Work Finished'), ('COMPLETED', 'Completed'), ('CANCELLED', 'Cancelled')]
    EXECUTION_STAGES = [('PRE', 'Preliminary'), ('MAIN', 'Main Work'), ('POST', 'Post / Restoration')]
    EXECUTION_TYPES = [('INTERNAL', 'Internal'), ('EXTERNAL', 'External Service')]
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name='operations')
    sequence = models.PositiveIntegerField(default=10)
    description = models.TextField()
    work_centre = models.ForeignKey(WorkCentre, on_delete=models.PROTECT, related_name='work_order_operations')
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='assigned_work_order_operations')
    parent_operation = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='suboperations')
    predecessor = models.ForeignKey('self', on_delete=models.PROTECT, null=True, blank=True, related_name='successors')
    execution_stage = models.CharField(max_length=10, choices=EXECUTION_STAGES, default='MAIN')
    execution_type = models.CharField(max_length=10, choices=EXECUTION_TYPES, default='INTERNAL')
    control_key = models.CharField(max_length=20, default='PM01', help_text='SAP-style control key; PM01 internal / PM03 external by convention.')
    persons_required = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    planned_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0, validators=NON_NEGATIVE_DECIMAL)
    actual_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0, validators=NON_NEGATIVE_DECIMAL)
    scheduled_start = models.DateTimeField(null=True, blank=True)
    scheduled_end = models.DateTimeField(null=True, blank=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    vendor = models.CharField(max_length=180, blank=True)
    external_service_description = models.TextField(blank=True)
    service_item = models.ForeignKey('SparePart', on_delete=models.PROTECT, null=True, blank=True, related_name='external_service_operations')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['work_order', 'sequence']
        constraints = [models.UniqueConstraint(fields=['work_order', 'sequence'], name='uniq_work_order_operation_sequence')]

    def clean(self):
        if self.work_centre_id and self.work_order_id and self.work_centre.plant_id != self.work_order.plant_id:
            raise ValidationError({'work_centre': 'Operation work centre must belong to the work-order plant.'})
        if self.parent_operation_id:
            if self.pk and self.parent_operation_id == self.pk:
                raise ValidationError({'parent_operation': 'An operation cannot be its own parent.'})
            if self.parent_operation.work_order_id != self.work_order_id:
                raise ValidationError({'parent_operation': 'Parent operation must belong to this work order.'})
        if self.predecessor_id:
            if self.pk and self.predecessor_id == self.pk:
                raise ValidationError({'predecessor': 'An operation cannot depend on itself.'})
            if self.predecessor.work_order_id != self.work_order_id:
                raise ValidationError({'predecessor': 'Predecessor must belong to this work order.'})
            if self.predecessor.sequence >= self.sequence:
                raise ValidationError({'predecessor': 'Predecessor sequence must be earlier than the successor operation.'})
        if self.scheduled_start and self.scheduled_end and self.scheduled_end <= self.scheduled_start:
            raise ValidationError({'scheduled_end': 'Scheduled end must be after scheduled start.'})
        if self.execution_type == 'EXTERNAL' and not self.service_item_id:
            raise ValidationError({'service_item': 'External operations require a service item for procurement.'})

    def __str__(self):
        return f'{self.work_order.wo_number} / {self.sequence}'


class WorkOrderLabour(TimeStampedModel):
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name='labour_entries')
    person = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='work_order_labour_entries')
    role = models.CharField(max_length=100, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    hours = models.DecimalField(max_digits=8, decimal_places=2, default=0, validators=NON_NEGATIVE_DECIMAL)
    hourly_rate = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=NON_NEGATIVE_DECIMAL)
    remarks = models.CharField(max_length=200, blank=True)

    def clean(self):
        if self.started_at and self.ended_at and self.ended_at < self.started_at:
            raise ValidationError({'ended_at': 'Labour end cannot be earlier than start.'})
        if self.work_order_id and self.work_order.status not in {'IN_PROGRESS', 'COMPLETED', 'VERIFIED'}:
            raise ValidationError({'work_order': 'Labour may only be recorded after the work order has started and before TECO.'})
        if self.work_order_id and self.work_order.technical_lock:
            raise ValidationError({'work_order': 'TECO work orders are technically locked.'})

    def save(self, *args, **kwargs):
        if self.started_at and self.ended_at and self.ended_at > self.started_at:
            self.hours = Decimal(str(round((self.ended_at - self.started_at).total_seconds() / 3600, 2)))
        super().save(*args, **kwargs)

    @property
    def cost(self):
        return self.hours * self.hourly_rate

    def __str__(self):
        return f'{self.work_order.wo_number} - {self.person}'


class ShutdownJob(TimeStampedModel):
    STATUS_CHOICES = [('PENDING', 'Pending'), ('IN_PROGRESS', 'In Progress'), ('COMPLETED', 'Completed'), ('CLOSED', 'Closed'), ('DELAYED', 'Delayed')]
    shutdown_plan = models.ForeignKey(ShutdownPlan, on_delete=models.CASCADE, related_name='jobs')
    work_order = models.OneToOneField(WorkOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name='shutdown_job')
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name='shutdown_jobs')
    work_centre = models.ForeignKey(WorkCentre, on_delete=models.PROTECT, related_name='shutdown_jobs')
    description = models.TextField()
    planned_start = models.DateTimeField()
    planned_end = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    progress_percent = models.PositiveIntegerField(default=0, validators=[MaxValueValidator(100)])
    delay_reason = models.TextField(blank=True)

    class Meta:
        ordering = ['planned_start']

    def __str__(self):
        return f'{self.shutdown_plan.plan_no} - {self.asset.asset_id}'


class AssetDowntimeEvent(TimeStampedModel):
    DOWNTIME_TYPES = [('BREAKDOWN', 'Breakdown'), ('PLANNED', 'Planned'), ('UTILITY', 'Utility Failure'), ('OTHER', 'Other')]
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name='downtime_events')
    work_order = models.ForeignKey(WorkOrder, on_delete=models.PROTECT, null=True, blank=True, related_name='downtime_events')
    downtime_type = models.CharField(max_length=20, choices=DOWNTIME_TYPES)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField()
    reason = models.TextField()
    production_impact = models.TextField(blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='recorded_downtime_events')

    class Meta:
        ordering = ['-started_at']

    def clean(self):
        if self.ended_at <= self.started_at:
            raise ValidationError({'ended_at': 'Downtime end must be after downtime start.'})
        if self.work_order_id and self.work_order.asset_id != self.asset_id:
            raise ValidationError({'work_order': 'Work order must belong to the selected asset.'})
        if self.work_order_id and self.work_order.technical_lock:
            raise ValidationError({'work_order': 'Downtime cannot be added after TECO because the work order is technically locked.'})

    @property
    def duration_hours(self):
        return round((self.ended_at - self.started_at).total_seconds() / 3600, 2)

    def __str__(self):
        return f'{self.asset.asset_id} - {self.duration_hours} h'


class WorkOrderSpare(TimeStampedModel):
    PROCUREMENT_TYPES = [('STOCK', 'Stock Component'), ('NON_STOCK', 'Non-stock / Procure')]
    RESERVATION_STATUSES = [('UNRESERVED', 'Unreserved'), ('RESERVED', 'Reserved'), ('PARTIAL', 'Partially Reserved'), ('PROCUREMENT', 'Procurement Required'), ('ISSUED', 'Issued')]
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name='spares_used')
    operation = models.ForeignKey(WorkOrderOperation, on_delete=models.CASCADE, null=True, blank=True, related_name='planned_materials')
    spare_part = models.ForeignKey('SparePart', on_delete=models.PROTECT)
    procurement_type = models.CharField(max_length=20, choices=PROCUREMENT_TYPES, default='STOCK')
    reservation_status = models.CharField(max_length=20, choices=RESERVATION_STATUSES, default='UNRESERVED')
    purchase_request = models.ForeignKey('PurchaseRequest', on_delete=models.SET_NULL, null=True, blank=True, related_name='planned_material_lines')
    quantity_required = models.DecimalField(max_digits=12, decimal_places=2, default=1, validators=POSITIVE_DECIMAL)
    quantity_reserved = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=NON_NEGATIVE_DECIMAL)
    quantity_used = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=NON_NEGATIVE_DECIMAL)
    remarks = models.CharField(max_length=180, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['work_order', 'operation', 'spare_part'], name='uniq_work_order_operation_spare')]

    def clean(self):
        if self.work_order_id and self.spare_part_id and self.work_order.plant_id != self.spare_part.plant_id:
            raise ValidationError({'spare_part': 'Planned material must belong to the work-order plant.'})
        if self.operation_id and self.operation.work_order_id != self.work_order_id:
            raise ValidationError({'operation': 'Material operation must belong to this work order.'})
        if self.quantity_used > self.quantity_required:
            raise ValidationError({'quantity_used': 'Used quantity cannot exceed the planned requirement.'})

    def __str__(self):
        return f'{self.work_order.wo_number} - {self.spare_part.part_code}'


class WorkOrderConfirmation(TimeStampedModel):
    CONFIRMATION_TYPES = [('PARTIAL', 'Partial Confirmation'), ('FINAL', 'Final Confirmation')]
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name='confirmations')
    operation = models.ForeignKey(WorkOrderOperation, on_delete=models.CASCADE, related_name='confirmations')
    person = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='maintenance_confirmations')
    confirmation_type = models.CharField(max_length=20, choices=CONFIRMATION_TYPES, default='PARTIAL')
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField()
    actual_work_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0, validators=NON_NEGATIVE_DECIMAL)
    remaining_work_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0, validators=NON_NEGATIVE_DECIMAL)
    confirmation_text = models.TextField(blank=True)

    class Meta:
        ordering = ['operation', 'created_at']

    def clean(self):
        if self.ended_at <= self.started_at:
            raise ValidationError({'ended_at': 'Confirmation end must be after start.'})
        if self.operation_id and self.work_order_id and self.operation.work_order_id != self.work_order_id:
            raise ValidationError({'operation': 'Operation must belong to the selected work order.'})
        if self.work_order_id and self.work_order.technical_lock:
            raise ValidationError({'work_order': 'TECO work orders are technically locked.'})
        if self.work_order_id and self.work_order.status not in {'IN_PROGRESS', 'COMPLETED'}:
            raise ValidationError({'work_order': 'Operation confirmations are only allowed during execution or completion.'})
        if self.operation_id and self.operation.predecessor_id and self.operation.predecessor.status != 'COMPLETED':
            raise ValidationError({'operation': f'Predecessor operation {self.operation.predecessor.sequence} must be completed before confirming this operation.'})

    def save(self, *args, **kwargs):
        self.actual_work_hours = Decimal(str(round((self.ended_at - self.started_at).total_seconds()/3600, 2)))
        super().save(*args, **kwargs)
        total = self.operation.confirmations.aggregate(total=models.Sum('actual_work_hours'))['total'] or Decimal('0')
        self.operation.actual_hours = total
        if self.confirmation_type == 'FINAL':
            self.operation.status = 'COMPLETED'
        self.operation.save(update_fields=['actual_hours', 'status', 'updated_at'])


class OperationTimeEvent(TimeStampedModel):
    ACTIONS = [('START', 'Start'), ('PAUSE', 'Pause'), ('RESUME', 'Resume'), ('STOP', 'Stop')]
    operation = models.ForeignKey(WorkOrderOperation, on_delete=models.CASCADE, related_name='time_events')
    action = models.CharField(max_length=10, choices=ACTIONS)
    event_at = models.DateTimeField(default=timezone.now)
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='maintenance_time_events')
    remarks = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['operation', 'event_at']


class InventoryReservation(TimeStampedModel):
    STATUS_CHOICES = [('ACTIVE', 'Active'), ('PARTIAL', 'Partial'), ('ISSUED', 'Issued'), ('CANCELLED', 'Cancelled'), ('CLOSED', 'Closed')]
    work_order_spare = models.ForeignKey(WorkOrderSpare, on_delete=models.CASCADE, related_name='reservations')
    item = models.ForeignKey('SparePart', on_delete=models.PROTECT, related_name='inventory_reservations')
    location = models.ForeignKey('StoreLocation', on_delete=models.PROTECT, related_name='inventory_reservations')
    quantity = models.DecimalField(max_digits=14, decimal_places=3, validators=POSITIVE_DECIMAL)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    reserved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_inventory_reservations')
    reserved_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['work_order_spare', 'location'], name='uniq_material_reservation_location')]


class SettlementRule(TimeStampedModel):
    RECEIVER_TYPES = [('COST_CENTRE', 'Cost Centre'), ('ASSET', 'Asset'), ('WBS', 'WBS Element'), ('INTERNAL_ORDER', 'Internal Order')]
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name='settlement_rules')
    receiver_type = models.CharField(max_length=30, choices=RECEIVER_TYPES)
    receiver_reference = models.CharField(max_length=100)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(Decimal('0.01')), MaxValueValidator(Decimal('100.00'))])

    def __str__(self):
        return f'{self.work_order.wo_number} → {self.receiver_type}:{self.receiver_reference} {self.percentage}%'


class SettlementPosting(TimeStampedModel):
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name='settlement_postings')
    rule = models.ForeignKey(SettlementRule, on_delete=models.PROTECT, related_name='postings')
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=NON_NEGATIVE_DECIMAL)
    posted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='maintenance_settlement_postings')
    posted_at = models.DateTimeField(default=timezone.now)
    reference = models.CharField(max_length=100, blank=True)


class InspectionPlan(TimeStampedModel):
    STATUTORY_FORM_CHOICES = [('FORM_9', 'Form 9'), ('FORM_10', 'Form 10'), ('FORM_11', 'Form 11'), ('OTHER', 'Other'), ('NA', 'Not Applicable')]
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name='inspection_plans')
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name='inspection_plans')
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='assigned_inspection_plans')
    statutory_equipment = models.BooleanField(default=False)
    statutory_form = models.CharField(max_length=20, choices=STATUTORY_FORM_CHOICES, default='NA')
    inspection_type = models.CharField(max_length=150)
    standard_reference = models.CharField(max_length=180, blank=True)
    frequency_months = models.PositiveIntegerField(default=12, validators=[MinValueValidator(1)])
    checklist = models.TextField(blank=True)
    next_due_date = models.DateField()
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['next_due_date']

    def save(self, *args, **kwargs):
        if self.asset_id:
            self.plant = self.asset.plant
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.inspection_type} - {self.asset.asset_id}'


class InspectionRecord(TimeStampedModel):
    RESULT_CHOICES = [('PASS', 'Pass'), ('FAIL', 'Fail'), ('OBSERVATION', 'Observation')]
    plan = models.ForeignKey(InspectionPlan, on_delete=models.PROTECT, related_name='records')
    inspected_on = models.DateField()
    inspector_name = models.CharField(max_length=150)
    result = models.CharField(max_length=20, choices=RESULT_CHOICES)
    thickness_reading = models.CharField(max_length=120, blank=True)
    corrosion_observation = models.TextField(blank=True)
    recommendation = models.TextField(blank=True)
    certificate = models.FileField(upload_to='inspection_certificates/', blank=True, null=True, validators=DOCUMENT_VALIDATORS)
    next_inspection_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-inspected_on']

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.next_inspection_date:
            InspectionPlan.objects.filter(pk=self.plan_id).update(next_due_date=self.next_inspection_date, updated_at=timezone.now())

    def __str__(self):
        return f'{self.plan.asset.asset_id} - {self.inspected_on}'


class CalibrationPlan(TimeStampedModel):
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name='calibration_plans')
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name='calibration_plans')
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='assigned_calibration_plans')
    permit_required = models.BooleanField(default=False)
    instrument_range = models.CharField(max_length=120, blank=True)
    accuracy = models.CharField(max_length=120, blank=True)
    frequency_months = models.PositiveIntegerField(default=6, validators=[MinValueValidator(1)])
    next_due_date = models.DateField()
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['next_due_date']

    def save(self, *args, **kwargs):
        if self.asset_id:
            self.plant = self.asset.plant
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Calibration - {self.asset.asset_id}'


class CalibrationRecord(TimeStampedModel):
    RESULT_CHOICES = [('PASS', 'Pass'), ('FAIL', 'Fail')]
    plan = models.ForeignKey(CalibrationPlan, on_delete=models.PROTECT, related_name='records')
    calibrated_on = models.DateField()
    calibrated_by = models.CharField(max_length=150)
    standard_instrument = models.CharField(max_length=180, blank=True)
    before_reading = models.TextField(blank=True)
    after_reading = models.TextField(blank=True)
    error_observed = models.CharField(max_length=120, blank=True)
    result = models.CharField(max_length=20, choices=RESULT_CHOICES)
    certificate = models.FileField(upload_to='calibration_certificates/', blank=True, null=True, validators=DOCUMENT_VALIDATORS)
    next_calibration_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-calibrated_on']

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.next_calibration_date:
            CalibrationPlan.objects.filter(pk=self.plan_id).update(next_due_date=self.next_calibration_date, updated_at=timezone.now())

    def __str__(self):
        return f'{self.plan.asset.asset_id} - {self.calibrated_on}'


class PermitToWork(TimeStampedModel):
    PERMIT_TYPES = [
        ('HOT_WORK', 'Hot Work'), ('COLD_WORK', 'Cold Work'), ('CONFINED_SPACE', 'Confined Space Entry'),
        ('HEIGHT_WORK', 'Height Work'), ('ELECTRICAL', 'Electrical Isolation'), ('LINE_BREAKING', 'Line Breaking'),
        ('VESSEL_ENTRY', 'Vessel Entry'), ('EXCAVATION', 'Excavation Work'), ('LOTO', 'LOTO'),
    ]
    STATUS_CHOICES = [('REQUESTED', 'Requested'), ('SAFETY_REVIEW', 'Safety Review'), ('APPROVED', 'Approved'), ('ISSUED', 'Issued'), ('CLOSED', 'Closed'), ('REJECTED', 'Rejected')]
    permit_no = models.CharField(max_length=60, unique=True)
    work_order = models.ForeignKey(WorkOrder, on_delete=models.PROTECT, related_name='permits')
    permit_type = models.CharField(max_length=30, choices=PERMIT_TYPES)
    permit_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    hazards = models.TextField(blank=True)
    ppe_required = models.TextField(blank=True)
    isolation_done = models.BooleanField(default=False)
    gas_test_required = models.BooleanField(default=False)
    gas_test_result = models.CharField(max_length=150, blank=True)
    loto_applied = models.BooleanField(default=False)
    fire_extinguisher_available = models.BooleanField(default=False)
    area_barricaded = models.BooleanField(default=False)
    approved_by_safety = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='safety_approved_permits')
    approved_by_area_owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='area_approved_permits')
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_to = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='REQUESTED')
    closure_notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.permit_no} - {self.get_permit_type_display()}'


class RiskAssessment(TimeStampedModel):
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name='risk_assessments')
    activity = models.CharField(max_length=180)
    hazard = models.TextField()
    consequence = models.TextField()
    existing_control = models.TextField(blank=True)
    likelihood = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(5)])
    severity = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(5)])
    additional_control = models.TextField(blank=True)

    @property
    def risk_score(self):
        return self.likelihood * self.severity

    def __str__(self):
        return f'{self.work_order.wo_number} - Risk {self.risk_score}'


class RCARecord(TimeStampedModel):
    METHOD_CHOICES = [('FIVE_WHY', '5-Why'), ('FISHBONE', 'Fishbone'), ('BOTH', '5-Why and Fishbone')]
    rca_no = models.CharField(max_length=80, unique=True, blank=True)
    work_order = models.ForeignKey(WorkOrder, on_delete=models.PROTECT, related_name='rca_records')
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default='FIVE_WHY')
    failure_mode = models.CharField(max_length=180)
    event_description = models.TextField()
    why_1 = models.TextField(blank=True)
    why_2 = models.TextField(blank=True)
    why_3 = models.TextField(blank=True)
    why_4 = models.TextField(blank=True)
    why_5 = models.TextField(blank=True)
    root_cause = models.TextField()
    responsible_person = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='responsible_rcas')
    target_date = models.DateField(null=True, blank=True)
    closed = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.rca_no:
            from .services.numbering import next_document_number
            self.rca_no = next_document_number('RCA', self.work_order.plant)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.rca_no} - {self.work_order.wo_number}'


class FishboneCause(TimeStampedModel):
    CATEGORY_CHOICES = [
        ('MAN', 'Man'), ('MACHINE', 'Machine'), ('METHOD', 'Method'), ('MATERIAL', 'Material'),
        ('MEASUREMENT', 'Measurement'), ('ENVIRONMENT', 'Environment'),
    ]
    rca = models.ForeignKey(RCARecord, on_delete=models.CASCADE, related_name='fishbone_causes')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    cause = models.TextField()
    verified = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.rca.rca_no} - {self.get_category_display()}'


class CAPAAction(TimeStampedModel):
    ACTION_TYPES = [('CORRECTIVE', 'Corrective Action'), ('PREVENTIVE', 'Preventive Action')]
    STATUS_CHOICES = [('OPEN', 'Open'), ('IN_PROGRESS', 'In Progress'), ('COMPLETED', 'Completed'), ('VERIFIED', 'Verified'), ('CLOSED', 'Closed'), ('OVERDUE', 'Overdue')]
    rca = models.ForeignKey(RCARecord, on_delete=models.CASCADE, related_name='capa_actions')
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    description = models.TextField()
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='owned_capa_actions')
    due_date = models.DateField()
    severity = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(5)])
    probability = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(5)])
    detectability = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(5)])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    completion_evidence = models.FileField(upload_to='capa_evidence/', blank=True, null=True, validators=DOCUMENT_VALIDATORS)
    effectiveness_review = models.TextField(blank=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='verified_capa_actions')

    @property
    def score(self):
        return self.severity * self.probability * self.detectability

    def __str__(self):
        return f'{self.rca.rca_no} - {self.get_action_type_display()}'


class LLFObservation(TimeStampedModel):
    SENSE_CHOICES = [('LOOK', 'Look'), ('LISTEN', 'Listen'), ('FEEL', 'Feel'), ('MULTIPLE', 'Multiple')]
    SEVERITY_CHOICES = [('LOW', 'Low'), ('MEDIUM', 'Medium'), ('HIGH', 'High'), ('CRITICAL', 'Critical')]
    STATUS_CHOICES = [('OPEN', 'Open'), ('MR_CREATED', 'Maintenance Request Created'), ('CLOSED', 'Closed')]
    observation_no = models.CharField(max_length=80, unique=True, blank=True)
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name='llf_observations')
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name='llf_observations')
    observed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='llf_observations')
    observed_at = models.DateTimeField(default=timezone.now)
    sense = models.CharField(max_length=20, choices=SENSE_CHOICES)
    observation = models.TextField()
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='LOW')
    photo = models.ImageField(upload_to='llf_observations/', blank=True, null=True, validators=IMAGE_VALIDATORS)
    assigned_work_centre = models.ForeignKey(WorkCentre, on_delete=models.PROTECT, related_name='llf_observations')
    maintenance_request = models.ForeignKey(MaintenanceRequest, on_delete=models.PROTECT, null=True, blank=True, related_name='source_llf_observations')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')

    def save(self, *args, **kwargs):
        if self.asset_id:
            self.plant = self.asset.plant
        if not self.observation_no:
            from .services.numbering import next_document_number
            self.observation_no = next_document_number('LLF', self.plant)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.observation_no} - {self.asset.asset_id}'


class ModificationOrder(TimeStampedModel):
    CHANGE_TYPES = [('PROCESS', 'Process'), ('EQUIPMENT', 'Equipment'), ('INSTRUMENT', 'Instrument'), ('ELECTRICAL', 'Electrical'), ('CIVIL', 'Civil'), ('DOCUMENT', 'Document'), ('OTHER', 'Other')]
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'), ('SUBMITTED', 'Submitted'), ('REVIEWED', 'Reviewed'), ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'), ('IN_PROGRESS', 'In Progress'), ('COMPLETED', 'Completed'), ('CLOSED', 'Closed'),
    ]
    mod_order_no = models.CharField(max_length=80, unique=True, blank=True)
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name='modification_orders')
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name='modification_orders')
    work_centre = models.ForeignKey(WorkCentre, on_delete=models.PROTECT, related_name='modification_orders')
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='requested_modification_orders')
    assigned_approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='assigned_modification_orders')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='approved_modification_orders')
    requested_date = models.DateField(default=timezone.localdate)
    change_type = models.CharField(max_length=20, choices=CHANGE_TYPES)
    title = models.CharField(max_length=200)
    current_condition = models.TextField()
    proposed_change = models.TextField()
    reason = models.TextField()
    safety_impact = models.TextField(blank=True)
    quality_impact = models.TextField(blank=True)
    environment_impact = models.TextField(blank=True)
    production_impact = models.TextField(blank=True)
    risk_assessment = models.TextField()
    implementation_plan = models.TextField()
    rollback_plan = models.TextField()
    validation_plan = models.TextField(blank=True)
    attachment = models.FileField(upload_to='moc/', blank=True, null=True, validators=DOCUMENT_VALIDATORS)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    approval_remarks = models.TextField(blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-requested_date', '-created_at']

    def save(self, *args, **kwargs):
        if self.asset_id:
            self.plant = self.asset.plant
        if not self.mod_order_no:
            from .services.numbering import next_document_number
            self.mod_order_no = next_document_number('MOC', self.plant)
        super().save(*args, **kwargs)

    @property
    def is_locked(self):
        return bool(self.locked_at or self.status in ['APPROVED', 'IN_PROGRESS', 'COMPLETED', 'CLOSED'])

    def __str__(self):
        return f'{self.mod_order_no} - {self.title}'


class SparePart(TimeStampedModel):
    ITEM_CATEGORY_CHOICES = [
        ('MECHANICAL', 'Mechanical'), ('ELECTRICAL', 'Electrical'), ('INSTRUMENTATION', 'Instrumentation'),
        ('CONSUMABLE', 'Consumable'), ('SAFETY', 'Safety'), ('SERVICE', 'Service'), ('OTHER', 'Other'),
    ]
    ITEM_CLASS_CHOICES = [('CRITICAL', 'Critical Spare'), ('NON_CRITICAL', 'Non Critical'), ('FAST_MOVING', 'Fast Moving'), ('SLOW_MOVING', 'Slow Moving'), ('INSURANCE', 'Insurance Spare'), ('OTHER', 'Other')]
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name='spare_parts')
    part_code = models.CharField(max_length=60)
    item_no = models.CharField(max_length=60)
    name = models.CharField(max_length=180)
    item_description = models.TextField()
    item_category = models.CharField(max_length=40, choices=ITEM_CATEGORY_CHOICES, default='OTHER')
    item_class = models.CharField(max_length=40, choices=ITEM_CLASS_CHOICES, default='OTHER')
    unit = models.CharField(max_length=30, default='Nos')
    current_stock = models.DecimalField(max_digits=14, decimal_places=3, default=0, validators=NON_NEGATIVE_DECIMAL)
    minimum_stock = models.DecimalField(max_digits=14, decimal_places=3, default=0, validators=NON_NEGATIVE_DECIMAL)
    maximum_stock = models.DecimalField(max_digits=14, decimal_places=3, default=0, validators=NON_NEGATIVE_DECIMAL)
    item_rate = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=NON_NEGATIVE_DECIMAL)
    tax_code = models.CharField(max_length=30, blank=True)
    preferred_vendor = models.CharField(max_length=150, blank=True)
    procurement_type = models.CharField(max_length=20, choices=[('STOCK', 'Stock'), ('NON_STOCK', 'Non-stock'), ('SERVICE', 'Service')], default='STOCK')
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['plant__code', 'item_no']
        constraints = [
            models.UniqueConstraint(fields=['plant', 'item_no'], name='uniq_plant_item_no'),
            models.UniqueConstraint(fields=['plant', 'part_code'], name='uniq_plant_part_code'),
        ]

    @property
    def is_low_stock(self):
        return self.current_stock <= self.minimum_stock

    @property
    def stock_value(self):
        return self.current_stock * self.item_rate

    @property
    def reserved_stock(self):
        return self.inventory_reservations.filter(status__in=['ACTIVE', 'PARTIAL']).aggregate(total=models.Sum('quantity'))['total'] or Decimal('0')

    @property
    def available_stock(self):
        return max(Decimal('0'), self.current_stock - self.reserved_stock)

    def __str__(self):
        return f'{self.item_no} - {self.name}'


class AssetBOM(TimeStampedModel):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='bom_items')
    spare_part = models.ForeignKey(SparePart, on_delete=models.PROTECT, related_name='asset_boms')
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1, validators=POSITIVE_DECIMAL)
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['asset', 'spare_part'], name='uniq_asset_spare_bom')]

    def __str__(self):
        return f'{self.asset.asset_id} - {self.spare_part.item_no}'


class StoreLocation(TimeStampedModel):
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name='store_locations')
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=120)
    bin_code = models.CharField(max_length=50, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['plant__code', 'code', 'bin_code']
        constraints = [models.UniqueConstraint(fields=['plant', 'code', 'bin_code'], name='uniq_store_location_bin')]

    def __str__(self):
        suffix = f'/{self.bin_code}' if self.bin_code else ''
        return f'{self.plant.code}/{self.code}{suffix}'


class InventoryBalance(TimeStampedModel):
    item = models.ForeignKey(SparePart, on_delete=models.PROTECT, related_name='balances')
    location = models.ForeignKey(StoreLocation, on_delete=models.PROTECT, related_name='balances')
    quantity = models.DecimalField(max_digits=14, decimal_places=3, default=0, validators=NON_NEGATIVE_DECIMAL)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['item', 'location'], name='uniq_item_location_balance')]

    def clean(self):
        if self.item_id and self.location_id and self.item.plant_id != self.location.plant_id:
            raise ValidationError('Item and store location must belong to the same plant.')

    def __str__(self):
        return f'{self.item.item_no} @ {self.location}: {self.quantity}'


class StockTransaction(TimeStampedModel):
    TYPE_CHOICES = [
        ('RECEIPT', 'Receipt'), ('ISSUE', 'Issue'), ('TRANSFER_OUT', 'Transfer Out'),
        ('TRANSFER_IN', 'Transfer In'), ('ADJUSTMENT', 'Adjustment'), ('RETURN', 'Return'), ('REVERSAL', 'Reversal'),
    ]
    item = models.ForeignKey(SparePart, on_delete=models.PROTECT, related_name='stock_transactions')
    transaction_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    quantity = models.DecimalField(max_digits=14, decimal_places=3, validators=POSITIVE_DECIMAL)
    from_location = models.ForeignKey(StoreLocation, on_delete=models.PROTECT, null=True, blank=True, related_name='outgoing_transactions')
    to_location = models.ForeignKey(StoreLocation, on_delete=models.PROTECT, null=True, blank=True, related_name='incoming_transactions')
    reference_type = models.CharField(max_length=50)
    reference_no = models.CharField(max_length=80)
    posted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='posted_stock_transactions')
    posted_at = models.DateTimeField(default=timezone.now)
    remarks = models.TextField(blank=True)
    reversed_transaction = models.OneToOneField('self', on_delete=models.PROTECT, null=True, blank=True, related_name='reversal')

    class Meta:
        ordering = ['-posted_at']
        constraints = [
            models.UniqueConstraint(fields=['reference_type', 'reference_no', 'transaction_type', 'item', 'from_location', 'to_location'], name='uniq_stock_reference_leg'),
        ]

    def __str__(self):
        return f'{self.reference_no} - {self.get_transaction_type_display()} {self.quantity}'


class PurchaseRequest(TimeStampedModel):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'), ('SUBMITTED', 'Submitted'), ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'), ('PROCESSING', 'Purchase Processing'), ('PO_CREATED', 'PO Created'),
        ('CLOSED', 'Closed'), ('CANCELLED', 'Cancelled'),
    ]
    request_no = models.CharField(max_length=80, unique=True, blank=True)
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name='purchase_requests')
    work_centre = models.ForeignKey(WorkCentre, on_delete=models.PROTECT, related_name='purchase_requests')
    work_order = models.ForeignKey(WorkOrder, on_delete=models.PROTECT, null=True, blank=True, related_name='purchase_requests')
    source_operation = models.ForeignKey(WorkOrderOperation, on_delete=models.PROTECT, null=True, blank=True, related_name='purchase_requests')
    item = models.ForeignKey(SparePart, on_delete=models.PROTECT, related_name='purchase_requests')
    request_date = models.DateField(default=timezone.localdate)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='purchase_requests')
    assigned_hod = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='assigned_purchase_requests')
    quantity = models.DecimalField(max_digits=14, decimal_places=3, validators=POSITIVE_DECIMAL)
    required_date = models.DateField(null=True, blank=True)
    purpose = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='submitted_purchase_requests')
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='approved_purchase_requests')
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_remarks = models.TextField(blank=True)
    rejected_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='rejected_purchase_requests')
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ['-request_date', '-created_at']

    def clean(self):
        if self.item_id and self.item.plant_id != self.plant_id:
            raise ValidationError({'item': 'Item must belong to the selected plant.'})
        if self.work_centre_id and self.work_centre.plant_id != self.plant_id:
            raise ValidationError({'work_centre': 'Work centre must belong to the selected plant.'})
        if self.work_order_id and self.work_order.plant_id != self.plant_id:
            raise ValidationError({'work_order': 'Work order must belong to the selected plant.'})
        if self.source_operation_id and (not self.work_order_id or self.source_operation.work_order_id != self.work_order_id):
            raise ValidationError({'source_operation': 'Source operation must belong to the selected work order.'})
        if self.assigned_hod_id == self.requested_by_id:
            raise ValidationError({'assigned_hod': 'Requester cannot approve their own purchase request.'})

    def save(self, *args, **kwargs):
        if not self.request_no:
            from .services.numbering import next_document_number
            self.request_no = next_document_number('PR', self.plant)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.request_no} - {self.item}'


class PurchaseRequestApprovalHistory(models.Model):
    ACTION_CHOICES = [
        ('CREATED', 'Created'), ('SUBMITTED', 'Submitted'), ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'), ('RESUBMITTED', 'Resubmitted'), ('PROCESSING', 'Processing'),
        ('PO_CREATED', 'PO Created'), ('CANCELLED', 'Cancelled'),
    ]
    purchase_request = models.ForeignKey(PurchaseRequest, on_delete=models.CASCADE, related_name='approval_history')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    previous_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20)
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='purchase_request_actions')
    remarks = models.TextField(blank=True)
    performed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['performed_at']

    def __str__(self):
        return f'{self.purchase_request.request_no} - {self.action}'


class PurchaseOrder(TimeStampedModel):
    PO_TYPE_CHOICES = [('MATERIAL', 'Material PO'), ('SERVICE', 'Service PO'), ('IN_COMPANY', 'In Company')]
    STATUS_CHOICES = [('DRAFT', 'Draft'), ('RELEASED', 'Released'), ('PARTIAL_RECEIVED', 'Partially Received'), ('RECEIVED', 'Received'), ('INVOICED', 'Invoiced'), ('CLOSED', 'Closed'), ('CANCELLED', 'Cancelled')]
    po_number = models.CharField(max_length=80, unique=True, blank=True)
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name='purchase_orders')
    po_type = models.CharField(max_length=20, choices=PO_TYPE_CHOICES, default='MATERIAL')
    purchase_request = models.ForeignKey(PurchaseRequest, on_delete=models.PROTECT, related_name='purchase_orders')
    vendor = models.CharField(max_length=180)
    order_date = models.DateField(default=timezone.localdate)
    item = models.ForeignKey(SparePart, on_delete=models.PROTECT, related_name='purchase_orders')
    description = models.TextField(blank=True)
    quantity = models.DecimalField(max_digits=14, decimal_places=3, validators=POSITIVE_DECIMAL)
    unit_rate = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=NON_NEGATIVE_DECIMAL)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='DRAFT')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_purchase_orders')
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ['-order_date', '-created_at']
        constraints = [
            models.UniqueConstraint(fields=['purchase_request'], name='uniq_po_per_purchase_request'),
        ]

    @property
    def total_amount(self):
        return self.quantity * self.unit_rate

    @property
    def expected_po_type(self):
        if not self.purchase_request_id:
            return self.po_type
        pr = self.purchase_request
        is_external_service = bool(
            pr.source_operation_id and pr.source_operation.execution_type == 'EXTERNAL'
            and pr.source_operation.service_item_id == pr.item_id
        )
        return 'SERVICE' if pr.item.procurement_type == 'SERVICE' or is_external_service else 'MATERIAL'

    def clean(self):
        if self.purchase_request_id and self.purchase_request.status not in ['APPROVED', 'PROCESSING', 'PO_CREATED']:
            raise ValidationError({'purchase_request': 'A PO can only be created from an approved purchase request.'})
        if self.purchase_request_id and self.purchase_request.plant_id != self.plant_id:
            raise ValidationError({'purchase_request': 'Purchase request must belong to the selected plant.'})
        if self.item_id and self.item.plant_id != self.plant_id:
            raise ValidationError({'item': 'Item must belong to the selected plant.'})
        if self.purchase_request_id and self.quantity != self.purchase_request.quantity:
            raise ValidationError({'quantity': 'For the current one-stage workflow, PO quantity must equal the approved PR quantity.'})
        if self.purchase_request_id and self.po_type != self.expected_po_type:
            raise ValidationError({'po_type': f'PO type must be {self.expected_po_type} for this purchase request.'})

    def save(self, *args, **kwargs):
        if self.purchase_request_id:
            self.plant = self.purchase_request.plant
            self.item = self.purchase_request.item
            self.po_type = self.expected_po_type
        if self._state.adding:
            self.status = 'DRAFT'
        if not self.po_number:
            from .services.numbering import next_document_number
            self.po_number = next_document_number('PO', self.plant)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.po_number} - {self.vendor}'


class GoodsReceipt(TimeStampedModel):
    STATUS_CHOICES = [('DRAFT', 'Draft'), ('POSTED', 'Posted / MIGO Completed'), ('CANCELLED', 'Cancelled')]
    receipt_no = models.CharField(max_length=80, unique=True, blank=True)
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name='goods_receipts')
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name='goods_receipts')
    item = models.ForeignKey(SparePart, on_delete=models.PROTECT, related_name='goods_receipts')
    received_date = models.DateField(default=timezone.localdate)
    quantity_received = models.DecimalField(max_digits=14, decimal_places=3, validators=POSITIVE_DECIMAL)
    received_location = models.ForeignKey(StoreLocation, on_delete=models.PROTECT, related_name='goods_receipts')
    migo_reference = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='DRAFT')
    posted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='posted_goods_receipts')
    posted_at = models.DateTimeField(null=True, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ['-received_date', '-created_at']

    def clean(self):
        if self.purchase_order_id and self.purchase_order.plant_id != self.plant_id:
            raise ValidationError('Purchase order must belong to the selected plant.')
        if self.purchase_order_id and self.purchase_order.po_type != 'MATERIAL':
            raise ValidationError({'purchase_order': 'Goods receipts require a Material PO.'})
        if self.purchase_order_id and self.purchase_order.status not in {'RELEASED', 'PARTIAL_RECEIVED'}:
            raise ValidationError({'purchase_order': 'Goods receipts require a Released or Partially Received Material PO.'})
        if self.received_location_id and self.received_location.plant_id != self.plant_id:
            raise ValidationError('Store location must belong to the selected plant.')

    def save(self, *args, **kwargs):
        if self.purchase_order_id:
            self.plant = self.purchase_order.plant
            self.item = self.purchase_order.item
        if not self.receipt_no:
            from .services.numbering import next_document_number
            self.receipt_no = next_document_number('GRN', self.plant)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.receipt_no} - {self.item}'


class StockTransfer(TimeStampedModel):
    STATUS_CHOICES = [('DRAFT', 'Draft'), ('POSTED', 'Posted'), ('CANCELLED', 'Cancelled')]
    transfer_no = models.CharField(max_length=80, unique=True, blank=True)
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name='stock_transfers')
    item = models.ForeignKey(SparePart, on_delete=models.PROTECT, related_name='stock_transfers')
    transfer_date = models.DateField(default=timezone.localdate)
    from_location = models.ForeignKey(StoreLocation, on_delete=models.PROTECT, related_name='transfers_out')
    to_location = models.ForeignKey(StoreLocation, on_delete=models.PROTECT, related_name='transfers_in')
    quantity = models.DecimalField(max_digits=14, decimal_places=3, validators=POSITIVE_DECIMAL)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    posted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='posted_stock_transfers')
    posted_at = models.DateTimeField(null=True, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ['-transfer_date', '-created_at']

    def clean(self):
        if self.from_location_id == self.to_location_id:
            raise ValidationError({'to_location': 'Destination must differ from source.'})
        if self.item_id and self.item.plant_id != self.plant_id:
            raise ValidationError({'item': 'Item must belong to the selected plant.'})
        if self.from_location_id and self.from_location.plant_id != self.plant_id:
            raise ValidationError({'from_location': 'Source location must belong to the selected plant.'})
        if self.to_location_id and self.to_location.plant_id != self.plant_id:
            raise ValidationError({'to_location': 'Destination location must belong to the selected plant.'})

    def save(self, *args, **kwargs):
        if not self.transfer_no:
            from .services.numbering import next_document_number
            self.transfer_no = next_document_number('TRANSFER', self.plant)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.transfer_no} - {self.item}'


class MaterialIssue(TimeStampedModel):
    STATUS_CHOICES = [('DRAFT', 'Draft'), ('POSTED', 'Posted / Issued'), ('CANCELLED', 'Cancelled')]
    issue_no = models.CharField(max_length=80, unique=True, blank=True)
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name='material_issues')
    item = models.ForeignKey(SparePart, on_delete=models.PROTECT, related_name='material_issues')
    work_order = models.ForeignKey(WorkOrder, on_delete=models.PROTECT, null=True, blank=True, related_name='material_issues')
    operation = models.ForeignKey(WorkOrderOperation, on_delete=models.PROTECT, null=True, blank=True, related_name='material_issues')
    source_location = models.ForeignKey(StoreLocation, on_delete=models.PROTECT, related_name='material_issues')
    issue_date = models.DateField(default=timezone.localdate)
    quantity_issued = models.DecimalField(max_digits=14, decimal_places=3, validators=POSITIVE_DECIMAL)
    issued_to = models.CharField(max_length=150, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    posted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='posted_material_issues')
    posted_at = models.DateTimeField(null=True, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ['-issue_date', '-created_at']

    def clean(self):
        if self.item_id and self.item.plant_id != self.plant_id:
            raise ValidationError({'item': 'Item must belong to the selected plant.'})
        if self.source_location_id and self.source_location.plant_id != self.plant_id:
            raise ValidationError({'source_location': 'Store location must belong to the selected plant.'})
        if self.work_order_id and self.work_order.plant_id != self.plant_id:
            raise ValidationError({'work_order': 'Work order must belong to the selected plant.'})
        if self.operation_id and (not self.work_order_id or self.operation.work_order_id != self.work_order_id):
            raise ValidationError({'operation': 'Operation must belong to the selected work order.'})
        if self.work_order_id:
            if self.work_order.technical_lock or self.work_order.status not in {'RELEASED', 'IN_PROGRESS'}:
                raise ValidationError({'work_order': 'Material issue is only allowed for Released or In Progress work orders before TECO.'})
            if self.item_id and not self.operation_id:
                planned = WorkOrderSpare.objects.filter(work_order_id=self.work_order_id, spare_part_id=self.item_id)
                if planned.values('operation_id').distinct().count() > 1:
                    raise ValidationError({'operation': 'This spare is planned on multiple operations; select the operation before posting the material issue.'})

    def save(self, *args, **kwargs):
        if not self.issue_no:
            from .services.numbering import next_document_number
            self.issue_no = next_document_number('ISSUE', self.plant)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.issue_no} - {self.item}'


class ServiceEntrySheet(TimeStampedModel):
    STATUS_CHOICES = [('DRAFT', 'Draft'), ('ACCEPTED', 'Accepted'), ('REJECTED', 'Rejected'), ('CANCELLED', 'Cancelled')]
    entry_no = models.CharField(max_length=80, unique=True, blank=True)
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name='service_entries')
    work_order_operation = models.ForeignKey(WorkOrderOperation, on_delete=models.PROTECT, null=True, blank=True, related_name='service_entries')
    service_date = models.DateField(default=timezone.localdate)
    description = models.TextField()
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=1, validators=POSITIVE_DECIMAL)
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=NON_NEGATIVE_DECIMAL)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_service_entries')
    accepted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='accepted_service_entries')
    accepted_at = models.DateTimeField(null=True, blank=True)
    acceptance_notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-service_date', '-created_at']

    def clean(self):
        if self.purchase_order_id and self.purchase_order.po_type != 'SERVICE':
            raise ValidationError({'purchase_order': 'Service entry sheets require a Service PO.'})
        if self.purchase_order_id and self.purchase_order.status not in {'RELEASED', 'PARTIAL_RECEIVED'}:
            raise ValidationError({'purchase_order': 'Service entry requires a Released or Partially Received service PO.'})
        if self.work_order_operation_id and self.purchase_order_id:
            if self.purchase_order.purchase_request.source_operation_id != self.work_order_operation_id:
                raise ValidationError({'work_order_operation': 'Operation must match the source operation of the service PO.'})
        if self.purchase_order_id:
            accepted = self.purchase_order.service_entries.filter(status='ACCEPTED').exclude(pk=self.pk)
            accepted_qty = accepted.aggregate(total=models.Sum('quantity'))['total'] or Decimal('0')
            accepted_amount = accepted.aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
            if accepted_qty + self.quantity > self.purchase_order.quantity:
                raise ValidationError({'quantity': f'Service quantity exceeds PO balance. Remaining quantity: {self.purchase_order.quantity - accepted_qty}.'})
            if accepted_amount + self.amount > self.purchase_order.total_amount:
                raise ValidationError({'amount': f'Service value exceeds PO balance. Remaining value: {self.purchase_order.total_amount - accepted_amount}.'})

    def save(self, *args, **kwargs):
        if not self.entry_no:
            from .services.numbering import next_document_number
            self.entry_no = next_document_number('SES', self.purchase_order.plant)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.entry_no} - {self.purchase_order.po_number}'


class VendorInvoice(TimeStampedModel):
    CLEARANCE_STATUS_CHOICES = [('PENDING', 'Pending with Accounts'), ('CLEARED', 'Cleared by Accounts'), ('HOLD', 'On Hold')]
    PAYMENT_STATUS_CHOICES = [('NOT_RELEASED', 'Payment Not Released'), ('RELEASED', 'Payment Released'), ('PARTIAL', 'Partially Paid')]
    invoice_no = models.CharField(max_length=80, unique=True)
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name='vendor_invoices')
    goods_receipt = models.ForeignKey(GoodsReceipt, on_delete=models.PROTECT, null=True, blank=True, related_name='vendor_invoices')
    invoice_date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=NON_NEGATIVE_DECIMAL)
    accounts_clearance_status = models.CharField(max_length=20, choices=CLEARANCE_STATUS_CHOICES, default='PENDING')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='NOT_RELEASED')
    cleared_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='cleared_vendor_invoices')
    clearance_notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-invoice_date', '-created_at']

    def clean(self):
        if self.goods_receipt_id and self.goods_receipt.purchase_order_id != self.purchase_order_id:
            raise ValidationError({'goods_receipt': 'Goods receipt must belong to the selected purchase order.'})
        if self.purchase_order_id:
            po = self.purchase_order
            if po.po_type == 'MATERIAL':
                received = po.goods_receipts.filter(status='POSTED').aggregate(total=models.Sum('quantity_received'))['total'] or Decimal('0')
                if received < po.quantity:
                    raise ValidationError({'purchase_order': 'Material PO must be fully received / service accepted before invoice entry.'})
            else:
                accepted = po.service_entries.filter(status='ACCEPTED').aggregate(total=models.Sum('quantity'))['total'] or Decimal('0')
                if accepted < po.quantity:
                    raise ValidationError({'purchase_order': 'Service PO must be fully received / service accepted before invoice entry.'})
            existing = po.vendor_invoices.exclude(pk=self.pk).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
            if existing + self.amount > po.total_amount:
                raise ValidationError({'amount': 'Invoice amount exceeds remaining PO value.'})

    def __str__(self):
        return f'{self.invoice_no} - {self.get_payment_status_display()}'


class UtilityMeter(TimeStampedModel):
    UTILITY_TYPES = [
        ('STEAM', 'Steam'), ('WATER', 'Water'), ('CHILLED_WATER', 'Chilled Water'),
        ('BRINE', 'Brine'), ('DM_WATER', 'DM Water'), ('AIR', 'Compressed Air'),
        ('NITROGEN', 'Nitrogen'), ('ELECTRICITY', 'Electricity'),
    ]
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name='utility_meters')
    meter_code = models.CharField(max_length=60)
    name = models.CharField(max_length=150)
    utility_type = models.CharField(max_length=30, choices=UTILITY_TYPES)
    unit = models.CharField(max_length=30)
    location = models.CharField(max_length=180)
    target_per_day = models.DecimalField(max_digits=14, decimal_places=3, default=0, validators=NON_NEGATIVE_DECIMAL)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['plant__code', 'utility_type', 'meter_code']
        constraints = [models.UniqueConstraint(fields=['plant', 'meter_code'], name='uniq_plant_meter_code')]

    def __str__(self):
        return f'{self.plant.code}/{self.meter_code} - {self.name}'


class MeterReading(TimeStampedModel):
    meter = models.ForeignKey(UtilityMeter, on_delete=models.PROTECT, related_name='readings')
    reading_date = models.DateField()
    opening_reading = models.DecimalField(max_digits=16, decimal_places=3, validators=NON_NEGATIVE_DECIMAL)
    closing_reading = models.DecimalField(max_digits=16, decimal_places=3, validators=NON_NEGATIVE_DECIMAL)
    multiplier = models.DecimalField(max_digits=10, decimal_places=3, default=1, validators=POSITIVE_DECIMAL)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='meter_readings')
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ['-reading_date']
        constraints = [models.UniqueConstraint(fields=['meter', 'reading_date'], name='uniq_meter_reading_date')]

    def clean(self):
        if self.closing_reading < self.opening_reading:
            raise ValidationError({'closing_reading': 'Closing reading cannot be less than opening reading.'})

    @property
    def consumption(self):
        return (self.closing_reading - self.opening_reading) * self.multiplier

    def __str__(self):
        return f'{self.meter.meter_code} - {self.reading_date}'


class CAPEXProposal(TimeStampedModel):
    STATUS_CHOICES = [('DRAFT', 'Draft'), ('SUBMITTED', 'Submitted'), ('APPROVED', 'Approved'), ('REJECTED', 'Rejected'), ('CLOSED', 'Closed')]
    proposal_no = models.CharField(max_length=80, unique=True, blank=True)
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name='capex_proposals')
    work_centre = models.ForeignKey(WorkCentre, on_delete=models.PROTECT, related_name='capex_proposals')
    budget_year = models.PositiveIntegerField()
    cost_centre = models.CharField(max_length=80)
    title = models.CharField(max_length=200)
    justification = models.TextField()
    business_benefit = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=16, decimal_places=2, validators=POSITIVE_DECIMAL)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='requested_capex_proposals')
    assigned_approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='assigned_capex_proposals')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='approved_capex_proposals')
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_remarks = models.TextField(blank=True)
    attachment = models.FileField(upload_to='capex/', blank=True, null=True, validators=DOCUMENT_VALIDATORS)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.proposal_no:
            from .services.numbering import next_document_number
            self.proposal_no = next_document_number('CAPEX', self.plant)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.proposal_no} - {self.title}'


class AssetDisposalRequest(TimeStampedModel):
    DISPOSAL_METHODS = [('SCRAP', 'Scrap Sale'), ('TRANSFER', 'Transfer'), ('RETURN_VENDOR', 'Return to Vendor'), ('DONATION', 'Donation'), ('OTHER', 'Other')]
    STATUS_CHOICES = [('DRAFT', 'Draft'), ('SUBMITTED', 'Submitted'), ('APPROVED', 'Approved'), ('REJECTED', 'Rejected'), ('EXECUTED', 'Executed')]
    disposal_no = models.CharField(max_length=80, unique=True, blank=True)
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name='asset_disposals')
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name='disposal_requests')
    condition = models.TextField()
    reason = models.TextField()
    estimated_value = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=NON_NEGATIVE_DECIMAL)
    disposal_method = models.CharField(max_length=20, choices=DISPOSAL_METHODS)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='requested_asset_disposals')
    assigned_approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='assigned_asset_disposals')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='approved_asset_disposals')
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_remarks = models.TextField(blank=True)
    evidence = models.FileField(upload_to='asset_disposal/', blank=True, null=True, validators=DOCUMENT_VALIDATORS)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if self.asset_id:
            self.plant = self.asset.plant
        if not self.disposal_no:
            from .services.numbering import next_document_number
            self.disposal_no = next_document_number('DISPOSAL', self.plant)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.disposal_no} - {self.asset.asset_id}'


class AuditLog(models.Model):
    ACTION_CHOICES = [('CREATE', 'Create'), ('UPDATE', 'Update'), ('DELETE', 'Delete'), ('STATUS', 'Status Change'), ('LOGIN', 'Login'), ('SECURITY', 'Security Event')]
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=120)
    object_reference = models.CharField(max_length=180, blank=True)
    object_pk = models.CharField(max_length=80, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    previous_values = models.JSONField(default=dict, blank=True)
    new_values = models.JSONField(default=dict, blank=True)
    remarks = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        permissions = [('view_full_audit_log', 'Can view full audit log')]

    def __str__(self):
        return f'{self.action} - {self.model_name} - {self.object_reference}'
