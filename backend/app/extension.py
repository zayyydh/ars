"""
extensions.py — shared extension instances.

Why a separate file for extensions?
    Flask extensions (SQLAlchemy, Celery, Redis) need to be imported by
    both the app factory (app/__init__.py) AND the route/task files.

    If we created db = SQLAlchemy(app) inside __init__.py, the routes
    would need to import from __init__.py, creating circular imports:
        routes/resumes.py imports app/__init__.py
        app/__init__.py imports routes/resumes.py  ← circular!

    The fix: create extension instances here WITHOUT an app attached.
    The app factory calls db.init_app(app) later to bind them.
    This is the standard Flask pattern for avoiding circular imports.

    routes/resumes.py  imports db from extensions  ← no circular import
    app/__init__.py    imports db from extensions, calls db.init_app(app)
"""

from flask_sqlalchemy import SQLAlchemy
from celery import Celery

# SQLAlchemy instance — no app attached yet
# Routes and models import this directly:  from app.extensions import db
db = SQLAlchemy()

# Celery instance — configured in create_app()
celery = Celery()

# Redis client — initialised in create_app()
# We use a module-level variable so tasks can import it
redis_client = None