# Sistema de reservas UES

Sistema para reservar espacios de la Universidad de El Salvador (aulas, laboratorios y otros). Está hecho con Django y PostgreSQL.

Hoy el proyecto deja lista la base de datos, el modelo de usuario y el formulario de registro. Todavía no hay pantallas propias: la página de inicio es la de Django y la administración está en `/admin/`.

## Qué incluye

- Usuarios con rol `usuario` o `admin`. El correo es obligatorio y único, sin distinguir mayúsculas.
- Inicio de sesión por correo o por nombre de usuario.
- Espacios, tipos de espacio, bloques horarios y motivos de reserva.
- Reservas con estados pendiente, aprobada, rechazada y cancelada.
- En PostgreSQL, dos reservas aprobadas del mismo espacio no pueden traslaparse.
- Catálogos iniciales: Aula, Laboratorio y Otro; seis bloques horarios; motivos de clase, práctica, reunión, taller y examen. El examen permite horario libre.

## Requisitos

- Python 3.12 o superior
- PostgreSQL 15 o superior

## Configuración

PostgreSQL tiene que estar en marcha. Django no crea la base ni el usuario: `migrate` solo crea las tablas dentro de una base que ya existe.

Entra a `psql` como superusuario y ejecuta:

```sql
CREATE USER reservas_user WITH PASSWORD 'cambiar_esta_clave';
CREATE DATABASE reservas_db OWNER reservas_user;
\c reservas_db
ALTER SCHEMA public OWNER TO reservas_user;
```

Esos datos ya son los que usa el proyecto. Si quieres otros, defínelos antes de migrar:

| Variable | Valor por defecto |
|---|---|
| `DB_NAME` | `reservas_db` |
| `DB_USER` | `reservas_user` |
| `DB_PASSWORD` | `cambiar_esta_clave` |
| `DB_HOST` | `localhost` |
| `DB_PORT` | `5432` |

## Ponerlo en marcha

En la carpeta del proyecto:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

En Windows, activa el entorno con `.venv\Scripts\activate`.

Abre http://127.0.0.1:8000/.

Para entrar al panel de administración crea un administrador y abre http://127.0.0.1:8000/admin/:

```bash
python manage.py createsuperuser
```

## Conexión desde DataGrip

| Campo | Valor |
|---|---|
| Host | `localhost` |
| Puerto | `5432` |
| Usuario | `reservas_user` |
| Contraseña | `cambiar_esta_clave` |
| Base de datos | `reservas_db` |

## Estructura

```text
manage.py
requirements.txt
gestionDeEspacios/   configuración del proyecto
usuarios/            usuario, registro e inicio de sesión
reservas/            espacios, horarios y reservas
```
