"""Daily backup: pg_dump (when on PostgreSQL) + JSON fixture + full Excel export, with 90-day retention.

Schedule it with Windows Task Scheduler or cron, e.g. daily at 23:30:
    python manage.py backup
"""
import datetime
import gzip
import io
import os
import shutil
import subprocess

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

from reports.full_export import build_sheets


class Command(BaseCommand):
    help = "Write a dated backup to BACKUP_DIR and delete backups older than BACKUP_RETENTION_DAYS."

    def handle(self, *args, **opts):
        root = settings.BACKUP_DIR
        root.mkdir(parents=True, exist_ok=True)
        stamp = timezone.localtime().strftime("%Y%m%d-%H%M%S")
        target = root / stamp
        target.mkdir()

        buf = io.StringIO()
        call_command("dumpdata", "--natural-foreign", "--exclude=contenttypes", "--exclude=auth.permission",
                     "--exclude=sessions", "--exclude=token_blacklist", stdout=buf)
        with gzip.open(target / "data.json.gz", "wt", encoding="utf-8") as fh:
            fh.write(buf.getvalue())

        if connection.vendor == "postgresql" and shutil.which("pg_dump"):
            db = settings.DATABASES["default"]
            env = {**os.environ, "PGPASSWORD": db.get("PASSWORD", "")}
            cmd = ["pg_dump", "-Fc", "-h", db.get("HOST") or "localhost", "-p", str(db.get("PORT") or 5432),
                   "-U", db.get("USER", ""), "-f", str(target / "database.dump"), db["NAME"]]
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            if result.returncode != 0:
                self.stderr.write(f"pg_dump failed: {result.stderr.strip()}")
        elif connection.vendor == "sqlite":
            shutil.copy2(settings.DATABASES["default"]["NAME"], target / "db.sqlite3")

        from core.exporting import Workbook, _add_sheet  # reuse the xlsx writer

        wb = Workbook()
        for i, s in enumerate(build_sheets()):
            _add_sheet(wb, s["title"], s["columns"], s["rows"], first=(i == 0))
        wb.save(target / "full-export.xlsx")

        cutoff = timezone.localtime() - datetime.timedelta(days=settings.BACKUP_RETENTION_DAYS)
        removed = 0
        for d in root.iterdir():
            try:
                when = datetime.datetime.strptime(d.name, "%Y%m%d-%H%M%S")
            except ValueError:
                continue
            if timezone.make_aware(when) < cutoff:
                shutil.rmtree(d, ignore_errors=True)
                removed += 1
        self.stdout.write(self.style.SUCCESS(f"Backup written to {target} (removed {removed} old backup(s))."))
