from datetime import datetime, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from usuarios.models import Usuario

from .models import BloqueHorario, Espacio, MotivoReserva, Reserva, TipoEspacio


def combinar(fecha, hora):
    return timezone.make_aware(datetime.combine(fecha, hora), timezone.get_current_timezone())


class SolicitudReservaTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="ana",
            email="ana@ues.edu.sv",
            password="ClaveSegura2026",
            first_name="Ana",
            last_name="Martinez",
        )
        self.client.force_login(self.usuario)
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

    def datos(self, **cambios):
        datos = {
            "espacio": self.espacio.pk,
            "fecha": self.fecha.isoformat(),
            "horario": self.bloque.pk,
            "cantidad": 10,
            "motivo": self.motivo.pk,
            "detalle": "Clase de reposición",
        }
        datos.update(cambios)
        return datos

    def test_sin_sesion_redirige_al_login(self):
        self.client.logout()
        respuesta = self.client.get(reverse("solicitar_reserva"))
        self.assertRedirects(
            respuesta,
            f"{reverse('login')}?next={reverse('solicitar_reserva')}",
            fetch_redirect_response=False,
        )

    def test_la_capacidad_excedida_no_guarda_la_reserva(self):
        respuesta = self.client.post(reverse("solicitar_reserva"), self.datos(cantidad=31))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Supera la capacidad del espacio (30)")
        self.assertEqual(Reserva.objects.count(), 0)

    def test_el_traslape_con_una_reserva_aprobada_no_guarda_otra(self):
        Reserva.objects.create(
            usuario=self.usuario,
            espacio=self.espacio,
            bloque_horario=self.bloque,
            motivo=self.motivo,
            motivo_detalle="Clase ya aprobada",
            inicio=combinar(self.fecha, self.bloque.hora_inicio),
            fin=combinar(self.fecha, self.bloque.hora_fin),
            cantidad_personas=10,
            estado=Reserva.Estado.APROBADA,
        )
        respuesta = self.client.post(reverse("solicitar_reserva"), self.datos())
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Ya existe una reserva aprobada en ese espacio y horario.")
        self.assertEqual(Reserva.objects.count(), 1)

    def test_una_solicitud_valida_queda_aprobada_y_ocupa_el_horario(self):
        respuesta = self.client.post(reverse("solicitar_reserva"), self.datos(), follow=True)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Aprobada")
        reserva = Reserva.objects.get()
        self.assertEqual(reserva.estado, Reserva.Estado.APROBADA)
        self.assertEqual(reserva.usuario, self.usuario)
        self.assertEqual(reserva.espacio, self.espacio)
        self.assertEqual(reserva.cantidad_personas, 10)
        busqueda = self.client.get(
            reverse("buscar_disponibilidad"),
            {"fecha": self.fecha.isoformat(), "horario": self.bloque.pk},
        )
        self.assertNotContains(busqueda, "Aula B-21")
