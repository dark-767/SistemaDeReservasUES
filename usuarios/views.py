from django.db import DatabaseError, IntegrityError
from django.shortcuts import redirect, render
from django.contrib.auth import authenticate, login as auth_login

from .forms import RegistroForm
from .forms import LoginForm
from .models import Usuario

SESION_REGISTRO = "registro_exitoso"


def hay_administrador():
    """True cuando el sistema ya tiene su cuenta de administrador."""
    return Usuario.objects.filter(rol=Usuario.Rol.ADMIN).exists()



def inicio(request):
    if not hay_administrador():
        return render(request, "usuarios/bienvenida.html")

    if not request.user.is_authenticated:
        return redirect("login")

    return render(request, "usuarios/index.html")



def login(request):
    """Vista de inicio de sesión."""
    if not hay_administrador():
        return redirect("inicio")

    if request.user.is_authenticated:
        return redirect("inicio")

    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            usuario = form.obtener_usuario()
            auth_login(request, usuario)
            return redirect(request.GET.get("next", "inicio"))
    else:
        form = LoginForm()

    return render(request, "usuarios/login.html", {"form": form})



def registro(request):
    """Registro público: siempre crea usuarios normales."""

    if not hay_administrador():
        return redirect("inicio")

    if request.method == "POST":
        form = RegistroForm(request.POST)

        if form.is_valid():
            try:
                usuario = form.guardar(
                    rol=Usuario.Rol.USUARIO
                )
            except IntegrityError:
                form.add_error(
                    "correo",
                    "Este correo electrónico ya está registrado."
                )
            except DatabaseError:
                form.add_error(
                    None,
                    "No se pudo crear la cuenta. Inténtalo de nuevo."
                )
            else:
                request.session[SESION_REGISTRO] = {
                    "nombre": usuario.get_full_name(),
                    "correo": usuario.email,
                }
                return redirect("registro_exitoso")
    else:
        form = RegistroForm()

    return render(
        request,
        "usuarios/registro.html",
        {
            "form": form,
            "es_registro_admin": False,
        }
    )


def registro_admin(request):
    """Registro exclusivo del administrador inicial."""

    if hay_administrador():
        return redirect("login")

    if request.method == "POST":
        form = RegistroForm(request.POST)

        if form.is_valid():
            try:
                usuario = form.guardar(
                    rol=Usuario.Rol.ADMIN
                )
            except IntegrityError:
                form.add_error(
                    None,
                    "No se pudo completar el registro. "
                    "Verifica que la cuenta no exista."
                )
            except DatabaseError:
                form.add_error(
                    None,
                    "Ocurrió un problema al crear el administrador."
                )
            else:
                request.session[SESION_REGISTRO] = {
                    "nombre": usuario.get_full_name(),
                    "correo": usuario.email,
                }
                return redirect("registro_exitoso")
    else:
        form = RegistroForm()

    return render(
        request,
        "usuarios/registro.html",
        {
            "form": form,
            "es_registro_admin": True,
        }
    )


def registro_exitoso(request):
    """Confirmación de cuenta creada. Solo se llega aquí justo después de registrarse."""
    datos = request.session.pop(SESION_REGISTRO, None)
    if datos is None:
        return redirect("inicio")
    return render(request, "usuarios/registro_exitoso.html", datos)
