"""
Knowledge graph builder for extracting entities and relationships.
"""

import os
import logging
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime, timezone
import asyncio
import re

from graphiti_core import Graphiti
from dotenv import load_dotenv

from .chunker import DocumentChunk

# Import graph utilities
try:
    from ..agent.graph_utils import GraphitiClient
except ImportError:
    # For direct execution or testing
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from agent.graph_utils import GraphitiClient

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class GraphBuilder:
    """Builds knowledge graph from document chunks."""
    
    def __init__(self):
        """Initialize graph builder."""
        self.graph_client = GraphitiClient()
        self._initialized = False
    
    async def initialize(self):
        """Initialize graph client."""
        if not self._initialized:
            await self.graph_client.initialize()
            self._initialized = True
    
    async def close(self):
        """Close graph client."""
        if self._initialized:
            await self.graph_client.close()
            self._initialized = False
    
    async def add_document_to_graph(
        self,
        chunks: List[DocumentChunk],
        document_title: str,
        document_source: str,
        document_metadata: Optional[Dict[str, Any]] = None,
        batch_size: int = 3  # Reduced batch size for Graphiti
    ) -> Dict[str, Any]:
        """
        Add document chunks to the knowledge graph.
        
        Args:
            chunks: List of document chunks
            document_title: Title of the document
            document_source: Source of the document
            document_metadata: Additional metadata
            batch_size: Number of chunks to process in each batch
        
        Returns:
            Processing results
        """
        if not self._initialized:
            await self.initialize()
        
        if not chunks:
            return {"episodes_created": 0, "errors": []}
        
        logger.info(f"Adding {len(chunks)} chunks to knowledge graph for document: {document_title}")
        
        episodes_created = 0
        errors = []
        
        # Process chunks in batches
        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i:i + batch_size]
            
            for chunk in batch_chunks:
                try:
                    # Create episode ID
                    episode_id = f"{document_source}_{chunk.index}_{datetime.now().timestamp()}"
                    
                    # Prepare episode content with context
                    episode_content = self._prepare_episode_content(
                        chunk,
                        document_title,
                        document_metadata
                    )
                    
                    # Create source description
                    source_description = f"Document: {document_title} (Source: {document_source}, Chunk: {chunk.index})"
                    
                    # Add episode to graph
                    await self.graph_client.add_episode(
                        episode_id=episode_id,
                        content=episode_content,
                        source=source_description,
                        timestamp=datetime.now(timezone.utc),
                        metadata={
                            "document_title": document_title,
                            "document_source": document_source,
                            "chunk_index": chunk.index,
                            "chunk_start": chunk.start_char,
                            "chunk_end": chunk.end_char,
                            **(document_metadata or {}),
                            **chunk.metadata
                        }
                    )
                    
                    episodes_created += 1
                    logger.info(f"✓ Added episode {episode_id} to knowledge graph ({episodes_created}/{len(chunks)})")
                    
                except Exception as e:
                    error_msg = f"Failed to add chunk {chunk.index} to graph: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            # Longer delay between batches to avoid rate limits and reduce API pressure
            if i + batch_size < len(chunks):
                logger.info(f"Processed batch {(i//batch_size)+1}, waiting before next batch...")
                await asyncio.sleep(2.0)  # Increased delay
        
        result = {
            "episodes_created": episodes_created,
            "total_chunks": len(chunks),
            "errors": errors
        }
        
        logger.info(f"Graph building complete: {episodes_created} episodes created, {len(errors)} errors")
        return result
    
    def _prepare_episode_content(
        self,
        chunk: DocumentChunk,
        document_title: str,
        document_metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Prepare episode content with context for better entity extraction.
        
        Args:
            chunk: Document chunk
            document_title: Title of the document
            document_metadata: Additional metadata
        
        Returns:
            Formatted episode content
        """
        # Add context to help with entity extraction
        context_info = []
        
        if document_title:
            context_info.append(f"Document: {document_title}")
        
        # Add relevant metadata as context
        if document_metadata:
            if "date" in document_metadata:
                context_info.append(f"Date: {document_metadata['date']}")
            if "company" in document_metadata:
                context_info.append(f"Company: {document_metadata['company']}")
            if "topic" in document_metadata:
                context_info.append(f"Topic: {document_metadata['topic']}")
        
        # Extract key entities from chunk metadata
        if "entities" in chunk.metadata:
            entities_dict = chunk.metadata["entities"]
            if entities_dict and isinstance(entities_dict, dict):
                # Flatten all entity lists and take first 5
                all_entities = []
                for entity_type, entity_list in entities_dict.items():
                    if isinstance(entity_list, list):
                        all_entities.extend(entity_list)
                
                if all_entities:
                    context_info.append(f"Key entities: {', '.join(all_entities[:5])}")  # Limit to 5
        
        # Build episode content
        if context_info:
            context_str = " | ".join(context_info)
            episode_content = f"[Context: {context_str}]\n\n{chunk.content}"
        else:
            episode_content = chunk.content
        
        return episode_content
    
    async def extract_entities_from_chunks(
        self,
        chunks: List[DocumentChunk],
        extract_companies: bool = True,
        extract_technologies: bool = True,
        extract_people: bool = True
    ) -> List[DocumentChunk]:
        """
        Extract entities from chunks and add to metadata.
        
        Args:
            chunks: List of document chunks
            extract_companies: Whether to extract company names
            extract_technologies: Whether to extract technology terms
            extract_people: Whether to extract person names
        
        Returns:
            Chunks with entity metadata added
        """
        logger.info(f"Extracting entities from {len(chunks)} chunks")
        
        enriched_chunks = []
        
        for chunk in chunks:
            entities = {
                "companies": [],
                "technologies": [],
                "people": [],
                "locations": []
            }
            
            content = chunk.content
            
            # Extract companies
            if extract_companies:
                entities["companies"] = self._extract_companies(content)
            
            # Extract technologies
            if extract_technologies:
                entities["technologies"] = self._extract_technologies(content)
            
            # Extract people
            if extract_people:
                entities["people"] = self._extract_people(content)
            
            # Extract locations
            entities["locations"] = self._extract_locations(content)
            
            # Create enriched chunk
            enriched_chunk = DocumentChunk(
                content=chunk.content,
                index=chunk.index,
                start_char=chunk.start_char,
                end_char=chunk.end_char,
                metadata={
                    **chunk.metadata,
                    "entities": entities,
                    "entity_extraction_date": datetime.now().isoformat()
                },
                token_count=chunk.token_count
            )
            
            # Preserve embedding if it exists
            if hasattr(chunk, 'embedding'):
                enriched_chunk.embedding = chunk.embedding
            
            enriched_chunks.append(enriched_chunk)
        
        logger.info("Entity extraction complete")
        return enriched_chunks
    
    def _extract_companies(self, text: str) -> List[str]:
        """Extract company names from text."""
        # Known tech companies (extend this list as needed)
        tech_companies = {
            "Google", "Microsoft", "Apple", "Amazon", "Meta", "Facebook",
            "Tesla", "OpenAI", "Anthropic", "Nvidia", "Intel", "AMD",
            "IBM", "Oracle", "Salesforce", "Adobe", "Netflix", "Uber",
            "Airbnb", "Spotify", "Twitter", "LinkedIn", "Snapchat",
            "TikTok", "ByteDance", "Baidu", "Alibaba", "Tencent",
            "Samsung", "Sony", "Huawei", "Xiaomi", "DeepMind"
        }
        
        found_companies = set()
        text_lower = text.lower()
        
        for company in tech_companies:
            # Case-insensitive search with word boundaries
            pattern = r'\b' + re.escape(company.lower()) + r'\b'
            if re.search(pattern, text_lower):
                found_companies.add(company)
        
        return list(found_companies)
    
    def _extract_technologies(self, text: str) -> List[str]:
        """Extract technology terms from text."""
        tech_terms = {
            "AI", "artificial intelligence", "machine learning", "ML",
            "deep learning", "neural network", "LLM", "large language model",
            "GPT", "transformer", "NLP", "natural language processing",
            "computer vision", "reinforcement learning", "generative AI",
            "foundation model", "multimodal", "chatbot", "API",
            "cloud computing", "edge computing", "quantum computing",
            "blockchain", "cryptocurrency", "IoT", "5G", "AR", "VR",
            "autonomous vehicles", "robotics", "automation"
        }
        
        found_terms = set()
        text_lower = text.lower()
        
        for term in tech_terms:
            if term.lower() in text_lower:
                found_terms.add(term)
        
        return list(found_terms)
    
    def _extract_people(self, text: str) -> List[str]:
        """Extract person names from text."""
        # Known tech leaders (extend this list as needed)
        tech_leaders = {
            "Elon Musk", "Jeff Bezos", "Tim Cook", "Satya Nadella",
            "Sundar Pichai", "Mark Zuckerberg", "Sam Altman",
            "Dario Amodei", "Daniela Amodei", "Jensen Huang",
            "Bill Gates", "Larry Page", "Sergey Brin", "Jack Dorsey",
            "Reed Hastings", "Marc Benioff", "Andy Jassy"
        }
        
        found_people = set()
        
        for person in tech_leaders:
            if person in text:
                found_people.add(person)
        
        return list(found_people)
    
    def _extract_locations(self, text: str) -> List[str]:
        """Extract location names from text."""
        locations = {
            "Silicon Valley", "San Francisco", "Seattle", "Austin",
            "New York", "Boston", "London", "Tel Aviv", "Singapore",
            "Beijing", "Shanghai", "Tokyo", "Seoul", "Bangalore",
            "Mountain View", "Cupertino", "Redmond", "Menlo Park"
        }
        
        found_locations = set()
        
        for location in locations:
            if location in text:
                found_locations.add(location)
        
        return list(found_locations)
    
    async def clear_graph(self):
        """Clear all data from the knowledge graph."""
        if not self._initialized:
            await self.initialize()
        
        logger.warning("Clearing knowledge graph...")
        await self.graph_client.clear_graph()
        logger.info("Knowledge graph cleared")


class SimpleEntityExtractor:
    """Simple rule-based entity extractor as fallback."""
    
    def __init__(self):
        """Initialize extractor."""
        self.company_patterns = [
            r'\b(?:Google|Microsoft|Apple|Amazon|Meta|Facebook|Tesla|OpenAI)\b',
            r'\b\w+\s+(?:Inc|Corp|Corporation|Ltd|Limited|AG|SE)\b'
        ]
        
        self.tech_patterns = [
            r'\b(?:AI|artificial intelligence|machine learning|ML|deep learning)\b',
            r'\b(?:neural network|transformer|GPT|LLM|NLP)\b',
            r'\b(?:cloud computing|API|blockchain|IoT|5G)\b'
        ]
    
    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract entities using patterns."""
        entities = {
            "companies": [],
            "technologies": []
        }
        
        # Extract companies
        for pattern in self.company_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            entities["companies"].extend(matches)
        
        # Extract technologies
        for pattern in self.tech_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            entities["technologies"].extend(matches)
        
        # Remove duplicates and clean up
        entities["companies"] = list(set(entities["companies"]))
        entities["technologies"] = list(set(entities["technologies"]))
        
        return entities


# Factory function
def create_graph_builder() -> GraphBuilder:
    """Create graph builder instance."""
    return GraphBuilder()


# Example usage
async def main():
    """Example usage of the graph builder."""
    from .chunker import ChunkingConfig, create_chunker
    
    # Create chunker and graph builder
    config = ChunkingConfig(chunk_size=300, use_semantic_splitting=False)
    chunker = create_chunker(config)
    graph_builder = create_graph_builder()
    
    sample_text = """
    Google's DeepMind has made significant breakthroughs in artificial intelligence,
    particularly in areas like protein folding prediction with AlphaFold and
    game-playing AI with AlphaGo. The company continues to invest heavily in
    transformer architectures and large language models.
    
    Microsoft's partnership with OpenAI has positioned them as a leader in
    the generative AI space. Sam Altman's OpenAI has developed GPT models
    that Microsoft integrates into Office 365 and Azure cloud services.
    """
    
    # Chunk the document
    chunks = chunker.chunk_document(
        content=sample_text,
        title="AI Company Developments",
        source="example.md"
    )
    
    print(f"Created {len(chunks)} chunks")
    
    # Extract entities
    enriched_chunks = await graph_builder.extract_entities_from_chunks(chunks)
    
    for i, chunk in enumerate(enriched_chunks):
        print(f"Chunk {i}: {chunk.metadata.get('entities', {})}")
    
    # Add to knowledge graph
    try:
        result = await graph_builder.add_document_to_graph(
            chunks=enriched_chunks,
            document_title="AI Company Developments",
            document_source="example.md",
            document_metadata={"topic": "AI", "date": "2024"}
        )
        
        print(f"Graph building result: {result}")
        
    except Exception as e:
        print(f"Graph building failed: {e}")
    
    finally:
        await graph_builder.close()


if __name__ == "__main__":
    asyncio.run(main())