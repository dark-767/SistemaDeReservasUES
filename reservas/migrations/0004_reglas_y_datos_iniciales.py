from datetime import time

from django.db import migrations

CREAR_FUNCION = """
CREATE FUNCTION fn_reserva_validar_capacidad() RETURNS trigger AS $$
DECLARE
    v_capacidad INTEGER;
BEGIN
    SELECT capacidad INTO v_capacidad FROM espacio WHERE id = NEW.espacio_id;
    IF NEW.cantidad_personas > v_capacidad THEN
        RAISE EXCEPTION 'La cantidad de personas (%) supera la capacidad del espacio (%)',
            NEW.cantidad_personas, v_capacidad
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

CREAR_TRIGGER = """
CREATE TRIGGER tr_reserva_capacidad
    BEFORE INSERT OR UPDATE OF espacio_id, cantidad_personas ON reserva
    FOR EACH ROW EXECUTE FUNCTION fn_reserva_validar_capacidad();
"""

ELIMINAR = [
    "DROP TRIGGER IF EXISTS tr_reserva_capacidad ON reserva;",
    "DROP FUNCTION IF EXISTS fn_reserva_validar_capacidad();",
]


def cargar_catalogos(apps, schema_editor):
    TipoEspacio = apps.get_model("reservas", "TipoEspacio")
    BloqueHorario = apps.get_model("reservas", "BloqueHorario")
    MotivoReserva = apps.get_model("reservas", "MotivoReserva")

    for nombre in ("Aula", "Laboratorio", "Otro"):
        TipoEspacio.objects.get_or_create(nombre=nombre)

    # EJEMPLO: ajustar a las horas clase reales de la institución
    bloques = [
        ("Bloque 1", time(7, 0), time(8, 40)),
        ("Bloque 2", time(8, 40), time(10, 20)),
        ("Bloque 3", time(10, 20), time(12, 0)),
        ("Bloque 4", time(13, 0), time(14, 40)),
        ("Bloque 5", time(14, 40), time(16, 20)),
        ("Bloque 6", time(16, 20), time(18, 0)),
    ]
    for nombre, ini, fin in bloques:
        BloqueHorario.objects.get_or_create(nombre=nombre, defaults={"hora_inicio": ini, "hora_fin": fin})

    motivos = [
        ("Clase", False),
        ("Práctica de laboratorio", False),
        ("Reunión", False),
        ("Taller o capacitación", False),
        ("Examen", True),  # único con horario modificable
    ]
    for nombre, libre in motivos:
        MotivoReserva.objects.get_or_create(nombre=nombre, defaults={"permite_horario_libre": libre})


class Migration(migrations.Migration):
    dependencies = [("reservas", "0003_initial")]

    operations = [
        migrations.RunSQL(sql=[CREAR_FUNCION, CREAR_TRIGGER], reverse_sql=ELIMINAR),
        migrations.RunPython(cargar_catalogos, migrations.RunPython.noop),
    ]
