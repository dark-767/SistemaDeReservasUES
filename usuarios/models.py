from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower


class Usuario(AbstractUser):
    """
    Usuario del sistema. Hereda de AbstractUser (login, contraseñas con hash,
    sesiones, permisos y admin de Django ya resueltos) y agrega el rol.

    Roles del plan: "usuario" y "admin".
    """

    class Rol(models.TextChoices):
        USUARIO = "usuario", "Usuario"
        ADMIN = "admin", "Administrador"

    # AbstractUser define email como opcional; aquí es obligatorio y único (HU02)
    email = models.EmailField("correo electrónico")
    rol = models.CharField(max_length=10, choices=Rol.choices, default=Rol.USUARIO)

    REQUIRED_FIELDS = ["email"]  # lo pide "createsuperuser"

    class Meta:
        db_table = "usuario"
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        constraints = [
            # Correo único sin distinguir mayúsculas
            models.UniqueConstraint(Lower("email"), name="ux_usuario_email"),
            models.CheckConstraint(
                condition=Q(rol__in=["usuario", "admin"]), name="ck_usuario_rol"
            ),
        ]

    @property
    def es_admin(self) -> bool:
        return self.rol == self.Rol.ADMIN

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        if self.is_superuser:
            self.rol = self.Rol.ADMIN
        # El rol admin puede entrar al panel /admin/ (ahí ve solo lo que
        # permite SoloRolAdminMixin en reservas/admin.py)
        self.is_staff = self.is_superuser or self.rol == self.Rol.ADMIN
        super().save(*args, **kwargs)

    def __str__(self):
        return self.get_full_name() or self.username
