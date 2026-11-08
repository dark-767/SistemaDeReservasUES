from django.contrib import admin

from .models import BloqueHorario, Espacio, MotivoReserva, Reserva, TipoEspacio


class SoloRolAdminMixin:
    """Solo los usuarios con rol 'admin' ven y gestionan estos modelos en /admin/."""

    def _ok(self, request):
        return request.user.is_active and getattr(request.user, "es_admin", False)

    def has_module_permission(self, request):
        return self._ok(request)

    def has_view_permission(self, request, obj=None):
        return self._ok(request)

    def has_add_permission(self, request):
        return self._ok(request)

    def has_change_permission(self, request, obj=None):
        return self._ok(request)

    def has_delete_permission(self, request, obj=None):
        return self._ok(request)


@admin.register(TipoEspacio)
class TipoEspacioAdmin(SoloRolAdminMixin, admin.ModelAdmin):
    search_fields = ("nombre",)


@admin.register(BloqueHorario)
class BloqueHorarioAdmin(SoloRolAdminMixin, admin.ModelAdmin):
    list_display = ("nombre", "hora_inicio", "hora_fin", "activo")


@admin.register(MotivoReserva)
class MotivoReservaAdmin(SoloRolAdminMixin, admin.ModelAdmin):
    list_display = ("nombre", "permite_horario_libre", "activo")


@admin.register(Espacio)
class EspacioAdmin(SoloRolAdminMixin, admin.ModelAdmin):
    list_display = ("codigo", "nombre", "tipo_espacio", "capacidad", "activo")
    list_filter = ("tipo_espacio", "activo")
    search_fields = ("codigo", "nombre")


@admin.register(Reserva)
class ReservaAdmin(SoloRolAdminMixin, admin.ModelAdmin):
    list_display = ("espacio", "usuario", "inicio", "fin", "estado")
    list_filter = ("estado", "espacio__tipo_espacio", "espacio")
    search_fields = ("usuario__username", "usuario__email", "espacio__codigo")
    date_hierarchy = "inicio"
    readonly_fields = ("created_at", "updated_at")
