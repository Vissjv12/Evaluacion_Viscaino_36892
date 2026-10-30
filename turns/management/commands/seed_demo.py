from datetime import timedelta
import os
import secrets

import pyotp
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from turns.models import AvailabilitySlot, Establishment, Profile, Representation, Specialty


class Command(BaseCommand):
    help = "Crea datos sintéticos y credenciales de demostración del prototipo."

    def handle(self, *args, **options):
        password = os.environ.get("DEMO_PASSWORD") or secrets.token_urlsafe(12)
        definitions = [
            ("patient", "999999001", Profile.Role.AFFILIATE, False),
            ("representative", "999999002", Profile.Role.REPRESENTATIVE, False),
            ("frontdesk", "999999003", Profile.Role.FRONT_DESK, True),
            ("doctor", "999999004", Profile.Role.DOCTOR, True),
            ("auditor", "999999005", Profile.Role.AUDITOR, True),
        ]
        User = get_user_model()
        users = {}
        for username, national_id, role, needs_totp in definitions:
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={"first_name": username.title(), "is_active": True},
            )
            user.set_password(password)
            user.save(update_fields=["password", "first_name", "is_active"])
            profile, _ = Profile.objects.get_or_create(
                user=user,
                defaults={"national_id": national_id, "role": role},
            )
            profile.national_id = national_id
            profile.role = role
            if needs_totp and not profile.totp_secret_encrypted:
                secret = pyotp.random_base32()
                profile.set_totp_secret(secret)
                profile.totp_enabled = True
                profile.save(update_fields=["national_id", "role", "totp_secret_encrypted", "totp_enabled"])
                self.stdout.write(f"TOTP {username}: {secret}")
            else:
                profile.save(update_fields=["national_id", "role"])
            users[username] = user

        establishment, _ = Establishment.objects.get_or_create(name="Centro demo Quito")
        specialty, _ = Specialty.objects.get_or_create(name="Medicina general")
        start = timezone.now().replace(second=0, microsecond=0) + timedelta(days=1)
        for offset in (0, 30, 60):
            AvailabilitySlot.objects.get_or_create(
                establishment=establishment,
                specialty=specialty,
                starts_at=start + timedelta(minutes=offset),
                defaults={"active": True},
            )

        Representation.objects.update_or_create(
            representative=users["representative"],
            patient=users["patient"],
            defaults={
                "relationship": "familiar",
                "can_view": True,
                "can_reserve": True,
                "can_cancel": True,
                "can_reschedule": False,
                "valid_until": timezone.now() + timedelta(days=30),
                "status": Representation.Status.ACTIVE,
            },
        )
        self.stdout.write(self.style.SUCCESS("Datos demo listos."))
        self.stdout.write(f"Contraseña demo: {password}")
        self.stdout.write("Paciente: 999999001 · Representante: 999999002 · Staff: usar TOTP mostrado arriba")
