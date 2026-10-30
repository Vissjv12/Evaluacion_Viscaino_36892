from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Appointment, AuditEvent, AvailabilitySlot, Notification, Representation


def authorized_subjects(user):
    """Return subjects the user may act for, always including themselves."""
    subjects = {user.id: user}
    for representation in Representation.objects.select_related("patient").filter(
        representative=user,
        status=Representation.Status.ACTIVE,
        valid_until__gt=timezone.now(),
    ):
        subjects[representation.patient_id] = representation.patient
    return subjects


def get_representation(user, patient, action: str) -> Representation | None:
    if user.id == patient.id:
        return None
    representation = Representation.objects.filter(
        representative=user,
        patient=patient,
        status=Representation.Status.ACTIVE,
        valid_until__gt=timezone.now(),
    ).first()
    if representation and getattr(representation, f"can_{action}", False):
        return representation
    return None


def can_act(user, patient, action: str) -> bool:
    if user.id == patient.id:
        return True
    return get_representation(user, patient, action) is not None


@transaction.atomic
def book_slot(*, actor, patient, slot: AvailabilitySlot) -> Appointment:
    if not can_act(actor, patient, "reserve"):
        raise PermissionError("No autorizado")
    if not slot.active:
        raise ValueError("El cupo no está disponible")
    if Appointment.objects.filter(
        patient=patient,
        slot__specialty=slot.specialty,
        status=Appointment.Status.CONFIRMED,
    ).exists():
        raise ValueError("Ya existe un turno activo para esta especialidad")
    try:
        appointment = Appointment.objects.create(patient=patient, slot=slot, booked_by=actor)
    except IntegrityError as exc:
        raise ValueError("El cupo ya fue tomado") from exc
    Notification.objects.create(
        user=patient,
        appointment=appointment,
        kind="APPOINTMENT_CREATED",
        safe_message=f"Turno registrado para {slot.starts_at:%Y-%m-%d %H:%M} en {slot.establishment.name}. Código: {appointment.pk}",
    )
    AuditEvent.record(actor=actor, subject=patient, action="BOOK_APPOINTMENT", resource=str(appointment.pk), result="SUCCESS")
    return appointment


def cancel_appointment(*, actor, appointment: Appointment) -> None:
    if not can_act(actor, appointment.patient, "cancel"):
        AuditEvent.record(actor=actor, subject=appointment.patient, action="CANCEL_APPOINTMENT", resource=str(appointment.pk), result="DENIED")
        raise PermissionError("No autorizado")
    with transaction.atomic():
        if appointment.status != Appointment.Status.CONFIRMED:
            raise ValueError("El turno no está confirmado")
        appointment.status = Appointment.Status.CANCELLED
        appointment.cancelled_at = timezone.now()
        appointment.save(update_fields=["status", "cancelled_at"])
        Notification.objects.create(
            user=appointment.patient,
            appointment=appointment,
            kind="APPOINTMENT_CANCELLED",
            safe_message=f"Turno cancelado para {appointment.slot.starts_at:%Y-%m-%d %H:%M} en {appointment.slot.establishment.name}.",
        )
        AuditEvent.record(actor=actor, subject=appointment.patient, action="CANCEL_APPOINTMENT", resource=str(appointment.pk), result="SUCCESS")

