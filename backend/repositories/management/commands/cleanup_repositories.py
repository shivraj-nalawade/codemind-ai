from django.core.management.base import BaseCommand

from repositories.repository_lifecycle import (
    cleanup_expired_repositories,
)


class Command(BaseCommand):

    help = (
        "Remove expired uploaded repositories "
        "after 24 hours of inactivity."
    )

    def handle(self, *args, **options):

        self.stdout.write(
            "Starting repository cleanup..."
        )

        result = cleanup_expired_repositories(
            force=True
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Repository cleanup completed."
            )
        )

        self.stdout.write(
            f"Deleted repositories: {result['deleted']}"
        )

        self.stdout.write(
            f"Active repositories skipped: "
            f"{result['active_skipped']}"
        )

        self.stdout.write(
            f"Failed deletions: {result['failed']}"
        )