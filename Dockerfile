FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBUG=0

WORKDIR /app

# gettext provides msgfmt for compiling translation catalogs (.po -> .mo).
RUN apt-get update && apt-get install -y --no-install-recommends gettext \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first to leverage Docker layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Compile translations and collect static assets at build time.
RUN SECRET_KEY=build-only python manage.py compilemessages \
    && SECRET_KEY=build-only python manage.py collectstatic --noinput

EXPOSE 8000

# entrypoint runs migrations then serves the ASGI app with Daphne.
CMD ["sh", "-c", "python manage.py migrate --noinput && daphne -b 0.0.0.0 -p 8000 config.asgi:application"]
