from django.core.exceptions import PermissionDenied
from django.db.models import Q

from .models import UserAssignment


def is_admin(user):
    return bool(user and user.is_authenticated and (user.is_superuser or user.groups.filter(name='Admin').exists()))


def is_asset_admin(user):
    return bool(user and user.is_authenticated and user.groups.filter(name='Asset Admin').exists())


def is_manager(user):
    return bool(user and user.is_authenticated and (is_admin(user) or user.groups.filter(name__in=['Manager', 'HOD']).exists()))


def user_plant_ids(user):
    if not user or not user.is_authenticated:
        return []
    if is_admin(user) or is_asset_admin(user):
        return None
    return list(UserAssignment.objects.filter(user=user, active=True).values_list('plant_id', flat=True).distinct())


def user_workcentre_ids(user):
    if not user or not user.is_authenticated:
        return []
    if is_admin(user) or is_asset_admin(user):
        return None
    return list(UserAssignment.objects.filter(user=user, active=True, work_centre__isnull=False).values_list('work_centre_id', flat=True).distinct())


def is_hod_for(user, plant_id, work_centre_id=None):
    if is_admin(user):
        return True
    query = UserAssignment.objects.filter(user=user, plant_id=plant_id, designation__in=['HOD', 'PLANT_HEAD'], active=True)
    if work_centre_id:
        query = query.filter(Q(work_centre_id=work_centre_id) | Q(work_centre__isnull=True))
    return query.exists()


def is_plant_head_for(user, plant_id):
    if is_admin(user):
        return True
    return UserAssignment.objects.filter(
        user=user, plant_id=plant_id, designation='PLANT_HEAD', active=True
    ).exists()


def scope_queryset_for_user(queryset, user):
    """Apply plant scoping to models that expose plant directly or through common relations."""
    plant_ids = user_plant_ids(user)
    if plant_ids is None:
        return queryset
    if not plant_ids:
        return queryset.none()
    model_fields = {f.name for f in queryset.model._meta.get_fields()}
    if 'plant' in model_fields:
        return queryset.filter(plant_id__in=plant_ids)
    if 'asset' in model_fields:
        return queryset.filter(asset__plant_id__in=plant_ids)
    if 'plan' in model_fields:
        plan_model = queryset.model._meta.get_field('plan').related_model
        plan_fields = {f.name for f in plan_model._meta.get_fields()}
        if 'plant' in plan_fields:
            return queryset.filter(plan__plant_id__in=plant_ids)
        if 'asset' in plan_fields:
            return queryset.filter(plan__asset__plant_id__in=plant_ids)
    if 'pm_plan' in model_fields:
        return queryset.filter(pm_plan__plant_id__in=plant_ids)
    if 'work_order' in model_fields:
        return queryset.filter(work_order__plant_id__in=plant_ids)
    if 'meter' in model_fields:
        meter_model = queryset.model._meta.get_field('meter').related_model
        meter_fields = {f.name for f in meter_model._meta.get_fields()}
        if 'plant' in meter_fields:
            return queryset.filter(meter__plant_id__in=plant_ids)
        if 'asset' in meter_fields:
            return queryset.filter(meter__asset__plant_id__in=plant_ids)
    if 'purchase_order' in model_fields:
        return queryset.filter(purchase_order__plant_id__in=plant_ids)
    if 'item' in model_fields:
        return queryset.filter(item__plant_id__in=plant_ids)
    return queryset


def assert_object_access(user, obj):
    if is_admin(user):
        return
    plant_id = getattr(obj, 'plant_id', None)
    if not plant_id and getattr(obj, 'asset_id', None):
        plant_id = obj.asset.plant_id
    if not plant_id and getattr(obj, 'pm_plan_id', None):
        plant_id = obj.pm_plan.plant_id
    if not plant_id and getattr(obj, 'work_order_id', None):
        plant_id = obj.work_order.plant_id
    if not plant_id and getattr(obj, 'meter_id', None):
        plant_id = getattr(obj.meter, 'plant_id', None) or getattr(getattr(obj.meter, 'asset', None), 'plant_id', None)
    if not plant_id and getattr(obj, 'operation_id', None):
        plant_id = obj.operation.work_order.plant_id
    plant_ids = user_plant_ids(user) or []
    if plant_id and plant_id not in plant_ids:
        raise PermissionDenied('You do not have access to this plant record.')
