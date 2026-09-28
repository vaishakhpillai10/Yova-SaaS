from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from asset_mgmt.models import PurchaseRequest, PurchaseRequestApprovalHistory
from asset_mgmt.permissions import is_admin, is_plant_head_for


def _history(pr, action, previous, new, user, remarks=''):
    PurchaseRequestApprovalHistory.objects.create(
        purchase_request=pr, action=action, previous_status=previous,
        new_status=new, performed_by=user, remarks=remarks,
    )


@transaction.atomic
def submit_purchase_request(pr, user):
    pr = PurchaseRequest.objects.select_for_update().get(pk=pr.pk)
    if pr.requested_by_id != user.id and not is_admin(user):
        raise PermissionDenied('Only the requester can submit this purchase request.')
    if pr.status not in ['DRAFT', 'REJECTED']:
        raise ValidationError('Only a draft or rejected purchase request can be submitted.')
    previous = pr.status
    pr.status = 'SUBMITTED'
    pr.submitted_by = user
    pr.submitted_at = timezone.now()
    pr.rejection_reason = ''
    pr.rejected_by = None
    pr.rejected_at = None
    pr.save(update_fields=['status', 'submitted_by', 'submitted_at', 'rejection_reason', 'rejected_by', 'rejected_at', 'updated_at'])
    _history(pr, 'RESUBMITTED' if previous == 'REJECTED' else 'SUBMITTED', previous, pr.status, user)
    return pr


@transaction.atomic
def approve_purchase_request(pr, user, remarks):
    pr = PurchaseRequest.objects.select_for_update().get(pk=pr.pk)
    if pr.status != 'SUBMITTED':
        raise ValidationError('Only a submitted purchase request can be approved.')
    if pr.requested_by_id == user.id:
        raise PermissionDenied('Self-approval is not allowed.')
    if pr.assigned_hod_id != user.id and not is_admin(user) and not is_plant_head_for(user, pr.plant_id):
        raise PermissionDenied('Only the assigned HOD can approve this purchase request.')
    previous = pr.status
    pr.status = 'APPROVED'
    pr.approved_by = user
    pr.approved_at = timezone.now()
    pr.approval_remarks = remarks
    pr.save(update_fields=['status', 'approved_by', 'approved_at', 'approval_remarks', 'updated_at'])
    _history(pr, 'APPROVED', previous, pr.status, user, remarks)
    return pr


@transaction.atomic
def reject_purchase_request(pr, user, reason):
    pr = PurchaseRequest.objects.select_for_update().get(pk=pr.pk)
    if pr.status != 'SUBMITTED':
        raise ValidationError('Only a submitted purchase request can be rejected.')
    if pr.requested_by_id == user.id:
        raise PermissionDenied('Self-approval is not allowed.')
    if pr.assigned_hod_id != user.id and not is_admin(user) and not is_plant_head_for(user, pr.plant_id):
        raise PermissionDenied('Only the assigned HOD can reject this purchase request.')
    previous = pr.status
    pr.status = 'REJECTED'
    pr.rejected_by = user
    pr.rejected_at = timezone.now()
    pr.rejection_reason = reason
    pr.save(update_fields=['status', 'rejected_by', 'rejected_at', 'rejection_reason', 'updated_at'])
    _history(pr, 'REJECTED', previous, pr.status, user, reason)
    return pr


@transaction.atomic
def mark_pr_processing(pr, user):
    pr = PurchaseRequest.objects.select_for_update().get(pk=pr.pk)
    if pr.status != 'APPROVED':
        raise ValidationError('Only an approved purchase request can be processed.')
    previous = pr.status
    pr.status = 'PROCESSING'
    pr.save(update_fields=['status', 'updated_at'])
    _history(pr, 'PROCESSING', previous, pr.status, user)
    return pr


def choose_hod(user, plant, work_centre):
    from asset_mgmt.models import UserAssignment

    assignment = user.plant_assignments.filter(
        plant=plant, work_centre=work_centre, active=True
    ).select_related('reporting_hod').first()
    if assignment and assignment.reporting_hod:
        valid_reporting_hod = UserAssignment.objects.filter(
            user=assignment.reporting_hod,
            plant=plant,
            designation__in=['HOD', 'PLANT_HEAD'],
            active=True,
        ).filter(work_centre=work_centre).exists() or UserAssignment.objects.filter(
            user=assignment.reporting_hod,
            plant=plant,
            designation='PLANT_HEAD',
            active=True,
        ).exists()
        if valid_reporting_hod:
            return assignment.reporting_hod
    hod = UserAssignment.objects.filter(plant=plant, work_centre=work_centre, designation='HOD', active=True).select_related('user').first()
    if not hod:
        hod = UserAssignment.objects.filter(plant=plant, designation='PLANT_HEAD', active=True).select_related('user').first()
    if not hod:
        raise ValidationError('No active HOD or Plant Head is assigned for this plant/work centre.')
    return hod.user
