"""Punto de entrada WSGI para producción: gunicorn wsgi:app"""
from app import create_app

app = create_app()
