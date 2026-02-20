# ============================================
# Imagen base
# ============================================
FROM python:3.11-slim

# ============================================
# Variables de entorno seguras para producción
# ============================================
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Configuración de producción por defecto
    DEBUG=false

# ============================================
# Directorio de trabajo
# ============================================
WORKDIR /app

# ============================================
# Instalar dependencias del sistema
# ============================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Dependencies for psycopg2
    libpq-dev \
    gcc \
    # Dependencies for pdf processing
    poppler-utils \
    tesseract-ocr \
    # curl para healthcheck
    curl \
    && rm -rf /var/lib/apt/lists/*

# ============================================
# Copiar requirements e instalar dependencias Python
# ============================================
COPY requirements.txt .
# Instalar PyTorch CPU-only primero (mucho más ligero que la versión completa)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# ============================================
# Copiar código de la aplicación (sin .env)
# ============================================
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY .env.example ./

# ============================================
# Crear directorio de uploads y logs
# ============================================
RUN mkdir -p /app/uploads /app/logs

# ============================================
# Exponer puerto
# ============================================
EXPOSE 8000

# ============================================
# Usuario no root para seguridad
# ============================================
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# ============================================
# Comando de inicio
# Las variables de entorno se pasan desde docker-compose
# ============================================
CMD sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"
