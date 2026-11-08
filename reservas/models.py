from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeBoundary, RangeOperators
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.db.models import Exists, F, Func, OuterRef, Q
from django.utils import timezone


class TsTzRange(Func):
    """tstzrange(inicio, fin, '[)') de PostgreSQL, para la restricción anti-traslape."""

    function = "TSTZRANGE"
    output_field = DateTimeRangeField()


# ---------------------------------------------------------------- catálogos
class TipoEspacio(models.Model):
    id = models.SmallAutoField(primary_key=True)
    nombre = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = "tipo_espacio"
        verbose_name = "tipo de espacio"
        verbose_name_plural = "tipos de espacio"

    def __str__(self):
        return self.nombre


class BloqueHorario(models.Model):
    """Horas clase fijas (los exámenes pueden usar horario libre)."""

    id = models.SmallAutoField(primary_key=True)
    nombre = models.CharField(max_length=50, unique=True)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "bloque_horario"
        verbose_name = "bloque horario"
        verbose_name_plural = "bloques horarios"
        ordering = ["hora_inicio"]
        constraints = [
            models.CheckConstraint(condition=Q(hora_fin__gt=F("hora_inicio")), name="ck_bloque_horas"),
            models.UniqueConstraint(fields=["hora_inicio", "hora_fin"], name="uq_bloque_horas"),
        ]

    def __str__(self):
        return f"{self.nombre} ({self.hora_inicio:%H:%M}-{self.hora_fin:%H:%M})"


class MotivoReserva(models.Model):
    """Motivos predefinidos. Si permite_horario_libre, la reserva ignora los bloques fijos."""

    id = models.SmallAutoField(primary_key=True)
    nombre = models.CharField(max_length=80, unique=True)
    permite_horario_libre = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "motivo_reserva"
        verbose_name = "motivo de reserva"
        verbose_name_plural = "motivos de reserva"

    def __str__(self):
        return self.nombre


# ------------------------------------------------------------------ espacio
class EspacioQuerySet(models.QuerySet):
    def disponibles(self, inicio, fin, capacidad_minima=None):
        """Espacios activos sin reservas aprobadas que se traslapen con [inicio, fin)."""
        ocupado = Reserva.objects.filter(
            espacio=OuterRef("pk"), estado=Reserva.Estado.APROBADA, inicio__lt=fin, fin__gt=inicio
        )
        qs = self.filter(activo=True).exclude(Exists(ocupado))
        if capacidad_minima:
            qs = qs.filter(capacidad__gte=capacidad_minima)
        return qs


class Espacio(models.Model):
    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=100)
    tipo_espacio = models.ForeignKey(TipoEspacio, on_delete=models.PROTECT, related_name="espacios")
    ubicacion = models.CharField(max_length=150, blank=True, default="")
    capacidad = models.PositiveIntegerField(help_text="Capacidad fija del local")
    descripcion = models.TextField(blank=True, default="")
    activo = models.BooleanField(default=True, help_text="Desmarcar para dejar de ofrecerlo")
    created_at = models.DateTimeField(auto_now_add=True)

    objects = EspacioQuerySet.as_manager()

    class Meta:
        db_table = "espacio"
        verbose_name = "espacio"
        verbose_name_plural = "espacios"
        ordering = ["codigo"]
        constraints = [
            models.CheckConstraint(condition=Q(capacidad__gt=0), name="ck_espacio_capacidad"),
        ]

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


# ------------------------------------------------------------------ reserva
class Reserva(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        APROBADA = "aprobada", "Aprobada"
        RECHAZADA = "rechazada", "Rechazada"
        CANCELADA = "cancelada", "Cancelada"

    ESTADOS_ACTIVOS = (Estado.PENDIENTE, Estado.APROBADA)  # los que se pueden rechazar/cancelar

    # db_index=False: los índices compuestos de Meta ya cubren estas columnas
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reservas", db_index=False
    )
    espacio = models.ForeignKey(Espacio, on_delete=models.PROTECT, related_name="reservas", db_index=False)
    motivo = models.ForeignKey(MotivoReserva, on_delete=models.PROTECT, null=True, blank=True, related_name="reservas")
    motivo_detalle = models.TextField("motivo libre / detalle", blank=True, default="")
    bloque_horario = models.ForeignKey(
        BloqueHorario, on_delete=models.PROTECT, null=True, blank=True, related_name="reservas"
    )
    inicio = models.DateTimeField()
    fin = models.DateTimeField()
    cantidad_personas = models.PositiveIntegerField()
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    motivo_rechazo = models.TextField(blank=True, default="")
    gestionado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="reservas_gestionadas",
    )
    fecha_gestion = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "reserva"
        verbose_name = "reserva"
        verbose_name_plural = "reservas"
        ordering = ["-inicio"]
        indexes = [
            models.Index(fields=["usuario", "-inicio"], name="ix_reserva_usuario"),
            models.Index(fields=["espacio", "inicio"], name="ix_reserva_espacio"),
            models.Index(fields=["estado"], name="ix_reserva_estado"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(estado__in=["pendiente", "aprobada", "rechazada", "cancelada"]),
                name="ck_reserva_estado",
            ),
            models.CheckConstraint(condition=Q(fin__gt=F("inicio")), name="ck_reserva_horario"),
            models.CheckConstraint(condition=Q(cantidad_personas__gt=0), name="ck_reserva_personas"),
            models.CheckConstraint(
                condition=Q(motivo__isnull=False) | ~Q(motivo_detalle=""), name="ck_reserva_motivo"
            ),
            models.CheckConstraint(
                condition=~Q(estado="rechazada") | ~Q(motivo_rechazo=""), name="ck_reserva_rechazo"
            ),
            # Dos reservas APROBADAS no pueden traslaparse en el mismo espacio
            ExclusionConstraint(
                name="ex_reserva_sin_traslape",
                expressions=[
                    ("espacio", RangeOperators.EQUAL),
                    (TsTzRange("inicio", "fin", RangeBoundary()), RangeOperators.OVERLAPS),
                ],
                condition=Q(estado="aprobada"),
            ),
        ]

    def __str__(self):
        return f"{self.espacio} | {self.inicio:%Y-%m-%d %H:%M} | {self.estado}"

    # ---------------------------------------------------------- validaciones
    def clean(self):
        """Reglas que un CHECK no puede expresar (cruzan tablas o dependen de la hora local)."""
        errores = {}
        if self.inicio and self.fin and self.fin > self.inicio:
            ini, fin = timezone.localtime(self.inicio), timezone.localtime(self.fin)
            if ini.date() != fin.date():
                errores["fin"] = "La reserva debe terminar el mismo día en que inicia."
            elif self._state.adding and self.inicio < timezone.now():
                errores["inicio"] = "No se pueden reservar horarios pasados."
            else:
                libre = bool(self.motivo_id and self.motivo.permite_horario_libre)
                if not libre:
                    b = self.bloque_horario
                    if b is None:
                        errores["bloque_horario"] = "Selecciona un bloque horario (horario fijo)."
                    elif (ini.time(), fin.time()) != (b.hora_inicio, b.hora_fin):
                        errores["bloque_horario"] = "El horario no coincide con el bloque seleccionado."
        if self.espacio_id:
            if self._state.adding and not self.espacio.activo:
                errores["espacio"] = "El espacio no está disponible para reservas."
            if self.cantidad_personas and self.cantidad_personas > self.espacio.capacidad:
                errores["cantidad_personas"] = (
                    f"Supera la capacidad del espacio ({self.espacio.capacidad})."
                )
            if self.inicio and self.fin and self.estado == self.Estado.APROBADA:
                conflicto = Reserva.objects.filter(
                    espacio_id=self.espacio_id, estado=self.Estado.APROBADA,
                    inicio__lt=self.fin, fin__gt=self.inicio,
                ).exclude(pk=self.pk)
                if conflicto.exists():
                    errores["inicio"] = "Ya existe una reserva aprobada en ese espacio y horario."
        if errores:
            raise ValidationError(errores)

    # ------------------------------------------------------------ flujo
    @classmethod
    def solicitar(cls, **datos):
        """HU03: registra la solicitud (pendiente) y la aprueba automáticamente si no hay conflicto."""
        reserva = cls(**datos)
        reserva.full_clean()
        conflicto = cls.objects.filter(
            espacio=reserva.espacio, estado=cls.Estado.APROBADA,
            inicio__lt=reserva.fin, fin__gt=reserva.inicio,
        ).exists()
        if conflicto:
            raise ValidationError("Ya existe una reserva aprobada en ese espacio y horario.")
        try:
            with transaction.atomic():
                reserva.save()
                reserva.estado = cls.Estado.APROBADA  # aprobación automática (T23)
                reserva.save(update_fields=["estado", "updated_at"])
        except IntegrityError:  # otro usuario reservó al mismo tiempo
            raise ValidationError("Ya existe una reserva aprobada en ese espacio y horario.")
        return reserva

    def rechazar(self, admin, motivo):
        """HU04: solo un administrador, siempre con motivo."""
        if not getattr(admin, "es_admin", False):
            raise PermissionError("Solo un administrador puede rechazar reservas.")
        if not (motivo or "").strip():
            raise ValidationError("Debes indicar el motivo del rechazo.")
        self._cambiar_estado(self.Estado.RECHAZADA, admin, motivo_rechazo=motivo.strip())

    def cancelar(self, usuario):
        """HU07: el dueño de la reserva o un administrador."""
        if not (usuario.es_admin or self.usuario_id == usuario.pk):
            raise PermissionError("Solo el propietario o un administrador puede cancelar.")
        self._cambiar_estado(self.Estado.CANCELADA, usuario)

    def _cambiar_estado(self, nuevo, quien, **extra):
        if self.estado not in self.ESTADOS_ACTIVOS:
            raise ValidationError(f"No se puede cambiar una reserva {self.get_estado_display().lower()}.")
        self.estado, self.gestionado_por, self.fecha_gestion = nuevo, quien, timezone.now()
        for campo, valor in extra.items():
            setattr(self, campo, valor)
        self.save(update_fields=["estado", "gestionado_por", "fecha_gestion", "updated_at", *extra])
