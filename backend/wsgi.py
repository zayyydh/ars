import sys
import os

# Absolute path to the backend folder — works no matter where flask is called from
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Verify the app package is findable before importing
app_path = os.path.join(BACKEND_DIR, "app")
print(f"[wsgi] backend dir: {BACKEND_DIR}")
print(f"[wsgi] app package exists: {os.path.isdir(app_path)}")
print(f"[wsgi] sys.path[0]: {sys.path[0]}")

from dotenv import load_dotenv
load_dotenv(os.path.join(BACKEND_DIR, ".env"))

from app import create_app
from app.extensions import celery  # noqa: F401

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)