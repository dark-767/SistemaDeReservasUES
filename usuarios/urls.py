
from django.urls import path
from . import views

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("login/", views.login, name="login"),

    # Registro de usuarios normales
    path("registro/", views.registro, name="registro"),

    # Registro del administrador inicial
    path("registro/admin/", views.registro_admin, name="registro_admin"),

    path(
        "registro/exitoso/",
        views.registro_exitoso,
        name="registro_exitoso"
    ),
]
