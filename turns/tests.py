from datetime import timedelta
import secrets

import pyotp
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Appointment, AuditEvent, AvailabilitySlot, Establishment, Profile, Representation, Specialty
from .external_services import agenda_status
from .services import book_slot, cancel_appointment


class SecurePrototypeTests(TestCase):
    TEST_SECRET = secrets.token_urlsafe(16)

    def setUp(self):
        User = get_user_model()
        self.patient = User.objects.create_user("patient", password=self.TEST_SECRET)
        self.other = User.objects.create_user("other", password=self.TEST_SECRET)
        self.representative = User.objects.create_user("representative", password=self.TEST_SECRET)
        for user, national_id, role in (
            (self.patient, "100000001", Profile.Role.AFFILIATE),
            (self.other, "100000002", Profile.Role.AFFILIATE),
            (self.representative, "100000003", Profile.Role.REPRESENTATIVE),
        ):
            Profile.objects.create(user=user, national_id=national_id, role=role)
        self.establishment = Establishment.objects.create(name="Centro de prueba")
        self.specialty = Specialty.objects.create(name="Odontología")
        self.slot = AvailabilitySlot.objects.create(
            establishment=self.establishment,
            specialty=self.specialty,
            starts_at=timezone.now() + timedelta(days=1),
        )

    def test_object_level_authorization_blocks_idor_cancel(self):
        appointment = book_slot(actor=self.patient, patient=self.patient, slot=self.slot)
        with self.assertRaises(PermissionError):
            cancel_appointment(actor=self.other, appointment=appointment)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.CONFIRMED)
        self.assertTrue(AuditEvent.objects.filter(result="DENIED").exists())

    def test_representation_scope_allows_only_granted_action(self):
        Representation.objects.create(
            representative=self.representative,
            patient=self.patient,
            relationship="familiar",
            can_view=True,
            can_reserve=True,
            can_cancel=False,
            valid_until=timezone.now() + timedelta(days=2),
        )
        appointment = book_slot(actor=self.representative, patient=self.patient, slot=self.slot)
        with self.assertRaises(PermissionError):
            cancel_appointment(actor=self.representative, appointment=appointment)

    def test_duplicate_specialty_is_rejected(self):
        book_slot(actor=self.patient, patient=self.patient, slot=self.slot)
        another_slot = AvailabilitySlot.objects.create(
            establishment=self.establishment,
            specialty=self.specialty,
            starts_at=timezone.now() + timedelta(days=2),
        )
        with self.assertRaises(ValueError):
            book_slot(actor=self.patient, patient=self.patient, slot=another_slot)

    def test_login_requires_valid_totp_for_staff(self):
        User = get_user_model()
        staff = User.objects.create_user("auditor", password=self.TEST_SECRET)
        secret = pyotp.random_base32()
        profile = Profile.objects.create(user=staff, national_id="100000004", role=Profile.Role.AUDITOR)
        profile.set_totp_secret(secret)
        profile.totp_enabled = True
        profile.save()
        client = Client()
        response = client.post(reverse("login"), {"national_id": "100000004", "password": self.TEST_SECRET, "totp": "000000"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("sessionid", client.cookies)
        response = client.post(reverse("login"), {"national_id": "100000004", "password": self.TEST_SECRET, "totp": pyotp.TOTP(secret).now()})
        self.assertEqual(response.status_code, 302)

    def test_security_headers_and_csrf_are_present(self):
        client = Client(enforce_csrf_checks=True)
        response = client.get(reverse("login"))
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertIn("default-src 'self'", response["Content-Security-Policy"])
        invalid_secret = secrets.token_urlsafe(8)
        post = client.post(reverse("login"), {"national_id": "100000001", "password": invalid_secret})
        self.assertEqual(post.status_code, 403)

    def test_login_input_is_html_escaped(self):
        invalid_secret = secrets.token_urlsafe(8)
        response = Client().post(
            reverse("login"),
            {"national_id": "<script>alert(1)</script>", "password": invalid_secret},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"<script>alert(1)</script>", response.content)

    def test_authenticated_http_booking_flow(self):
        client = Client()
        client.force_login(self.patient)
        response = client.post(reverse("book", args=[self.slot.id]), {"patient_id": self.patient.id})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Appointment.objects.filter(patient=self.patient).count(), 1)

    def test_logout_uses_csrf_protected_post(self):
        client = Client()
        client.force_login(self.patient)
        self.assertEqual(client.get(reverse("logout")).status_code, 405)
        response = client.post(reverse("logout"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(client.get(reverse("dashboard")).status_code, 302)

    def test_audit_chain_can_be_verified_and_detects_tampering(self):
        book_slot(actor=self.patient, patient=self.patient, slot=self.slot)
        valid, message = AuditEvent.verify_chain()
        self.assertTrue(valid)
        self.assertIn("íntegra", message)
        event = AuditEvent.objects.first()
        event.payload["result"] = "TAMPERED"
        event.save(update_fields=["payload"])
        valid, _ = AuditEvent.verify_chain()
        self.assertFalse(valid)

    @override_settings(DEMO_AGENDA_MODE="unavailable")
    def test_external_dependency_exposes_degraded_mode(self):
        status = agenda_status()
        self.assertFalse(status.available)
        self.assertEqual(status.mode, "unavailable")
