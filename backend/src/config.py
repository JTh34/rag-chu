
import os
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Configuration centralisée de l'application RAG CHU"""
    
    # API Keys
    anthropic_api_key: Optional[str] = Field(None, env="ANTHROPIC_API_KEY")
    openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY")
    langsmith_api_key: Optional[str] = Field(None, env="LANGSMITH_API_KEY")
    
        
    # Application Configuration
    app_title: str = "RAG CHU - Système médical intelligent"
    app_description: str = "Application RAG pour l'analyse de documents médicaux"
    app_version: str = "0.1.0"
    debug: bool = Field(False, env="DEBUG")
    
    # File Processing
    max_file_size: int = Field(50 * 1024 * 1024, env="MAX_FILE_SIZE")
    allowed_extensions: list = [".pdf", ".docx", ".jpg", ".jpeg", ".png"]
    upload_dir: str = Field("uploads", env="UPLOAD_DIR")
    
    # LLM Configuration
    openai_model: str = Field("gpt-4o-mini", env="OPENAI_MODEL")
    anthropic_model: str = Field("claude-3-sonnet-20240229", env="ANTHROPIC_MODEL")
    embedding_model: str = Field("text-embedding-3-small", env="EMBEDDING_MODEL")
    
    # RAG Configuration
    chunk_size: int = Field(800, env="CHUNK_SIZE")
    chunk_overlap: int = Field(100, env="CHUNK_OVERLAP")
    retrieval_k: int = Field(6, env="RETRIEVAL_K")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
Path(settings.upload_dir).mkdir(exist_ok=True) 