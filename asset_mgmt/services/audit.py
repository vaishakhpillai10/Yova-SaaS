from __future__ import annotations

import json

from django.core.serializers.json import DjangoJSONEncoder
from django.forms.models import model_to_dict
from django.db.models import Model
from django.db.models.fields.files import FieldFile

from asset_mgmt.models import AuditLog


def client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return forwarded.split(',')[0].strip() if forwarded else request.META.get('REMOTE_ADDR')


def serialise_instance(instance):
    def json_safe(value):
        if isinstance(value, FieldFile):
            return value.name or ''
        if isinstance(value, Model):
            return value.pk
        if isinstance(value, dict):
            return {key: json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [json_safe(item) for item in value]
        # DjangoJSONEncoder covers dates, datetimes, Decimal, UUID and lazy
        # translation values while returning only JSON-native data.
        return json.loads(json.dumps(value, cls=DjangoJSONEncoder))

    return {key: json_safe(value) for key, value in model_to_dict(instance).items()}


def log_action(request, action, instance, previous=None, new=None, remarks=''):
    AuditLog.objects.create(
        action=action,
        model_name=instance.__class__.__name__,
        object_reference=str(instance),
        object_pk=str(instance.pk or ''),
        user=request.user if request and request.user.is_authenticated else None,
        previous_values=previous or {},
        new_values=new if new is not None else (serialise_instance(instance) if instance.pk else {}),
        remarks=remarks,
        ip_address=client_ip(request) if request else None,
    )
