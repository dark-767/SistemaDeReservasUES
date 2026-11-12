from django.core.management.base import BaseCommand

from reservas.semilla import cargar_espacios


class Command(BaseCommand):
    help = (
        "Carga espacios institucionales plausibles de la UES: "
        "aulas, laboratorios, auditorios y salas de reuniones."
    )

    def handle(self, *args, **options):
        creados, actualizados = cargar_espacios()
        self.stdout.write(
            self.style.SUCCESS(
                f"Espacios institucionales listos: {creados} creados, {actualizados} actualizados."
            )
        )
