"""Espacios institucionales de ejemplo para la Facultad de Ingeniería y Arquitectura de la UES.

No es el inventario oficial. Sirve para consultar disponibilidad con datos plausibles.
"""

from .models import Espacio, TipoEspacio

ESPACIOS = (
    {
        "codigo": "B-21",
        "nombre": "Aula B-21",
        "tipo": "Aula",
        "ubicacion": "Edificio B, nivel 2",
        "capacidad": 60,
        "descripcion": "Aula teórica con pizarra y proyector.",
    },
    {
        "codigo": "B-12",
        "nombre": "Aula B-12",
        "tipo": "Aula",
        "ubicacion": "Edificio B, nivel 1",
        "capacidad": 45,
        "descripcion": "Aula teórica para grupos medianos.",
    },
    {
        "codigo": "C-08",
        "nombre": "Aula C-08",
        "tipo": "Aula",
        "ubicacion": "Edificio C, nivel 1",
        "capacidad": 40,
        "descripcion": "Aula con escritorio del docente y pizarra acrílica.",
    },
    {
        "codigo": "A-03",
        "nombre": "Aula A-03",
        "tipo": "Aula",
        "ubicacion": "Edificio A, nivel 1",
        "capacidad": 35,
        "descripcion": "Aula pequeña para secciones de posgrado.",
    },
    {
        "codigo": "L-INF-01",
        "nombre": "Laboratorio de Informática 1",
        "tipo": "Laboratorio",
        "ubicacion": "Edificio de laboratorios, nivel 2",
        "capacidad": 30,
        "descripcion": "Treinta equipos, proyector y aire acondicionado.",
    },
    {
        "codigo": "L-INF-02",
        "nombre": "Laboratorio de Informática 2",
        "tipo": "Laboratorio",
        "ubicacion": "Edificio de laboratorios, nivel 2",
        "capacidad": 28,
        "descripcion": "Equipos para prácticas de programación.",
    },
    {
        "codigo": "L-RED-01",
        "nombre": "Laboratorio de Redes",
        "tipo": "Laboratorio",
        "ubicacion": "Edificio de laboratorios, nivel 1",
        "capacidad": 24,
        "descripcion": "Racks, switches y mesas de práctica.",
    },
    {
        "codigo": "L-FIS-01",
        "nombre": "Laboratorio de Física",
        "tipo": "Laboratorio",
        "ubicacion": "Edificio de ciencias básicas, nivel 1",
        "capacidad": 20,
        "descripcion": "Mesas de experimentación y equipo de medición.",
    },
    {
        "codigo": "AUD-FIA",
        "nombre": "Auditorio de la Facultad",
        "tipo": "Auditorio",
        "ubicacion": "Edificio A, planta baja",
        "capacidad": 180,
        "descripcion": "Auditorio para actos y defensas de la Facultad de Ingeniería y Arquitectura.",
    },
    {
        "codigo": "AUD-AV",
        "nombre": "Auditorio de audiovisuales",
        "tipo": "Auditorio",
        "ubicacion": "Edificio C, nivel 2",
        "capacidad": 80,
        "descripcion": "Proyección y sonido para conferencias.",
    },
    {
        "codigo": "SR-ESC",
        "nombre": "Sala de reuniones de Escuela",
        "tipo": "Sala de reuniones",
        "ubicacion": "Edificio administrativo, nivel 2",
        "capacidad": 16,
        "descripcion": "Mesa de reuniones para coordinación de escuela.",
    },
    {
        "codigo": "SR-DOC",
        "nombre": "Sala de docentes",
        "tipo": "Sala de reuniones",
        "ubicacion": "Edificio B, nivel 3",
        "capacidad": 12,
        "descripcion": "Sala para reuniones breves del personal docente.",
    },
)


def cargar_espacios():
    """Crea o actualiza el catalogo. Volver a ejecutarlo no duplica filas."""
    tipos = {}
    for nombre in dict.fromkeys(item["tipo"] for item in ESPACIOS):
        tipos[nombre], _ = TipoEspacio.objects.get_or_create(nombre=nombre)

    creados = 0
    actualizados = 0
    for item in ESPACIOS:
        _, creado = Espacio.objects.update_or_create(
            codigo=item["codigo"],
            defaults={
                "nombre": item["nombre"],
                "tipo_espacio": tipos[item["tipo"]],
                "ubicacion": item["ubicacion"],
                "capacidad": item["capacidad"],
                "descripcion": item["descripcion"],
                "activo": True,
            },
        )
        if creado:
            creados += 1
        else:
            actualizados += 1
    return creados, actualizados
