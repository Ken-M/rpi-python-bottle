# syntax=docker/dockerfile:1.7
FROM python:3.14.6-slim

USER root
RUN apt-get update && \
    apt-get upgrade -y --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Takumi Guard (Shisho Guard) 経由で PyPI を取得しサプライチェーン攻撃を防ぐ。
# トークンは BuildKit secret (takumi_guard_token) でマウントし、イメージ層へは焼き込まない。
# トークン未設定時は匿名モード (registry のみ) でフォールバックする。
RUN --mount=type=secret,id=takumi_guard_token \
    TG_TOKEN="$(grep -vE '^[[:space:]]*#' /run/secrets/takumi_guard_token 2>/dev/null | grep -oE 'tg_[A-Za-z0-9_]+' | head -n1)"; \
    export PIP_INDEX_URL="https://${TG_TOKEN:+token:${TG_TOKEN}@}pypi.flatt.tech/simple/"; \
    pip3 install --no-cache-dir redis flask Flask-HTTPAuth pip-review && \
    pip-review --auto
