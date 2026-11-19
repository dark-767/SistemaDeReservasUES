from datetime import datetime, time, timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction

from .forms import RechazoReservaForm, SolicitudReservaForm
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


CLASES_ESTADO = {
    Reserva.Estado.PENDIENTE: "badge--warning",
    Reserva.Estado.APROBADA: "badge--success",
    Reserva.Estado.RECHAZADA: "badge--danger",
    Reserva.Estado.CANCELADA: "badge--neutral",
}


def solo_admin(view):
    @login_required
    @wraps(view)
    def interior(request, *args, **kwargs):
        if not getattr(request.user, "es_admin", False):
            return HttpResponseForbidden("Solo un administrador puede gestionar solicitudes.")
        return view(request, *args, **kwargs)

    return interior


def _barra(usuario, nav_activa=""):
    return {
        "iniciales": _iniciales(usuario),
        "nombre_usuario": usuario.get_full_name() or usuario.username,
        "rol_usuario": usuario.get_rol_display(),
        "es_admin": getattr(usuario, "es_admin", False),
        "nav_activa": nav_activa,
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


def _presentar(reserva):
    inicio = timezone.localtime(reserva.inicio)
    reserva.fecha_legible = _fecha_legible(inicio.date())
    reserva.fecha_valor = inicio.date().isoformat()
    reserva.horario_legible = _etiqueta_horario(reserva)
    reserva.dia = inicio.day
    reserva.mes_corto = MESES[inicio.month - 1][:3]
    reserva.iniciales_usuario = _iniciales(reserva.usuario)
    reserva.nombre_solicitante = reserva.usuario.get_full_name() or reserva.usuario.username
    reserva.clase_estado = CLASES_ESTADO.get(reserva.estado, "badge--neutral")
    reserva.motivo_texto = reserva.motivo.nombre if reserva.motivo_id else reserva.motivo_detalle
    reserva.inactiva = reserva.estado not in Reserva.ESTADOS_ACTIVOS
    return reserva


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
            **_barra(request.user, "buscar"),
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
    reserva = get_object_or_404(
        Reserva.objects.select_related("espacio", "motivo", "bloque_horario", "usuario"),
        pk=pk,
        usuario=request.user,
    )
    _presentar(reserva)
    titulos = {
        Reserva.Estado.APROBADA: (
            "Reserva registrada",
            "La solicitud cumplió la capacidad y no tiene conflicto de horario.",
        ),
        Reserva.Estado.PENDIENTE: ("Solicitud pendiente", "Tu solicitud está en revisión."),
        Reserva.Estado.RECHAZADA: (
            "Solicitud rechazada",
            "El administrador rechazó esta reserva. El horario quedó libre.",
        ),
        Reserva.Estado.CANCELADA: ("Reserva cancelada", "Esta reserva ya no está vigente."),
    }
    titulo, subtitulo = titulos.get(reserva.estado, ("Solicitud", ""))
    return render(
        request,
        "reservas/confirmacion_reserva.html",
        {
            "reserva": reserva,
            "titulo": titulo,
            "subtitulo": subtitulo,
            **_barra(request.user, "mis_solicitudes"),
        },
    )


@solo_admin
def listar_solicitudes(request):
    """HU04: el administrador ve las solicitudes que todavía puede rechazar."""
    solicitudes = [
        _presentar(reserva)
        for reserva in (
            Reserva.objects.filter(estado__in=Reserva.ESTADOS_ACTIVOS)
            .select_related("usuario", "espacio", "motivo", "bloque_horario")
            .order_by("inicio")
        )
    ]
    return render(
        request,
        "reservas/solicitudes.html",
        {"solicitudes": solicitudes, **_barra(request.user, "solicitudes")},
    )


@solo_admin
def rechazar_solicitud(request, pk):
    """HU04: selecciona una solicitud activa y la rechaza con motivo."""
    reserva = get_object_or_404(
        Reserva.objects.select_related("usuario", "espacio", "motivo", "bloque_horario"),
        pk=pk,
        estado__in=Reserva.ESTADOS_ACTIVOS,
    )
    _presentar(reserva)
    if request.method == "POST":
        form = RechazoReservaForm(request.POST)
        if form.is_valid():
            try:
                reserva.rechazar(request.user, form.cleaned_data["motivo"])
            except ValidationError as exc:
                form.add_error("motivo", exc.messages[0] if getattr(exc, "messages", None) else exc)
            except PermissionError:
                return HttpResponseForbidden("Solo un administrador puede rechazar reservas.")
            else:
                messages.success(
                    request,
                    "Solicitud rechazada. El usuario verá el motivo en Mis solicitudes.",
                )
                return redirect("solicitudes")
    else:
        form = RechazoReservaForm()
    return render(
        request,
        "reservas/rechazar_solicitud.html",
        {"form": form, "reserva": reserva, **_barra(request.user, "solicitudes")},
    )

@login_required
def consultar_solicitudes(request):
    """
    Consulta las reservas propias del usuario.
    Filtros: todas, proximas y cancelada.
    """

    ahora = timezone.now()

    filtros_validos = (
        "todas",
        "proximas",
        "cancelada"
    )

    filtro = request.GET.get("estado", "todas")

    if filtro not in filtros_validos:
        filtro = "todas"

    todas = list(
        Reserva.objects.filter(
            usuario=request.user
        )
        .select_related(
            "espacio",
            "espacio__tipo_espacio",
            "motivo",
            "bloque_horario",
            "gestionado_por"
        )
        .order_by("-inicio")
    )

    proximas = [
        r for r in todas
        if r.estado in Reserva.ESTADOS_ACTIVOS
        and r.inicio > ahora
    ]

    canceladas = [
        r for r in todas
        if r.estado == Reserva.Estado.CANCELADA
    ]

    if filtro == "proximas":
        seleccionadas = proximas

    elif filtro == "cancelada":
        seleccionadas = canceladas

    else:
        seleccionadas = todas

    solicitudes = []

    for r in seleccionadas:

        inicio_local = timezone.localtime(r.inicio)

        es_pendiente = (
            r.estado == Reserva.Estado.PENDIENTE
        )

        es_aprobada = (
            r.estado == Reserva.Estado.APROBADA
        )

        es_rechazada = (
            r.estado == Reserva.Estado.RECHAZADA
        )

        es_cancelada_admin = (
            r.estado == Reserva.Estado.CANCELADA
            and r.gestionado_por_id is not None
            and r.gestionado_por_id != r.usuario_id
        )

        es_cancelada_usuario = (
            r.estado == Reserva.Estado.CANCELADA
            and not es_cancelada_admin
        )

        es_proxima = (
            r.estado in Reserva.ESTADOS_ACTIVOS
            and r.inicio > ahora
        )

        ya_paso = (
            r.estado in Reserva.ESTADOS_ACTIVOS
            and r.inicio <= ahora
        )

        motivo_base = (
            r.motivo.nombre
            if r.motivo_id
            else "Otro motivo"
        )

        motivo_completo = (
            f"{motivo_base} · {r.motivo_detalle}"
            if r.motivo_detalle
            else motivo_base
        )

        solicitudes.append({
            "id": r.pk,
            "pk": r.pk,
            "espacio_id": r.espacio_id,
            "espacio_nombre": r.espacio.nombre,
            "espacio_codigo": r.espacio.codigo,
            "espacio_ubicacion": r.espacio.ubicacion,
            "dia_num": inicio_local.day,
            "mes_corto": MESES[inicio_local.month - 1][:3],
            "fecha_legible": _fecha_legible(
                inicio_local.date()
            ),
            "fecha_iso": inicio_local.date().isoformat(),
            "horario": _etiqueta_horario(r),
            "tipo_bloque": (
                "Hora clase"
                if r.bloque_horario_id
                else "Horario libre"
            ),
            "motivo_completo": motivo_completo,
            "cantidad_personas": r.cantidad_personas,
            "estado": r.estado,
            "estado_display": r.get_estado_display(),
            "motivo_rechazo": r.motivo_rechazo,
            "es_pendiente": es_pendiente,
            "es_aprobada": es_aprobada,
            "es_rechazada": es_rechazada,
            "es_cancelada_admin": es_cancelada_admin,
            "es_cancelada_usuario": es_cancelada_usuario,
            "es_proxima": es_proxima,
            "ya_paso": ya_paso,
            "inactiva": (
                es_rechazada
                or r.estado == Reserva.Estado.CANCELADA
                or ya_paso
            ),
        })

    return render(
        request,
        "reservas/mis_solicitudes.html",
        {
            "solicitudes": solicitudes,
            "filtro": filtro,
            "total_todas": len(todas),
            "total_proximas": len(proximas),
            "total_canceladas": len(canceladas),
            **_barra(request.user),
            "nav_activa": "mis_solicitudes",
        }
    )


@login_required
def mis_solicitudes(request):
    """El usuario consulta el resultado de sus solicitudes, incluido el motivo de rechazo."""
    reservas = [
        _presentar(reserva)
        for reserva in (
            Reserva.objects.filter(usuario=request.user)
            .select_related("espacio", "motivo", "bloque_horario")
            .order_by("-inicio")
        )
    ]
    return render(
        request,
        "reservas/mis_solicitudes.html",
        {"reservas": reservas, **_barra(request.user, "mis_solicitudes")},
    )

def consultar_calendario(request):
    """Consulta y renderiza el calendario real por semana o día desde PostgreSQL."""
    vista = request.GET.get("vista", "semana")
    if vista not in ("semana", "dia"):
        vista = "semana"

    fecha_base, error_fecha = _parse_fecha(request.GET.get("fecha"))
    if error_fecha or not fecha_base:
        fecha_base = timezone.localdate()

    # Lunes de la semana seleccionada (lunes=0 ... domingo=6)
    lunes = fecha_base - timedelta(days=fecha_base.weekday())
    dias_semana = [lunes + timedelta(days=i) for i in range(6)]  # Lunes a Sábado
    hoy = timezone.localdate()

    # Navegación anterior / siguiente
    salto = timedelta(days=7) if vista == "semana" else timedelta(days=1)
    fecha_anterior = (fecha_base - salto).isoformat()
    fecha_siguiente = (fecha_base + salto).isoformat()

    sabado = dias_semana[-1]
    if lunes.month == sabado.month:
        rango_semana_label = f"{lunes.day} – {sabado.day} de {MESES[lunes.month - 1]}"
    else:
        rango_semana_label = (
            f"{lunes.day} de {MESES[lunes.month - 1][:3]} – "
            f"{sabado.day} de {MESES[sabado.month - 1][:3]}"
        )
    dia_label = _fecha_legible(fecha_base)

    tipos = list(TipoEspacio.objects.filter(espacios__activo=True).distinct().order_by("nombre"))
    tipo_id = request.GET.get("tipo") or ""
    espacios_qs = Espacio.objects.filter(activo=True).select_related("tipo_espacio").order_by("codigo")
    if tipo_id.isdigit():
        espacios_qs = espacios_qs.filter(tipo_espacio_id=int(tipo_id))
    espacios = list(espacios_qs)

    espacio_id = request.GET.get("espacio") or ""
    espacio_actual = None
    if espacios:
        if espacio_id.isdigit():
            espacio_actual = next((e for e in espacios if str(e.pk) == espacio_id), None)
        if espacio_actual is None:
            espacio_actual = espacios[0]

    bloques = list(BloqueHorario.objects.filter(activo=True).order_by("hora_inicio"))

    # Rango de consulta en BD según vista
    if vista == "semana":
        inicio_rango = _combinar(lunes, time.min)
        fin_rango = _combinar(sabado + timedelta(days=1), time.min)
        reservas_qs = Reserva.objects.filter(
            estado=Reserva.Estado.APROBADA,
            inicio__lt=fin_rango,
            fin__gt=inicio_rango,
        )
        if espacio_actual:
            reservas_qs = reservas_qs.filter(espacio=espacio_actual)
        else:
            reservas_qs = reservas_qs.none()
    else:
        inicio_rango = _combinar(fecha_base, time.min)
        fin_rango = _combinar(fecha_base + timedelta(days=1), time.min)
        reservas_qs = Reserva.objects.filter(
            estado=Reserva.Estado.APROBADA,
            espacio__in=espacios,
            inicio__lt=fin_rango,
            fin__gt=inicio_rango,
        )

    reservas = list(reservas_qs.select_related("espacio", "motivo", "bloque_horario"))

    def _construir_celda(espacio_obj, fecha_dia, bloque_obj):
        b_ini = _combinar(fecha_dia, bloque_obj.hora_inicio)
        b_fin = _combinar(fecha_dia, bloque_obj.hora_fin)
        match = next(
            (
                r for r in reservas
                if r.espacio_id == espacio_obj.pk and r.inicio < b_fin and r.fin > b_ini
            ),
            None,
        )
        if match:
            es_mia = match.usuario_id == request.user.pk
            es_examen = bool(match.motivo_id and match.motivo.permite_horario_libre)
            if es_mia:
                tipo_evento = "mine"
                titulo_celda = "Tu reserva"
            elif es_examen:
                tipo_evento = "exam"
                titulo_celda = match.motivo.nombre
            else:
                tipo_evento = "busy"
                titulo_celda = "Reservado"

            subtitulo = (
                _etiqueta_horario(match)
                if es_examen and not match.bloque_horario_id
                else (match.motivo.nombre if match.motivo_id else "Reserva")
            )
            return {
                "ocupado": True,
                "tipo": tipo_evento,
                "titulo": titulo_celda,
                "subtitulo": subtitulo,
                "espacio": espacio_obj.nombre,
                "fecha": _fecha_legible(fecha_dia),
                "fecha_iso": fecha_dia.isoformat(),
                "horario": _etiqueta_horario(match),
                "motivo": match.motivo.nombre if match.motivo_id else (match.motivo_detalle or "Reserva"),
            }
        return {
            "ocupado": False,
            "espacio_id": espacio_obj.pk,
            "fecha_iso": fecha_dia.isoformat(),
            "bloque_id": bloque_obj.pk,
        }

    # Filas para vista Semana (un espacio x 6 días)
    filas_semana = []
    if espacio_actual:
        for b in bloques:
            filas_semana.append({
                "horario": f"{b.hora_inicio:%H:%M} – {b.hora_fin:%H:%M}",
                "celdas": [_construir_celda(espacio_actual, d, b) for d in dias_semana],
            })

    # Filas para vista Día (todos los espacios filtrados en fecha_base)
    filas_dia = []
    for b in bloques:
        filas_dia.append({
            "horario": f"{b.hora_inicio:%H:%M} – {b.hora_fin:%H:%M}",
            "celdas": [_construir_celda(e, fecha_base, b) for e in espacios],
        })

    # Primer evento ocupado para inicializar el panel lateral derecho
    primer_evento = None
    filas_activas = filas_semana if vista == "semana" else filas_dia
    for fila in filas_activas:
        for c in fila["celdas"]:
            if c["ocupado"]:
                primer_evento = c
                break
        if primer_evento:
            break

    encabezados_semana = [
        {
            "dia_corto": DIAS[d.weekday()][:3].capitalize(),
            "numero": d.day,
            "es_hoy": d == hoy,
        }
        for d in dias_semana
    ]

    return render(
        request,
        "reservas/calendario.html",
        {
            "vista": vista,
            "fecha_valor": fecha_base.isoformat(),
            "fecha_anterior": fecha_anterior,
            "fecha_siguiente": fecha_siguiente,
            "rango_semana_label": rango_semana_label,
            "dia_label": dia_label,
            "tipos": tipos,
            "tipo_id": tipo_id,
            "espacios": espacios,
            "espacio_actual": espacio_actual,
            "encabezados_semana": encabezados_semana,
            "filas_semana": filas_semana,
            "filas_dia": filas_dia,
            "primer_evento": primer_evento,
            "viene_de_busqueda": bool(request.GET.get("espacio")),
            **_barra(request.user),
        },
    )


@require_POST
def salir(request):
    logout(request)
    return redirect("login")


@login_required
@require_POST
def cancelar_reserva(request, reserva_id):
    """
    HU07: Cancelar una reserva propia.
    """

    with transaction.atomic():

        reserva = get_object_or_404(
            Reserva.objects.select_for_update(),
            pk=reserva_id,
            usuario=request.user
        )

        if reserva.inicio <= timezone.now():
            messages.error(
                request,
                "No puedes cancelar una reserva que ya comenzó."
            )
            return redirect("mis_solicitudes")

        try:
            reserva.cancelar(request.user)

        except ValidationError as error:
            messages.error(
                request,
                "; ".join(error.messages)
            )

        else:
            messages.success(
                request,
                "La reserva se canceló correctamente."
            )

    return redirect("mis_solicitudes")
