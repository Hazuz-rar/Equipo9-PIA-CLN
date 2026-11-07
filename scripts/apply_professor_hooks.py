"""Incorpora rutas y modelos nuevos conservando cambios del main.py local.

Ejecutar UNA VEZ tras copiar el ZIP en la raíz del proyecto:
    python -m scripts.apply_professor_hooks
Es idempotente y crea copias .bak_profesor antes de tocar archivos existentes.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def patch(path: Path, replacements: list[tuple[str, str]], already: str):
    content = path.read_text(encoding="utf-8-sig")
    if already in content:
        print(f"Sin cambios: {path.relative_to(ROOT)}")
        return
    new_content = content
    for anchor, inserted in replacements:
        if anchor not in new_content:
            raise RuntimeError(f"No encuentro el ancla {anchor!r} en {path}. No se ha modificado.")
        new_content = new_content.replace(anchor, inserted + anchor, 1)
    backup = path.with_name(path.name + ".bak_profesor")
    if not backup.exists():
        backup.write_text(content, encoding="utf-8")
    path.write_text(new_content, encoding="utf-8")
    print(f"Actualizado: {path.relative_to(ROOT)} (respaldo: {backup.name})")


def main():
    patch(ROOT / "src/infrastructure/database/models/__init__.py", [(
        "from src.infrastructure.database.models.room_model import RoomModel",
        "from src.infrastructure.database.models.demo_operational_model import (\n"
        "    DemoGuestModel, DemoScenarioModel, DemoScenarioLineModel,\n)\n\n",
    )], "from src.infrastructure.database.models.demo_operational_model import")
    patch(ROOT / "src/main.py", [(
        "from src.api.routes.health import router as health_router",
        "from src.api.routes.demo_data import router as demo_data_router\n",
    ), (
        "app.include_router(auth_router,",
        "app.include_router(\n    demo_data_router,\n    prefix=f\"{settings.api_v1_prefix}/staff/demo-data\",\n    tags=[\"Datos del profesor\"],\n)\n",
    )], "app.include_router(\n    demo_data_router,")
    print("Listo. Reconstruye la API y aplica Alembic antes de importar datos.")


if __name__ == "__main__":
    main()
