"""
Utility functions for the Crawl4AI MCP server.
"""
import os
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings

def get_chroma_client(db_dir: str = "./chroma_db") -> chromadb.Client:
    """
    Get a ChromaDB client with the specified database directory.
    
    Args:
        db_dir: Path to the ChromaDB directory
        
    Returns:
        ChromaDB client instance
    """
    # Ensure the directory exists
    os.makedirs(db_dir, exist_ok=True)
    
    # Create and return a persistent client
    return chromadb.PersistentClient(
        path=db_dir,
        settings=Settings(anonymized_telemetry=False)
    )

def get_or_create_collection(client: chromadb.Client, collection_name: str, embedding_model_name: str = "all-MiniLM-L6-v2") -> chromadb.Collection:
    """
    Get or create a ChromaDB collection with the specified name and embedding model.
    
    Args:
        client: ChromaDB client
        collection_name: Name of the collection
        embedding_model_name: Name of the embedding model to use
        
    Returns:
        ChromaDB collection
    """
    try:
        # Try to get the collection
        return client.get_collection(name=collection_name)
    except Exception:
        # Create the collection if it doesn't exist
        return client.create_collection(
            name=collection_name,
            embedding_function=chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=embedding_model_name
            )
        )

def add_documents_to_collection(collection, ids: List[str], documents: List[str], metadatas: List[Dict[str, Any]], batch_size: int = 100) -> None:
    """
    Add documents to a ChromaDB collection in batches.
    
    Args:
        collection: ChromaDB collection
        ids: List of document IDs
        documents: List of document contents
        metadatas: List of document metadata
        batch_size: Size of each batch for insertion
    """
    # Process in batches to avoid memory issues
    for i in range(0, len(documents), batch_size):
        batch_end = min(i + batch_size, len(documents))
        collection.add(
            ids=ids[i:batch_end],
            documents=documents[i:batch_end],
            metadatas=metadatas[i:batch_end]
        )
