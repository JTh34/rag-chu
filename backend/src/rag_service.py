import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from langchain_community.vectorstores import Qdrant
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.prompts import PromptTemplate
from langchain.docstore.document import Document

from .config import settings
from .vision_processor import IntelligentMedicalProcessor

logger = logging.getLogger(__name__)

class RAGService:
    """Service principal pour le RAG médical avec Qdrant et OpenAI"""
    def __init__(self):
        self.qdrant_client = None
        self.embeddings = None
        self.llm = None
        self.processor = None
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialise les composants Qdrant, OpenAI et Anthropic"""
        self.qdrant_client = QdrantClient(":memory:")
        
        if settings.openai_api_key:
            self.embeddings = OpenAIEmbeddings(
                model=settings.embedding_model,
                api_key=settings.openai_api_key
            )
            
            self.llm = ChatOpenAI(
                model=settings.openai_model,
                temperature=0,
                api_key=settings.openai_api_key,
                streaming=True
            )
        
        if settings.anthropic_api_key:
            self.processor = IntelligentMedicalProcessor(settings.anthropic_api_key)
    
    def _get_embedding_dimension(self) -> int:
        """Retourne la dimension des embeddings selon le modèle configuré"""
        model_dimensions = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
            "text-embedding-002": 1536
        }
        
        model = settings.embedding_model
        dimension = model_dimensions.get(model, 1536)
        return dimension
    
    def ensure_collection(self, collection_name: str) -> bool:
        """Assure que la collection Qdrant existe avec la bonne dimension"""
        try:
            collections = self.qdrant_client.get_collections().collections
            exists = any(col.name == collection_name for col in collections)
            current_dimension = self._get_embedding_dimension()
            
            if exists:
                try:
                    collection_info = self.qdrant_client.get_collection(collection_name)
                    existing_dimension = collection_info.config.params.vectors.size
                    
                    if existing_dimension != current_dimension:
                        self.qdrant_client.delete_collection(collection_name)
                        exists = False
                except Exception:
                    try:
                        self.qdrant_client.delete_collection(collection_name)
                    except:
                        pass
                    exists = False
            
            if not exists:
                self.qdrant_client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(size=current_dimension, distance=Distance.COSINE)
                )
            
            return True
        except Exception as e:
            logger.error(f"Erreur création collection {collection_name}: {e}")
            return False
    
    async def process_document(self, file_path: str, document_id: str, progress_callback=None) -> Dict[str, Any]:
        """Traite un document médical et le vectorise dans Qdrant"""
        if not self.processor:
            raise ValueError("Processeur médical non initialisé (clé Anthropic manquante)")
        
        if not self.embeddings:
            raise ValueError("Embeddings non initialisés (clé OpenAI manquante)")
        
        try:
            if progress_callback:
                await progress_callback("Démarrage de l'analyse visuelle avec Anthropic...", "vision")
            
            documents = await self.processor.process_medical_document(file_path, progress_callback)
            
            if not documents:
                raise ValueError("Aucun contenu extrait du document")
            
            if progress_callback:
                await progress_callback(f"Analyse terminée: {len(documents)} sections extraites", "success")
                await progress_callback("Création de la collection vectorielle...", "chunking")
            
            collection_name = f"medical_doc_{document_id}"
            self.ensure_collection(collection_name)
            
            texts = [doc.page_content for doc in documents]
            metadatas = [doc.metadata for doc in documents]
            
            if progress_callback:
                await progress_callback(f"Génération des embeddings pour {len(texts)} chunks...", "chunking")
            
            embeddings_vectors = self.embeddings.embed_documents(texts)
            
            points = []
            for i, (text, metadata, vector) in enumerate(zip(texts, metadatas, embeddings_vectors)):
                # Debug: Afficher le contenu de chaque chunk
                logger.info(f"CHUNK {i+1}/{len(texts)}:")
                logger.info(f"Page: {metadata.get('page', 'N/A')}")
                logger.info(f"Taille: {metadata.get('chunk_size', 'N/A')} caractères")
                logger.info(f"Entités médicales: {metadata.get('medical_entities', [])}")
                logger.info(f"Contenu (200 premiers chars): {text[:200]}{'...' if len(text) > 200 else ''}")
                logger.info("   " + "="*80)
                
                # Envoyer les détails du chunk via WebSocket si callback disponible
                if progress_callback:
                    await progress_callback(
                        f"📝 Chunk {i+1}/{len(texts)}: Page {metadata.get('page', 'N/A')}, {metadata.get('chunk_size', 'N/A')} chars",
                        "chunking",
                        {
                            "chunk_index": i + 1,
                            "total_chunks": len(texts),
                            "page": metadata.get('page', 'N/A'),
                            "chunk_size": metadata.get('chunk_size', 0),
                            "medical_entities": metadata.get('medical_entities', []),
                            "content_preview": text[:200] + "..." if len(text) > 200 else text
                        }
                    )
                
                points.append(PointStruct(
                    id=i,
                    vector=vector,
                    payload={
                        "page_content": text,
                        "metadata": metadata
                    }
                ))

            logger.info(f"CHUNKING TERMINÉ: {len(points)} chunks créés au total")
            
            if progress_callback:
                await progress_callback(f"Stockage dans Qdrant: {len(points)} vecteurs...", "chunking")
            
            self.qdrant_client.upsert(
                collection_name=collection_name,
                points=points
            )
            
            if progress_callback:
                await progress_callback("Vectorisation terminée avec succès.", "success")
            
            vectorstore = Qdrant(
                client=self.qdrant_client,
                collection_name=collection_name,
                embeddings=self.embeddings,
            )
            
            return {
                "document_id": document_id,
                "collection_name": collection_name,
                "total_chunks": len(documents),
                "vectorstore": vectorstore,
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Erreur traitement document {document_id}: {e}")
            raise
    
    def create_rag_chain(self, collection_name: str):
        """Crée une chaîne RAG médicale pour une collection donnée"""
        if not self.embeddings or not self.llm:
            raise ValueError("Composants RAG non initialisés")
        
        try:
            vectorstore = Qdrant(
                client=self.qdrant_client,
                collection_name=collection_name,
                embeddings=self.embeddings,
            )
            
            retriever = vectorstore.as_retriever(
                search_kwargs={"k": settings.retrieval_k}
            )
            
            def format_docs(docs):
                logger.info("🔍 CHUNKS RÉCUPÉRÉS POUR LE RAG:")
                logger.info("="*100)
                
                for i, doc in enumerate(docs):
                    metadata = doc.metadata
                    logger.info(f"CHUNK RÉCUPÉRÉ {i+1}/{len(docs)}:")
                    logger.info(f"Page: {metadata.get('page', 'N/A')}")
                    logger.info(f"Taille: {metadata.get('chunk_size', 'N/A')} caractères")
                    logger.info(f"Entités médicales: {metadata.get('medical_entities', [])}")
                    logger.info(f"Contenu (300 premiers chars): {doc.page_content[:300]}{'...' if len(doc.page_content) > 300 else ''}")
                    logger.info("  " + "-"*80)
                
                context = "\n\n".join([doc.page_content for doc in docs])
                logger.info(f"CONTEXTE FINAL: {len(context)} caractères total pour le LLM")
                logger.info("="*100)
                
                return context
            
            medical_prompt_template = """Tu es un assistant médical expert analysant des recommandations cliniques officielles.

                                        CONTEXTE MÉDICAL :
                                        {context}

                                        QUESTION : {question}

                                        INSTRUCTIONS :
                                        1. Si l'information nécessaire N'EST PAS dans le contexte, réponds exactement : "INFORMATION NON DISPONIBLE : Les éléments nécessaires pour répondre à cette question ne sont pas présents dans les documents fournis."

                                        2. Si l'information EST présente, structure ta réponse ainsi :

                                        RÉPONSE :
                                        Donne une réponse directe et précise.

                                        DÉTAILS CLINIQUES :
                                        - Posologie/Critères : cite les valeurs exactes du document
                                        - Situation clinique : précise le contexte d'application  
                                        - Source : indique le tableau ou la section du document

                                        PRÉCAUTIONS :
                                        Mentionne les contre-indications ou limitations du contexte, ou indique "Aucune précaution spécifique mentionnée".

                                        RÈGLES ABSOLUES :
                                        - Cite uniquement les informations présentes dans le contexte
                                        - Pour les posologies : valeurs exactes, pas d'approximation
                                        - Ne jamais inventer ou extrapoler
                                        - Distingue clairement les différentes situations cliniques (avec/sans comorbidité, grave/non grave)

                                        RÉPONSE :"""
                                                    
            medical_prompt = PromptTemplate(
                input_variables = ["context", "question"],
                template = medical_prompt_template
            )
            
            rag_chain = (
                { 
                    "context" : retriever | format_docs,
                 "question": RunnablePassthrough()
                }
                | medical_prompt
                | self.llm
                | StrOutputParser()
            )
            
            return rag_chain
            
        except Exception as e:
            logger.error(f"Erreur création chaîne RAG pour {collection_name}: {e}")
            raise
    
    def search_similar_documents(self, query: str, collection_name: str, limit: int = 5) -> List[Dict]:
        """Recherche les documents les plus similaires à une requête"""
        if not self.embeddings:
            raise ValueError("Embeddings non initialisés")
        
        try:
            logger.info(f"RECHERCHE DE SIMILARITÉ:")
            logger.info(f"Requête: {query}")
            logger.info(f"Collection: {collection_name}")
            logger.info(f"Limite: {limit} chunks")
            logger.info("="*100)
            
            vectorstore = Qdrant(
                client=self.qdrant_client,
                collection_name=collection_name,
                embeddings=self.embeddings,
            )
            
            results = vectorstore.similarity_search_with_score(query, k=limit)
            
            logger.info(f"📋 RÉSULTATS DE RECHERCHE ({len(results)} chunks trouvés):")
            
            formatted_results = []
            for i, (doc, score) in enumerate(results):
                logger.info(f"RÉSULTAT {i+1}:")
                logger.info(f"Score de similarité: {float(score):.4f}")
                logger.info(f"Page: {doc.metadata.get('page', 'N/A')}")
                logger.info(f"Entités: {doc.metadata.get('medical_entities', [])}")
                logger.info(f"Contenu (200 chars): {doc.page_content[:200]}{'...' if len(doc.page_content) > 200 else ''}")
                logger.info("      " + "-"*60)
                
                formatted_results.append({  
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "similarity_score": float(score) 
                })
            
            logger.info("RECHERCHE TERMINÉE")
            logger.info("="*100)
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Erreur recherche dans {collection_name}: {e}")
            return []
    
    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """Récupère les informations détaillées d'une collection Qdrant"""
        try:
            info = self.qdrant_client.get_collection(collection_name)
            return {
                "name": collection_name,
                "vectors_count": info.vectors_count,
                "status": info.status,
                "config": {
                    "distance": info.config.params.vectors.distance.value,
                    "size": info.config.params.vectors.size
                }
            }
        except Exception as e:
            logger.error(f"Erreur info collection {collection_name}: {e}")
            return {}
    
    def delete_collection(self, collection_name: str) -> bool:
        """Supprime définitivement une collection Qdrant"""
        try:
            self.qdrant_client.delete_collection(collection_name)
            return True
        except Exception as e:
            logger.error(f"Erreur suppression collection {collection_name}: {e}")
            return False

rag_service = RAGService() 