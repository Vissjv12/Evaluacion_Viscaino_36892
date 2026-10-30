import hashlib
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .security import SafeAuditPayload, canonical_json, encrypt_text


class Profile(models.Model):
    class Role(models.TextChoices):
        AFFILIATE = "AFFILIATE", "Afiliado"
        REPRESENTATIVE = "REPRESENTATIVE", "Representante"
        FRONT_DESK = "FRONT_DESK", "Atención al usuario"
        DOCTOR = "DOCTOR", "Médico"
        ADMIN = "ADMIN", "Administración"
        SUPPORT = "SUPPORT", "Soporte"
        AUDITOR = "AUDITOR", "Auditor"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    national_id = models.CharField(max_length=20, unique=True)
    birth_date = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.AFFILIATE)
    totp_secret_encrypted = models.TextField(blank=True)
    totp_enabled = models.BooleanField(default=False)

    def set_totp_secret(self, secret: str) -> None:
        self.totp_secret_encrypted = encrypt_text(secret)

    @property
    def requires_totp(self) -> bool:
        return self.role in {self.Role.FRONT_DESK, self.Role.DOCTOR, self.Role.ADMIN, self.Role.SUPPORT, self.Role.AUDITOR}


class Establishment(models.Model):
    name = models.CharField(max_length=120, unique=True)

    def __str__(self) -> str:
        return self.name


class Specialty(models.Model):
    name = models.CharField(max_length=120, unique=True)

    def __str__(self) -> str:
        return self.name


class AvailabilitySlot(models.Model):
    establishment = models.ForeignKey(Establishment, on_delete=models.PROTECT)
    specialty = models.ForeignKey(Specialty, on_delete=models.PROTECT)
    starts_at = models.DateTimeField()
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["establishment", "specialty", "starts_at"],
                name="unique_availability_slot",
            )
        ]
        ordering = ["starts_at"]


class Representation(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Activa"
        REVOKED = "REVOKED", "Revocada"
        EXPIRED = "EXPIRED", "Expirada"

    representative = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="representations")
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="representatives")
    relationship = models.CharField(max_length=60)
    can_view = models.BooleanField(default=True)
    can_reserve = models.BooleanField(default=False)
    can_cancel = models.BooleanField(default=False)
    can_reschedule = models.BooleanField(default=False)
    valid_until = models.DateTimeField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="verified_representations")
    created_at = models.DateTimeField(auto_now_add=True)

    def is_active(self) -> bool:
        return self.status == self.Status.ACTIVE and self.valid_until > timezone.now()


class Appointment(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "CONFIRMED", "Confirmado"
        CANCELLED = "CANCELLED", "Cancelado"
        RESCHEDULED = "RESCHEDULED", "Reprogramado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="appointments")
    slot = models.ForeignKey(AvailabilitySlot, on_delete=models.PROTECT, related_name="appointments")
    booked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="booked_appointments")
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.CONFIRMED)
    reschedule_count = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["slot"],
                condition=Q(status="CONFIRMED"),
                name="one_confirmed_appointment_per_slot",
            ),
            models.UniqueConstraint(
                fields=["patient", "slot"],
                condition=Q(status="CONFIRMED"),
                name="one_confirmed_patient_slot",
            ),
        ]

    @property
    def establishment(self) -> str:
        return self.slot.establishment.name


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    appointment = models.ForeignKey(Appointment, null=True, blank=True, on_delete=models.PROTECT)
    kind = models.CharField(max_length=40)
    safe_message = models.TextField()
    sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class AuditEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="audit_events")
    represented_subject = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="represented_audit_events")
    action = models.CharField(max_length=80)
    resource = models.CharField(max_length=160)
    result = models.CharField(max_length=30)
    correlation_id = models.UUIDField(default=uuid.uuid4, editable=False)
    payload = models.JSONField(default=dict)
    previous_hash = models.CharField(max_length=64, blank=True)
    current_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def record(cls, *, actor, subject, action: str, resource: str, result: str) -> "AuditEvent":
        previous = cls.objects.order_by("-created_at", "-id").first()
        previous_hash = previous.current_hash if previous else "GENESIS"
        safe = SafeAuditPayload(
            actor_id=getattr(actor, "id", None),
            subject_id=getattr(subject, "id", None),
            action=action,
            resource=resource,
            result=result,
            correlation_id=str(uuid.uuid4()),
        )
        payload = safe.as_dict()
        current_hash = hashlib.sha256((previous_hash + canonical_json(payload)).encode()).hexdigest()
        return cls.objects.create(
            actor=actor,
            represented_subject=subject,
            action=action,
            resource=resource,
            result=result,
            correlation_id=payload["correlation_id"],
            payload=payload,
            previous_hash=previous_hash,
            current_hash=current_hash,
        )

    @classmethod
    def verify_chain(cls) -> tuple[bool, str]:
        """Verify ordering, predecessor links and hashes without changing data."""
        previous_hash = "GENESIS"
        for event in cls.objects.order_by("created_at", "id"):
            if event.previous_hash != previous_hash:
                return False, f"Predecesor inválido en evento {event.pk}"
            expected_hash = hashlib.sha256(
                (previous_hash + canonical_json(event.payload)).encode()
            ).hexdigest()
            if event.current_hash != expected_hash:
                return False, f"Hash inválido en evento {event.pk}"
            previous_hash = event.current_hash
        return True, "Cadena de auditoría íntegra"

