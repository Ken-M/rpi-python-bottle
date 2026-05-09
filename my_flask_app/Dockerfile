FROM python:3.14-slim

USER root
# libgnutls30t64: CVE-2026-33845 (CRITICAL) DoS via DTLS zero-length の修正を確実に適用
RUN apt-get update && \
    apt-get upgrade -y --no-install-recommends && \
    apt-get install -y --no-install-recommends libgnutls30t64 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip3 install --no-cache-dir redis flask Flask-HTTPAuth pip-review && \
    pip-review --auto
