#!/bin/bash

# Script de démarrage pour l'application RAG CHU avec uv
echo "🏥 Démarrage de l'application RAG CHU..."

# Vérifier si uv est installé
if ! command -v uv &> /dev/null; then
    echo "❌ uv n'est pas installé."
    echo "📦 Installation automatique de uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    
    # Recharger le shell pour utiliser uv
    if [ -f "$HOME/.cargo/env" ]; then
        source "$HOME/.cargo/env"
    fi
    
    # Vérifier à nouveau
    if ! command -v uv &> /dev/null; then
        echo "❌ Échec de l'installation de uv. Installez-le manuellement:"
        echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi
fi

echo "✅ uv version: $(uv --version)"

# Vérifier si Node.js est installé
if ! command -v node &> /dev/null; then
    echo "❌ Node.js n'est pas installé."
    echo "📦 Installez Node.js depuis https://nodejs.org"
    echo "   Ou avec Homebrew: brew install node"
    read -p "Voulez-vous continuer sans Node.js (backend seulement) ? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
    FRONTEND_AVAILABLE=false
else
    echo "✅ Node.js version: $(node --version)"
    FRONTEND_AVAILABLE=true
fi

# Configuration Qdrant
echo "🧠 Configuration Qdrant en mode in-memory (RAM)"
echo "✅ Aucune infrastructure externe requise"

# Initialiser le projet avec uv si nécessaire
echo "📦 Configuration du projet avec uv..."

# Synchroniser spécifiquement le backend
echo "📦 Synchronisation du backend..."
cd backend
if [ ! -f "uv.lock" ]; then
    echo "🔧 Initialisation du backend..."
    uv init --no-readme --python 3.9
fi

uv sync
cd ..

# Installation des dépendances Node.js si disponible
if [ "$FRONTEND_AVAILABLE" = true ]; then
    echo "📦 Installation des dépendances frontend..."
    cd frontend
    if [ ! -f "package.json" ]; then
        echo "⚠️  package.json non trouvé dans frontend/"
    else
        npm install
    fi
    cd ..
fi

# Vérifier les variables d'environnement
if [ ! -f "backend/.env" ]; then
    echo "⚠️  Fichier .env manquant dans le backend."
    echo "📋 Création du fichier .env à partir de l'exemple..."
    
    if [ -f "backend/.env.example" ]; then
        cp backend/.env.example backend/.env
        echo "✅ Fichier .env créé à partir de l'exemple"
        echo ""
        echo "⚠️  IMPORTANT: Configurez vos clés API dans backend/.env"
        echo "   Vous aurez besoin de:"
        echo "   - ANTHROPIC_API_KEY (pour l'analyse vision)"
        echo "   - OPENAI_API_KEY (pour embeddings et LLM)"
        echo ""
    fi
    
    read -p "Voulez-vous continuer sans les clés API configurées ? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Configurez vos clés API dans backend/.env et relancez le script."
        exit 1
    fi
fi

# Déplacer le module vision_chunking s'il existe au niveau racine
if [ -f "vision_chunking.py" ]; then
    echo "📁 Déplacement de vision_chunking.py vers le backend..."
    mv vision_chunking.py backend/src/backend/vision_chunking_legacy.py
    echo "✅ Module déplacé (renommé en vision_chunking_legacy.py)"
fi

# Fonction pour tuer les processus en arrière-plan
cleanup() {
    echo "🛑 Arrêt de l'application..."
    kill $BACKEND_PID 2>/dev/null
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null
    fi
    exit 0
}

# Gérer Ctrl+C
trap cleanup SIGINT

# Tuer les processus utilisant les ports
echo "🔪 Vérification des ports..."
BACKEND_PIDS=$(lsof -ti :8000 2>/dev/null)
if [ ! -z "$BACKEND_PIDS" ]; then
    echo "⚠️  Processus trouvés sur le port 8000: $BACKEND_PIDS"
    echo $BACKEND_PIDS | xargs kill -9 2>/dev/null
    echo "✅ Port 8000 libéré"
    sleep 1
fi

if [ "$FRONTEND_AVAILABLE" = true ]; then
    FRONTEND_PIDS=$(lsof -ti :3000 2>/dev/null)
    if [ ! -z "$FRONTEND_PIDS" ]; then
        echo "⚠️  Processus trouvés sur le port 3000: $FRONTEND_PIDS"
        echo $FRONTEND_PIDS | xargs kill -9 2>/dev/null
        echo "✅ Port 3000 libéré"
        sleep 1
    fi
fi

# Créer les répertoires nécessaires
mkdir -p uploads
mkdir -p backend/static

# Démarrer le backend
echo "🔧 Démarrage du backend FastAPI avec uv..."
cd backend
PYTHONPATH=src uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd ..

# Attendre que le backend démarre
echo "⏳ Attente du démarrage du backend..."
sleep 5

# Vérifier que le backend est bien démarré
if curl -s http://localhost:8000/api/health &> /dev/null; then
    echo "✅ Backend démarré avec succès"
else
    echo "❌ Erreur de démarrage du backend"
    echo "📋 Vérifiez les logs ci-dessus pour diagnostiquer le problème"
fi

# Démarrer le frontend si disponible
if [ "$FRONTEND_AVAILABLE" = true ] && [ -f "frontend/package.json" ]; then
    echo "🎨 Démarrage du frontend React..."
    cd frontend
    npm start &
    FRONTEND_PID=$!
    cd ..
    
    echo "⏳ Attente du démarrage du frontend..."
    sleep 3
fi

echo ""
echo "🎉 Application RAG CHU démarrée avec succès !"
echo ""
echo "🔗 Endpoints disponibles:"
echo "   🔧 Backend API: http://localhost:8000"
echo "   📖 Documentation API: http://localhost:8000/docs"

if [ "$FRONTEND_AVAILABLE" = true ] && [ -f "frontend/package.json" ]; then
    echo "   🎨 Frontend React: http://localhost:3000"
    echo "   🏥 Interface complète: http://localhost:3000"
else
    echo "   🏥 Interface simple: http://localhost:8000"
fi

echo ""
echo "📊 Tests rapides:"
echo "   curl http://localhost:8000/api/health"
echo ""
echo "💡 Pour tester l'upload: utilisez l'interface à http://localhost:3000"
echo "📡 WebSocket: ws://localhost:8000/ws"
echo ""
echo "⚠️  N'oubliez pas de configurer vos clés API dans backend/.env"
echo "Appuyez sur Ctrl+C pour arrêter l'application."

# Attendre que les processus se terminent
wait 