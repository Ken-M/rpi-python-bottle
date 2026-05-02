FROM python:3.14-slim

USER root
RUN apt-get update && \
    apt-get upgrade -y --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip3 install --no-cache-dir redis flask Flask-HTTPAuth pip-review && \
    pip-review --auto
