from django.urls import path

from . import views

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("login/", views.login, name="login"),
    path("registro/", views.registro, name="registro"),
    path("registro/exitoso/", views.registro_exitoso, name="registro_exitoso"),
]
