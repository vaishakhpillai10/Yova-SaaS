from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from ..models import MaintenanceRequest, WorkOrder, PermitToWork
from .sap_pm import (
    advance_pm_counters, dispatch_work_order, procurement_ready,
    reserve_or_procure_work_order, schedule_work_order, settle_work_order,
)

MR_TRANSITIONS = {
    'start_screening': ('REPORTED', 'SCREENING'),
    'request_info': ('SCREENING', 'NEED_INFO'),
    'accept': ('SCREENING', 'ACCEPTED'),
    'reject': ('SCREENING', 'REJECTED'),
    'resubmit': ('NEED_INFO', 'REPORTED'),
    'close': ('COMPLETED', 'CLOSED'),
}

# Each action owns its allowed source status(es). This is the single source of truth for WO state changes.
WO_TRANSITIONS = {
    'plan': (('DRAFT',), 'PLANNED'),
    'submit_approval': (('PLANNED',), 'PENDING_APPROVAL'),
    'approve': (('PENDING_APPROVAL',), 'APPROVED'),
    'reject_approval': (('PENDING_APPROVAL',), 'PLANNED'),
    'prepare': (('APPROVED',), 'PREPARATION'),
    'return_planning': (('APPROVED', 'PREPARATION', 'READY_TO_SCHEDULE', 'SCHEDULED', 'DISPATCHED'), 'PLANNED'),
    'ready_schedule': (('PREPARATION',), 'READY_TO_SCHEDULE'),
    'schedule': (('READY_TO_SCHEDULE',), 'SCHEDULED'),
    'dispatch': (('SCHEDULED',), 'DISPATCHED'),
    'release': (('DISPATCHED',), 'RELEASED'),
    'start': (('RELEASED',), 'IN_PROGRESS'),
    'complete': (('IN_PROGRESS',), 'COMPLETED'),
    'verify': (('COMPLETED',), 'VERIFIED'),
    'return_execution': (('COMPLETED', 'VERIFIED'), 'IN_PROGRESS'),
    'teco': (('VERIFIED',), 'TECO'),
    'cost_close': (('TECO',), 'COST_CLOSURE'),
    'close': (('COST_CLOSURE',), 'CLOSED'),
    'cancel': (('DRAFT', 'PLANNED', 'PENDING_APPROVAL', 'APPROVED', 'PREPARATION', 'READY_TO_SCHEDULE', 'SCHEDULED', 'DISPATCHED', 'RELEASED'), 'CANCELLED'),
}


def work_order_actions_for_status(status):
    return [action for action, (sources, _target) in WO_TRANSITIONS.items() if status in sources]


def _require(condition, message):
    if not condition:
        raise ValidationError(message)


@transaction.atomic
def transition_maintenance_request(request_obj: MaintenanceRequest, action: str, user, notes: str = ''):
    if action not in MR_TRANSITIONS:
        raise ValidationError('Unsupported maintenance-request action.')
    source, target = MR_TRANSITIONS[action]
    _require(request_obj.status == source, f'This action requires request status {source}.')
    if action in {'request_info', 'reject'}:
        _require(len((notes or '').strip()) >= 5, 'Please enter a clear screening reason (minimum 5 characters).')
    if action == 'accept' and request_obj.failure_mode:
        _require(request_obj.items.exists() or len(request_obj.failure_mode.strip()) >= 3, 'Add a notification item/catalog code or a clear failure mode before acceptance.')
    if action == 'close':
        _require(not request_obj.work_orders.exclude(status__in=['CLOSED', 'CANCELLED']).exists(), 'All linked work orders must be closed or cancelled before closing the notification.')
    if action in {'start_screening', 'request_info', 'accept', 'reject'}:
        request_obj.screened_by = user
        request_obj.screened_at = timezone.now()
        if notes:
            request_obj.screening_notes = notes.strip()
    request_obj.status = target
    request_obj.full_clean()
    request_obj.save()
    return request_obj


def validate_work_order_transition(work_order: WorkOrder, action: str, user=None, notes: str = ''):
    if action not in WO_TRANSITIONS:
        raise ValidationError('Unsupported work-order action.')
    sources, _ = WO_TRANSITIONS[action]
    _require(work_order.status in sources, f'This action is not valid from work-order status {work_order.status}.')

    if action in {'reject_approval', 'return_planning', 'return_execution', 'cancel'}:
        _require(len((notes or '').strip()) >= 5, 'A clear reason (minimum 5 characters) is required for this exception action.')

    if action == 'plan':
        _require(work_order.assigned_to_id, 'Assign a technician before planning the work order.')
        _require(work_order.supervisor_id, 'Assign a supervisor before planning the work order.')
        _require(work_order.planned_start and work_order.planned_end, 'Planned start and end are required.')
        _require(work_order.operations.exists(), 'Add at least one planned operation before moving to Planned.')
        _require(not work_order.operations.filter(planned_hours=0).exists(), 'Every active operation must have planned work hours.')

    if action == 'submit_approval':
        _require(work_order.operations.exists(), 'At least one operation is required before approval.')
        _require(work_order.assigned_to_id, 'Assign a technician before approval.')
        _require(work_order.supervisor_id, 'Assign a supervisor before approval.')
        _require(bool(work_order.job_description.strip()), 'Job description is required before approval.')

    if action == 'approve':
        _require(user is not None, 'Approving user is required.')
        _require(user.pk != work_order.created_by_id, 'Segregation of duties: the work-order creator cannot approve their own work order.')

    if action == 'return_planning':
        _require(not work_order.purchase_requests.filter(purchase_orders__isnull=False).exclude(purchase_orders__status='CANCELLED').exists(), 'Cancel/resolve created purchase orders before returning the work order to planning.')

    if action == 'ready_schedule':
        if work_order.priority in {'HIGH', 'URGENT'} or work_order.permit_required or work_order.loto_required:
            _require(work_order.risk_assessments.exists(), 'A risk assessment is required before scheduling high/urgent or permit/LOTO work.')
        for op in work_order.operations.filter(execution_type='EXTERNAL'):
            _require(op.service_item_id, f'External operation {op.sequence} requires a service item.')

    if action == 'schedule':
        _require(work_order.planned_start and work_order.planned_end, 'Planning dates are required for scheduling.')

    if action == 'dispatch':
        _require(not work_order.operations.filter(scheduled_start__isnull=True).exclude(status='CANCELLED').exists(), 'All active operations must be scheduled before dispatch.')
        for op in work_order.operations.exclude(status='CANCELLED').select_related('predecessor'):
            if op.predecessor_id:
                _require(op.predecessor.scheduled_end and op.scheduled_start >= op.predecessor.scheduled_end, f'Operation {op.sequence} is scheduled before predecessor {op.predecessor.sequence} completes.')

    if action == 'release':
        _require(work_order.assigned_to_id, 'A technician must be assigned before release.')
        _require(work_order.operations.exists(), 'Operations must be planned before release.')
        _require(procurement_ready(work_order), 'Materials/services are not ready: reserve stock or progress generated PRs before release.')
        if work_order.permit_required:
            _require(work_order.permits.filter(status='ISSUED').exists(), 'Required permit must be ISSUED before release.')
        if work_order.loto_required:
            _require(work_order.permits.filter(status='ISSUED', loto_applied=True).exists(), 'LOTO must be applied on an issued permit before release.')

    if action == 'complete':
        _require(work_order.actual_start, 'Actual start is missing. Start the work order before completion.')
        incomplete = work_order.operations.exclude(status__in=['COMPLETED', 'CANCELLED']).exists()
        _require(not incomplete, 'Final-confirm or cancel every operation before work completion.')
        _require(len((work_order.completion_notes or '').strip()) >= 3, 'Completion notes are required.')
        if work_order.work_type == 'BREAKDOWN':
            _require(bool((work_order.failure_mode or '').strip()), 'Failure mode is required for breakdown completion.')
            _require(bool((work_order.failure_cause or '').strip()), 'Failure cause is required for breakdown completion.')

    if action == 'verify':
        _require(not work_order.operations.filter(execution_stage='POST').exclude(status__in=['COMPLETED', 'CANCELLED']).exists(), 'Complete all POST/restoration operations before verification.')

    if action == 'return_execution':
        _require(not work_order.technical_lock, 'TECO work orders cannot be returned to execution.')

    if action == 'teco':
        open_permits = work_order.permits.exclude(status__in=['CLOSED', 'REJECTED']).exists()
        _require(not open_permits, 'Close all permits before TECO.')
        draft_issues = work_order.material_issues.filter(status='DRAFT').exists()
        _require(not draft_issues, 'Post or cancel all draft material issues before TECO.')
        _require(not work_order.confirmations.filter(confirmation_type='PARTIAL').exclude(operation__confirmations__confirmation_type='FINAL').exists(), 'Final-confirm all partially confirmed operations before TECO.')
        if work_order.maintenance_request_id and work_order.maintenance_request.production_stopped:
            _require(work_order.downtime_events.filter(downtime_type='BREAKDOWN').exists(), 'Record breakdown downtime before TECO because production was stopped.')

    if action == 'cost_close':
        calc = Decimal(work_order.calculated_actual_cost)
        if calc > 0:
            total_pct = work_order.settlement_rules.aggregate(total=Sum('percentage'))['total'] or Decimal('0')
            _require(total_pct == Decimal('100'), 'Settlement rules must total 100% before cost closure.')

    if action == 'close':
        _require(work_order.settlement_status in {'SETTLED', 'NOT_REQUIRED'}, 'Financial settlement must be complete before business closure.')
        _require(not work_order.purchase_requests.exclude(status__in=['CLOSED', 'CANCELLED', 'REJECTED']).exists(), 'Every purchase request must be closed/cancelled/rejected before business closure.')
        _require(not work_order.purchase_requests.filter(purchase_orders__isnull=False).exclude(purchase_orders__status__in=['CLOSED', 'CANCELLED']).exists(), 'Every linked purchase order must be financially/operationally closed before business closure.')

    if action == 'cancel':
        _require(not work_order.material_issues.filter(status='POSTED').exists(), 'A work order with posted material issues cannot be cancelled; complete and technically close it instead.')
        _require(not work_order.confirmations.exists(), 'A work order with execution confirmations cannot be cancelled; use the controlled completion path.')
        _require(not work_order.purchase_requests.filter(purchase_orders__isnull=False).exclude(purchase_orders__status='CANCELLED').exists(), 'Cancel linked purchase orders before cancelling this work order.')

    return True


def _release_planning_commitments(work_order):
    work_order.spares_used.all().update(quantity_reserved=Decimal('0'))
    for line in work_order.spares_used.all():
        line.reservations.filter(status__in=['ACTIVE', 'PARTIAL']).update(status='CANCELLED')
        if line.quantity_used >= line.quantity_required and line.quantity_required > 0:
            line.reservation_status = 'ISSUED'
        elif line.quantity_used > 0:
            line.reservation_status = 'PARTIAL'
        else:
            line.reservation_status = 'UNRESERVED'
        line.save(update_fields=['quantity_reserved', 'reservation_status', 'updated_at'])
    work_order.purchase_requests.filter(purchase_orders__isnull=True).exclude(status__in=['CLOSED', 'CANCELLED', 'REJECTED']).update(status='CANCELLED')


@transaction.atomic
def transition_work_order(work_order: WorkOrder, action: str, user, notes: str = ''):
    validate_work_order_transition(work_order, action, user=user, notes=notes)
    _, target = WO_TRANSITIONS[action]
    now = timezone.now()

    if action == 'approve':
        work_order.approved_by = user
        work_order.approved_at = now
        work_order.approval_notes = (notes or '').strip()
        if work_order.baseline_cost == 0:
            work_order.baseline_cost = work_order.estimated_cost
    elif action == 'reject_approval':
        work_order.approval_notes = f'Rejected / returned for replanning: {(notes or "").strip()}'
        work_order.approved_by = None
        work_order.approved_at = None
    elif action == 'prepare':
        reserve_or_procure_work_order(work_order, user)
        work_order.prepared_by = user
        work_order.prepared_at = now
        work_order.planned_cost = work_order.estimated_cost
    elif action == 'return_planning':
        _release_planning_commitments(work_order)
        work_order.operations.exclude(status='CANCELLED').update(status='PENDING', scheduled_start=None, scheduled_end=None, dispatched_at=None)
        work_order.prepared_by = None
        work_order.prepared_at = None
        work_order.ready_to_schedule_at = None
        work_order.scheduled_by = None
        work_order.scheduled_at = None
        work_order.dispatched_by = None
        work_order.dispatched_at = None
        work_order.approval_notes = f'Returned to planning: {(notes or "").strip()}'
    elif action == 'ready_schedule':
        work_order.ready_to_schedule_at = now
    elif action == 'schedule':
        schedule_work_order(work_order, user)
    elif action == 'dispatch':
        dispatch_work_order(work_order, user)
    elif action == 'release':
        work_order.released_by = user
        work_order.released_at = now
    elif action == 'start':
        if not work_order.actual_start:
            work_order.actual_start = now
        if work_order.asset.status != 'MAINTENANCE':
            work_order.asset.status = 'MAINTENANCE'
            work_order.asset.save(update_fields=['status', 'updated_at'])
    elif action == 'return_execution':
        work_order.actual_end = None
        work_order.completed_by = None
        work_order.verified_by = None
        work_order.verified_at = None
        work_order.completion_notes = ((work_order.completion_notes or '') + f'\nReturned to execution: {(notes or "").strip()}').strip()
    elif action == 'complete':
        if not work_order.actual_end:
            work_order.actual_end = now
        work_order.completed_by = user
    elif action == 'verify':
        work_order.verified_by = user
        work_order.verified_at = now
    elif action == 'teco':
        work_order.teco_by = user
        work_order.teco_at = now
        work_order.technical_lock = True
        # TECO releases unused reservations. It never claims unissued material was consumed.
        for line in work_order.spares_used.all():
            line.reservations.filter(status__in=['ACTIVE', 'PARTIAL']).update(status='CLOSED')
            line.quantity_reserved = Decimal('0')
            if line.quantity_used >= line.quantity_required and line.quantity_required > 0:
                line.reservation_status = 'ISSUED'
            elif line.quantity_used > 0:
                line.reservation_status = 'PARTIAL'
            else:
                line.reservation_status = 'UNRESERVED'
            line.save(update_fields=['quantity_reserved', 'reservation_status', 'updated_at'])
        if work_order.asset.status == 'MAINTENANCE':
            work_order.asset.status = 'RUNNING'
            work_order.asset.save(update_fields=['status', 'updated_at'])
        if work_order.pm_plan_id:
            advance_pm_counters(work_order.pm_plan)
            if hasattr(work_order, 'pm_call'):
                work_order.pm_call.status = 'COMPLETED'
                work_order.pm_call.completed_at = now
                work_order.pm_call.save(update_fields=['status', 'completed_at', 'updated_at'])
    elif action == 'cost_close':
        if Decimal(work_order.calculated_actual_cost) > 0:
            settle_work_order(work_order, user)
        else:
            work_order.actual_cost = Decimal('0')
            work_order.settlement_status = 'NOT_REQUIRED'
        work_order.cost_closed_by = user
        work_order.cost_closed_at = now
    elif action == 'close':
        work_order.closed_by = user
        work_order.closed_at = now
        work_order.business_completed_by = user
        work_order.business_completed_at = now
    elif action == 'cancel':
        _release_planning_commitments(work_order)
        work_order.approval_notes = f'Cancelled: {(notes or "").strip()}'
        if work_order.asset.status == 'MAINTENANCE':
            work_order.asset.status = 'RUNNING'
            work_order.asset.save(update_fields=['status', 'updated_at'])
        if work_order.pm_plan_id and hasattr(work_order, 'pm_call'):
            work_order.pm_call.status = 'CANCELLED'
            work_order.pm_call.save(update_fields=['status', 'updated_at'])

    work_order.status = target
    work_order.full_clean()
    work_order.save()

    mr = work_order.maintenance_request
    if mr:
        status_map = {'IN_PROGRESS': 'IN_PROGRESS', 'COMPLETED': 'COMPLETED', 'CLOSED': 'CLOSED'}
        if target == 'CANCELLED' and mr.status not in {'REJECTED', 'CLOSED'}:
            # The notification remains accepted so a replacement WO can be created if needed.
            mr.status = 'ACCEPTED'
            mr.save(update_fields=['status', 'updated_at'])
        elif target in status_map and mr.status not in {'REJECTED', 'CANCELLED'}:
            mr.status = status_map[target]
            mr.save(update_fields=['status', 'updated_at'])

    if work_order.pm_plan_id and target in {'TECO', 'CLOSED'}:
        plan = work_order.pm_plan
        if work_order.actual_end:
            plan.last_completed_date = timezone.localdate(work_order.actual_end)
            if plan.scheduling_mode == 'COMPLETION' and plan.frequency_unit != 'RUNNING_HOURS':
                from .pm import next_date_from_completion
                plan.next_due_date = next_date_from_completion(plan, plan.last_completed_date)
            plan.save()

    return work_order


PERMIT_TRANSITIONS = {
    'review': (('REQUESTED',), 'SAFETY_REVIEW'),
    'approve': (('SAFETY_REVIEW',), 'APPROVED'),
    'reject': (('SAFETY_REVIEW', 'APPROVED'), 'REJECTED'),
    'issue': (('APPROVED',), 'ISSUED'),
    'close': (('ISSUED',), 'CLOSED'),
}


@transaction.atomic
def transition_permit(permit: PermitToWork, action: str, user, notes: str = ''):
    if action not in PERMIT_TRANSITIONS:
        raise ValidationError('Unsupported permit action.')
    sources, target = PERMIT_TRANSITIONS[action]
    _require(permit.status in sources, f'This action is not valid from permit status {permit.status}.')
    if action == 'approve':
        _require(bool((permit.hazards or '').strip()), 'Hazards must be recorded before permit approval.')
        _require(bool((permit.ppe_required or '').strip()), 'Required PPE must be recorded before permit approval.')
        permit.approved_by_safety = user
    if action == 'issue':
        _require(permit.valid_from and permit.valid_to, 'Permit validity start/end must be defined before issue.')
        _require(permit.valid_to > permit.valid_from, 'Permit validity end must be after start.')
    if action == 'close' and notes:
        permit.closure_notes = notes.strip()
    permit.status = target
    permit.full_clean()
    permit.save()
    return permit
