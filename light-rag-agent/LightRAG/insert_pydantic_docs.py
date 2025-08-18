"""Script to insert documents into LightRAG for processing."""

import os
import asyncio
import argparse
from pathlib import Path
from typing import List, Optional

import httpx

from common import RAGManager, RAGConfig, get_default_config, validate_file_path, sanitize_filename

# URL of the Pydantic AI documentation
PYDANTIC_DOCS_URL = "https://ai.pydantic.dev/llms.txt"

def fetch_pydantic_docs() -> str:
    """Fetch the Pydantic AI documentation from the URL.
    
    Returns:
        The content of the documentation
        
    Raises:
        Exception: If fetching fails
    """
    try:
        response = httpx.get(PYDANTIC_DOCS_URL)
        response.raise_for_status()
        return response.text
    except Exception as e:
        raise Exception(f"Error fetching Pydantic AI documentation: {e}")

def load_local_document(file_path: str) -> str:
    """Load a local document file.
    
    Args:
        file_path: Path to the document file
        
    Returns:
        Content of the document
        
    Raises:
        Exception: If reading fails
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if not content.strip():
                raise ValueError("File is empty")
            return content
    except Exception as e:
        raise Exception(f"Error reading file {file_path}: {e}")

def load_documents_from_directory(directory_path: str) -> List[str]:
    """Load all text documents from a directory.
    
    Args:
        directory_path: Path to directory containing documents
        
    Returns:
        List of document contents
    """
    documents = []
    supported_extensions = ['.txt', '.md', '.rst', '.py']
    
    try:
        for root, _dirs, files in os.walk(directory_path):
            for file in files:
                if any(file.endswith(ext) for ext in supported_extensions):
                    file_path = os.path.join(root, file)
                    try:
                        content = load_local_document(file_path)
                        documents.append(content)
                        print(f"Loaded: {file_path}")
                    except Exception as e:
                        print(f"Skipping {file_path}: {e}")
    except Exception as e:
        print(f"Error walking directory {directory_path}: {e}")
    
    return documents

async def insert_documents(
    config: RAGConfig,
    documents: List[str],
    document_names: Optional[List[str]] = None
) -> None:
    """Insert documents into LightRAG.
    
    Args:
        config: RAG configuration
        documents: List of document contents
        document_names: Optional list of document names for identification
    """
    try:
        rag_manager = RAGManager(config)
        rag = await rag_manager.initialize()
        
        print(f"Inserting {len(documents)} documents...")
        
        for i, doc in enumerate(documents):
            try:
                await rag.ainsert(doc)
                doc_name = document_names[i] if document_names and i < len(document_names) else f"Document {i+1}"
                print(f"✓ Inserted: {doc_name}")
            except Exception as e:
                print(f"✗ Failed to insert document {i+1}: {e}")
        
        print("Document insertion completed!")
        
    except Exception as e:
        print(f"Error during document insertion: {e}")
        raise

async def main():
    """Main function to handle document insertion."""
    parser = argparse.ArgumentParser(description="Insert documents into LightRAG")
    parser.add_argument("--working-dir", default="./pydantic-docs", help="Working directory for LightRAG")
    parser.add_argument("--file", help="Path to a single document file")
    parser.add_argument("--directory", help="Path to directory containing documents")
    parser.add_argument("--url", help="URL to fetch document from")
    parser.add_argument("--no-rerank", action="store_true", help="Disable reranking")
    
    args = parser.parse_args()
    
    # Create configuration
    config = RAGConfig(
        working_dir=args.working_dir,
        rerank_enabled=not args.no_rerank
    )
    
    try:
        documents = []
        document_names = []
        
        # Handle different input sources
        if args.file:
            if not validate_file_path(args.file):
                print(f"Error: Invalid file path: {args.file}")
                return
            
            documents.append(load_local_document(args.file))
            document_names.append(Path(args.file).name)
            
        elif args.directory:
            if not os.path.isdir(args.directory):
                print(f"Error: Invalid directory path: {args.directory}")
                return
            
            documents = load_documents_from_directory(args.directory)
            document_names = [f"Document from {args.directory}"]
            
        elif args.url:
            documents.append(fetch_pydantic_docs())
            document_names.append("Document from URL")
            
        else:
            # Default: use local file (commented out in original)
            print("No input source specified. Please use --file, --directory, or --url")
            print("Example usage:")
            print("  python insert_pydantic_docs.py --file /path/to/document.txt")
            print("  python insert_pydantic_docs.py --directory /path/to/documents/")
            print("  python insert_pydantic_docs.py --url")
            return
        
        if documents:
            await insert_documents(config, documents, document_names)
        else:
            print("No documents to insert.")
            
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())