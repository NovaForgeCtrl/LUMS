"""Gunicorn entry point for the PostgreSQL LUMS application."""

if __package__:
    from .postgres_app import create_postgres_app
else:
    from postgres_app import create_postgres_app


app = create_postgres_app()
