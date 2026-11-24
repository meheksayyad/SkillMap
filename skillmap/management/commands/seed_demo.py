from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from skillmap import services
from skillmap.models import JobDescription, Resume
from skillmap.samples import SAMPLE_JOBS, SAMPLE_RESUME

User = get_user_model()
DEMO_USER = "demo"
DEMO_PASSWORD = "demo12345"


class Command(BaseCommand):
    help = "Load the taxonomy plus a demo user with a sample resume, jobs and analyses."

    def handle(self, *args, **options):
        services.seed_skills()

        user, created = User.objects.get_or_create(username=DEMO_USER)
        if created:
            user.set_password(DEMO_PASSWORD)
            user.save()

        resume, _ = Resume.objects.get_or_create(
            user=user, title="Sample backend resume", defaults={"text": SAMPLE_RESUME}
        )
        jobs = []
        for data in SAMPLE_JOBS:
            job, _ = JobDescription.objects.get_or_create(
                user=user, title=data["title"], defaults={"company": data["company"], "text": data["text"]}
            )
            jobs.append(job)

        for analysis in services.run_many(user, resume, jobs):
            self.stdout.write(f"  {analysis.score:3d}  {analysis.job.title}")
        self.stdout.write(
            self.style.SUCCESS(f"Done. Log in as '{DEMO_USER}' / '{DEMO_PASSWORD}' (local demo only).")
        )
