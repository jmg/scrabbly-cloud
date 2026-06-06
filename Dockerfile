FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBUG=0

WORKDIR /app

# Install dependencies first to leverage Docker layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Collect static assets (hashed/compressed by WhiteNoise) at build time.
RUN SECRET_KEY=build-only python manage.py collectstatic --noinput

EXPOSE 8000

# entrypoint runs migrations then serves the ASGI app with Daphne.
CMD ["sh", "-c", "python manage.py migrate --noinput && daphne -b 0.0.0.0 -p 8000 config.asgi:application"]
