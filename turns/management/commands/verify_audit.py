from django.core.management.base import BaseCommand, CommandError

from turns.models import AuditEvent


class Command(BaseCommand):
    help = "Verifica la cadena de hashes de auditoría sin modificarla."

    def handle(self, *args, **options):
        valid, message = AuditEvent.verify_chain()
        if not valid:
            raise CommandError(message)
        self.stdout.write(self.style.SUCCESS(message))
