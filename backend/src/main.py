"""
Application FastAPI pour RAG CHU 
"""
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import os
import json
import uuid
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import shutil
from pydantic import BaseModel
import logging

from config import settings
from rag_service import rag_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_title,
    description=settings.app_description,
    version=settings.app_version,
    debug=settings.debug
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Stockage en mémoire
upload_directory = Path(settings.upload_dir)
upload_directory.mkdir(exist_ok=True)
documents_store: Dict[str, Dict[str, Any]] = {}
rag_chains: Dict[str, Any] = {}

# WebSocket Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connecté. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket déconnecté. Total: {len(self.active_connections)}")

    async def send_message(self, message: dict):
        """Envoie un message à tous les clients connectés"""
        logger.info(f"Envoi message WebSocket: {message}")
        logger.info(f"Connexions actives: {len(self.active_connections)}")
        
        for connection in self.active_connections[:]:
            try:
                message_str = json.dumps(message)
                await connection.send_text(message_str)
                logger.info(f"Message envoyé avec succès: {message_str[:100]}...")
            except Exception as e:
                logger.error(f"Erreur envoi WebSocket: {e}")
                self.active_connections.remove(connection)

manager = ConnectionManager()

# Modèles Pydantic pour la structure des données
class ChatRequest(BaseModel):
    question: str
    document_id: str = None

class DocumentResponse(BaseModel):
    document_id: str
    filename: str
    status: str
    total_chunks: int = 0

class ChatResponse(BaseModel):
    response: str
    document_id: str
    sources: List[Dict] = []

# Routes WebSocket
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    
    # Message de test immédiat
    await manager.send_message({
        "type": "debug",
        "level": "info",
        "message": "WebSocket connecté au backend",
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })
    
    try:
        while True:
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Routes API
@app.get("/api/health")
async def health_check():
    """Vérification de santé de l'API"""
    return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": settings.app_version,
            "qdrant_status": "in-memory" if rag_service.qdrant_client else "disconnected",
            "anthropic_configured": bool(settings.anthropic_api_key),
            "openai_configured": bool(settings.openai_api_key),
            "storage_mode": "RAM (in-memory)"
    }

@app.post("/api/upload", response_model=DocumentResponse)
async def upload_document(file: UploadFile = File(...)):
    """Upload et validation d'un document"""
    
    # Validation du type de fichier
    file_extension = Path(file.filename).suffix.lower()
    if file_extension not in settings.allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"Type de fichier non supporté. Types autorisés: {settings.allowed_extensions}"
        )
    
    # Validation de la taille
    if file.size > settings.max_file_size:
        raise HTTPException(
            status_code=400,
            detail=f"Fichier trop volumineux. Taille max: {settings.max_file_size // (1024*1024)}MB"
        )
    
    # Génération ID et sauvegarde
    document_id = str(uuid.uuid4())
    file_path = upload_directory / f"{document_id}_{file.filename}"
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Stockage des métadonnées
        documents_store[document_id] = {
                                        "document_id": document_id,
                                        "filename": file.filename,
                                        "file_path": str(file_path),
                                        "status": "uploaded",
                                        "upload_time": datetime.now().isoformat(),
                                        "file_size": file.size
        }
        
        # Notification WebSocket
        await manager.send_message({
                                    "type": "upload_success",
                                    "message": f"Document uploadé: {file.filename}",
                                    "document_id": document_id,
                                    "timestamp": datetime.now().strftime("%H:%M:%S")
                                     }
        )
        
        logger.info(f"Document uploadé: {file.filename} (ID: {document_id})")
        
        return DocumentResponse(
                                document_id=document_id,
                                filename=file.filename,
                                status="uploaded"
        )
        
    except Exception as e:
        logger.error(f"Erreur upload: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de l'upload")

@app.post("/api/analyze/{document_id}", response_model=DocumentResponse)
async def analyze_document(document_id: str):
    """Analyse un document avec vision et création du vectorstore"""
    
    if document_id not in documents_store:
        raise HTTPException(status_code=404, detail="Document non trouvé")
    
    document = documents_store[document_id]
    file_path = document["file_path"]
    
    try:
        # Notification début d'analyse
        await manager.send_message({
                                    "type": "analysis_start",
                                    "message": "Analyse visuelle en cours...",
                                    "document_id": document_id,
                                    "timestamp": datetime.now().strftime("%H:%M:%S")
                                    }
        )
        
        # Vérification des clés API
        if not settings.anthropic_api_key or not settings.openai_api_key:
            raise HTTPException(
                status_code=500, 
                detail="Clés API manquantes (Anthropic et OpenAI requises)"
            )
        
        # Callback de progression pour les messages WebSocket
        async def progress_callback(message: str, level: str = "info", details: dict = None):
            await manager.send_message({
                                        "type": "debug",
                                        "level": level,
                                        "message": message,
                                        "details": details,
                                        "document_id": document_id,
                                        "timestamp": datetime.now().strftime("%H:%M:%S")
                                        }
            )
                                
        # Traitement du document avec le service RAG
        result = await rag_service.process_document(file_path, document_id, progress_callback)
        
        # Création de la chaîne RAG
        await manager.send_message({
                                    "type": "rag_creation",
                                    "message": "Création de la chaîne RAG...",
                                    "document_id": document_id,
                                    "timestamp": datetime.now().strftime("%H:%M:%S")
                                    }
        )
        
        rag_chain = rag_service.create_rag_chain(result["collection_name"])
        rag_chains[document_id] = rag_chain
        
        # Mise à jour du document
        documents_store[document_id].update({
                                            "status": "ready",
                                            "collection_name": result["collection_name"],
                                            "total_chunks": result["total_chunks"],
                                            "analysis_time": datetime.now().isoformat()
                                            }
        )
        
        # Notification succès
        await manager.send_message({
                                    "type": "analysis_complete",
                                    "message": f"Analyse terminée: {result['total_chunks']} sections analysées",
                                    "document_id": document_id,
                                    "timestamp": datetime.now().strftime("%H:%M:%S")
                                    }
        )
        
        logger.info(f"Document {document_id} analysé avec succès")
        
        return DocumentResponse(
            document_id=document_id,
            filename=document["filename"],
            status="ready",
            total_chunks=result["total_chunks"]
        )
        
    except Exception as e:
        error_msg = f"Erreur lors de l'analyse: {str(e)}"
        logger.error(error_msg)
        
        # Notification erreur
        await manager.send_message({
                                    "type": "error",
                                    "message": f"ERREUR: {error_msg}",
                                    "document_id": document_id,
                                    "timestamp": datetime.now().strftime("%H:%M:%S")
                                    }
        )
        
        # Mise à jour du statut
        documents_store[document_id]["status"] = "error"
        
        raise HTTPException(status_code=500, detail=error_msg)

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Endpoint de chat avec RAG"""
    
    if not request.document_id:
        raise HTTPException(status_code=400, detail="document_id requis")
    
    if request.document_id not in documents_store:
        raise HTTPException(status_code=404, detail="Document non trouvé")
    
    if request.document_id not in rag_chains:
        raise HTTPException(status_code=400, detail="Document non analysé")
    
    document = documents_store[request.document_id]
    if document["status"] != "ready":
        raise HTTPException(status_code=400, detail="Document pas prêt pour le chat")
    
    try:
        # Notification début de réponse
        await manager.send_message({
                                    "type": "debug",
                                    "level": "info",
                                    "message": f"Recherche RAG pour: '{request.question[:50]}...'",
                                    "document_id": request.document_id,
                                    "timestamp": datetime.now().strftime("%H:%M:%S")
                                    }
        )
        
        # Recherche des sources similaires AVANT génération
        collection_name = document["collection_name"]
        sources = rag_service.search_similar_documents(
            request.question, 
            collection_name, 
            limit=settings.retrieval_k
        )
        
        # Notification des chunks trouvés dans la console debug
        await manager.send_message({
                                    "type": "debug",
                                    "level": "rag",
                                    "message": f"Chunks trouvés: {len(sources)}/{settings.retrieval_k} attendus",
                                    "details": {
                                                "query": request.question,
                                                "collection": collection_name,
                                                "chunks_found": len(sources),
                                                "chunks_expected": settings.retrieval_k
                                                },
                                    "timestamp": datetime.now().strftime("%H:%M:%S")
                                    }
        )
        
        # Détail de chaque chunk dans la console debug
        for i, source in enumerate(sources):
            await manager.send_message({
                                        "type": "debug",
                                        "level": "rag",
                                        "message": f"Chunk {i+1}: Score {source['similarity_score']:.3f} | Page {source.get('metadata', {}).get('page', '?')}",
                                        "details": {
                                            "chunk_index": i+1,
                                            "similarity_score": source['similarity_score'],
                                            "content_preview": source['content'][:100] + "..." if len(source['content']) > 100 else source['content'],
                                            "metadata": source.get('metadata', {})
                                        },
                                        "timestamp": datetime.now().strftime("%H:%M:%S")
                                        }
            )
        
        # Génération de la réponse
        await manager.send_message({
                                    "type": "debug",
                                    "level": "info",
                                    "message": "Génération de la réponse avec contexte RAG",
                                    "timestamp": datetime.now().strftime("%H:%M:%S")
                                    }
        )
        
        rag_chain = rag_chains[request.document_id]
        response = rag_chain.invoke(request.question)
        
        # Notification réponse prête
        await manager.send_message({
                                    "type": "debug",
                                    "level": "success",
                                    "message": f"Réponse générée ({len(response)} caractères)",
                                    "timestamp": datetime.now().strftime("%H:%M:%S")
                                    }
        )
        
        logger.info(f"Réponse générée pour document {request.document_id}")
        
        # Retourner SANS les sources (elles sont dans la console debug)
        return ChatResponse(
                            response=response,
                            document_id=request.document_id,
                            sources=[]
                )
        
    except Exception as e:
        error_msg = f"Erreur génération réponse: {str(e)}"
        logger.error(error_msg)
        
        await manager.send_message({
                                    "type": "error",
                                    "message": f"Erreur : {error_msg}",
                                    "document_id": request.document_id,
                                    "timestamp": datetime.now().strftime("%H:%M:%S")
                                    }
        )
        
        raise HTTPException(status_code=500, detail=error_msg)

@app.get("/api/documents")
async def list_documents():
    """Liste tous les documents uploadés"""
    return {
            "documents": list(documents_store.values()),
            "total": len(documents_store)
            }

@app.get("/api/documents/{document_id}")
async def get_document(document_id: str):
    """Récupère les détails d'un document"""
    if document_id not in documents_store:
        raise HTTPException(status_code=404, detail="Document non trouvé")
    
    document = documents_store[document_id]
    
    # Ajouter les infos de collection si disponible
    if "collection_name" in document:
        collection_info = rag_service.get_collection_info(document["collection_name"])
        document["collection_info"] = collection_info
    
    return document

@app.delete("/api/documents/{document_id}")
async def delete_document(document_id: str):
    """Supprime un document et sa collection"""
    if document_id not in documents_store:
        raise HTTPException(status_code=404, detail="Document non trouvé")
    
    document = documents_store[document_id]
    
    try:
        # Supprimer le fichier
        file_path = Path(document["file_path"])
        if file_path.exists():
            file_path.unlink()
        
        # Supprimer la collection Qdrant
        if "collection_name" in document:
            rag_service.delete_collection(document["collection_name"])
        
        # Supprimer la chaîne RAG
        if document_id in rag_chains:
            del rag_chains[document_id]
        
        # Supprimer de la mémoire
        del documents_store[document_id]
        
        logger.info(f"Document {document_id} supprimé")
        return {"message": "Document supprimé avec succès"}
        
    except Exception as e:
        logger.error(f"Erreur suppression document {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de la suppression")



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 