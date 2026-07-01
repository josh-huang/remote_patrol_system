FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps for Pillow (image handling) and healthchecks.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential libjpeg-dev zlib1g-dev netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x /app/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "dynamic_patrol_system.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
