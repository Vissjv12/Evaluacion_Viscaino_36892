from django.contrib import admin

from .models import Appointment, AuditEvent, AvailabilitySlot, Establishment, Notification, Profile, Representation, Specialty

admin.site.register([Profile, Establishment, Specialty, AvailabilitySlot, Appointment, Representation, Notification, AuditEvent])

