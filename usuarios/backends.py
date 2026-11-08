from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailOrUsernameBackend(ModelBackend):
    """HU01: permite iniciar sesión con el correo O con el nombre de usuario."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        Usuario = get_user_model()
        if username is None:
            username = kwargs.get(Usuario.USERNAME_FIELD)
        if not username or password is None:
            return None

        # Primero se busca por nombre de usuario; si no existe, por correo
        user = Usuario.objects.filter(username__iexact=username).first()
        if user is None:
            user = Usuario.objects.filter(email__iexact=username).first()
        if user is None:
            Usuario().set_password(password)  # iguala tiempos de respuesta
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
