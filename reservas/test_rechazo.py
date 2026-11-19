from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from usuarios.models import Usuario

from .models import BloqueHorario, Espacio, MotivoReserva, Reserva, TipoEspacio


def combinar(fecha, hora):
    return timezone.make_aware(datetime.combine(fecha, hora), timezone.get_current_timezone())


class RechazoDeSolicitudTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user(
            username="admin",
            email="admin@ues.edu.sv",
            password="ClaveSegura2026",
            first_name="Ana",
            last_name="Admin",
            rol=Usuario.Rol.ADMIN,
        )
        self.usuario = Usuario.objects.create_user(
            username="ana",
            email="ana@ues.edu.sv",
            password="ClaveSegura2026",
            first_name="Ana",
            last_name="Martinez",
        )
        self.otro = Usuario.objects.create_user(
            username="luis",
            email="luis@ues.edu.sv",
            password="ClaveSegura2026",
            first_name="Luis",
            last_name="Perez",
        )
        self.aula = TipoEspacio.objects.get(nombre="Aula")
        self.bloque = BloqueHorario.objects.get(nombre="Bloque 1")
        self.motivo = MotivoReserva.objects.get(nombre="Clase")
        self.fecha = timezone.localdate() + timedelta(days=2)
        self.espacio = Espacio.objects.create(
            codigo="B-21",
            nombre="Aula B-21",
            tipo_espacio=self.aula,
            ubicacion="Edificio B, nivel 2",
            capacidad=30,
        )

    def crear_reserva(self, estado=Reserva.Estado.APROBADA, usuario=None, **cambios):
        datos = {
            "usuario": usuario or self.usuario,
            "espacio": self.espacio,
            "bloque_horario": self.bloque,
            "motivo": self.motivo,
            "motivo_detalle": "Clase de reposición",
            "inicio": combinar(self.fecha, self.bloque.hora_inicio),
            "fin": combinar(self.fecha, self.bloque.hora_fin),
            "cantidad_personas": 10,
            "estado": estado,
        }
        datos.update(cambios)
        return Reserva.objects.create(**datos)

    def test_sin_sesion_solicitudes_redirige_al_login(self):
        respuesta = self.client.get(reverse("solicitudes"))
        self.assertRedirects(
            respuesta,
            f"{reverse('login')}?next={reverse('solicitudes')}",
            fetch_redirect_response=False,
        )

    def test_sin_sesion_mis_solicitudes_redirige_al_login(self):
        respuesta = self.client.get(reverse("mis_solicitudes"))
        self.assertRedirects(
            respuesta,
            f"{reverse('login')}?next={reverse('mis_solicitudes')}",
            fetch_redirect_response=False,
        )

    def test_un_usuario_normal_no_ve_las_solicitudes_del_administrador(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("solicitudes"))
        self.assertEqual(respuesta.status_code, 403)

    def test_un_usuario_normal_no_puede_rechazar(self):
        reserva = self.crear_reserva()
        self.client.force_login(self.usuario)
        respuesta = self.client.post(
            reverse("rechazar_solicitud", args=[reserva.pk]),
            {"motivo": "Evento institucional"},
        )
        self.assertEqual(respuesta.status_code, 403)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.APROBADA)

    def test_el_administrador_ve_solicitudes_pendientes_y_aprobadas(self):
        self.crear_reserva(estado=Reserva.Estado.APROBADA)
        self.crear_reserva(
            estado=Reserva.Estado.PENDIENTE,
            inicio=combinar(self.fecha + timedelta(days=1), self.bloque.hora_inicio),
            fin=combinar(self.fecha + timedelta(days=1), self.bloque.hora_fin),
        )
        self.crear_reserva(
            estado=Reserva.Estado.RECHAZADA,
            motivo_rechazo="Ya rechazada",
            inicio=combinar(self.fecha + timedelta(days=2), self.bloque.hora_inicio),
            fin=combinar(self.fecha + timedelta(days=2), self.bloque.hora_fin),
        )
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse("solicitudes"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Aula B-21")
        self.assertContains(respuesta, "Ana Martinez")
        self.assertContains(respuesta, "2 solicitudes pendientes")
        self.assertContains(respuesta, "badge--warning")
        self.assertContains(respuesta, "badge--success")
        self.assertContains(respuesta, "Rechazar")
        self.assertNotContains(respuesta, "Ya rechazada")

    def test_el_administrador_no_ve_reservas_cuyo_horario_ya_paso(self):
        pasado = timezone.now() - timedelta(days=1)
        pasada = self.crear_reserva(
            estado=Reserva.Estado.APROBADA,
            inicio=pasado.replace(hour=7, minute=0, second=0, microsecond=0),
            fin=pasado.replace(hour=8, minute=40, second=0, microsecond=0),
        )
        self.crear_reserva(
            estado=Reserva.Estado.APROBADA,
            inicio=combinar(self.fecha + timedelta(days=1), self.bloque.hora_inicio),
            fin=combinar(self.fecha + timedelta(days=1), self.bloque.hora_fin),
        )
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse("solicitudes"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "1 solicitud pendiente")
        self.assertNotContains(respuesta, reverse("rechazar_solicitud", args=[pasada.pk]))
        self.assertEqual(
            self.client.get(reverse("rechazar_solicitud", args=[pasada.pk])).status_code,
            404,
        )

    def test_el_administrador_abre_el_formulario_de_rechazo(self):
        reserva = self.crear_reserva()
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse("rechazar_solicitud", args=[reserva.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Motivo del rechazo")
        self.assertContains(respuesta, "Aula B-21")
        self.assertContains(respuesta, "Ana Martinez")

    def test_sin_motivo_no_se_rechaza_la_solicitud(self):
        reserva = self.crear_reserva()
        self.client.force_login(self.admin)
        respuesta = self.client.post(reverse("rechazar_solicitud", args=[reserva.pk]), {"motivo": ""})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Debes indicar el motivo del rechazo.")
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.APROBADA)

    def test_un_motivo_en_blanco_no_se_acepta(self):
        reserva = self.crear_reserva()
        self.client.force_login(self.admin)
        respuesta = self.client.post(reverse("rechazar_solicitud", args=[reserva.pk]), {"motivo": "   "})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Debes indicar el motivo del rechazo.")
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.APROBADA)

    def test_el_administrador_rechaza_con_motivo_y_actualiza_el_estado(self):
        reserva = self.crear_reserva()
        self.client.force_login(self.admin)
        respuesta = self.client.post(
            reverse("rechazar_solicitud", args=[reserva.pk]),
            {"motivo": "  Evento institucional  "},
            follow=True,
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Solicitud rechazada")
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.RECHAZADA)
        self.assertEqual(reserva.motivo_rechazo, "Evento institucional")
        self.assertEqual(reserva.gestionado_por, self.admin)
        self.assertIsNotNone(reserva.fecha_gestion)

    def test_el_usuario_consulta_el_resultado_y_el_motivo(self):
        reserva = self.crear_reserva()
        reserva.rechazar(self.admin, "El aula se usará para una ceremonia.")
        self.client.force_login(self.usuario)
        listado = self.client.get(reverse("mis_solicitudes"))
        self.assertEqual(listado.status_code, 200)
        self.assertContains(listado, "Rechazada")
        self.assertContains(listado, "El aula se usará para una ceremonia.")
        detalle = self.client.get(reverse("confirmacion_reserva", args=[reserva.pk]))
        self.assertEqual(detalle.status_code, 200)
        self.assertContains(detalle, "Solicitud rechazada")
        self.assertContains(detalle, "El aula se usará para una ceremonia.")

    def test_otro_usuario_no_consulta_la_solicitud_ajena(self):
        reserva = self.crear_reserva()
        self.client.force_login(self.otro)
        respuesta = self.client.get(reverse("confirmacion_reserva", args=[reserva.pk]))
        self.assertEqual(respuesta.status_code, 404)
        listado = self.client.get(reverse("mis_solicitudes"))
        self.assertNotContains(listado, "Aula B-21")

    def test_al_rechazar_el_horario_queda_libre(self):
        reserva = self.crear_reserva()
        self.client.force_login(self.admin)
        self.client.post(
            reverse("rechazar_solicitud", args=[reserva.pk]),
            {"motivo": "Mantenimiento eléctrico"},
        )
        self.client.force_login(self.usuario)
        busqueda = self.client.get(
            reverse("buscar_disponibilidad"),
            {"fecha": self.fecha.isoformat(), "horario": self.bloque.pk},
        )
        self.assertContains(busqueda, "Aula B-21")

    def test_rechazar_en_el_modelo_exige_administrador_y_motivo(self):
        reserva = self.crear_reserva(estado=Reserva.Estado.PENDIENTE)
        with self.assertRaises(PermissionError):
            reserva.rechazar(self.usuario, "No corresponde")
        with self.assertRaises(ValidationError):
            reserva.rechazar(self.admin, "   ")
        reserva.rechazar(self.admin, "Uso no permitido")
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.RECHAZADA)
        with self.assertRaises(ValidationError):
            reserva.rechazar(self.admin, "Otro motivo")
