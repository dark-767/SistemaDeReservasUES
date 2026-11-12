from datetime import datetime

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import BloqueHorario, Espacio, MotivoReserva, Reserva


def _combinar(fecha, hora):
    return timezone.make_aware(datetime.combine(fecha, hora), timezone.get_current_timezone())

CAMPOS_DEL_MODELO = {
    "cantidad_personas": "cantidad",
    "bloque_horario": "horario",
    "inicio": "fecha",
    "fin": "horario",
    "espacio": "espacio",
    "motivo": "motivo",
    "motivo_detalle": "detalle",
}


class SolicitudReservaForm(forms.Form):
    """Datos de HU03. La capacidad, el traslape y la aprobación los resuelve Reserva.solicitar()."""

    espacio = forms.ModelChoiceField(
        queryset=Espacio.objects.filter(activo=True),
        widget=forms.HiddenInput,
        error_messages={"required": "Selecciona un espacio desde la búsqueda de disponibilidad.", "invalid_choice": "Ese espacio no está disponible."},
    )
    fecha = forms.DateField(
        label="Fecha",
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"class": "input", "type": "date"}),
        error_messages={"required": "Indica la fecha de la reserva.", "invalid": "Ingresa una fecha válida."},
    )
    horario = forms.ModelChoiceField(
        label="Horario",
        queryset=BloqueHorario.objects.filter(activo=True),
        empty_label=None,
        widget=forms.Select(attrs={"class": "select"}),
        error_messages={"required": "Selecciona un horario.", "invalid_choice": "Selecciona un horario válido."},
    )
    cantidad = forms.IntegerField(
        label="Cantidad de personas",
        min_value=1,
        widget=forms.NumberInput(attrs={"class": "input", "min": "1"}),
        error_messages={
            "required": "Indica cuántas personas asistirán.",
            "invalid": "La cantidad debe ser un número entero.",
            "min_value": "La cantidad debe ser al menos 1.",
        },
    )
    motivo = forms.ModelChoiceField(
        label="Motivo",
        queryset=MotivoReserva.objects.filter(activo=True),
        empty_label="Selecciona un motivo",
        widget=forms.Select(attrs={"class": "select"}),
        error_messages={"required": "Selecciona el motivo de la reserva.", "invalid_choice": "Selecciona un motivo válido."},
    )
    detalle = forms.CharField(
        label="Detalle",
        widget=forms.Textarea(attrs={"class": "textarea", "rows": 3}),
        error_messages={"required": "Describe el motivo de la reserva."},
    )

    def __init__(self, *args, usuario=None, **kwargs):
        self.usuario = usuario
        super().__init__(*args, **kwargs)
        self.fields["fecha"].input_formats = ["%Y-%m-%d"]
        valor = self.data.get("espacio") if self.is_bound else self.initial.get("espacio")
        self.espacio_visible = None
        if valor:
            self.espacio_visible = (
                Espacio.objects.filter(pk=valor, activo=True).select_related("tipo_espacio").first()
            )

    def clean_fecha(self):
        fecha = self.cleaned_data["fecha"]
        if fecha < timezone.localdate():
            raise ValidationError("No se pueden reservar horarios pasados.")
        return fecha

    def guardar(self):
        datos = self.cleaned_data
        bloque = datos["horario"]
        try:
            return Reserva.solicitar(
                usuario=self.usuario,
                espacio=datos["espacio"],
                motivo=datos["motivo"],
                motivo_detalle=datos["detalle"].strip(),
                bloque_horario=bloque,
                inicio=_combinar(datos["fecha"], bloque.hora_inicio),
                fin=_combinar(datos["fecha"], bloque.hora_fin),
                cantidad_personas=datos["cantidad"],
            )
        except ValidationError as exc:
            self._cargar_errores(exc)
            return None

    def _cargar_errores(self, exc):
        if hasattr(exc, "error_dict"):
            for campo, errores in exc.error_dict.items():
                destino = CAMPOS_DEL_MODELO.get(campo)
                for error in errores:
                    self.add_error(destino, error)
            return
        self.add_error(None, exc)
