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
    """
    Primera pantalla del sistema.
    - Sin administrador (primer uso): bienvenida que lleva a crear la cuenta.
    - Con administrador: inicio de sesión.
    """
    if not hay_administrador():
        return render(request,"usuarios/bienvenida.html")

    if not request.user.is_authenticated:
        return redirect("login")
    
    #Si ya hay admin y el usuario inicio sesión, se renderiza su vista principal
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
    """
    Registro de la cuenta de administrador (solo en el primer uso).
    Cuando ya existe un administrador, las cuentas las crea él, no se registran solas.
    """
    if hay_administrador():
        return redirect("login")

    if request.method == "POST":
        form = RegistroForm(request.POST)
        if form.is_valid():
            try:
                usuario = form.guardar()
            except IntegrityError:  # el correo se registró justo en este momento
                form.add_error("correo", "Este correo electrónico ya está registrado.")
            except DatabaseError:
                form.add_error(
                    None,
                    "No se pudo crear la cuenta por un problema con la base de datos. "
                    "Inténtalo de nuevo más tarde.",
                )
            else:
                request.session[SESION_REGISTRO] = {
                    "nombre": usuario.get_full_name(),
                    "correo": usuario.email,
                }
                return redirect("registro_exitoso")
    else:
        form = RegistroForm()
    return render(request, "usuarios/registro.html", {"form": form})


def registro_exitoso(request):
    """Confirmación de cuenta creada. Solo se llega aquí justo después de registrarse."""
    datos = request.session.pop(SESION_REGISTRO, None)
    if datos is None:
        return redirect("inicio")
    return render(request, "usuarios/registro_exitoso.html", datos)
