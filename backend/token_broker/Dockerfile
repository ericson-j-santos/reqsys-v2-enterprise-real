FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BROKER_TOKEN_STATE_DB_PATH=/var/lib/reqsys-token-broker/token-broker.db

WORKDIR /app

COPY backend/token_broker/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --disable-pip-version-check -r /app/requirements.txt \
    && useradd --create-home --uid 10001 broker \
    && mkdir -p /var/lib/reqsys-token-broker \
    && chown -R broker:broker /var/lib/reqsys-token-broker /app

COPY --chown=broker:broker backend/token_broker /app/token_broker

USER broker
EXPOSE 8080
VOLUME ["/var/lib/reqsys-token-broker"]

CMD ["uvicorn", "token_broker.app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
