FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /code

# 1. les dépendances d'abord : cette couche est réutilisée tant que requirements.txt ne change pas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. puis le code
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
COPY scripts ./scripts
COPY data ./data

# 3. un utilisateur sans droits particuliers pour lancer l'application
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

# Render fournit le port dans la variable PORT ; en local, on prend 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]