"""python manage.py purge_demo  ->  delete expired visitor demo accounts (run it from a scheduled job, e.g. hourly)."""
from django.core.management.base import BaseCommand

from core.demo import purge_expired_demo


class Command(BaseCommand):
    help = "Delete visitor demo accounts older than the demo lifetime, with all their data."

    def handle(self, *args, **options):
        self.stdout.write(f"Removed {purge_expired_demo()} expired demo account(s).")
