# syntax=docker/dockerfile:1.7
# python:3.14.6-slim (Debian ベース、arm64 対応) を使用。
# 以前は debian:trixie 上で Python をソースビルドしていたが、
# 公式 slim イメージで同一バージョンが提供されているため移行した（ビルド時間 30〜60 分 → 数分）。
FROM python:3.14.6-slim

USER root

RUN apt-get update && \
    apt-get upgrade -y --no-install-recommends && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# pip をアップグレード
# Takumi Guard (Shisho Guard) 経由で PyPI を取得しサプライチェーン攻撃を防ぐ。
# トークンは BuildKit secret (takumi_guard_token) でマウントし、イメージ層へは焼き込まない。
# トークン未設定時は匿名モード (registry のみ) でフォールバックする。
RUN --mount=type=secret,id=takumi_guard_token \
    TG_TOKEN="$(grep -vE '^[[:space:]]*#' /run/secrets/takumi_guard_token 2>/dev/null | grep -oE 'tg_[A-Za-z0-9_]+' | head -n1)"; \
    export PIP_INDEX_URL="https://${TG_TOKEN:+token:${TG_TOKEN}@}pypi.flatt.tech/simple/"; \
    pip3 install --upgrade pip setuptools wheel

# Python パッケージをインストール
# cryptography・grpcio はいずれも linux/arm64 の pre-built wheel が PyPI に存在するため
# Rust コンパイルは不要（Rustup インストール不要）
# こちらも Takumi Guard 経由で取得する（secret マウントは RUN ごとに必要）。
RUN --mount=type=secret,id=takumi_guard_token \
    TG_TOKEN="$(grep -vE '^[[:space:]]*#' /run/secrets/takumi_guard_token 2>/dev/null | grep -oE 'tg_[A-Za-z0-9_]+' | head -n1)"; \
    export PIP_INDEX_URL="https://${TG_TOKEN:+token:${TG_TOKEN}@}pypi.flatt.tech/simple/"; \
    pip3 install --no-cache-dir \
        wheel \
        pyserial \
        retry2 \
        jpholiday \
        pycryptodome \
        requests \
        pyjwt \
        google-api-python-client \
        google-auth-httplib2 \
        google-auth \
        pychromecast \
        six \
        grpcio \
        cryptography \
        pip-review \
        redis && \
    pip-review --auto

# ユーザ作成 + ドングル読み取り権限付与
RUN groupadd web && \
    useradd -d /home/bottle -m bottle && \
    usermod -a -G tty bottle && \
    usermod -a -G dialout bottle

USER bottle
