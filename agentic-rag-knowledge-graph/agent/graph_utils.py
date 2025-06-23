"""
Graph utilities for Neo4j/Graphiti integration.
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from contextlib import asynccontextmanager
import asyncio

from graphiti_core import Graphiti
from neo4j import AsyncGraphDatabase, AsyncDriver
from neo4j.exceptions import Neo4jError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class GraphitiClient:
    """Manages Graphiti knowledge graph operations."""
    
    def __init__(
        self,
        neo4j_uri: Optional[str] = None,
        neo4j_user: Optional[str] = None,
        neo4j_password: Optional[str] = None
    ):
        """
        Initialize Graphiti client.
        
        Args:
            neo4j_uri: Neo4j connection URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
        """
        self.neo4j_uri = neo4j_uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = neo4j_user or os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password = neo4j_password or os.getenv("NEO4J_PASSWORD")
        
        if not self.neo4j_password:
            raise ValueError("NEO4J_PASSWORD environment variable not set")
        
        self.graphiti: Optional[Graphiti] = None
        self.driver: Optional[AsyncDriver] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize Graphiti and Neo4j driver."""
        if self._initialized:
            return
        
        try:
            # Initialize Neo4j driver
            self.driver = AsyncGraphDatabase.driver(
                self.neo4j_uri,
                auth=(self.neo4j_user, self.neo4j_password)
            )
            
            # Verify connection
            await self.driver.verify_connectivity()
            
            # Initialize Graphiti
            self.graphiti = Graphiti(
                neo4j_uri=self.neo4j_uri,
                neo4j_user=self.neo4j_user,
                neo4j_password=self.neo4j_password
            )
            
            await self.graphiti.build_indices()
            
            self._initialized = True
            logger.info("Graphiti client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Graphiti: {e}")
            raise
    
    async def close(self):
        """Close Neo4j driver connection."""
        if self.driver:
            await self.driver.close()
            self.driver = None
            self._initialized = False
            logger.info("Graphiti client closed")
    
    async def add_episode(
        self,
        episode_id: str,
        content: str,
        source: str,
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Add an episode to the knowledge graph.
        
        Args:
            episode_id: Unique episode identifier
            content: Episode content
            source: Source of the content
            timestamp: Episode timestamp
            metadata: Additional metadata
        """
        if not self._initialized:
            await self.initialize()
        
        episode_timestamp = timestamp or datetime.now(timezone.utc)
        
        await self.graphiti.add_episode(
            name=episode_id,
            episode_body=content,
            source_description=source,
            created_at=episode_timestamp,
            metadata=metadata or {}
        )
        
        logger.info(f"Added episode {episode_id} to knowledge graph")
    
    async def search(
        self,
        query: str,
        limit: int = 10,
        center_node_distance: int = 2,
        use_hybrid_search: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Search the knowledge graph.
        
        Args:
            query: Search query
            limit: Maximum number of results
            center_node_distance: Distance from center nodes
            use_hybrid_search: Whether to use hybrid search
        
        Returns:
            Search results
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            results = await self.graphiti.search(
                query=query,
                num_results=limit,
                center_node_distance=center_node_distance,
                use_hybrid_search=use_hybrid_search
            )
            
            # Convert results to dictionaries
            return [
                {
                    "fact": result.fact,
                    "episodes": [ep.model_dump() for ep in result.episodes],
                    "created_at": result.created_at.isoformat() if result.created_at else None,
                    "expired_at": result.expired_at.isoformat() if result.expired_at else None,
                    "valid_at": result.valid_at.isoformat() if result.valid_at else None,
                    "uuid": str(result.uuid)
                }
                for result in results
            ]
            
        except Exception as e:
            logger.error(f"Graph search failed: {e}")
            return []
    
    async def get_related_entities(
        self,
        entity_name: str,
        relationship_types: Optional[List[str]] = None,
        depth: int = 1
    ) -> Dict[str, Any]:
        """
        Get entities related to a given entity.
        
        Args:
            entity_name: Name of the entity
            relationship_types: Types of relationships to follow
            depth: Maximum depth to traverse
        
        Returns:
            Related entities and relationships
        """
        if not self._initialized:
            await self.initialize()
        
        async with self.driver.session() as session:
            # Build the Cypher query
            if relationship_types:
                rel_filter = f"[r:{' | '.join(relationship_types)}]"
            else:
                rel_filter = "[r]"
            
            query = f"""
            MATCH path = (start:Entity {{name: $entity_name}})-{rel_filter}*1..{depth}-(end:Entity)
            RETURN 
                start.name AS start_entity,
                [rel in relationships(path) | type(rel)] AS relationships,
                [node in nodes(path) | node.name] AS entities,
                end.name AS end_entity
            LIMIT 50
            """
            
            result = await session.run(query, entity_name=entity_name)
            records = await result.data()
            
            # Process results
            related_entities = set()
            relationships = []
            
            for record in records:
                path_entities = record["entities"]
                path_relationships = record["relationships"]
                
                # Add entities
                related_entities.update(path_entities)
                
                # Add relationships
                for i in range(len(path_relationships)):
                    relationships.append({
                        "from": path_entities[i],
                        "to": path_entities[i + 1],
                        "type": path_relationships[i]
                    })
            
            return {
                "central_entity": entity_name,
                "related_entities": list(related_entities),
                "relationships": relationships,
                "depth": depth
            }
    
    async def get_entity_timeline(
        self,
        entity_name: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get timeline of facts for an entity.
        
        Args:
            entity_name: Name of the entity
            start_date: Start of time range
            end_date: End of time range
        
        Returns:
            Timeline of facts
        """
        if not self._initialized:
            await self.initialize()
        
        async with self.driver.session() as session:
            query = """
            MATCH (e:Entity {name: $entity_name})-[r]-(fact:Fact)
            WHERE ($start_date IS NULL OR fact.created_at >= $start_date)
            AND ($end_date IS NULL OR fact.created_at <= $end_date)
            RETURN 
                fact.content AS content,
                fact.created_at AS created_at,
                fact.valid_at AS valid_at,
                type(r) AS relationship_type
            ORDER BY fact.created_at DESC
            """
            
            result = await session.run(
                query,
                entity_name=entity_name,
                start_date=start_date.isoformat() if start_date else None,
                end_date=end_date.isoformat() if end_date else None
            )
            records = await result.data()
            
            return [
                {
                    "content": record["content"],
                    "created_at": record["created_at"],
                    "valid_at": record["valid_at"],
                    "relationship_type": record["relationship_type"]
                }
                for record in records
            ]
    
    async def get_graph_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the knowledge graph.
        
        Returns:
            Graph statistics
        """
        if not self._initialized:
            await self.initialize()
        
        async with self.driver.session() as session:
            # Get node counts
            node_stats = await session.run("""
                MATCH (n)
                RETURN labels(n)[0] AS label, count(n) AS count
                ORDER BY count DESC
            """)
            node_data = await node_stats.data()
            
            # Get relationship counts
            rel_stats = await session.run("""
                MATCH ()-[r]->()
                RETURN type(r) AS type, count(r) AS count
                ORDER BY count DESC
            """)
            rel_data = await rel_stats.data()
            
            # Get total counts
            total_nodes = await session.run("MATCH (n) RETURN count(n) AS count")
            total_node_count = (await total_nodes.single())["count"]
            
            total_rels = await session.run("MATCH ()-[r]->() RETURN count(r) AS count")
            total_rel_count = (await total_rels.single())["count"]
            
            return {
                "total_nodes": total_node_count,
                "total_relationships": total_rel_count,
                "node_types": {item["label"]: item["count"] for item in node_data},
                "relationship_types": {item["type"]: item["count"] for item in rel_data}
            }
    
    async def clear_graph(self):
        """Clear all data from the graph (USE WITH CAUTION)."""
        if not self._initialized:
            await self.initialize()
        
        async with self.driver.session() as session:
            # Delete all relationships first
            await session.run("MATCH ()-[r]->() DELETE r")
            
            # Then delete all nodes
            await session.run("MATCH (n) DELETE n")
            
        logger.warning("Cleared all data from knowledge graph")


# Global Graphiti client instance
graph_client = GraphitiClient()


async def initialize_graph():
    """Initialize graph client."""
    await graph_client.initialize()


async def close_graph():
    """Close graph client."""
    await graph_client.close()


# Convenience functions for common operations
async def add_to_knowledge_graph(
    content: str,
    source: str,
    episode_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    Add content to the knowledge graph.
    
    Args:
        content: Content to add
        source: Source of the content
        episode_id: Optional episode ID
        metadata: Optional metadata
    
    Returns:
        Episode ID
    """
    if not episode_id:
        episode_id = f"episode_{datetime.now(timezone.utc).isoformat()}"
    
    await graph_client.add_episode(
        episode_id=episode_id,
        content=content,
        source=source,
        metadata=metadata
    )
    
    return episode_id


async def search_knowledge_graph(
    query: str,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Search the knowledge graph.
    
    Args:
        query: Search query
        limit: Maximum number of results
    
    Returns:
        Search results
    """
    return await graph_client.search(query, limit=limit)


async def get_entity_relationships(
    entity: str,
    depth: int = 2
) -> Dict[str, Any]:
    """
    Get relationships for an entity.
    
    Args:
        entity: Entity name
        depth: Maximum traversal depth
    
    Returns:
        Entity relationships
    """
    return await graph_client.get_related_entities(entity, depth=depth)


async def test_graph_connection() -> bool:
    """
    Test graph database connection.
    
    Returns:
        True if connection successful
    """
    try:
        await graph_client.initialize()
        stats = await graph_client.get_graph_statistics()
        logger.info(f"Graph connection successful. Stats: {stats}")
        return True
    except Exception as e:
        logger.error(f"Graph connection test failed: {e}")
        return False