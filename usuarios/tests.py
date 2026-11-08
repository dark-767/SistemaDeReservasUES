from django.test import TestCase
from django.urls import reverse

from .models import Usuario

DATOS = {
    "nombre": "Ana Martínez",
    "correo": "ana@ues.edu.sv",
    "contrasena": "ClaveSegura2026",
    "confirmar": "ClaveSegura2026",
}


def crear_admin():
    return Usuario.objects.create_user(
        username="admin", email="admin@ues.edu.sv", password="ClaveSegura2026", rol=Usuario.Rol.ADMIN
    )


class FlujoInicialTests(TestCase):
    def test_sin_administrador_la_primera_pantalla_es_la_bienvenida(self):
        r = self.client.get(reverse("inicio"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Debes crear una cuenta primero")
        self.assertContains(r, reverse("registro"))

    def test_sin_administrador_login_lleva_a_la_bienvenida(self):
        self.assertRedirects(self.client.get(reverse("login")), reverse("inicio"))

    def test_con_administrador_la_primera_pantalla_es_el_inicio_de_sesion(self):
        crear_admin()
        self.assertRedirects(self.client.get(reverse("inicio")), reverse("login"))
        r = self.client.get(reverse("login"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Trabajando en la Vista de Inicio de sesion")

    def test_un_usuario_normal_no_cuenta_como_administrador(self):
        Usuario.objects.create_user(username="u", email="u@ues.edu.sv", password="ClaveSegura2026")
        self.assertEqual(self.client.get(reverse("inicio")).status_code, 200)

    def test_con_administrador_el_registro_publico_se_cierra(self):
        crear_admin()
        self.assertRedirects(self.client.get(reverse("registro")), reverse("login"))
        self.client.post(reverse("registro"), DATOS)
        self.assertEqual(Usuario.objects.count(), 1)


class RegistroTests(TestCase):
    def test_formulario_se_muestra(self):
        r = self.client.get(reverse("registro"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Crear cuenta")

    def test_el_primer_registro_crea_el_administrador_y_muestra_confirmacion(self):
        r = self.client.post(reverse("registro"), DATOS, follow=True)
        self.assertRedirects(r, reverse("registro_exitoso"))
        self.assertContains(r, "Cuenta creada con éxito")

        u = Usuario.objects.get(email="ana@ues.edu.sv")
        self.assertEqual((u.first_name, u.last_name), ("Ana", "Martínez"))
        self.assertEqual(u.rol, Usuario.Rol.ADMIN)
        self.assertTrue(u.es_admin)
        self.assertFalse(u.is_superuser)
        self.assertNotEqual(u.password, DATOS["contrasena"])
        self.assertTrue(u.check_password(DATOS["contrasena"]))

    def test_tras_registrarse_la_primera_pantalla_pasa_a_ser_el_login(self):
        self.client.post(reverse("registro"), DATOS)
        self.assertRedirects(self.client.get(reverse("inicio")), reverse("login"))

    def test_confirmacion_solo_se_ve_una_vez(self):
        self.client.post(reverse("registro"), DATOS)
        self.assertEqual(self.client.get(reverse("registro_exitoso")).status_code, 200)
        self.assertRedirects(self.client.get(reverse("registro_exitoso")), reverse("inicio"), fetch_redirect_response=False)

    def test_confirmacion_sin_registrarse_redirige(self):
        self.assertRedirects(self.client.get(reverse("registro_exitoso")), reverse("inicio"))

    def test_campos_obligatorios(self):
        r = self.client.post(reverse("registro"), {})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "No se pudo crear la cuenta")
        self.assertContains(r, "Ingresa tu nombre completo.")
        self.assertContains(r, "Ingresa tu correo electrónico.")
        self.assertContains(r, "Ingresa una contraseña.")
        self.assertContains(r, "Confirma tu contraseña.")
        self.assertEqual(Usuario.objects.count(), 0)

    def test_correo_invalido(self):
        r = self.client.post(reverse("registro"), {**DATOS, "correo": "no-es-correo"})
        self.assertContains(r, "Ingresa un correo electrónico válido.")
        self.assertEqual(Usuario.objects.count(), 0)

    def test_correo_repetido_sin_distinguir_mayusculas(self):
        Usuario.objects.create_user(username="ana", email="ana@ues.edu.sv", password="ClaveSegura2026")
        r = self.client.post(reverse("registro"), {**DATOS, "correo": "ANA@ues.edu.sv"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Este correo electrónico ya está registrado.")
        self.assertEqual(Usuario.objects.count(), 1)

    def test_contrasenas_distintas(self):
        r = self.client.post(reverse("registro"), {**DATOS, "confirmar": "OtraClave2026"})
        self.assertContains(r, "Las contraseñas no coinciden.")
        self.assertEqual(Usuario.objects.count(), 0)

    def test_contrasena_corta_o_comun(self):
        r = self.client.post(reverse("registro"), {**DATOS, "contrasena": "abc", "confirmar": "abc"})
        self.assertContains(r, "field__error")
        self.assertEqual(Usuario.objects.count(), 0)

    def test_no_se_puede_pedir_superusuario_desde_el_formulario(self):
        self.client.post(reverse("registro"), {**DATOS, "is_superuser": "on", "rol": "usuario"})
        u = Usuario.objects.get()
        self.assertFalse(u.is_superuser)
        self.assertEqual(u.rol, Usuario.Rol.ADMIN)

    def test_se_puede_iniciar_sesion_con_el_correo(self):
        self.client.post(reverse("registro"), DATOS)
        self.assertTrue(self.client.login(username="ana@ues.edu.sv", password=DATOS["contrasena"]))
