from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from asset_mgmt.models import PMPlan
from asset_mgmt.services.pm import generate_pm_work_order
from asset_mgmt.services.sap_pm import pm_plan_is_due

User = get_user_model()


class Command(BaseCommand):
    help = 'Generate preventive-maintenance work orders for due calendar, strategy, running-hour and multi-counter PM plans.'

    def add_arguments(self, parser):
        parser.add_argument('--username', default='admin', help='User recorded as the WO creator.')
        parser.add_argument('--date', dest='run_date', help='Optional due date in YYYY-MM-DD format.')
        parser.add_argument('--dry-run', action='store_true', help='Show due plans without creating work orders.')

    def handle(self, *args, **options):
        try:
            run_date = date.fromisoformat(options['run_date']) if options.get('run_date') else timezone.localdate()
        except ValueError as exc:
            raise CommandError('--date must use YYYY-MM-DD.') from exc
        try:
            creator = User.objects.get(username=options['username'], is_active=True)
        except User.DoesNotExist as exc:
            raise CommandError(f"Active user '{options['username']}' was not found.") from exc

        plans = PMPlan.objects.filter(active=True, auto_generate_work_order=True).select_related('counter_meter').prefetch_related('counters__meter').order_by('next_due_date', 'pk')
        created = skipped = 0
        for plan in plans:
            due, reasons = pm_plan_is_due(plan, run_date)
            if not due:
                continue
            if options['dry_run']:
                self.stdout.write(f"DUE: {plan} ({'; '.join(reasons)})")
                continue
            try:
                wo = generate_pm_work_order(plan, creator)
                created += 1
                self.stdout.write(self.style.SUCCESS(f'Created {wo.wo_number} from {plan}.'))
            except ValidationError as exc:
                skipped += 1
                self.stdout.write(self.style.WARNING(f"Skipped {plan}: {'; '.join(exc.messages)}"))
        if options['dry_run']:
            self.stdout.write(self.style.SUCCESS('Dry run complete. No records were changed.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'PM generation complete: {created} created, {skipped} skipped.'))
