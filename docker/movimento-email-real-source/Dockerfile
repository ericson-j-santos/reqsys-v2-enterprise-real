FROM python:3.12-slim

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates gnupg unixodbc-dev \
 && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
 && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/microsoft-prod.list \
 && apt-get update \
 && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY scripts/sincronizar_movimento_email_corporate.py scripts/sincronizar_movimento_email_corporate.py
COPY scripts/pc24x7_movimento_email_real_source_worker.py scripts/pc24x7_movimento_email_real_source_worker.py
COPY config/movimento-email-corporate-source-map.example.json config/movimento-email-corporate-source-map.example.json

RUN pip install --no-cache-dir pyodbc==5.2.0

ENV PYTHONUNBUFFERED=1 \
    MOVIMENTO_EMAIL_SOURCE_MAP=/app/config/movimento-email-corporate-source-map.example.json

CMD ["python", "scripts/pc24x7_movimento_email_real_source_worker.py"]
