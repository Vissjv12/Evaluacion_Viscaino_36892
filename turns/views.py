import uuid
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import AvailabilityFilterForm, LoginForm, RepresentationForm
from .external_services import agenda_status
from .models import Appointment, AuditEvent, AvailabilitySlot, Notification, Profile, Representation
from .security import clear_login_failures, login_is_throttled, register_login_failure, verify_totp
from .services import authorized_subjects, book_slot, cancel_appointment, can_act


def login_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        national_id = form.cleaned_data["national_id"].strip()
        ip_address = request.META.get("REMOTE_ADDR", "unknown")
        if login_is_throttled(national_id, ip_address):
            messages.error(request, "Acceso temporalmente bloqueado. Intente más tarde.")
            return render(request, "registration/login.html", {"form": form})
        user = None
        try:
            user = Profile.objects.select_related("user").get(national_id=national_id).user
        except Profile.DoesNotExist:
            pass
        authenticated = authenticate(request, username=user.username if user else "", password=form.cleaned_data["password"])
        if authenticated is not None:
            profile = authenticated.profile
            if profile.requires_totp or profile.totp_enabled:
                if not verify_totp(profile.totp_secret_encrypted, form.cleaned_data["totp"]):
                    register_login_failure(national_id, ip_address)
                    messages.error(request, "Usuario o contraseña incorrectos.")
                    return render(request, "registration/login.html", {"form": form})
            login(request, authenticated)
            clear_login_failures(national_id, ip_address)
            AuditEvent.record(actor=authenticated, subject=authenticated, action="LOGIN", resource="session", result="SUCCESS")
            return redirect("dashboard")
        register_login_failure(national_id, ip_address)
        messages.error(request, "Usuario o contraseña incorrectos.")
    return render(request, "registration/login.html", {"form": form})


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    subjects = authorized_subjects(request.user)
    appointments = Appointment.objects.select_related("patient", "slot__specialty", "slot__establishment").filter(patient_id__in=subjects).order_by("-slot__starts_at")
    representations = Representation.objects.select_related("patient").filter(representative=request.user, status=Representation.Status.ACTIVE)
    notifications = Notification.objects.filter(user=request.user).order_by("-created_at")[:10]
    return render(request, "turns/dashboard.html", {
        "appointments": appointments,
        "representations": representations,
        "notifications": notifications,
        "representation_form": RepresentationForm(),
        "agenda_status": agenda_status(),
    })


@login_required
def availability(request: HttpRequest) -> HttpResponse:
    form = AvailabilityFilterForm(request.GET or None)
    slots = AvailabilitySlot.objects.select_related("specialty", "establishment").filter(active=True, starts_at__gte=timezone.now())
    if form.is_valid():
        if form.cleaned_data["specialty"]:
            slots = slots.filter(specialty__name__icontains=form.cleaned_data["specialty"])
        if form.cleaned_data["establishment"]:
            slots = slots.filter(establishment__name__icontains=form.cleaned_data["establishment"])
    return render(request, "turns/availability.html", {"form": form, "slots": slots[:50], "subjects": authorized_subjects(request.user).values(), "agenda_status": agenda_status()})


@login_required
def book(request: HttpRequest, slot_id: int) -> HttpResponse:
    if request.method != "POST":
        raise Http404
    slot = get_object_or_404(AvailabilitySlot.objects.select_related("specialty", "establishment"), pk=slot_id)
    patient_id = request.POST.get("patient_id", "")
    patient = None
    if patient_id.isdigit():
        patient = authorized_subjects(request.user).get(int(patient_id))
    if patient is None:
        messages.error(request, "No autorizado.")
        return redirect("availability")
    try:
        book_slot(actor=request.user, patient=patient, slot=slot)
        messages.success(request, "Turno registrado correctamente.")
    except (PermissionError, ValueError, IntegrityError):
        messages.error(request, "No fue posible registrar el turno.")
    return redirect("dashboard")


@login_required
def cancel(request: HttpRequest, appointment_id: uuid.UUID) -> HttpResponse:
    if request.method != "POST":
        raise Http404
    appointment = get_object_or_404(Appointment.objects.select_related("patient", "slot__establishment"), pk=appointment_id)
    try:
        cancel_appointment(actor=request.user, appointment=appointment)
        messages.success(request, "Turno cancelado.")
    except (PermissionError, ValueError):
        messages.error(request, "No fue posible cancelar el turno.")
    return redirect("dashboard")


@login_required
def create_representation(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        raise Http404
    form = RepresentationForm(request.POST)
    if form.is_valid():
        representative = Profile.objects.filter(
            pk=form.cleaned_data["representative_id"]
        ).select_related("user").first()
        if (
            representative is None
            or representative.user == request.user
            or form.cleaned_data["valid_until"] > timezone.now() + timedelta(days=366)
        ):
            messages.error(request, "No se pudo crear la representación.")
        else:
            Representation.objects.create(
                representative=representative.user,
                patient=request.user,
                relationship=form.cleaned_data["relationship"],
                can_view=form.cleaned_data["can_view"],
                can_reserve=form.cleaned_data["can_reserve"],
                can_cancel=form.cleaned_data["can_cancel"],
                can_reschedule=form.cleaned_data["can_reschedule"],
                valid_until=form.cleaned_data["valid_until"],
            )
            AuditEvent.record(actor=request.user, subject=representative.user, action="CREATE_REPRESENTATION", resource=str(representative.user_id), result="SUCCESS")
            messages.success(request, "Representación creada.")
    return redirect("dashboard")


@login_required
def audit(request: HttpRequest) -> HttpResponse:
    if not hasattr(request.user, "profile") or request.user.profile.role != Profile.Role.AUDITOR:
        raise Http404
    events = AuditEvent.objects.select_related("actor", "represented_subject").order_by("-created_at")[:100]
    return render(request, "turns/audit.html", {"events": events})

