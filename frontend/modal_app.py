"""Deploy the user-facing Next.js site with ``modal deploy frontend/modal_app.py``."""

from pathlib import Path
import subprocess

import modal

FRONTEND_DIR = Path(__file__).resolve().parent
ROOT_DIR = FRONTEND_DIR.parent
BACKEND_DIR = ROOT_DIR / "backend"

app = modal.App("what-now-by-meridian-site")
image = (
    modal.Image.from_registry("node:22-bookworm-slim", add_python="3.11")
    .pip_install_from_requirements(str(BACKEND_DIR / "requirements.txt"))
    .env({"API_URL": "http://127.0.0.1:8000", "NEXT_TELEMETRY_DISABLED": "1"})
    .add_local_dir(
        str(BACKEND_DIR), "/backend", copy=True,
        ignore=[".venv", ".venv/**", "__pycache__", "**/__pycache__", "tests/**", "*.pyc", ".*.json"],
    )
    .add_local_dir(
        str(FRONTEND_DIR), "/app", copy=True,
        ignore=["node_modules", "node_modules/**", ".next", ".next/**", ".next-dev", ".next-dev/**",
                ".env*", "*.tsbuildinfo"],
    )
    .run_commands("cd /app && npm ci --no-audit --no-fund && npm run build")
)

if modal.is_local():
    from dotenv import dotenv_values

    values = dotenv_values(ROOT_DIR / ".env")
    runtime_keys = {name: values[name] for name in ("EXA_API_KEY", "GEMINI_API_KEY", "CONTEXT_DEV_API_KEY")
                    if values.get(name)}
else:
    runtime_keys = {}
runtime_secret = modal.Secret.from_dict(runtime_keys)


@app.function(image=image, secrets=[runtime_secret], scaledown_window=300, timeout=300)
@modal.web_server(3000, startup_timeout=60)
def web():
    subprocess.Popen(["python", "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
                     cwd="/backend")
    subprocess.Popen(["npm", "run", "start", "--", "-H", "0.0.0.0", "-p", "3000"], cwd="/app")
