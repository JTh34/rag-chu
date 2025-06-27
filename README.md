# 🏥 RAG CHU - Application RAG pour Documents Médicaux

Une application moderne d'analyse et de recherche dans les documents médicaux utilisant la technologie RAG (Retrieval-Augmented Generation) avec vision par IA.

## 🚀 Fonctionnalités

- **📄 Analyse Vision** : Traitement intelligent des documents PDF et images avec Claude d'Anthropic
- **🧠 RAG Avancé** : Recherche sémantique avec Qdrant et OpenAI embeddings  
- **💬 Chat Médical** : Interface conversationnelle spécialisée pour les recommandations cliniques
- **📡 Temps Réel** : Notifications WebSocket pour suivre le traitement
- **🔧 API Moderne** : FastAPI avec documentation automatique
- **📦 Gestion uv** : Gestion moderne des dépendances Python
- **🎨 Interface React** : Frontend moderne avec React

## 🏗️ Architecture

```
RAG_CHU-app/
├── 🐍 backend/                 # Backend FastAPI + uv
│   ├── src/
│   │   ├── backend/
│   │   │   ├── config.py           # Configuration centralisée
│   │   │   ├── vision_processor.py # Analyse vision Claude
│   │   │   ├── rag_service.py      # Service RAG principal
│   │   │   └── __init__.py
│   │   └── main.py                 # Application FastAPI
│   ├── pyproject.toml              # Dépendances backend
│   ├── Dockerfile                  # Container backend
│   └── .env.example               # Variables d'environnement
├── ⚛️ frontend/                # Frontend React
│   ├── src/
│   │   ├── components/             # Composants React
│   │   │   ├── DocumentUpload.js   # Upload de documents
│   │   │   ├── DocumentList.js     # Liste des documents
│   │   │   ├── ChatInterface.js    # Interface de chat
│   │   │   └── StatusPanel.js      # Notifications temps réel
│   │   ├── App.js                  # Application principale
│   │   ├── App.css                 # Styles CSS
│   │   └── index.js               # Point d'entrée
│   ├── public/                     # Fichiers publics
│   └── package.json               # Dépendances frontend
├── 📁 uploads/                 # Stockage documents
├── 🗃️ scripts/                # Scripts utilitaires
│   ├── init_project.sh            # Initialisation projet
│   └── quick_start.sh             # Démarrage rapide
├── 🐳 docker-compose.yml       # Services Docker
├── 🚀 start_app_uv.sh         # Script de démarrage
└── 📋 pyproject.toml          # Configuration workspace
```

## 📋 Prérequis

- **Python 3.9+**
- **Node.js 16+** (pour le frontend)
- **uv** (gestionnaire de paquets moderne)
- **Qdrant** (mode in-memory intégré)
- **Clés API** :
  - Anthropic (pour l'analyse vision)
  - OpenAI (pour embeddings et LLM)

## 🛠️ Installation Rapide

### Option 1: Script d'initialisation (Recommandé)

```bash
# Cloner le repository
git clone <your-repo>
cd RAG_CHU-app

# Initialiser le projet
./scripts/init_project.sh

# Configurer les clés API
nano backend/.env

# Qdrant est maintenant intégré en mode in-memory
# Plus besoin de Docker pour Qdrant !

# Lancer l'application complète
./start_app_uv.sh
```

### Option 2: Installation manuelle

```bash
# Installation d'uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Configuration backend
cd backend
cp .env.example .env
# Éditer .env avec vos clés API
uv sync

# Configuration frontend
cd ../frontend
npm install

# Démarrage
cd ..
./start_app_uv.sh
```

## 🔗 Accès à l'Application

- **🎨 Frontend React** : http://localhost:3000 *(Interface principale)*
- **🔧 Backend API** : http://localhost:8000
- **📖 Documentation API** : http://localhost:8000/docs
- **🧠 Stockage** : In-memory (RAM) - Aucun service externe requis
- **⚡ Health Check** : http://localhost:8000/api/health

## 📖 Utilisation

### Interface Web (Recommandé)

1. Ouvrez http://localhost:3000
2. Glissez un document PDF/DOCX dans la zone d'upload
3. Attendez l'analyse automatique
4. Posez vos questions dans le chat

### API REST

```bash
# Upload d'un document
curl -X POST "http://localhost:8000/api/upload" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@document.pdf"

# Analyse du document
curl -X POST "http://localhost:8000/api/analyze/{document_id}"

# Chat avec le document
curl -X POST "http://localhost:8000/api/chat" \
     -H "Content-Type: application/json" \
     -d '{
       "question": "Quelle est la posologie recommandée ?",
       "document_id": "your-document-id"
     }'
```

### WebSocket (Notifications temps réel)

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');
ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Notification:', data);
};
```

## ⚙️ Configuration

### Variables d'Environnement (backend/.env)

```bash
# API Keys (REQUIS)
ANTHROPIC_API_KEY=your_anthropic_key
OPENAI_API_KEY=your_openai_key

# Qdrant Configuration
QDRANT_URL=http://localhost:6333

# Modèles IA
ANTHROPIC_MODEL=claude-3-sonnet-20240229
OPENAI_MODEL=gpt-4
EMBEDDING_MODEL=text-embedding-3-large

# Configuration RAG
RETRIEVAL_K=6
CHUNK_SIZE=1000
```

### Formats Supportés

- **Documents** : PDF, DOCX
- **Images** : JPG, JPEG, PNG
- **Taille max** : 50MB par défaut

## 🧪 Tests et Développement

```bash
# Test de santé global
curl http://localhost:8000/api/health

# Lister les documents
curl http://localhost:8000/api/documents

# Frontend en mode développement
cd frontend && npm start

# Backend en mode développement
cd backend && uv run uvicorn src.main:app --reload

# Tests WebSocket
wscat -c ws://localhost:8000/ws
```

## 🐳 Docker

```bash
# Construction de l'image backend
docker build -t rag-chu-backend -f backend/Dockerfile .

# Démarrage du backend containerisé
docker run -p 8000:8000 \
  -e ANTHROPIC_API_KEY=your_key \
  -e OPENAI_API_KEY=your_key \
  -v $(pwd)/uploads:/app/uploads \
  rag-chu-backend

# Logs
docker logs <container_id>
```

## 🔧 Développement

### Structure du Code

**Backend (Python/FastAPI)**
- **`config.py`** : Configuration centralisée avec Pydantic
- **`vision_processor.py`** : Analyse vision avec Claude
- **`rag_service.py`** : Service RAG avec Qdrant
- **`main.py`** : Application FastAPI principale

**Frontend (React)**
- **`App.js`** : Application principale
- **`components/`** : Composants React modulaires
- **`DocumentUpload.js`** : Upload avec drag & drop
- **`ChatInterface.js`** : Chat avec markdown

### Ajout de Nouvelles Fonctionnalités

1. **Backend** : Ajouter dans `backend/src/backend/`
2. **Frontend** : Créer des composants dans `frontend/src/components/`
3. **Configuration** : Étendre `backend/src/backend/config.py`

### Mode Debug

```bash
# Backend debug
export DEBUG=true
cd backend && uv run uvicorn src.main:app --log-level debug

# Frontend debug
cd frontend && npm start
```

## 📊 Monitoring et Logs

- **Backend** : Logs Python standard
- **Frontend** : Console navigateur + React DevTools
- **API** : Métriques FastAPI intégrées
- **Qdrant** : Dashboard web intégré
- **WebSocket** : Notifications temps réel

## 🚨 Résolution de Problèmes

### Erreurs Communes

**"Qdrant not accessible"**
```bash
docker-compose up qdrant -d
curl http://localhost:6333/health
```

**"API keys missing"**
```bash
# Vérifier la configuration
cat backend/.env
```

**"Frontend not loading"**
```bash
# Réinstaller les dépendances
cd frontend && npm install
```

**"Module import errors"**
```bash
# Resynchroniser uv
uv sync --force
```

### Scripts de Diagnostic

```bash
# Test complet de l'installation
./scripts/quick_start.sh

# Réinitialiser le projet
./scripts/init_project.sh
```

## 📦 Scripts Utilitaires

- **`start_app_uv.sh`** : Démarrage complet (backend + frontend)
- **`scripts/init_project.sh`** : Initialisation du projet
- **`scripts/quick_start.sh`** : Configuration interactive

## 🤝 Contribution

1. Fork le repository
2. Créer une branche feature (`git checkout -b feature/nouvelle-fonctionnalite`)
3. Commit (`git commit -m 'Ajout nouvelle fonctionnalité'`)
4. Push (`git push origin feature/nouvelle-fonctionnalite`)
5. Créer une Pull Request

## 📜 Licence

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

## 🆘 Support

- **Issues** : [GitHub Issues](https://github.com/your-repo/issues)
- **Documentation** : `/docs` endpoint de l'API
- **Email** : dev@chu.com

---

Développé avec ❤️ pour l'amélioration des soins de santé

*Structure organisée avec frontend/backend séparés pour un développement efficace* 