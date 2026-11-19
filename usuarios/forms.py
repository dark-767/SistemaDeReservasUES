from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.contrib.auth import authenticate

from .models import Usuario


class RegistroForm(forms.Form):
    """
    Registro de cuenta (HU02). Los nombres de los campos son los de la plantilla
    registro.html. Se usa solo en el primer uso del sistema, así que la cuenta
    que crea es la del administrador.
    """

    nombre = forms.CharField(
        label="Nombre completo",
        max_length=150,
        error_messages={"required": "Ingresa tu nombre completo."},
    )
    correo = forms.EmailField(
        label="Correo electrónico",
        max_length=150,  # también se usa como nombre de usuario (máx. 150)
        error_messages={
            "required": "Ingresa tu correo electrónico.",
            "invalid": "Ingresa un correo electrónico válido.",
        },
    )
    contrasena = forms.CharField(
        label="Contraseña",
        strip=False,
        widget=forms.PasswordInput,
        error_messages={"required": "Ingresa una contraseña."},
    )
    confirmar = forms.CharField(
        label="Confirmar contraseña",
        strip=False,
        widget=forms.PasswordInput,
        error_messages={"required": "Confirma tu contraseña."},
    )

    def clean_nombre(self):
        nombre = " ".join(self.cleaned_data["nombre"].split())
        if not nombre:
            raise ValidationError("Ingresa tu nombre completo.")
        return nombre

    def clean_correo(self):
        correo = self.cleaned_data["correo"].strip().lower()
        if Usuario.objects.filter(email__iexact=correo).exists() or Usuario.objects.filter(
            username__iexact=correo
        ).exists():
            raise ValidationError("Este correo electrónico ya está registrado.")
        return correo

    def clean(self):
        datos = super().clean()
        contrasena = datos.get("contrasena")
        confirmar = datos.get("confirmar")

        if contrasena and confirmar and contrasena != confirmar:
            self.add_error("confirmar", "Las contraseñas no coinciden.")
        elif contrasena:
            candidato = Usuario(
                username=datos.get("correo", ""),
                email=datos.get("correo", ""),
                first_name=datos.get("nombre", ""),
            )
            try:
                validate_password(contrasena, candidato)
            except ValidationError as error:
                self.add_error("contrasena", error)
        return datos

    
    def guardar(self, rol=Usuario.Rol.USUARIO):
        """Crea una cuenta con el rol asignado por la vista."""
        nombre = self.cleaned_data["nombre"]
        nombres, _, apellidos = nombre.partition(" ")
        correo = self.cleaned_data["correo"]

        with transaction.atomic():
            return Usuario.objects.create_user(
                username=correo,
                email=correo,
                password=self.cleaned_data["contrasena"],
                first_name=nombres,
                last_name=apellidos,
                rol=rol,
            )



class LoginForm(forms.Form):
    """
    Formulario de inicio de sesión. Mantiene los nombres de campos de la plantilla login.html
    (usuario y contrasena).
    """

    usuario = forms.CharField(
        label="Correo o usuario",
        error_messages={"required": "Ingresa tu correo o nombre de usuario."},
    )
    contrasena = forms.CharField(
        label="Contraseña",
        strip=False,
        widget=forms.PasswordInput,
        error_messages={"required": "Ingresa tu contraseña."},
    )

    def clean(self):
        datos = super().clean()
        usuario_input = datos.get("usuario")
        contrasena_input = datos.get("contrasena")

        if usuario_input and contrasena_input:
            # Autenticamos las credenciales contra la BD
            user = authenticate(
                username=usuario_input.strip(), password=contrasena_input
            )
            if user is None:
                raise ValidationError(
                    "Correo, usuario o contraseña incorrectos. Inténtalo de nuevo."
                )
            datos["user"] = user

        return datos

    def obtener_usuario(self):
        """Retorna el objeto Usuario autenticado."""
        return self.cleaned_data.get("user")
