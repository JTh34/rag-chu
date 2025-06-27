# Dockerfile pour le backend RAG CHU
FROM python:3.11-slim

# Métadonnées
LABEL maintainer="CHU Developer <dev@chu.com>"
LABEL description="Backend RAG pour documents médicaux CHU"

# Variables d'environnement
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV UV_CACHE_DIR=/tmp/uv-cache

# Installation des dépendances système
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    libmagic1 \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-fra \
    libreoffice \
    && rm -rf /var/lib/apt/lists/*

# Installation d'uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

# Répertoire de travail
WORKDIR /app

# Copier les fichiers de configuration
COPY pyproject.toml uv.lock* ./
COPY backend/pyproject.toml backend/uv.lock* ./backend/

# Installation des dépendances
RUN uv sync --frozen

# Copier le code source
COPY backend/src ./backend/src
COPY backend/.env.example ./backend/.env.example

# Créer les répertoires nécessaires
RUN mkdir -p uploads backend/static

# Exposer le port
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Point d'entrée
CMD ["uv", "run", "--directory", "backend", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"] 