@echo off
REM ============================================================
REM Docker build & push script for Raspberry Pi 5 (linux/arm64)
REM Run this file from the project root (where docker-compose.yml is)
REM ============================================================

REM [1/4] Login to Docker Hub
echo [1/4] Logging in to Docker Hub...
docker login
if %ERRORLEVEL% neq 0 (
    echo ERROR: docker login failed.
    exit /b 1
)

REM [2/4] Prepare buildx builder
REM       Use existing rpi-builder if present, otherwise create a new one
echo [2/4] Preparing buildx builder...
docker buildx use rpi-builder 2>nul || ^
    docker buildx create --use --name rpi-builder
docker buildx inspect --bootstrap
if %ERRORLEVEL% neq 0 (
    echo ERROR: Failed to prepare buildx builder.
    exit /b 1
)

REM [3/4] Build & push measure-application
REM       debian:trixie base + Python 3.14.4 source build (takes time)
echo [3/4] Building measure-application (linux/arm64)...
echo       NOTE: Python source build may take 30-60 minutes
docker buildx build ^
    --platform linux/arm64 ^
    --no-cache ^
    --pull ^
    --push ^
    -t kenonemorita/rpi-python-bottle-app-measure ^
    ./app_measure
if %ERRORLEVEL% neq 0 (
    echo ERROR: Build failed for measure-application.
    exit /b 1
)

REM [4/4] Build & push my_flask_app
REM       python:3.14-slim base (lightweight and fast)
echo [4/4] Building my_flask_app (linux/arm64)...
docker buildx build ^
    --platform linux/arm64 ^
    --pull ^
    --push ^
    -t kenonemorita/rpi-python-bottle-my-flask-app ^
    ./my_flask_app
if %ERRORLEVEL% neq 0 (
    echo ERROR: Build failed for my_flask_app.
    exit /b 1
)

echo.
echo ============================================================
echo All images built and pushed successfully.
echo   kenonemorita/rpi-python-bottle-app-measure
echo   kenonemorita/rpi-python-bottle-my-flask-app
echo.
echo To update on Raspberry Pi:
echo   docker compose pull
echo   docker compose up -d
echo ============================================================
