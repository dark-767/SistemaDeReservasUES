"""Datos de prueba para consultar solicitudes, disponibilidad y calendario.

Vuelve a ejecutarse sin duplicar usuarios ni reservas de estos correos.
No cambia la contraseña del administrador que ya exista.
"""

from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from reservas.models import BloqueHorario, Espacio, MotivoReserva, Reserva
from reservas.semilla import cargar_espacios
from usuarios.models import Usuario

CLAVE = "ClaveSegura2026"

USUARIOS = (
    {
        "email": "ana.martinez@ues.edu.sv",
        "nombre": "Ana",
        "apellido": "Martínez",
        "rol": Usuario.Rol.USUARIO,
    },
    {
        "email": "carlos.lopez@ues.edu.sv",
        "nombre": "Carlos",
        "apellido": "López",
        "rol": Usuario.Rol.USUARIO,
    },
)


def _combinar(fecha, hora):
    return timezone.make_aware(datetime.combine(fecha, hora), timezone.get_current_timezone())


class Command(BaseCommand):
    help = "Carga espacios, usuarios y reservas de ejemplo para probar el sistema."

    def handle(self, *args, **options):
        espacios_creados, espacios_actualizados = cargar_espacios()
        usuarios = {item["email"]: self._usuario(item) for item in USUARIOS}
        admin = Usuario.objects.filter(rol=Usuario.Rol.ADMIN).order_by("id").first()
        if admin is None:
            admin = self._usuario(
                {
                    "email": "admin@ues.edu.sv",
                    "nombre": "Ada",
                    "apellido": "Administradora",
                    "rol": Usuario.Rol.ADMIN,
                }
            )
            self.stdout.write(f"Administrador de prueba: {admin.email} / {CLAVE}")
        else:
            self.stdout.write(f"Se usa el administrador existente: {admin.email}")

        Reserva.objects.filter(usuario__in=usuarios.values()).delete()
        creadas = self._reservas(usuarios, admin)

        self.stdout.write(
            self.style.SUCCESS(
                f"Espacios: {espacios_creados} creados, {espacios_actualizados} actualizados."
            )
        )
        self.stdout.write(self.style.SUCCESS(f"Reservas de prueba: {creadas}."))
        self.stdout.write("Cuentas de usuario (contraseña " + CLAVE + "):")
        for correo in usuarios:
            self.stdout.write(f"  {correo}")

    def _usuario(self, datos):
        usuario, creado = Usuario.objects.get_or_create(
            email=datos["email"],
            defaults={
                "username": datos["email"],
                "first_name": datos["nombre"],
                "last_name": datos["apellido"],
                "rol": datos["rol"],
            },
        )
        if creado:
            usuario.set_password(CLAVE)
            usuario.save()
        return usuario

    def _reservas(self, usuarios, admin):
        ana = usuarios["ana.martinez@ues.edu.sv"]
        carlos = usuarios["carlos.lopez@ues.edu.sv"]
        hoy = timezone.localdate()
        bloques = {b.nombre: b for b in BloqueHorario.objects.filter(activo=True)}
        motivos = {m.nombre: m for m in MotivoReserva.objects.all()}
        espacios = {e.codigo: e for e in Espacio.objects.all()}

        filas = (
            {
                "usuario": ana,
                "codigo": "B-21",
                "bloque": "Bloque 1",
                "motivo": "Clase",
                "detalle": "Refuerzo de Análisis de Sistemas, grupo 02",
                "dia": hoy + timedelta(days=2),
                "personas": 40,
                "estado": Reserva.Estado.APROBADA,
            },
            {
                "usuario": ana,
                "codigo": "L-INF-01",
                "bloque": "Bloque 2",
                "motivo": "Práctica de laboratorio",
                "detalle": "Práctica de consultas SQL",
                "dia": hoy + timedelta(days=4),
                "personas": 24,
                "estado": Reserva.Estado.PENDIENTE,
            },
            {
                "usuario": ana,
                "codigo": "AUD-FIA",
                "bloque": "Bloque 4",
                "motivo": "Taller o capacitación",
                "detalle": "Defensa de anteproyecto",
                "dia": hoy + timedelta(days=6),
                "personas": 80,
                "estado": Reserva.Estado.RECHAZADA,
                "motivo_rechazo": (
                    "Evento institucional. El auditorio se usará para la ceremonia "
                    "de graduación. Puedes reservar otro espacio en el mismo horario."
                ),
                "gestionado_por": admin,
            },
            {
                "usuario": ana,
                "codigo": "C-08",
                "bloque": "Bloque 3",
                "motivo": "Reunión",
                "detalle": "Coordinación de proyecto",
                "dia": hoy + timedelta(days=3),
                "personas": 12,
                "estado": Reserva.Estado.CANCELADA,
                "gestionado_por": ana,
            },
            {
                "usuario": ana,
                "codigo": "B-12",
                "bloque": "Bloque 1",
                "motivo": "Clase",
                "detalle": "Clase regular",
                "dia": hoy - timedelta(days=7),
                "personas": 35,
                "estado": Reserva.Estado.APROBADA,
            },
            {
                "usuario": carlos,
                "codigo": "B-21",
                "bloque": "Bloque 3",
                "motivo": "Clase",
                "detalle": "Programación I",
                "dia": hoy + timedelta(days=2),
                "personas": 40,
                "estado": Reserva.Estado.APROBADA,
            },
            {
                "usuario": carlos,
                "codigo": "L-INF-02",
                "bloque": "Bloque 5",
                "motivo": "Examen",
                "detalle": "Segundo parcial",
                "dia": hoy + timedelta(days=5),
                "personas": 20,
                "estado": Reserva.Estado.APROBADA,
            },
        )

        for fila in filas:
            bloque = bloques[fila["bloque"]]
            Reserva.objects.create(
                usuario=fila["usuario"],
                espacio=espacios[fila["codigo"]],
                motivo=motivos[fila["motivo"]],
                motivo_detalle=fila["detalle"],
                bloque_horario=bloque,
                inicio=_combinar(fila["dia"], bloque.hora_inicio),
                fin=_combinar(fila["dia"], bloque.hora_fin),
                cantidad_personas=fila["personas"],
                estado=fila["estado"],
                motivo_rechazo=fila.get("motivo_rechazo", ""),
                gestionado_por=fila.get("gestionado_por"),
                fecha_gestion=timezone.now() if fila.get("gestionado_por") else None,
            )
        return len(filas)
