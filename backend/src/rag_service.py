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
    """Service principal pour le RAG"""
    
    def __init__(self):
        self.qdrant_client = None
        self.embeddings = None
        self.llm = None
        self.processor = None
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialise les composants du service RAG"""
        # Client Qdrant en mode in-memory (RAM)
        self.qdrant_client = QdrantClient(":memory:")
        logger.info("Qdrant initialisé dans la RAM")
        
        
        if settings.openai_api_key:
            # Embedding OpenAI
            self.embeddings = OpenAIEmbeddings(
                model=settings.embedding_model,
                api_key=settings.openai_api_key
            )
            
            # LLM pour les réponses
            self.llm = ChatOpenAI(
                model=settings.openai_model,
                temperature=0,
                api_key=settings.openai_api_key
            )
        
        # Processeur de documents médicaux
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
        dimension = model_dimensions.get(model, 1536)  # Défaut à 1536
        logger.info(f"Modèle embedding: {model} (dimension: {dimension})")
        return dimension
    
    def ensure_collection(self, collection_name: str) -> bool:
        """Assure que la collection existe dans Qdrant avec la bonne dimension"""
        try:
            collections = self.qdrant_client.get_collections().collections
            exists = any(col.name == collection_name for col in collections)
            current_dimension = self._get_embedding_dimension()
            
            if exists:
                # Vérifier si la dimension correspond
                try:
                    collection_info = self.qdrant_client.get_collection(collection_name)
                    existing_dimension = collection_info.config.params.vectors.size
                    
                    if existing_dimension != current_dimension:
                        logger.warning(f"Collection {collection_name} a une dimension incorrecte ({existing_dimension} vs {current_dimension}), suppression...")
                        self.qdrant_client.delete_collection(collection_name)
                        exists = False
                except Exception as e:
                    logger.warning(f"Erreur vérification dimension collection {collection_name}: {e}")
                    # En cas d'erreur, recréer la collection
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
                logger.info(f"Collection créée: {collection_name} (dim: {current_dimension})")
            
            return True
        except Exception as e:
            logger.error(f"Erreur création collection {collection_name}: {e}")
            return False
    
    async def process_document(self, file_path: str, document_id: str, progress_callback=None) -> Dict[str, Any]:
        """Traite un document et le vectorise dans Qdrant"""
        if not self.processor:
            raise ValueError("Processeur médical non initialisé (clé Anthropic manquante)")
        
        if not self.embeddings:
            raise ValueError("Embeddings non initialisés (clé OpenAI manquante)")
        
        try:
            if progress_callback:
                await progress_callback("Démarrage de l'analyse visuelle avec Anthropic...", "vision")
            
            # Analyse par LLM vision du document
            documents = await self.processor.process_medical_document(file_path, progress_callback)
            
            if not documents:
                raise ValueError("Aucun contenu extrait du document")
            
            if progress_callback:
                await progress_callback(f"Analyse terminée: {len(documents)} sections extraites", "success")
                await progress_callback("Création de la collection vectorielle...", "chunking")
            
            # Création de la collection
            collection_name = f"medical_doc_{document_id}"
            self.ensure_collection(collection_name)
            
            # Ajouter les documents un par un
            texts = [doc.page_content for doc in documents]
            metadatas = [doc.metadata for doc in documents]
            
            if progress_callback:
                await progress_callback(f"Génération des embeddings pour {len(texts)} chunks...", "chunking")
            
            # Générer les embeddings
            embeddings_vectors = self.embeddings.embed_documents(texts)
            
            # Ajouter les éléments à Qdrant avec la structure correcte
            points = []
            for i, (text, metadata, vector) in enumerate(zip(texts, metadatas, embeddings_vectors)):
                points.append(PointStruct(
                    id=i,
                    vector=vector,
                    payload={
                        "page_content": text,
                        "metadata": metadata
                    }
                ))
            
            if progress_callback:
                await progress_callback(f"Stockage dans Qdrant: {len(points)} vecteurs...", "chunking")
            
            self.qdrant_client.upsert(
                collection_name=collection_name,
                points=points
            )
            
            if progress_callback:
                await progress_callback("Vectorisation terminée avec succès.", "success")
            
            # Créer l'objet vectorstore pour compatibilité
            vectorstore = Qdrant(
                client=self.qdrant_client,
                collection_name=collection_name,
                embeddings=self.embeddings,
            )
            
            logger.info(f"Document {document_id} vectorisé: {len(documents)} chunks")
            
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
        """Crée une chaîne RAG pour une collection donnée"""
        if not self.embeddings or not self.llm:
            raise ValueError("Composants RAG non initialisés")
        
        try:
            # Créer le retriever
            vectorstore = Qdrant(
                client=self.qdrant_client,
                collection_name=collection_name,
                embeddings=self.embeddings,
            )
            
            retriever = vectorstore.as_retriever(
                search_kwargs={"k": settings.retrieval_k}
            )
            
            # Fonction pour formater les documents
            def format_docs(docs):
                return "\n\n".join([doc.page_content for doc in docs])
            
            # Template de prompt médical
            medical_prompt_template = """Tu es un expert médical spécialisé dans l'analyse de recommandations cliniques.

                                        Contexte médical:
                                        {context}

                                        Question: {question}

                                        Instructions:
                                        1. Réponds uniquement en français
                                        2. Base ta réponse exclusivement sur le contexte fourni
                                        3. Cite les sections pertinentes quand cela est possible
                                        4. Si une information n'est pas dans le contexte, indique-le clairement
                                        5. Pour les posologies, sois très précis
                                        6. Mentionne les contre-indications si elles existent

                                        Réponse:"""
                                                    
            # Prompt template
            medical_prompt = PromptTemplate(
                input_variables = ["context", "question"],
                template = medical_prompt_template
            )
            
            # Chaîne RAG
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
        """Recherche de documents similaires"""
        if not self.embeddings:
            raise ValueError("Embeddings non initialisés")
        
        try:
            vectorstore = Qdrant(
                client=self.qdrant_client,
                collection_name=collection_name,
                embeddings=self.embeddings,
            )
            
            # Recherche de similarité
            results = vectorstore.similarity_search_with_score(query, k=limit)
            
            # Formatage des résultats
            formatted_results = []

            for doc, score in results:
                formatted_results.append({  
                                            "content": doc.page_content,
                                            "metadata": doc.metadata,
                                            "similarity_score": float(score) 
                                        }
                )
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Erreur recherche dans {collection_name}: {e}")
            return []
    
    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """Récupère les informations sur une collection"""
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
        """Supprime une collection"""
        try:
            self.qdrant_client.delete_collection(collection_name)
            logger.info(f"Collection supprimée: {collection_name}")
            return True
        except Exception as e:
            logger.error(f"Erreur suppression collection {collection_name}: {e}")
            return False

# Instance globale du  RAG
rag_service = RAGService() 