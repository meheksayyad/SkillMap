from django.core.management.base import BaseCommand

from skillmap import services


class Command(BaseCommand):
    help = "Create or refresh the starting skill taxonomy (safe to run repeatedly)."

    def handle(self, *args, **options):
        n = services.seed_skills()
        self.stdout.write(self.style.SUCCESS(f"Taxonomy loaded: {n} skills."))
