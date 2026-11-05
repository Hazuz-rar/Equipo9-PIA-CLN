# Hotel Costa Azul — PIA de Componentes de Lógica de Negocios

API REST inicial para el PMS Hotel Costa Azul. La implementación sigue una separación en
`src/domain`, `src/application`, `src/infrastructure` y `src/api`.

## Estado comprobado

- Reservaciones: creación, consulta por ID, confirmación y cancelación **básica**.
- Habitación y folio: entidades y pruebas de dominio, aún sin persistencia ni API.
- PostgreSQL: migración inicial para la tabla `reservations`.
- La lógica completa de cancelación (RN-04/US-05), disponibilidad (US-02/US-25),
  no-show (RN-05), grupos (RN-07), autorizaciones (RN-08) y otros requisitos
  **todavía está pendiente**.

La documentación U2/U3 es la fuente de verdad. Los datos de ejemplo del paquete
`09_Hotel_Costa_Azul` son ilustrativos, no reemplazan las reglas del BRD.

## Requisitos

- Python 3.12+ (para ejecución local); en Docker se usa Python 3.12.
- PostgreSQL en local, o Docker Compose para base de datos + API + pruebas.

## Instalación local (Windows / PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Crea tu archivo `.env` a partir de `.env.example` y configura `DATABASE_URL`
con las credenciales reales de tu PostgreSQL local. No publiques `.env`.

```powershell
alembic upgrade head
python -m uvicorn src.main:app --reload
```

Swagger: http://127.0.0.1:8000/docs  
Salud: http://127.0.0.1:8000/api/v1/health

## Pruebas y cobertura

```powershell
python -m pytest -q --cov=src --cov-report=term-missing --cov-fail-under=80
```

Las pruebas HTTP usan una base SQLite **efímera y aislada**. No sustituyen
pruebas de integración específicas contra PostgreSQL, que siguen pendientes.

## Docker Compose

Agrega `POSTGRES_DB`, `POSTGRES_USER` y `POSTGRES_PASSWORD` al `.env`.
La base de datos Docker se expone en el puerto **5433** de Windows para no
colisionar con una instalación local de PostgreSQL en 5432.

```powershell
docker compose up -d --build
# API: http://localhost:8000/docs
docker compose --profile test run --rm tests
```

El servicio `api` ejecuta `alembic upgrade head` al iniciarse. Para detenerlo:

```powershell
docker compose down
```

No utilices `docker compose down -v` sobre una base de datos que desees conservar.

## Documentación y trazabilidad

La carpeta `docs` debe incluir el BRD, las historias Gherkin, el glosario, los
ADRs y los diagramas originales de las Unidades 2 y 3. Agrega una matriz de
trazabilidad que vincule RN/RF/US con archivos Python y pruebas.

## Automatización

`.github/workflows/ci.yml` comprueba las migraciones en PostgreSQL y ejecuta
las pruebas con el límite mínimo de 80 % de cobertura. El pipeline se activará
cuando el proyecto se suba a GitHub y se haga push.

## Funcionalidad pendiente

Esto aún no es un PMS completo ni cumple todos los criterios Gherkin. Las
prioridades siguientes son: Specification + State Machine explícitos, control
contra overbooking, políticas RN-04/RN-05, tarifas, folios con trazabilidad,
Unit of Work, permisos, grupos, reportes, documentación y despliegue.
