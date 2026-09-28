#!/usr/bin/env python3
"""Tareas de administración.

  python manage.py migrate                 Aplica migraciones y datos de referencia
  python manage.py seed-demo               Carga datos de DEMOSTRACIÓN (no usar en producción)
  python manage.py create-admin            Crea un usuario administrador (interactivo)
  python manage.py run [--port 5000]       Servidor de desarrollo
"""
import argparse
import getpass
import os
import sys
from pathlib import Path


def load_env_file() -> None:
    """Carga tienda/.env (si existe) antes de crear la app, sin dependencias.
    Las variables ya definidas en el sistema tienen prioridad y las vacías se ignoran."""
    env = Path(__file__).resolve().parent.parent / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if value and key not in os.environ:
            os.environ[key] = value


load_env_file()

from app import create_app  # noqa: E402
from app.db import get_db  # noqa: E402


def cmd_migrate(app, _args):
    from app.db.migrate import migrate
    with app.app_context():
        done = migrate(get_db())
    print("Migraciones aplicadas:", ", ".join(done) if done else "ninguna (ya estaba al día)")


def cmd_seed_demo(app, args):
    if app.config["ENV"] == "production" and not args.force:
        sys.exit("Negado: no se cargan datos de demostración en producción (use --force si está seguro).")
    from app.db.migrate import migrate
    from app.db.seeds.demo import seed
    with app.app_context():
        migrate(get_db())
        print(seed(get_db()))


def cmd_create_admin(app, args):
    from app.core.validation import V
    from app.services import user_service
    email = args.email or input("Correo: ").strip()
    first = args.first_name or input("Nombre: ").strip()
    last = args.last_name or input("Apellido: ").strip()
    password = os.getenv("ADMIN_PASSWORD") or getpass.getpass("Contraseña (mín. 8, letras y números): ")
    data = V({"email": email, "first_name": first, "last_name": last, "password": password}) \
        .email().str("first_name", max_len=80).str("last_name", max_len=80).password().check()
    with app.app_context():
        from app.db.migrate import migrate
        migrate(get_db())
        user = user_service.register(data, role_code="admin")
    print(f"Administrador creado: {user['email']} ({user['public_id']})")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate")
    s = sub.add_parser("seed-demo")
    s.add_argument("--force", action="store_true")
    a = sub.add_parser("create-admin")
    a.add_argument("--email")
    a.add_argument("--first-name")
    a.add_argument("--last-name")
    r = sub.add_parser("run")
    r.add_argument("--port", type=int, default=int(os.getenv("PORT", 5000)))
    r.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    app = create_app()
    if args.cmd == "run":
        app.run(host=args.host, port=args.port, debug=app.config["DEBUG"], threaded=True)
    else:
        {"migrate": cmd_migrate, "seed-demo": cmd_seed_demo, "create-admin": cmd_create_admin}[args.cmd](app, args)


if __name__ == "__main__":
    main()
