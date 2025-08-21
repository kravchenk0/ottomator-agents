"""Configuration management for LightRAG implementation."""

import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from pydantic import BaseModel, Field

class OpenAIConfig(BaseModel):
    """OpenAI API configuration."""
    api_key: str = Field(..., description="OpenAI API key")
    model: str = Field(default="gpt-5-mini", description="OpenAI model to use")
    temperature: float = Field(default=0.0, description="Model temperature")
    max_tokens: Optional[int] = Field(default=None, description="Maximum tokens for response")

class RAGConfig(BaseModel):
    """RAG system configuration."""
    working_dir: str = Field(default="./documents", description="Working directory for LightRAG")
    embedding_model: str = Field(default="gpt-5-mini", description="Embedding model name")
    llm_model: str = Field(default="gpt-5-mini", description="LLM model name")
    rerank_enabled: bool = Field(default=True, description="Enable document reranking")
    batch_size: int = Field(default=20, description="Batch size for processing")
    max_docs_for_rerank: int = Field(default=20, description="Maximum documents for reranking")
    chunk_size: int = Field(default=1000, description="Document chunk size")
    chunk_overlap: int = Field(default=200, description="Document chunk overlap")

class AppConfig(BaseModel):
    """Application configuration."""
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    max_conversation_history: int = Field(default=100, description="Maximum conversation history")
    enable_streaming: bool = Field(default=True, description="Enable response streaming")

class Config:
    """Main configuration class."""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or "config.yaml"
        self._load_config()
    
    def _load_config(self):
        """Load configuration from file or environment variables."""
        # Try to load from YAML file first
        if Path(self.config_file).exists():
            try:
                import yaml
                with open(self.config_file, 'r') as f:
                    config_data = yaml.safe_load(f)
                    self._apply_config_data(config_data)
            except Exception as e:
                print(f"Warning: Could not load config file {self.config_file}: {e}")
        
        # Override with environment variables
        self._load_from_env()
    
    def _apply_config_data(self, config_data: dict):
        """Apply configuration data from file."""
        if 'openai' in config_data:
            self.openai = OpenAIConfig(**config_data['openai'])
        if 'rag' in config_data:
            self.rag = RAGConfig(**config_data['rag'])
        if 'app' in config_data:
            self.app = AppConfig(**config_data['app'])
    
    def _load_from_env(self):
        """Load configuration from environment variables."""
        # OpenAI config
        if not hasattr(self, 'openai'):
            self.openai = OpenAIConfig(
                api_key=os.getenv("OPENAI_API_KEY", ""),
                model=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
                temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.0")),
                max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", "0")) if os.getenv("OPENAI_MAX_TOKENS") else None
            )
        
        # RAG config
        if not hasattr(self, 'rag'):
            self.rag = RAGConfig(
                working_dir=os.getenv("RAG_WORKING_DIR", "./documents"),
                embedding_model=os.getenv("RAG_EMBEDDING_MODEL", "gpt-5-mini"),
                llm_model=os.getenv("RAG_LLM_MODEL", "gpt-5-mini"),
                rerank_enabled=os.getenv("RAG_RERANK_ENABLED", "true").lower() == "true",
                batch_size=int(os.getenv("RAG_BATCH_SIZE", "20")),
                max_docs_for_rerank=int(os.getenv("RAG_MAX_DOCS_FOR_RERANK", "20")),
                chunk_size=int(os.getenv("RAG_CHUNK_SIZE", "1000")),
                chunk_overlap=int(os.getenv("RAG_CHUNK_OVERLAP", "200"))
            )
        
        # App config
        if not hasattr(self, 'app'):
            self.app = AppConfig(
                debug=os.getenv("APP_DEBUG", "false").lower() == "true",
                log_level=os.getenv("APP_LOG_LEVEL", "INFO"),
                max_conversation_history=int(os.getenv("APP_MAX_CONVERSATION_HISTORY", "100")),
                enable_streaming=os.getenv("APP_ENABLE_STREAMING", "true").lower() == "true"
            )
    
    def validate(self) -> bool:
        """Validate configuration."""
        errors = []
        
        if not self.openai.api_key:
            errors.append("OPENAI_API_KEY is required")
        
        if not Path(self.rag.working_dir).parent.exists():
            errors.append(f"Working directory parent does not exist: {self.rag.working_dir}")
        
        if self.rag.batch_size <= 0:
            errors.append("Batch size must be positive")
        
        if self.rag.chunk_size <= 0:
            errors.append("Chunk size must be positive")
        
        if errors:
            print("Configuration validation errors:")
            for error in errors:
                print(f"  - {error}")
            return False
        
        return True
    
    def save(self, filename: Optional[str] = None):
        """Save configuration to file."""
        import yaml
        
        config_data = {
            'openai': self.openai.dict(),
            'rag': self.rag.dict(),
            'app': self.app.dict()
        }
        
        filename = filename or self.config_file
        with open(filename, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, indent=2)
        
        print(f"Configuration saved to {filename}")

def get_default_config() -> Config:
    """Get default configuration."""
    return Config()

def create_sample_config(filename: str = "config.yaml"):
    """Create a sample configuration file."""
    config = get_default_config()
    config.save(filename)
    print(f"Sample configuration created: {filename}")

if __name__ == "__main__":
    # Create sample config when run directly
    create_sample_config() 