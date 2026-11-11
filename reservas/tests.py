from datetime import timedelta

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from usuarios.models import Usuario

from .models import Espacio, Reserva, TipoEspacio


class ReglasDeReservaTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="ana", email="ana@ues.edu.sv", password="ClaveSegura2026"
        )
        self.tipo = TipoEspacio.objects.create(nombre="Aula de prueba")
        self.espacio = Espacio.objects.create(
            codigo="AULA-T01",
            nombre="Aula de prueba",
            tipo_espacio=self.tipo,
            capacidad=30,
        )
        inicio = timezone.now() + timedelta(days=1)
        self.inicio = inicio.replace(hour=8, minute=0, second=0, microsecond=0)
        self.fin = inicio.replace(hour=9, minute=40, second=0, microsecond=0)

    def reserva(self, **cambios):
        datos = {
            "usuario": self.usuario,
            "espacio": self.espacio,
            "inicio": self.inicio,
            "fin": self.fin,
            "cantidad_personas": 10,
            "motivo_detalle": "Clase de reposición",
        }
        datos.update(cambios)
        return Reserva(**datos)

    def test_un_espacio_no_acepta_capacidad_cero(self):
        with self.assertRaises(IntegrityError):
            Espacio.objects.create(
                codigo="AULA-0",
                nombre="Sin cupo",
                tipo_espacio=self.tipo,
                capacidad=0,
            )

    def test_la_hora_de_fin_debe_ser_posterior_a_la_de_inicio(self):
        with self.assertRaises(IntegrityError):
            self.reserva(fin=self.inicio).save()

    def test_una_reserva_rechazada_exige_motivo(self):
        with self.assertRaises(IntegrityError):
            self.reserva(estado=Reserva.Estado.RECHAZADA, motivo_rechazo="").save()

    def test_los_asistentes_no_pueden_superar_la_capacidad(self):
        with self.assertRaises(IntegrityError):
            self.reserva(cantidad_personas=31).save()

    def test_una_reserva_valida_queda_pendiente(self):
        reserva = self.reserva()
        reserva.save()
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.PENDIENTE)
        self.assertEqual(reserva.cantidad_personas, 10)
