from datetime import datetime, time, timedelta

from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import SolicitudReservaForm
from .models import BloqueHorario, Espacio, Reserva, TipoEspacio

DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
MESES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


def _fecha_legible(fecha):
    return f"{DIAS[fecha.weekday()].capitalize()} {fecha.day} de {MESES[fecha.month - 1]}"


def _combinar(fecha, hora):
    return timezone.make_aware(datetime.combine(fecha, hora), timezone.get_current_timezone())


def _parse_fecha(valor):
    if not valor:
        return timezone.localdate(), None
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date(), None
    except ValueError:
        return None, "Ingresa una fecha válida."


def _parse_capacidad(valor):
    if valor is None or valor == "":
        return None, None
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        return None, "La capacidad mínima debe ser un número entero."
    if numero < 1:
        return None, "La capacidad mínima debe ser al menos 1."
    return numero, None


def _barra(usuario):
    return {
        "iniciales": _iniciales(usuario),
        "nombre_usuario": usuario.get_full_name() or usuario.username,
        "rol_usuario": usuario.get_rol_display(),
    }


def _iniciales(usuario):
    nombre = (usuario.get_full_name() or usuario.username or "").strip()
    partes = nombre.split()
    if len(partes) >= 2:
        return (partes[0][:1] + partes[-1][:1]).upper()
    return (nombre[:2] or "U").upper()


def _clase_media(tipo):
    nombre = tipo.lower()
    if "laborat" in nombre:
        return "space-card__media space-card__media--lab"
    if "audito" in nombre or "sala" in nombre:
        return "space-card__media space-card__media--hall"
    return "space-card__media"


def _etiqueta_horario(reserva):
    if reserva.bloque_horario_id:
        bloque = reserva.bloque_horario
        return f"{bloque.hora_inicio:%H:%M} - {bloque.hora_fin:%H:%M}"
    inicio = timezone.localtime(reserva.inicio)
    fin = timezone.localtime(reserva.fin)
    return f"{inicio:%H:%M} - {fin:%H:%M}"


def _marcar_ocupados(espacios, fecha):
    por_espacio = {espacio.pk: [] for espacio in espacios}
    if not espacios:
        return
    dia_inicio = _combinar(fecha, time.min)
    dia_fin = dia_inicio + timedelta(days=1)
    reservas = (
        Reserva.objects.filter(
            espacio_id__in=por_espacio,
            estado=Reserva.Estado.APROBADA,
            inicio__lt=dia_fin,
            fin__gt=dia_inicio,
        )
        .select_related("bloque_horario")
        .order_by("inicio")
    )
    for reserva in reservas:
        por_espacio[reserva.espacio_id].append(_etiqueta_horario(reserva))
    for espacio in espacios:
        espacio.horarios_ocupados = por_espacio[espacio.pk]


@login_required
def buscar_disponibilidad(request):
    """T20: espacios activos sin una reserva aprobada que se cruce con el bloque elegido."""
    bloques = list(BloqueHorario.objects.filter(activo=True))
    tipos = list(
        TipoEspacio.objects.filter(espacios__activo=True).distinct().order_by("nombre")
    )
    errores = []

    fecha, error_fecha = _parse_fecha(request.GET.get("fecha"))
    if error_fecha:
        errores.append(error_fecha)

    horario_id = request.GET.get("horario")
    bloque = None
    if not bloques:
        errores.append("No hay bloques horarios configurados.")
    elif horario_id:
        bloque = next((item for item in bloques if str(item.pk) == horario_id), None)
        if bloque is None:
            errores.append("Selecciona un horario válido.")
    else:
        bloque = bloques[0]

    tipo = None
    tipo_id = request.GET.get("tipo") or ""
    if tipo_id:
        if not tipo_id.isdigit():
            errores.append("Selecciona un tipo de espacio válido.")
        else:
            tipo = TipoEspacio.objects.filter(pk=int(tipo_id)).first()
            if tipo is None:
                errores.append("Selecciona un tipo de espacio válido.")

    capacidad, error_capacidad = _parse_capacidad(request.GET.get("capacidad"))
    if error_capacidad:
        errores.append(error_capacidad)

    espacios = []
    consulto = bool(fecha and bloque and not errores)
    if consulto:
        inicio = _combinar(fecha, bloque.hora_inicio)
        fin = _combinar(fecha, bloque.hora_fin)
        consulta = Espacio.objects.disponibles(inicio, fin, capacidad).select_related("tipo_espacio")
        if tipo is not None:
            consulta = consulta.filter(tipo_espacio=tipo)
        espacios = list(consulta)
        _marcar_ocupados(espacios, fecha)
        for espacio in espacios:
            espacio.clase_media = _clase_media(espacio.tipo_espacio.nombre)

    total = len(espacios)
    if total == 1:
        resumen = "1 espacio disponible"
    else:
        resumen = f"{total} espacios disponibles"

    return render(
        request,
        "reservas/buscar_disponibilidad.html",
        {
            "bloques": bloques,
            "tipos": tipos,
            "fecha": fecha,
            "fecha_valor": fecha.isoformat() if fecha else request.GET.get("fecha", ""),
            "fecha_legible": _fecha_legible(fecha) if fecha else "",
            "bloque": bloque,
            "tipo_id": str(tipo.pk) if tipo else "",
            "capacidad": request.GET.get("capacidad", ""),
            "errores": errores,
            "espacios": espacios,
            "resumen": resumen,
            "consulto": consulto,
            **_barra(request.user),
        },
    )


def _inicial_solicitud(request):
    inicial = {}
    if request.GET.get("espacio"):
        inicial["espacio"] = request.GET.get("espacio")
    if request.GET.get("horario"):
        inicial["horario"] = request.GET.get("horario")
    fecha_texto = request.GET.get("fecha")
    if fecha_texto:
        fecha, error = _parse_fecha(fecha_texto)
        if fecha and not error:
            inicial["fecha"] = fecha
    else:
        inicial["fecha"] = timezone.localdate()
    return inicial


def _fecha_valor(form):
    valor = form["fecha"].value()
    if hasattr(valor, "isoformat"):
        return valor.isoformat()
    return valor or ""


@login_required
def solicitar_reserva(request):
    """T21 a T24: valida capacidad y traslape, aprueba y guarda con Reserva.solicitar()."""
    if request.method == "POST":
        form = SolicitudReservaForm(request.POST, usuario=request.user)
        if form.is_valid():
            reserva = form.guardar()
            if reserva is not None:
                return redirect("confirmacion_reserva", pk=reserva.pk)
    else:
        form = SolicitudReservaForm(initial=_inicial_solicitud(request), usuario=request.user)
    return render(
        request,
        "reservas/solicitar_reserva.html",
        {"form": form, "fecha_valor": _fecha_valor(form), **_barra(request.user)},
    )


@login_required
def confirmacion_reserva(request, pk):
    reserva = get_object_or_404(Reserva, pk=pk, usuario=request.user)
    inicio = timezone.localtime(reserva.inicio)
    fin = timezone.localtime(reserva.fin)
    return render(
        request,
        "reservas/confirmacion_reserva.html",
        {
            "reserva": reserva,
            "fecha_legible": _fecha_legible(inicio.date()),
            "fecha_valor": inicio.date().isoformat(),
            "horario_legible": f"{inicio:%H:%M} - {fin:%H:%M}",
            **_barra(request.user),
        },
    )


@require_POST
def salir(request):
    logout(request)
    return redirect("login")
