from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("login/", views.login_view, name="custom_login"),
    path("availability/", views.availability, name="availability"),
    path("appointments/<uuid:appointment_id>/cancel/", views.cancel, name="cancel"),
    path("slots/<int:slot_id>/book/", views.book, name="book"),
    path("representations/create/", views.create_representation, name="create_representation"),
    path("audit/", views.audit, name="audit"),
]

