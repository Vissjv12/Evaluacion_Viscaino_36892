from dataclasses import dataclass

from django.conf import settings


@dataclass(frozen=True)
class DependencyStatus:
    name: str
    mode: str
    available: bool
    message: str


def agenda_status() -> DependencyStatus:
    """Synthetic external dependency status for safe degraded-mode demos."""
    mode = getattr(settings, "DEMO_AGENDA_MODE", "healthy")
    if mode == "timeout":
        return DependencyStatus("Agenda externa", mode, False, "Tiempo de espera agotado")
    if mode == "unavailable":
        return DependencyStatus("Agenda externa", mode, False, "Servicio temporalmente no disponible")
    return DependencyStatus("Agenda externa", "healthy", True, "Servicio disponible")
