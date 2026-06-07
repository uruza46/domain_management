FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl && rm -rf /var/lib/apt/lists/*

# supercronic: Docker-native cron runner (no syslog dependency)
ENV SUPERCRONIC_VERSION=v0.2.33
RUN curl -fsSL \
    https://github.com/aptible/supercronic/releases/download/${SUPERCRONIC_VERSION}/supercronic-linux-amd64 \
    -o /usr/local/bin/supercronic \
    && chmod +x /usr/local/bin/supercronic

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . .
