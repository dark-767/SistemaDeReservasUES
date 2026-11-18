from django.urls import path

from . import views

urlpatterns = [
    path("disponibilidad/", views.buscar_disponibilidad, name="buscar_disponibilidad"),
    path("solicitar/", views.solicitar_reserva, name="solicitar_reserva"),
    path("solicitar/<int:pk>/confirmacion/", views.confirmacion_reserva, name="confirmacion_reserva"),
    path("solicitudes/", views.listar_solicitudes, name="solicitudes"),
    path("solicitudes/<int:pk>/rechazar/", views.rechazar_solicitud, name="rechazar_solicitud"),
    path("mis-solicitudes/", views.mis_solicitudes, name="mis_solicitudes"),
    path("salir/", views.salir, name="salir"),
]
