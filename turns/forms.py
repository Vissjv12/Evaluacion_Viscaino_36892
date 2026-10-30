from django import forms


class LoginForm(forms.Form):
    national_id = forms.CharField(max_length=20, label="Cédula")
    password = forms.CharField(widget=forms.PasswordInput, label="Contraseña")
    totp = forms.CharField(max_length=6, required=False, label="Código TOTP")


class RepresentationForm(forms.Form):
    representative_id = forms.IntegerField(label="ID interno del representante", min_value=1)
    relationship = forms.CharField(max_length=60, label="Relación descriptiva")
    can_view = forms.BooleanField(required=False, initial=True, label="Consultar")
    can_reserve = forms.BooleanField(required=False, label="Reservar")
    can_cancel = forms.BooleanField(required=False, label="Cancelar")
    can_reschedule = forms.BooleanField(required=False, label="Reprogramar")
    valid_until = forms.DateTimeField(input_formats=["%Y-%m-%dT%H:%M"], label="Válida hasta")


class AvailabilityFilterForm(forms.Form):
    specialty = forms.CharField(required=False, max_length=120, label="Especialidad")
    establishment = forms.CharField(required=False, max_length=120, label="Establecimiento")

