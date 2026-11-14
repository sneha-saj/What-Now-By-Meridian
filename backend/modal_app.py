"""Deploy the existing FastAPI backend with ``modal deploy backend/modal_app.py``."""

from pathlib import Path
import sys

import modal

BACKEND_DIR = Path(__file__).resolve().parent
ROOT_DIR = BACKEND_DIR.parent

app = modal.App("what-now-by-meridian-api")
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install_from_requirements(str(BACKEND_DIR / "requirements.txt"))
    .add_local_dir(
        str(BACKEND_DIR), "/root/backend",
        ignore=[".venv", ".venv/**", "__pycache__", "**/__pycache__", "tests/**", "*.pyc", ".*.json"],
    )
)

# Send only the app's API keys, never the Modal deployment token or the entire .env.
if modal.is_local():
    from dotenv import dotenv_values

    values = dotenv_values(ROOT_DIR / ".env")
    runtime_keys = {name: values[name] for name in ("EXA_API_KEY", "GEMINI_API_KEY", "CONTEXT_DEV_API_KEY")
                    if values.get(name)}
else:
    runtime_keys = {}
runtime_secret = modal.Secret.from_dict(runtime_keys)


@app.function(image=image, secrets=[runtime_secret], timeout=300, scaledown_window=300)
@modal.concurrent(max_inputs=20)
@modal.asgi_app()
def web():
    sys.path.insert(0, "/root/backend")
    from main import app as api

    return api
