from datetime import datetime, time, timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from usuarios.models import Usuario

from .models import BloqueHorario, Espacio, Reserva, TipoEspacio
from .semilla import ESPACIOS


def combinar(fecha, hora):
    return timezone.make_aware(datetime.combine(fecha, hora), timezone.get_current_timezone())


class SeederEspaciosTests(TestCase):
    def test_carga_el_catalogo_sin_duplicar(self):
        salida = StringIO()
        call_command("seed_espacios", stdout=salida)
        self.assertIn("12 creados", salida.getvalue())
        self.assertEqual(Espacio.objects.count(), len(ESPACIOS))
        aula = Espacio.objects.get(codigo="B-21")
        self.assertEqual(aula.nombre, "Aula B-21")
        self.assertEqual(aula.tipo_espacio.nombre, "Aula")
        self.assertEqual(aula.capacidad, 60)
        self.assertEqual(Espacio.objects.get(codigo="AUD-FIA").tipo_espacio.nombre, "Auditorio")
        self.assertEqual(TipoEspacio.objects.filter(nombre="Sala de reuniones").count(), 1)

        aula.activo = False
        aula.capacidad = 1
        aula.save(update_fields=["activo", "capacidad"])
        segunda = StringIO()
        call_command("seed_espacios", stdout=segunda)
        aula.refresh_from_db()
        self.assertEqual(Espacio.objects.count(), len(ESPACIOS))
        self.assertTrue(aula.activo)
        self.assertEqual(aula.capacidad, 60)
        self.assertIn("0 creados", segunda.getvalue())

    def test_la_pantalla_lista_los_espacios_cargados(self):
        call_command("seed_espacios", stdout=StringIO())
        usuario = Usuario.objects.create_user(
            username="ana", email="ana@ues.edu.sv", password="ClaveSegura2026", first_name="Ana", last_name="Martinez"
        )
        self.client.force_login(usuario)
        respuesta = self.client.get(reverse("buscar_disponibilidad"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "12 espacios disponibles")
        self.assertContains(respuesta, "Aula B-21")
        self.assertContains(respuesta, "Laboratorio de Informática 1")
        self.assertContains(respuesta, "Auditorio de la Facultad")
        self.assertContains(respuesta, "Sala de reuniones de Escuela")
        self.assertContains(respuesta, "AM")


class ConsultaDisponibilidadTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="ana", email="ana@ues.edu.sv", password="ClaveSegura2026", first_name="Ana", last_name="Martinez"
        )
        self.client.force_login(self.usuario)
        self.aula = TipoEspacio.objects.get(nombre="Aula")
        self.laboratorio = TipoEspacio.objects.get(nombre="Laboratorio")
        self.bloque = BloqueHorario.objects.get(nombre="Bloque 1")
        self.tarde = BloqueHorario.objects.get(nombre="Bloque 4")
        self.fecha = timezone.localdate() + timedelta(days=2)
        self.libre = self.espacio("B-21", "Aula B-21", self.aula, 60)
        self.ocupado = self.espacio("B-12", "Aula B-12", self.aula, 45)
        self.laboratorio_libre = self.espacio("L-INF-01", "Laboratorio de Informática 1", self.laboratorio, 24)
        self.pendiente = self.espacio("C-08", "Aula C-08", self.aula, 40)
        self.inactivo = self.espacio("A-00", "Aula inactiva", self.aula, 50, activo=False)
        self.reservar(self.ocupado, self.bloque, Reserva.Estado.APROBADA)
        self.reservar(self.libre, self.tarde, Reserva.Estado.APROBADA)
        self.reservar(self.pendiente, self.bloque, Reserva.Estado.PENDIENTE)

    def espacio(self, codigo, nombre, tipo, capacidad, activo=True):
        return Espacio.objects.create(
            codigo=codigo,
            nombre=nombre,
            tipo_espacio=tipo,
            ubicacion="Edificio B, nivel 2",
            capacidad=capacidad,
            activo=activo,
        )

    def reservar(self, espacio, bloque, estado):
        return Reserva.objects.create(
            usuario=self.usuario,
            espacio=espacio,
            bloque_horario=bloque,
            inicio=combinar(self.fecha, bloque.hora_inicio),
            fin=combinar(self.fecha, bloque.hora_fin),
            cantidad_personas=10,
            motivo_detalle="Clase de reposición",
            estado=estado,
        )

    def buscar(self, **cambios):
        datos = {"fecha": self.fecha.isoformat(), "horario": self.bloque.pk}
        datos.update(cambios)
        return self.client.get(reverse("buscar_disponibilidad"), datos)

    def test_sin_sesion_redirige_al_login(self):
        self.client.logout()
        respuesta = self.client.get(reverse("buscar_disponibilidad"))
        self.assertRedirects(
            respuesta,
            f"{reverse('login')}?next={reverse('buscar_disponibilidad')}",
            fetch_redirect_response=False,
        )

    def test_un_espacio_aprobado_en_el_bloque_no_aparece_y_uno_pendiente_si(self):
        respuesta = self.buscar()
        self.assertContains(respuesta, "3 espacios disponibles")
        self.assertContains(respuesta, "Aula B-21")
        self.assertContains(respuesta, "Aula C-08")
        self.assertContains(respuesta, "Laboratorio de Informática 1")
        self.assertNotContains(respuesta, "Aula B-12")
        self.assertNotContains(respuesta, "Aula inactiva")
        self.assertContains(respuesta, "13:00 - 14:40")

    def test_filtra_por_capacidad_y_por_tipo(self):
        por_capacidad = self.buscar(capacidad=40)
        self.assertContains(por_capacidad, "2 espacios disponibles")
        self.assertContains(por_capacidad, "Aula B-21")
        self.assertNotContains(por_capacidad, "Laboratorio de Informática 1")

        por_tipo = self.buscar(tipo=self.laboratorio.pk)
        self.assertContains(por_tipo, "1 espacio disponible")
        self.assertContains(por_tipo, "Laboratorio de Informática 1")
        self.assertNotContains(por_tipo, "Aula B-21")

    def test_un_tipo_invalido_no_rompe_la_consulta(self):
        respuesta = self.buscar(tipo="abc")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Selecciona un tipo de espacio válido.")
        self.assertNotContains(respuesta, 'id="resultados"')

    def test_una_fecha_invalida_no_consulta(self):
        respuesta = self.buscar(fecha="no-es-fecha")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Ingresa una fecha válida.")
        self.assertNotContains(respuesta, 'id="resultados"')

    def test_salir_cierra_la_sesion(self):
        respuesta = self.client.post(reverse("salir"))
        self.assertRedirects(respuesta, reverse("login"), fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)
