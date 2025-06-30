# 🔄 Workflow de Développement et Déploiement HF

Ce document explique le nouveau workflow de développement avec la séparation entre l'application locale et le déploiement Hugging Face.

## 📁 Structure Réorganisée

```
03_BUILD_SHIP_SHARE/
├── 🏠 RAG_CHU-app/           # ← DÉVELOPPEMENT LOCAL
│   ├── backend/              # Code backend principal
│   ├── frontend/             # Code frontend principal
│   ├── .env                  # Variables locales
│   ├── workflow.sh           # Scripts locaux
│   ├── start_app_uv.sh      # Démarrage local
│   └── WORKFLOW_HF.md        # Ce fichier
│
└── 🚀 RAG_CHU-hf/            # ← DÉPLOIEMENT HF UNIQUEMENT
    ├── backend/              # Copie synchronisée
    ├── frontend/             # Copie synchronisée
    ├── Dockerfile            # Config Docker HF
    ├── start_hf.sh          # Démarrage HF
    ├── deploy_hf.sh         # Script déploiement
    ├── sync_from_local.sh   # Script synchronisation
    └── README_DEPLOIEMENT.md # Instructions HF
```

## 🔄 Workflow de Développement

### 1. 💻 Développement Local (RAG_CHU-app)

**Travaillez TOUJOURS dans ce répertoire pour le développement :**

```bash
# Dans RAG_CHU-app/
cd RAG_CHU-app

# Développement backend
cd backend
uv sync
uv run uvicorn src.main:app --reload

# Développement frontend
cd frontend
npm install
npm start

# Tests et modifications
# ... vos développements ...
```

### 2. 🧪 Tests et Validation

**Testez localement avant synchronisation :**

```bash
# Test complet local
./start_app_uv.sh

# Vérification des fonctionnalités
# - Upload de documents
# - Chat RAG
# - Interface utilisateur
```

### 3. 🔄 Synchronisation vers HF

**Une fois satisfait des modifications :**

```bash
# Depuis RAG_CHU-app/
cd ../RAG_CHU-hf

# Synchronisation complète
./sync_from_local.sh

# Ou synchronisation partielle
./sync_from_local.sh backend    # Backend seulement
./sync_from_local.sh frontend   # Frontend seulement
./sync_from_local.sh config     # Configuration seulement
```

### 4. 🚀 Déploiement HF

**Déploiement automatique :**

```bash
# Depuis RAG_CHU-hf/
./deploy_hf.sh
```

## 🛠️ Commandes Utiles

### Synchronisation Rapide

```bash
# Depuis RAG_CHU-app/, synchroniser et déployer
cd ../RAG_CHU-hf && \
./sync_from_local.sh && \
./deploy_hf.sh
```

### Développement Spécifique

```bash
# Modification backend uniquement
# 1. Développer dans RAG_CHU-app/backend/
# 2. Synchroniser
cd ../RAG_CHU-hf
./sync_from_local.sh backend
./deploy_hf.sh

# Modification frontend uniquement
# 1. Développer dans RAG_CHU-app/frontend/
# 2. Synchroniser
cd ../RAG_CHU-hf
./sync_from_local.sh frontend
./deploy_hf.sh
```

### Debug HF

```bash
# Test local du build HF
cd RAG_CHU-hf
docker build -t rag-chu-hf .
docker run -p 7860:7860 \
  -e ANTHROPIC_API_KEY=your_key \
  -e OPENAI_API_KEY=your_key \
  rag-chu-hf
```

## 📝 Bonnes Pratiques

### ✅ À Faire

- **Toujours** développer dans `RAG_CHU-app/`
- **Toujours** tester localement avant synchronisation
- Utiliser `sync_from_local.sh` pour synchroniser
- Vérifier les logs HF après déploiement
- Commiter régulièrement vos changements locaux

### ❌ À Éviter

- **Jamais** développer directement dans `RAG_CHU-hf/`
- **Jamais** modifier manuellement les fichiers dans `RAG_CHU-hf/`
- Ne pas oublier de synchroniser avant déploiement
- Ne pas déployer sans test local préalable

## 🔧 Configuration HF Spaces

### Variables d'Environnement Requises

Dans Hugging Face Spaces, configurez :

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-proj-...
```

### Surveillance du Déploiement

- **URL de l'app** : https://huggingface.co/spaces/JTh34/rag-chu
- **Logs** : Onglet "Logs" dans HF Spaces
- **Build** : Onglet "Docker build" pour les erreurs

## 🚨 Résolution de Problèmes

### Erreur de Synchronisation

```bash
# Vérifier les chemins
ls ../RAG_CHU-app/  # Doit exister
pwd                 # Doit être dans RAG_CHU-hf/

# Synchronisation manuelle
cp -r ../RAG_CHU-app/backend/ ./
```

### Erreur de Déploiement HF

```bash
# Vérifier Git config
git config --global --list | grep user

# Re-authentification HF
git config --global credential.helper store
```

### Debug Local

```bash
# Logs détaillés
cd RAG_CHU-app
./start_app_uv.sh --debug

# Vérification des dépendances
cd backend
uv sync --verbose
```

---

**Gardez ce workflow simple et structuré ! 🎯**

**Répertoire de développement** : `RAG_CHU-app/` ← Ici  
**Répertoire de déploiement** : `RAG_CHU-hf/` ← Automatisé 