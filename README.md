---
title: RAG CHU - Documents Médicaux
emoji: 🏥
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Application RAG pour l'analyse de documents médicaux avec IA
tags:
  - medical
  - rag
  - fastapi
  - react
  - document-analysis
  - healthcare
---

# 🏥 RAG CHU - Application RAG pour Documents Médicaux

Application locale de développement pour l'analyse et la recherche dans les documents médicaux utilisant la technologie RAG (Retrieval-Augmented Generation) avec vision par IA.

## 🚀 Démarrage Rapide

### 1. Installation et Configuration

```bash
# 1. Installation des dépendances backend (uv)
cd backend
uv sync
cd ..

# 2. Installation des dépendances frontend
cd frontend
npm install
cd ..

# 3. Configuration des clés API
cp backend/.env.example backend/.env
# Éditer backend/.env avec vos clés API
```

### 2. Variables d'Environnement

Dans `backend/.env` :
```bash
ANTHROPIC_API_KEY=your_anthropic_key    # Pour l'analyse vision
OPENAI_API_KEY=your_openai_key          # Pour embeddings et LLM
```

### 3. Démarrage de l'Application

```bash
# Démarrage complet (backend + frontend)
./start_app_uv.sh

# Ou démarrage séparé :
# Backend (terminal 1)
cd backend && uv run uvicorn src.main:app --reload

# Frontend (terminal 2)  
cd frontend && npm start
```

## 📁 Structure du Projet

```
RAG_CHU-app/
├── 📄 README.md              # Ce fichier
├── 📄 WORKFLOW_HF.md         # Instructions déploiement HF
├── 📄 ENV_CONFIG.md          # Guide configuration environnement
├── 🚀 start_app_uv.sh       # Script démarrage local
├── 🔧 workflow.sh           # Outils développement
├── 📦 requirements.txt       # Dépendances Python globales
├── ⚙️ pyproject.toml         # Configuration workspace
├── 🐍 backend/               # API FastAPI
│   ├── src/                  # Code source Python
│   ├── pyproject.toml        # Dépendances backend
│   └── .env                  # Variables d'environnement
├── ⚛️ frontend/              # Interface React
│   ├── src/                  # Code source React
│   ├── public/               # Assets publics
│   └── package.json          # Dépendances frontend
└── 📁 uploads/               # Fichiers temporaires
```

## 🛠️ Développement

### Backend (FastAPI + uv)

```bash
cd backend

# Synchroniser les dépendances
uv sync

# Démarrer en mode développement
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Ajouter une dépendance
uv add nouvelle-dependance

# Tests (si configurés)
uv run pytest
```

### Frontend (React)

```bash
cd frontend

# Installer les dépendances
npm install

# Démarrer en mode développement
npm start

# Build de production
npm run build

# Ajouter une dépendance
npm install nouvelle-dependance
```

## 🔗 Accès Local

- **🎨 Interface** : http://localhost:3000
- **🔧 API** : http://localhost:8000
- **📖 Documentation API** : http://localhost:8000/docs
- **⚡ Health Check** : http://localhost:8000/api/health

## 🧪 Tests et Validation

```bash
# Tests via workflow interactif
./workflow.sh

# Ou tests manuels
cd backend && uv run python -m py_compile src/main.py
cd frontend && npm run build
```

## 🚀 Déploiement

Une fois vos développements terminés :

1. **Voir** : `WORKFLOW_HF.md` pour les instructions complètes
2. **Synchroniser** : Copier vers `../RAG_CHU-hf/`
3. **Déployer** : Utiliser les scripts dans `RAG_CHU-hf/`

## 🔧 Outils Utiles

```bash
# Menu interactif complet
./workflow.sh

# Démarrage rapide
./start_app_uv.sh

# Configuration environnement
cat ENV_CONFIG.md
```

## 📝 Fonctionnalités

- **📄 Analyse Vision** : Documents PDF et images avec Claude d'Anthropic
- **🧠 RAG Avancé** : Recherche sémantique avec Qdrant et OpenAI
- **💬 Chat Médical** : Interface conversationnelle spécialisée
- **📡 Temps Réel** : WebSocket pour notifications
- **🔧 API REST** : Endpoints FastAPI documentés

## 🛠️ Technologies

- **Backend** : Python 3.11 + FastAPI + uv
- **Frontend** : React 18 + Axios
- **IA** : LangChain + OpenAI + Anthropic
- **Vector DB** : Qdrant (in-memory)
- **Dev Tools** : Hot reload, tests automatiques

---

**💻 Répertoire de développement local - Voir `WORKFLOW_HF.md` pour le déploiement** 