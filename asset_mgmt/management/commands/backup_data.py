import shutil
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone


class Command(BaseCommand):
    help = 'Create a timestamped logical JSON backup and, for SQLite, a database-file copy.'

    def add_arguments(self, parser):
        parser.add_argument('--output-dir', default='backups', help='Backup directory relative to the project root or an absolute path.')

    def handle(self, *args, **options):
        output_dir = Path(options['output_dir'])
        if not output_dir.is_absolute():
            output_dir = Path(settings.BASE_DIR) / output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = timezone.localtime().strftime('%Y%m%d-%H%M%S')

        json_path = output_dir / f'engineering-saas-{stamp}.json'
        with json_path.open('w', encoding='utf-8') as handle:
            call_command(
                'dumpdata',
                '--natural-foreign',
                '--natural-primary',
                '--exclude=contenttypes',
                '--exclude=auth.permission',
                '--indent=2',
                stdout=handle,
            )
        self.stdout.write(self.style.SUCCESS(f'Logical backup: {json_path}'))

        database = settings.DATABASES['default']
        if database.get('ENGINE', '').endswith('sqlite3'):
            connection.close()
            source = Path(database['NAME'])
            if source.exists():
                sqlite_path = output_dir / f'engineering-saas-{stamp}.sqlite3'
                shutil.copy2(source, sqlite_path)
                self.stdout.write(self.style.SUCCESS(f'SQLite copy: {sqlite_path}'))
