from django.contrib.postgres.operations import BtreeGistExtension
from django.db import migrations


class Migration(migrations.Migration):
    """Debe ir ANTES de la migración que crea 'reserva' (usa EXCLUDE USING gist)."""

    dependencies = []
    operations = [BtreeGistExtension()]
