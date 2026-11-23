"""python manage.py seed_demo [--reset]  ->  local demo student 'demo' / 'demo12345' with realistic FAKE data.
(The public 'Try the demo' button creates disposable per-visitor accounts instead; see core/demo.py.)"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from core.demo import populate_demo


class Command(BaseCommand):
    help = "Create (or with --reset, recreate) the local demo student with fake sample data."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete the existing demo user and its data first.")

    def handle(self, *args, **options):
        User = get_user_model()
        if options["reset"]:
            User.objects.filter(username="demo").delete()
        user, created = User.objects.get_or_create(username="demo", defaults={
            "first_name": "Amina", "last_name": "Wanjiru", "email": "demo@example.com"})
        if not created:
            self.stdout.write("Demo user already exists. Use --reset to recreate it.")
            return
        user.set_password("demo12345")
        user.save()
        populate_demo(user)
        self.stdout.write(self.style.SUCCESS("Demo created. Log in with  demo / demo12345"))
