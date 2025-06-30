# Dockerfile pour le backend RAG CHU
FROM python:3.11-slim

# Variables d'environnement
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_NO_CACHE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv

# Installer les dépendances système
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Installer uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Créer le répertoire de travail
WORKDIR /app

# Copier tout le backend en une fois
COPY backend/ ./

# Installer les dépendances Python
RUN uv sync --frozen --no-dev && \
    chmod -R 777 .venv

# Copier le frontend et le builder
COPY frontend/ ./frontend/

# Builder le frontend pendant le build Docker
WORKDIR /app/frontend
RUN npm install && npm run build

# Se placer dans le répertoire backend pour l'exécution
WORKDIR /app/backend

# Créer les répertoires nécessaires et configurer les permissions
RUN mkdir -p uploads static && \
    chmod 777 /tmp && \
    chmod -R 777 /app/.venv && \
    chmod -R 777 /app

# Exposer le port
EXPOSE 7860

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:7860/api/health || exit 1

# Commande de démarrage avec --no-cache
CMD ["uv", "run", "--no-cache", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "7860"] 