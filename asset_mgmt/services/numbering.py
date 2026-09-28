from django.db import transaction
from django.utils import timezone

from asset_mgmt.models import DocumentSequence


def next_document_number(document_type, plant=None, custom_prefix=None):
    """Generate a transaction-safe, plant/year scoped document number."""
    year = timezone.localdate().year
    with transaction.atomic():
        sequence, _ = DocumentSequence.objects.select_for_update().get_or_create(
            document_type=document_type,
            plant=plant,
            year=year,
            defaults={'last_number': 0},
        )
        sequence.last_number += 1
        sequence.save(update_fields=['last_number'])
    prefix = custom_prefix or document_type
    plant_code = plant.code if plant else 'GLOBAL'
    return f'{prefix}-{plant_code}-{year}-{sequence.last_number:06d}'
