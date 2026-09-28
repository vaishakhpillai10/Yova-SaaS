import calendar
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction, models
from django.utils import timezone

from asset_mgmt.models import PMCall, PMPlan, WorkOrder, WorkOrderOperation, WorkOrderSpare
from asset_mgmt.services.sap_pm import pm_plan_is_due, due_strategy_package_ids


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def next_date_from_completion(plan: PMPlan, completed_date: date) -> date:
    if plan.frequency_unit == 'DAYS':
        return completed_date + timedelta(days=plan.frequency_value)
    if plan.frequency_unit == 'WEEKS':
        return completed_date + timedelta(weeks=plan.frequency_value)
    if plan.frequency_unit == 'MONTHS':
        return add_months(completed_date, plan.frequency_value)
    return plan.next_due_date


def calculate_next_due_date(plan: PMPlan) -> date | None:
    if plan.scheduling_mode == 'COMPLETION' and plan.last_completed_date:
        return next_date_from_completion(plan, plan.last_completed_date)
    if plan.frequency_unit == 'DAYS':
        return plan.next_due_date + timedelta(days=plan.frequency_value)
    if plan.frequency_unit == 'WEEKS':
        return plan.next_due_date + timedelta(weeks=plan.frequency_value)
    if plan.frequency_unit == 'MONTHS':
        return add_months(plan.next_due_date, plan.frequency_value)
    return None


def _task_source(plan):
    if plan.task_list_id:
        qs = plan.task_list.operations.select_related('work_centre', 'strategy_package').prefetch_related('materials').order_by('sequence')
        if plan.strategy_id and plan.strategy_packages.exists():
            due_packages = due_strategy_package_ids(plan)
            qs = qs.filter(models.Q(strategy_package__isnull=True) | models.Q(strategy_package_id__in=due_packages))
        return list(qs)
    return list(plan.tasks.order_by('sequence'))


def _pm_call_snapshot(plan: PMPlan, today, reasons):
    if plan.frequency_unit == 'RUNNING_HOURS':
        trigger = 'COUNTER'
        due_reading = plan.next_counter_due
        token = f'counter-{due_reading}'
        due_date = None
    elif plan.strategy_id and plan.strategy_packages.exists():
        trigger = 'STRATEGY'
        due_reading = None
        due_date = plan.next_due_date
        package_ids = '-'.join(str(x) for x in sorted(due_strategy_package_ids(plan, today))) or 'base'
        token = f'strategy-{package_ids}-{due_date or today}'
    elif plan.counters.filter(active=True).exists():
        trigger = 'MULTI_COUNTER'
        due_reading = None
        due_date = plan.next_due_date
        counter_state = '-'.join(f'{c.pk}:{c.next_due_reading}' for c in plan.counters.filter(active=True).order_by('pk'))
        token = f'multi-{counter_state or today}'
    else:
        trigger = 'CALENDAR'
        due_reading = None
        due_date = plan.next_due_date
        token = f'calendar-{due_date or today}'
    call_key = f'PMCALL-{plan.pk}-{token}'[:180]
    return call_key, trigger, due_date, due_reading, '; '.join(reasons)


def ensure_due_pm_call(plan: PMPlan, today=None, reasons=None):
    """Persist one immutable PM occurrence used by compliance and WO generation."""
    today = today or timezone.localdate()
    reasons = reasons or pm_plan_is_due(plan, today)[1]
    call_key, trigger, due_date, due_reading, reason_text = _pm_call_snapshot(plan, today, reasons)
    call, _ = PMCall.objects.get_or_create(
        call_key=call_key,
        defaults={'pm_plan': plan, 'trigger_type': trigger, 'call_date': today, 'due_date': due_date,
                  'due_reading': due_reading, 'reason': reason_text, 'status': 'DUE'},
    )
    return call


@transaction.atomic
def generate_pm_work_order(plan: PMPlan, user, *, advance_due_date: bool = True) -> WorkOrder:
    locked_plan = PMPlan.objects.select_for_update().select_related(
        'plant', 'asset', 'work_centre', 'responsible_user', 'task_list', 'strategy', 'counter_meter'
    ).prefetch_related('tasks', 'task_list__operations__materials', 'counters__meter', 'strategy_packages__package').get(pk=plan.pk)

    if not locked_plan.active:
        raise ValidationError('The PM plan is inactive.')
    due, reasons = pm_plan_is_due(locked_plan)
    if not due:
        raise ValidationError('PM plan is not due yet.')
    pm_call = ensure_due_pm_call(locked_plan, timezone.localdate(), reasons)
    if pm_call.work_order_id and pm_call.status not in {'CANCELLED'}:
        raise ValidationError(f'PM call already generated work order {pm_call.work_order.wo_number}.')
    if WorkOrder.objects.filter(pm_plan=locked_plan).exclude(status__in=['CLOSED', 'CANCELLED']).exists():
        raise ValidationError('An open work order already exists for this PM plan.')

    task_rows = _task_source(locked_plan)
    now = timezone.now()
    checklist_lines = []
    tools = []
    total_hours = Decimal('0')
    if locked_plan.task_list_id:
        for task in task_rows:
            checklist_lines.append(f'{task.sequence}. {task.description}')
            if task.safety_instruction:
                checklist_lines[-1] += f' | Safety: {task.safety_instruction}'
            if task.required_tools:
                tools.append(task.required_tools)
            total_hours += task.planned_hours
    else:
        for task in task_rows:
            checklist_lines.append(f'{task.sequence}. {task.task}' + (f' | Safety: {task.safety_instruction}' if task.safety_instruction else ''))
            if task.required_tools:
                tools.append(task.required_tools)
        total_hours = locked_plan.estimated_duration_hours

    duration = total_hours or locked_plan.estimated_duration_hours
    supervisor = locked_plan.responsible_user
    try:
        from .workflows import choose_hod
        supervisor = choose_hod(locked_plan.responsible_user or user, locked_plan.plant, locked_plan.work_centre)
    except ValidationError:
        # Keep generation possible in minimally configured demo/client environments; planning will still require a supervisor.
        supervisor = locked_plan.responsible_user
    wo = WorkOrder.objects.create(
        plant=locked_plan.plant,
        asset=locked_plan.asset,
        work_centre=locked_plan.work_centre,
        pm_plan=locked_plan,
        created_by=user,
        assigned_to=locked_plan.responsible_user,
        supervisor=supervisor,
        work_type='PREVENTIVE',
        activity_type='ROUTINE',
        priority='MEDIUM',
        job_description=locked_plan.name + (f" | Due because: {', '.join(reasons)}" if reasons else ''),
        checklist='\n'.join(checklist_lines),
        required_tools='\n'.join(dict.fromkeys(filter(None, tools))),
        planned_start=now,
        planned_end=now + timedelta(hours=float(duration)),
        permit_required=locked_plan.permit_required,
        status='DRAFT',
    )

    if locked_plan.task_list_id:
        op_map = {}
        for task in task_rows:
            op = WorkOrderOperation.objects.create(
                work_order=wo,
                sequence=task.sequence,
                description=task.description,
                work_centre=task.work_centre,
                assigned_to=locked_plan.responsible_user,
                execution_stage=task.execution_stage,
                execution_type=task.execution_type,
                control_key='PM03' if task.execution_type == 'EXTERNAL' else 'PM01',
                planned_hours=task.planned_hours,
                persons_required=task.persons_required,
                vendor=task.vendor,
                service_item=task.service_item,
                external_service_description=task.external_service_description,
                notes=task.safety_instruction,
            )
            op_map[task.pk] = op
            for material in task.materials.select_related('spare_part'):
                WorkOrderSpare.objects.create(
                    work_order=wo, operation=op, spare_part=material.spare_part,
                    procurement_type='NON_STOCK' if material.spare_part.procurement_type != 'STOCK' else 'STOCK',
                    quantity_required=material.quantity,
                )
    else:
        count = max(len(task_rows), 1)
        if not task_rows:
            WorkOrderOperation.objects.create(
                work_order=wo, sequence=10, description=f'Perform {locked_plan.name}',
                work_centre=locked_plan.work_centre, assigned_to=locked_plan.responsible_user,
                execution_stage='MAIN', execution_type='INTERNAL', control_key='PM01',
                planned_hours=locked_plan.estimated_duration_hours, status='PENDING',
            )
        for task in task_rows:
            WorkOrderOperation.objects.create(
                work_order=wo,
                sequence=task.sequence,
                description=task.task + (f' | Expected: {task.expected_result}' if task.expected_result else ''),
                work_centre=locked_plan.work_centre,
                assigned_to=locked_plan.responsible_user,
                planned_hours=locked_plan.estimated_duration_hours / count,
                notes=task.safety_instruction,
            )

    pm_call.work_order = wo
    pm_call.status = 'GENERATED'
    pm_call.save(update_fields=['work_order', 'status', 'updated_at'])

    next_due = calculate_next_due_date(locked_plan)
    if advance_due_date and next_due and locked_plan.scheduling_mode == 'FIXED':
        locked_plan.next_due_date = next_due
        locked_plan.save(update_fields=['next_due_date', 'updated_at'])
    return wo
