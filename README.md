# Hotel Costa Azul — Sistema de Gestión Hotelera (PMS)

**Proyecto Integrador de Aprendizaje (PIA) — Componentes de Lógica de Negocios**  
Facultad de Ingeniería Mecánica y Eléctrica (FIME), Universidad Autónoma de Nuevo León.

> **Estado:** prototipo académico funcional para demostración local. No es un sistema listo para operar con huéspedes, pagos o datos personales reales.

Hotel Costa Azul es un sistema de gestión hotelera orientado a la administración de habitaciones, reservaciones, recepción, folios y operaciones internas. Fue desarrollado a partir del análisis de negocio de las **Unidades 2 y 3**: BRD, historias de usuario con Gherkin, BPMN, glosario, diagramas y registros de decisiones arquitectónicas (ADR).

## Contenido

- [Tecnologías y arquitectura](#tecnologías-y-arquitectura)
- [Funciones implementadas](#funciones-implementadas)
- [Requisitos previos](#requisitos-previos)
- [Ejecución en Windows con Docker](#ejecución-en-windows-con-docker)
- [Acceso e inicio de sesión](#acceso-e-inicio-de-sesión)
- [Pruebas automatizadas](#pruebas-automatizadas)
- [Datos de demostración del profesor](#datos-de-demostración-del-profesor)
- [Documentación y trazabilidad](#documentación-y-trazabilidad)
- [Limitaciones conocidas](#limitaciones-conocidas)
- [Seguridad y publicación](#seguridad-y-publicación)

## Tecnologías y arquitectura

| Capa / componente | Tecnología |
| --- | --- |
| API REST | Python, FastAPI y Pydantic |
| Dominio | DDD, Value Objects, agregados, Specification y State Machine |
| Aplicación | Casos de uso, servicios, puertos y Unit of Work |
| Persistencia | PostgreSQL, SQLAlchemy y Alembic |
| Seguridad de personal | Usuarios, roles, hash de contraseñas Argon2 y tokens JWT |
| Interfaz gráfica | HTML, CSS y JavaScript, consumiendo la API REST |
| Pruebas | Pytest, pytest-cov y validaciones JavaScript |
| Contenedores | Docker Compose (base de datos, API y servicio de pruebas) |
| Integración continua | GitHub Actions (`.github/workflows/`) |

La separación principal del backend sigue la arquitectura exigida por el PIA:

```text
src/
├── domain/           # Entidades, reglas, Value Objects y estados
├── application/      # Servicios, operaciones, consultas y puertos
├── infrastructure/   # SQLAlchemy, repositorios y Unit of Work
└── api/              # Rutas y esquemas HTTP
```

### Estructura general

```text
hotel-costa-azul-PIA/
├── .github/workflows/    # CI/CD
├── data/                 # CSV de origen y datos transformados para demo
├── docs/                 # Arquitectura y trazabilidad
├── frontend/             # Interfaz y pruebas del navegador
├── migrations/           # Versiones de Alembic
├── scripts/              # Alta de personal e importación de CSV
├── src/                  # Backend DDD + FastAPI
├── tests/                # Pruebas unitarias y de integración
├── .env.example          # Plantilla SIN secretos reales
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

## Funciones implementadas

- **Autenticación y roles:** login de personal, consulta de identidad y autorización por rol.
- **Habitaciones:** consulta de disponibilidad por fechas, capacidad y tipo; estados operativos, limpieza, inspección e incidencias de mantenimiento.
- **Reservaciones:** solicitud, consulta por UUID, confirmación, cancelación, cambios de habitación, extensión y políticas de excepción.
- **Recepción:** registro documental previo al check-in, check-in/check-out transaccionales y gestión de folio.
- **Folios:** consulta, cargos, vales de consumo y registro manual de pagos.
- **Tarifas:** configuración aprobada de temporadas y factores, cotización y aceptación.
- **Otros procesos:** reservas grupales, no-show, propuestas de reubicación (*walk*), auditoría, reportes operativos y eventos pendientes de canales.
- **Frontend:** inicio de sesión, panel por rol y formularios para consultar y operar los módulos autorizados.
- **Datos del profesor:** consulta de huéspedes y habitaciones ficticias, escenarios, casos de prueba y transiciones, tras ejecutar la importación opcional.

**Precisión:** la interfaz no dispone de un listado general de *todas* las reservaciones porque la API actual consulta por UUID. Los módulos y operaciones visibles dependen del rol y de la información existente en PostgreSQL.

## Requisitos previos

1. **Docker Desktop** instalado e iniciado.
2. **PowerShell** o terminal de Visual Studio Code.
3. **Git**, para el repositorio.
4. Un archivo `.env` local configurado a partir de `.env.example`.

> El método recomendado es Docker: **no requiere usar la instalación de Python ni el `.venv` de otra computadora**. Un entorno virtual copiado puede seguir apuntando a una ruta de Python inexistente en Windows.

### Configuración de entorno

Si aún no existe `.env`, en PowerShell, desde la raíz que contiene `docker-compose.yml`:

```powershell
Copy-Item .env.example .env
```

Edita `.env` y define, como mínimo, los valores reales de tu **entorno de desarrollo**:

- `POSTGRES_DB`, `POSTGRES_USER` y `POSTGRES_PASSWORD`.
- `AUTH_SECRET`: valor aleatorio de al menos 32 caracteres.
- `CHECKIN_DATA_KEY`: clave Fernet para cifrar documentación de recepción. **Conserva la clave anterior** si ya existen registros cifrados.
- `HOTEL_TIMEZONE`: zona horaria IANA aprobada para la operación del hotel.
- `APP_ENV`: `development` solo para pruebas locales.

Genera un secreto JWT desde un contenedor temporal, sin utilizar Python local:

```powershell
docker run --rm python:3.12-slim python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Para una **nueva instalación** sin registros cifrados, puedes generar una clave Fernet en un contenedor con dependencias instaladas. No cambies una clave existente sin planificar la migración de los datos cifrados.

**Nunca subas `.env`, contraseñas, tokens, claves, respaldos ni datos reales a GitHub.** `.env.example` debe contener únicamente marcadores o valores ficticios.

## Ejecución en Windows con Docker

Abre una terminal en la **carpeta interior del proyecto**, donde está `docker-compose.yml`.

### Terminal 1 — Backend y PostgreSQL

```powershell
docker compose up -d --build
docker compose ps
docker compose exec api alembic current
```

Para la versión con los CSV operativos del profesor, la migración esperada es:

```text
fa29demo (head)
```

En una instalación nueva, el servicio `api` aplica las migraciones automáticamente al arrancar. Si se necesita aplicarlas de forma explícita:

```powershell
docker compose exec api alembic upgrade head
```

Accesos locales:

| Servicio | URL |
| --- | --- |
| Frontend | http://127.0.0.1:5500 |
| API / FastAPI | http://127.0.0.1:8000 |
| Salud | http://127.0.0.1:8000/api/v1/health |
| Swagger (con protección de acceso) | http://127.0.0.1:8000/docs |

PostgreSQL escucha **dentro del contenedor** en `5432` y está publicado **solo en localhost** de Windows, habitualmente en `5433` según `docker-compose.yml`. La base de Docker no es la misma que una instancia PostgreSQL instalada directamente en Windows.

### Terminal 2 — Frontend

Sin depender de `py` ni de `.venv`:

```powershell
docker run --rm -p 127.0.0.1:5500:5500 -v "${PWD}/frontend:/site:ro" python:3.12-slim python -m http.server 5500 --bind 0.0.0.0 --directory /site
```

Abre <http://127.0.0.1:5500>. **Mantén esta terminal abierta** mientras uses el frontend. Después de modificar la interfaz, recarga el navegador con **Ctrl + F5**.

Para detener el frontend usa `Ctrl + C`. Para detener los servicios del backend sin eliminar los datos:

```powershell
docker compose down
```

**No utilices `docker compose down -v`** si deseas conservar la base de datos.

## Acceso e inicio de sesión

Los usuarios del PMS se crean desde un script administrativo. **No hay una contraseña universal del sistema.** Para crear una cuenta de pruebas:

```powershell
docker compose exec api python scripts/create_staff_user.py --username admin --role MANAGER_OPERATIONS
```

El script solicita la contraseña sin mostrarla. Si `admin` ya existe, usa esa cuenta con la contraseña establecida anteriormente o crea un usuario de nombre distinto.

Roles disponibles en el backend, según el módulo: `RECEPTION`, `RESERVATIONS`, `HOUSEKEEPING`, `MAINTENANCE`, `MANAGER_OPERATIONS` y `FINANCE`.

La interfaz inicia sesión con `POST /api/v1/auth/token` y consulta `GET /api/v1/auth/me`. Las operaciones de personal están protegidas en `/api/v1/staff/...`. **Las credenciales para abrir Swagger, si están configuradas, son independientes de las cuentas de personal.**

## Pruebas automatizadas

### Backend: Python + Pytest

```powershell
docker compose --profile test run --rm --build tests
```

**Última ejecución confirmada antes del adaptador operativo de CSV:** `203 passed`, `86.52 %` de cobertura, superior al **80 % exigido por la rúbrica**. La actualización del adaptador incorpora nuevas pruebas (referencia de 208), pero **ese resultado aún debe verificarse en Docker del equipo** antes de publicarlo como evidencia final.

> La cobertura se calcula sobre el código incluido en la medición. Las pruebas locales usan bases temporales en varios casos; para afirmar concurrencia o transacciones sobre PostgreSQL real se requieren pruebas específicas adicionales.

### Frontend: navegador

Abre:

<http://127.0.0.1:5500/tests.html>

**Última evidencia confirmada:** `15/15` validaciones del navegador aprobadas, sin escribir registros de prueba en PostgreSQL. El proyecto incluye además pruebas JavaScript para las validaciones (`frontend/tests/validation.test.cjs`), ejecutables con Node.js si está instalado:

```powershell
node --test frontend/tests/validation.test.cjs
```

**Las pruebas de formulario no sustituyen las pruebas funcionales completas** del flujo frontend → FastAPI → PostgreSQL.

## Datos de demostración del profesor

Los seis CSV originales aportan **377 registros ficticios**: 40 actores, 20 recursos, 60 operaciones, 117 líneas de detalle, 120 casos y 20 transiciones. No sustituyen los requisitos oficiales del BRD/U2/U3.

### Paso A — Datos originales en `demo_csv_records`

Con el ZIP original disponible en la raíz del proyecto:

```powershell
docker compose cp .\09_Hotel_Costa_Azul.zip api:/tmp/09_Hotel_Costa_Azul.zip
docker compose exec api python -m scripts.import_demo_csv --zip /tmp/09_Hotel_Costa_Azul.zip
docker compose exec api python -m scripts.import_demo_csv --zip /tmp/09_Hotel_Costa_Azul.zip --apply
```

Se valida primero **sin modificar la BD**, y `--apply` importa las filas a la tabla auxiliar. Si ya ejecutaste la importación, no necesitas repetirla.

### Paso B — Adaptación a datos del PMS

Después de instalar el adaptador y aplicar la migración `fa29demo`:

```powershell
docker compose exec api python -m scripts.seed_professor_pms
docker compose exec api python -m scripts.seed_professor_pms --apply --accept-demo-capacities
```

La vista previa **no modifica datos**. `--accept-demo-capacities` indica que se aceptan aforos ficticios, **solo para el entorno académico**.

La importación ya comprobada en el proyecto agregó:

| Destino | Datos añadidos |
| --- | ---: |
| `demo_guests` | 40 huéspedes ficticios |
| `rooms` | 20 habitaciones ficticias |
| `demo_scenarios` | 60 escenarios |
| `demo_scenario_lines` | 117 detalles |

Los **120 casos** y **20 transiciones** siguen disponibles en la tabla auxiliar y en las vistas de consulta. **Todavía no son pruebas ejecutadas ni aprobadas automáticamente**. Las operaciones `HOT-O013` y `HOT-O039` aparecen sin detalle asociado.

Los CSV del profesor no incluyen fechas de estancia; por eso no se convierten automáticamente en reservaciones reales. Los precios y las capacidades propuestas son de demostración, no políticas autorizadas del hotel. Los CSV adaptados están en `data/profesor_adaptado/`.

### Validar los registros importados

```powershell
$dbUser = (docker compose exec -T db printenv POSTGRES_USER).Trim()
$dbName = (docker compose exec -T db printenv POSTGRES_DB).Trim()
docker compose exec -T db psql -U $dbUser -d $dbName -c 'SELECT COUNT(*) FROM demo_guests;'
docker compose exec -T db psql -U $dbUser -d $dbName -c 'SELECT COUNT(*) FROM demo_scenarios;'
```

La interfaz contiene la sección **Datos del profesor**, desde la cual se pueden consultar los datos y usar UUID de huéspedes ficticios en los formularios de reservaciones.

## Documentación y trazabilidad

El PIA requiere coherencia entre requisitos, análisis, arquitectura, implementación y pruebas. Los documentos de las **Unidades 2 y 3** son la fuente principal, no los archivos CSV de ejemplo.

En el repositorio deben incluirse o enlazarse adecuadamente:

- BRD actualizado, al menos 15 historias de usuario con Gherkin, BPMN y glosario.
- Diagramas DDD y UML, justificación de patrones, SOLID y ADRs.
- Trazabilidad RN/RF/US → componente → ruta/caso de uso → prueba.
- OpenAPI/Swagger, evidencias de resultados, CI/CD y despliegue.

El backend incluye la matriz de seguimiento en `docs/technical/TRAZABILIDAD_U2_U3_BACKEND.md`. **Comprueba que los archivos originales de U2/U3 también estén incluidos en `docs/` antes de entregar**; no basta con que estén únicamente en tu computadora.

### Repositorio y despliegue

- **GitHub:** confirma la URL real de `origin` con `git remote -v` y agrega el enlace de la versión finalmente entregada.
- **GitHub Actions:** comprueba que el pipeline del último `push` esté en verde.
- **URL pública:** **pendiente de publicar y verificar**. La documentación oficial exige un despliegue accesible con Swagger.
- **Entrega:** reporte final PDF (BRD + arquitectura + evidencias + conclusiones), presentación de apoyo y defensa del sistema.

## Limitaciones conocidas

- La API todavía no proporciona un listado global de todas las reservaciones para el frontend; se consultan por UUID.
- El pago registrado en el folio **no ejecuta un cobro bancario real**.
- Penalizaciones y reembolsos pueden permanecer como movimientos pendientes de una pasarela externa.
- Los eventos OTA registrados en la bandeja **no implican sincronización real con plataformas externas**.
- Una propuesta *walk* no reserva automáticamente alojamiento en un hotel aliado.
- La facturación fiscal, contratos corporativos y algunos indicadores financieros requieren información o servicios externos.
- Los 120 casos y 20 transiciones del CSV del docente no constituyen todavía resultados de ejecución.
- Algunas reglas comerciales aún deben ser confirmadas; no se inventan multiplicadores ni políticas.

## Seguridad y publicación

**Solo demostración local mientras no se complete el endurecimiento de seguridad.** En la copia auditada del proyecto existían credenciales de Swagger escritas directamente en `src/main.py` y una política CORS demasiado amplia. Deben corregirse y verificarse antes de publicar la API. No confundas el hash de contraseñas y los tokens JWT con una revisión integral de seguridad.

Antes de subir a GitHub o desplegar:

1. Excluye `.env`, `.venv`, `.git/` en archivos comprimidos, respaldos, volcados SQL y otros secretos. Verifica `git status` y `git diff --cached --name-only`.
2. Sustituye credenciales literales de Swagger por configuración segura; revisa CORS, HTTPS, límites de acceso y autorización.
3. Conserva los UUID y datos ficticios solo como información de demostración.
4. Revisa la configuración de despliegue y utiliza variables de entorno reales **fuera del repositorio**.
5. Verifica que el README, el reporte y los diagramas describen la **versión realmente presentada**, sin afirmar que integraciones pendientes están completas.

---

**Proyecto académico — Hotel Costa Azul.** Documentación y código sujetos a los requisitos y decisiones de negocio definidos en las Unidades 2 y 3.
