from fastapi import FastAPI, WebSocket, UploadFile, File, HTTPException, WebSocketDisconnect
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
import json
import uuid
import atexit
import signal
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import asyncio
import logging

from .config import settings
from .rag_service import rag_service
from .vision_processor import IntelligentMedicalProcessor

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
    """Gestionnaire des connexions WebSocket pour les notifications temps réel"""
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Accepte et enregistre une nouvelle connexion WebSocket"""
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """Supprime une connexion WebSocket de la liste active"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_message(self, message: dict):
        """Envoie un message à tous les clients connectés"""
        for connection in self.active_connections[:]:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Erreur envoi WebSocket: {e}")
                self.active_connections.remove(connection)

manager = ConnectionManager()

# Configuration frontend
frontend_build_path = Path(__file__).parent.parent.parent / "frontend" / "build"
possible_paths = [
    frontend_build_path,
    Path("/app/frontend/build"),
    Path(__file__).parent.parent / "frontend" / "build",
]

frontend_build_path = None
for path in possible_paths:
    if path.exists():
        frontend_build_path = path
        break

if frontend_build_path:
    static_path = frontend_build_path / "static"
    if static_path.exists():
        app.mount("/static", StaticFiles(directory=static_path), name="static")

# Modèles Pydantic
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
    """Point d'entrée WebSocket pour les notifications temps réel"""
    await manager.connect(websocket)
    try:
        while True:
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Routes API
@app.get("/api/health")
async def health_check():
    """Vérification de l'état de santé de l'API et de ses composants"""
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
    """Upload et validation d'un document médical (PDF, DOCX, images)"""
    file_extension = Path(file.filename).suffix.lower()
    if file_extension not in settings.allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"Type de fichier non supporté. Types autorisés: {settings.allowed_extensions}"
        )
    
    if file.size > settings.max_file_size:
        raise HTTPException(
            status_code=400,
            detail=f"Fichier trop volumineux. Taille max: {settings.max_file_size // (1024*1024)}MB"
        )
    
    document_id = str(uuid.uuid4())
    file_path = upload_directory / f"{document_id}_{file.filename}"
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        documents_store[document_id] = {
            "document_id": document_id,
            "filename": file.filename,
            "file_path": str(file_path),
            "status": "uploaded",
            "upload_time": datetime.now().isoformat(),
            "file_size": file.size
        }
        
        await manager.send_message({
            "type": "upload_success",
            "message": f"Document uploadé: {file.filename}",
            "document_id": document_id,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
        
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
    """Analyse un document avec Claude Vision et création du vectorstore Qdrant"""
    if document_id not in documents_store:
        raise HTTPException(status_code=404, detail="Document non trouvé")
    
    document = documents_store[document_id]
    file_path = document["file_path"]
    
    if not settings.anthropic_api_key or not settings.openai_api_key:
        raise HTTPException(
            status_code=500, 
            detail="Clés API manquantes (Anthropic et OpenAI requises)"
        )
    
    try:
        await manager.send_message({
            "type": "analysis_start",
            "message": "Analyse visuelle en cours...",
            "document_id": document_id,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
        
        async def progress_callback(message: str, level: str = "info", details: dict = None):
            """Callback pour envoyer les notifications de progression via WebSocket"""
            await manager.send_message({
                "type": "debug",
                "level": level,
                "message": message,
                "details": details,
                "document_id": document_id,
                "timestamp": datetime.now().strftime("%H:%M:%S")
            })
                                
        result = await rag_service.process_document(file_path, document_id, progress_callback)
        rag_chain = rag_service.create_rag_chain(result["collection_name"])
        rag_chains[document_id] = rag_chain
        
        documents_store[document_id].update({
            "status": "ready",
            "collection_name": result["collection_name"],
            "total_chunks": result["total_chunks"],
            "analysis_time": datetime.now().isoformat()
        })
        
        await manager.send_message({
            "type": "analysis_complete",
            "message": f"Analyse terminée: {result['total_chunks']} sections analysées",
            "document_id": document_id,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
        
        return DocumentResponse(
            document_id=document_id,
            filename=document["filename"],
            status="ready",
            total_chunks=result["total_chunks"]
        )
        
    except Exception as e:
        error_msg = f"Erreur lors de l'analyse: {str(e)}"
        logger.error(error_msg)
        
        await manager.send_message({
            "type": "error",
            "message": f"ERREUR: {error_msg}",
            "document_id": document_id,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
        
        documents_store[document_id]["status"] = "error"
        raise HTTPException(status_code=500, detail=error_msg)

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Génère une réponse médicale basée sur le contenu du document analysé"""
    if not request.document_id:
        raise HTTPException(status_code=400, detail="document_id requis")
    
    if request.document_id not in documents_store:
        raise HTTPException(status_code=404, detail="Document non trouvé")
    
    if request.document_id not in rag_chains:
        raise HTTPException(status_code=400, detail="Document non analysé")
    
    document = documents_store[request.document_id]
    if document["status"] != "ready":
        raise HTTPException(status_code=400, detail="Document pas prêt pour le chat")
    
    # Debug: Afficher la question posée
    logger.info("NOUVELLE QUESTION RAG:")
    logger.info("="*100)
    logger.info(f"   Question: {request.question}")
    logger.info(f"   Document ID: {request.document_id}")
    logger.info(f"   Document: {document.get('filename', 'N/A')}")
    logger.info("="*100)
    
    # Envoyer la question à la console de debug
    await manager.send_message({
        "type": "debug",
        "level": "rag",
        "message": f"Question RAG: {request.question}",
        "details": {
            "document_id": request.document_id,
            "filename": document.get('filename', 'N/A'),
            "query": request.question
        },
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })
    
    try:
        rag_chain = rag_chains[request.document_id]
        logger.info("DÉMARRAGE DU PIPELINE RAG...")
        
        # Envoyer le début du pipeline RAG
        await manager.send_message({
            "type": "debug",
            "level": "rag",
            "message": "Démarrage pipeline RAG - Recherche de chunks similaires...",
            "document_id": request.document_id,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
        
        # Récupérer les chunks similaires pour debug
        collection_name = document.get("collection_name")
        if collection_name:
            similar_chunks = rag_service.search_similar_documents(
                request.question, 
                collection_name, 
                settings.retrieval_k
            )
            
            # Envoyer les résultats de recherche à la console de debug
            await manager.send_message({
                "type": "debug",
                "level": "rag",
                "message": f"Chunks trouvés: {len(similar_chunks)}/{settings.retrieval_k}",
                "details": {
                    "query": request.question,
                    "collection": collection_name,
                    "chunks_found": len(similar_chunks),
                    "chunks_expected": settings.retrieval_k
                },
                "timestamp": datetime.now().strftime("%H:%M:%S")
            })
            
            # Envoyer chaque chunk récupéré avec son score
            for i, chunk in enumerate(similar_chunks):
                await manager.send_message({
                    "type": "debug",
                    "level": "rag",
                    "message": f"Chunk {i+1}: Score {chunk['similarity_score']:.4f}",
                    "details": {
                        "chunk_index": i + 1,
                        "similarity_score": chunk['similarity_score'],
                        "metadata": chunk['metadata'],
                        "content_preview": chunk['content'][:200] + "..." if len(chunk['content']) > 200 else chunk['content']
                    },
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                })
        
        response = rag_chain.invoke(request.question)
        
        logger.info("RÉPONSE RAG GÉNÉRÉE:")
        logger.info(f"   Longueur réponse: {len(response)} caractères")
        logger.info(f"   Début réponse: {response[:200]}{'...' if len(response) > 200 else ''}")
        logger.info("="*100)
        
        # Envoyer la réponse générée à la console de debug
        await manager.send_message({
            "type": "debug",
            "level": "success",
            "message": f"Réponse générée: {len(response)} caractères",
            "details": {
                "response_length": len(response),
                "response_preview": response[:200] + "..." if len(response) > 200 else response
            },
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
        
        return ChatResponse(
            response=response,
            document_id=request.document_id,
            sources=[]
        )
        
    except Exception as e:
        error_msg = f"Erreur génération réponse: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@app.post("/api/chat/stream")
async def chat_stream_endpoint(request: ChatRequest):
    """Génère une réponse médicale en streaming basée sur le contenu du document analysé"""
    if not request.document_id:
        raise HTTPException(status_code=400, detail="document_id requis")
    
    if request.document_id not in documents_store:
        raise HTTPException(status_code=404, detail="Document non trouvé")
    
    if request.document_id not in rag_chains:
        raise HTTPException(status_code=400, detail="Document non analysé")
    
    document = documents_store[request.document_id]
    if document["status"] != "ready":
        raise HTTPException(status_code=400, detail="Document pas prêt pour le chat")
    
    # Debug: Afficher la question posée pour le streaming
    logger.info("NOUVELLE QUESTION RAG STREAMING:")
    logger.info("="*100)
    logger.info(f"   Question: {request.question}")
    logger.info(f"   Document ID: {request.document_id}")
    logger.info(f"   Document: {document.get('filename', 'N/A')}")
    logger.info("="*100)
    
    # Envoyer la question à la console de debug
    await manager.send_message({
        "type": "debug",
        "level": "rag",
        "message": f"Question RAG Streaming: {request.question}",
        "details": {
            "document_id": request.document_id,
            "filename": document.get('filename', 'N/A'),
            "query": request.question,
            "mode": "streaming"
        },
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })
    
    # Récupérer et envoyer les chunks similaires pour debug
    collection_name = document.get("collection_name")
    if collection_name:
        similar_chunks = rag_service.search_similar_documents(
            request.question, 
            collection_name, 
            settings.retrieval_k
        )
        
        # Envoyer les résultats de recherche à la console de debug
        await manager.send_message({
            "type": "debug",
            "level": "rag",
            "message": f"Chunks trouvés (streaming): {len(similar_chunks)}/{settings.retrieval_k}",
            "details": {
                "query": request.question,
                "collection": collection_name,
                "chunks_found": len(similar_chunks),
                "chunks_expected": settings.retrieval_k,
                "mode": "streaming"
            },
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
        
        # Envoyer chaque chunk récupéré avec son score
        for i, chunk in enumerate(similar_chunks):
            await manager.send_message({
                "type": "debug",
                "level": "rag",
                "message": f"Chunk {i+1}: Score {chunk['similarity_score']:.4f} (streaming)",
                "details": {
                    "chunk_index": i + 1,
                    "similarity_score": chunk['similarity_score'],
                    "metadata": chunk['metadata'],
                    "content_preview": chunk['content'][:200] + "..." if len(chunk['content']) > 200 else chunk['content'],
                    "mode": "streaming"
                },
                "timestamp": datetime.now().strftime("%H:%M:%S")
            })
    
    async def generate_response():
        """Générateur pour le streaming de la réponse"""
        try:
            rag_chain = rag_chains[request.document_id]
            
            # Envoyer un message de démarrage
            yield f"data: {json.dumps({'type': 'start', 'message': 'Génération de la réponse...', 'document_id': request.document_id})}\n\n"
            
            try:
                # Essayer d'abord le streaming natif
                response_chunks = []
                async for chunk in rag_chain.astream(request.question):
                    if chunk:
                        response_chunks.append(str(chunk))
                        chunk_data = {
                            'type': 'chunk',
                            'content': str(chunk),
                            'document_id': request.document_id
                        }
                        yield f"data: {json.dumps(chunk_data)}\n\n"
                        await asyncio.sleep(0.01)  # Petit délai pour fluidité
                        
            except Exception as streaming_error:
                # Fallback : récupérer la réponse complète et la streamer mot par mot
                logger.warning(f"Streaming natif échoué, fallback vers simulation: {streaming_error}")
                
                full_response = rag_chain.invoke(request.question)
                words = full_response.split()
                
                for i, word in enumerate(words):
                    chunk_data = {
                        'type': 'chunk',
                        'content': word + (" " if i < len(words) - 1 else ""),
                        'document_id': request.document_id
                    }
                    yield f"data: {json.dumps(chunk_data)}\n\n"
                    await asyncio.sleep(0.05)  # Simuler le streaming
            
            # Message de fin
            yield f"data: {json.dumps({'type': 'end', 'message': 'Réponse terminée', 'document_id': request.document_id})}\n\n"
            
        except Exception as e:
            error_msg = f"Erreur génération réponse: {str(e)}"
            logger.error(error_msg)
            error_data = {
                'type': 'error',
                'message': error_msg,
                'document_id': request.document_id
            }
            yield f"data: {json.dumps(error_data)}\n\n"
    
    return StreamingResponse(
        generate_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
            "X-Accel-Buffering": "no",  # Nginx : pas de buffering
        }
    )

@app.get("/api/documents")
async def list_documents():
    """Retourne la liste de tous les documents uploadés avec leurs métadonnées"""
    return {
        "documents": list(documents_store.values()),
        "total": len(documents_store)
    }

@app.get("/api/documents/{document_id}")
async def get_document(document_id: str):
    """Récupère les détails complets d'un document spécifique"""
    if document_id not in documents_store:
        raise HTTPException(status_code=404, detail="Document non trouvé")
    
    document = documents_store[document_id]
    if "collection_name" in document:
        collection_info = rag_service.get_collection_info(document["collection_name"])
        document["collection_info"] = collection_info
    
    return document

@app.delete("/api/documents/{document_id}")
async def delete_document(document_id: str):
    """Supprime définitivement un document et sa collection vectorielle associée"""
    if document_id not in documents_store:
        raise HTTPException(status_code=404, detail="Document non trouvé")
    
    document = documents_store[document_id]
    
    try:
        file_path = Path(document["file_path"])
        if file_path.exists():
            file_path.unlink()
        
        if "collection_name" in document:
            rag_service.delete_collection(document["collection_name"])
        
        if document_id in rag_chains:
            del rag_chains[document_id]
        
        del documents_store[document_id]
        return {"message": "Document supprimé avec succès"}
        
    except Exception as e:
        logger.error(f"Erreur suppression document {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de la suppression")

@app.post("/api/cleanup")
async def manual_cleanup():
    """Nettoie manuellement tous les documents de la mémoire et du disque"""
    try:
        docs_count = len(documents_store)
        collections_count = len([doc for doc in documents_store.values() if "collection_name" in doc])
        
        cleanup_memory()
        
        await manager.send_message({
            "type": "cleanup",
            "message": f"Nettoyage manuel effectué: {docs_count} documents supprimés",
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
        
        return {
            "message": "Nettoyage de la mémoire effectué avec succès",
            "documents_cleaned": docs_count,
            "collections_cleaned": collections_count
        }
        
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage manuel: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors du nettoyage")

# Routes frontend
@app.get("/")
async def serve_react_app():
    """Sert l'interface React du frontend ou une page d'erreur si indisponible"""
    if frontend_build_path:
        index_path = frontend_build_path / "index.html"
        if index_path.exists():
            return HTMLResponse(content=index_path.read_text(), status_code=200)
    
    return HTMLResponse("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>RAG CHU - Erreur Frontend</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; background: #f8d7da; color: #721c24; }
                .error { background: white; padding: 20px; border-radius: 8px; border-left: 4px solid #dc3545; }
            </style>
        </head>
        <body>
            <div class="error">
                <h1>Frontend React non trouvé</h1>
                <p>Le frontend n'a pas été correctement buildé.</p>
                <p><a href="/docs">Documentation API</a></p>
            </div>
        </body>
        </html>
    """)

@app.get("/{path:path}")
async def serve_spa(path: str):
    """Gère le routage SPA en servant index.html pour toutes les routes non-API"""
    if path.startswith("api/") or path.startswith("docs") or path.startswith("ws"):
        raise HTTPException(status_code=404, detail="Route API non trouvée")
    
    if frontend_build_path:
        index_path = frontend_build_path / "index.html"
        if index_path.exists():
            return HTMLResponse(content=index_path.read_text(), status_code=200)
    
    raise HTTPException(status_code=404, detail="Frontend non disponible")

def cleanup_memory():
    """Nettoie tous les documents de la mémoire et du disque lors de l'arrêt"""
    logger.info("Début du nettoyage de la mémoire...")
    
    try:
        docs_to_clean = list(documents_store.items())
        cleaned_files = 0
        cleaned_collections = 0
        
        for document_id, document in docs_to_clean:
            try:
                if "file_path" in document:
                    file_path = Path(document["file_path"])
                    if file_path.exists():
                        file_path.unlink()
                        cleaned_files += 1
                
                if "collection_name" in document:
                    if rag_service.delete_collection(document["collection_name"]):
                        cleaned_collections += 1
                
                if document_id in rag_chains:
                    del rag_chains[document_id]
                
            except Exception as e:
                logger.error(f"Erreur nettoyage document {document_id}: {e}")
        
        documents_store.clear()
        rag_chains.clear()
        
        logger.info(f"Nettoyage terminé: {cleaned_files} fichiers et {cleaned_collections} collections supprimés")
        
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage: {e}")

def signal_handler(signum, frame):
    """Gestionnaire de signaux système pour un arrêt propre de l'application"""
    logger.info(f"Signal reçu ({signum}), arrêt de l'application...")
    cleanup_memory()
    exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
atexit.register(cleanup_memory)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 