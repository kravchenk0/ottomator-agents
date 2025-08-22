"""
Intelligent caching system for chat responses.

Multi-level caching architecture:
1. Exact query cache (instant response)
2. Semantic similarity cache (fast response)
3. Context-aware caching (medium response)
"""

import json
import hashlib
import time
import asyncio
import os
from typing import Dict, List, Optional, Tuple, Any
from functools import lru_cache
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class CachedResponse:
    """Cached chat response with metadata."""
    response: str
    sources: List[str]
    timestamp: float
    query_hash: str
    embedding: Optional[List[float]] = None
    usage_count: int = 0
    conversation_context: str = ""


class SemanticCache:
    """Semantic similarity cache using TF-IDF vectors."""
    
    def __init__(self, similarity_threshold: float = 0.85):
        self.similarity_threshold = similarity_threshold
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words=['russian', 'english'] if hasattr(TfidfVectorizer, 'stop_words') else None,
            ngram_range=(1, 2)
        )
        self.query_vectors = []
        self.cached_responses = []
        self.is_fitted = False
        
    def _normalize_query(self, query: str) -> str:
        """Normalize query for better matching."""
        return query.lower().strip().replace('\n', ' ')
    
    async def add_to_cache(self, query: str, response: CachedResponse):
        """Add response to semantic cache."""
        normalized_query = self._normalize_query(query)
        
        # Update vectorizer and vectors
        all_queries = [normalized_query]
        if self.cached_responses:
            # Add existing queries for re-fitting
            existing_queries = [self._normalize_query(r.query_hash) for r in self.cached_responses[-100:]]  # Keep last 100
            all_queries.extend(existing_queries)
        
        # Fit vectorizer
        try:
            query_matrix = self.vectorizer.fit_transform(all_queries)
            self.query_vectors = query_matrix.toarray()
            self.is_fitted = True
            
            # Store response
            response.embedding = self.query_vectors[0].tolist()
            self.cached_responses.append(response)
            
            # Keep only last 500 responses to manage memory
            if len(self.cached_responses) > 500:
                self.cached_responses = self.cached_responses[-500:]
                self.query_vectors = self.query_vectors[-500:]
                
        except Exception as e:
            print(f"Error adding to semantic cache: {e}")
    
    async def find_similar(self, query: str) -> Optional[CachedResponse]:
        """Find semantically similar cached response."""
        if not self.is_fitted or not self.cached_responses:
            return None
            
        try:
            normalized_query = self._normalize_query(query)
            
            # Transform new query
            query_vector = self.vectorizer.transform([normalized_query]).toarray()
            
            # Calculate similarities
            similarities = cosine_similarity(query_vector, self.query_vectors)[0]
            
            # Find best match above threshold
            max_similarity = np.max(similarities)
            if max_similarity >= self.similarity_threshold:
                best_idx = np.argmax(similarities)
                cached_response = self.cached_responses[best_idx]
                cached_response.usage_count += 1
                return cached_response
                
        except Exception as e:
            print(f"Error finding similar response: {e}")
            
        return None


class IntelligentChatCache:
    """Multi-level intelligent caching system for chat responses."""
    
    def __init__(self, cache_dir: str = None):
        if cache_dir is None:
            # Use local cache directory, fallback to temp
            import tempfile
            cache_dir = os.getenv("RAG_CACHE_DIR", tempfile.gettempdir() + "/lightrag_cache")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True, parents=True)
        
        # Level 1: Exact query cache (LRU)
        self.exact_cache: Dict[str, CachedResponse] = {}
        self.max_exact_cache = 1000
        
        # Level 2: Semantic similarity cache
        self.semantic_cache = SemanticCache()
        
        # Level 3: Popular queries cache
        self.popular_cache: Dict[str, CachedResponse] = {}
        
        # Cache statistics
        self.stats = {
            "exact_hits": 0,
            "semantic_hits": 0,
            "misses": 0,
            "total_requests": 0
        }
        
        # Preload popular responses
        self._load_popular_cache()
    
    def _normalize_query(self, query: str) -> str:
        """Normalize query for consistent caching."""
        return query.lower().strip().replace('\n', ' ')
    
    def _get_query_hash(self, query: str, context: str = "") -> str:
        """Generate hash for query + context."""
        content = f"{self._normalize_query(query)}|{context}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    async def get_cached_response(self, query: str, context: str = "") -> Optional[CachedResponse]:
        """
        Get cached response using multi-level cache strategy.
        
        Args:
            query: User query
            context: Conversation context
            
        Returns:
            Cached response if found, None otherwise
        """
        self.stats["total_requests"] += 1
        query_hash = self._get_query_hash(query, context)
        
        # Level 1: Exact match cache (fastest)
        if query_hash in self.exact_cache:
            response = self.exact_cache[query_hash]
            response.usage_count += 1
            self.stats["exact_hits"] += 1
            return response
        
        # Level 2: Popular queries cache
        normalized = self._normalize_query(query)
        for pattern, response in self.popular_cache.items():
            if pattern in normalized or normalized in pattern:
                response.usage_count += 1
                self.stats["exact_hits"] += 1  # Count as exact for stats
                return response
        
        # Level 3: Semantic similarity cache (slower but smarter)
        if semantic_match := await self.semantic_cache.find_similar(query):
            self.stats["semantic_hits"] += 1
            return semantic_match
        
        # No cache hit
        self.stats["misses"] += 1
        return None
    
    async def cache_response(self, query: str, response: str, sources: List[str], context: str = ""):
        """
        Cache a new response in all appropriate cache levels.
        
        Args:
            query: Original user query
            response: Generated response
            sources: Source documents used
            context: Conversation context
        """
        query_hash = self._get_query_hash(query, context)
        
        cached_response = CachedResponse(
            response=response,
            sources=sources,
            timestamp=time.time(),
            query_hash=query_hash,
            conversation_context=context
        )
        
        # Add to exact cache
        self.exact_cache[query_hash] = cached_response
        
        # Manage exact cache size (LRU)
        if len(self.exact_cache) > self.max_exact_cache:
            # Remove oldest entry
            oldest_key = min(self.exact_cache.keys(), 
                           key=lambda k: self.exact_cache[k].timestamp)
            del self.exact_cache[oldest_key]
        
        # Add to semantic cache
        await self.semantic_cache.add_to_cache(query, cached_response)
        
        # Check if should add to popular cache
        await self._update_popular_cache(query, cached_response)
    
    async def _update_popular_cache(self, query: str, response: CachedResponse):
        """Update popular cache based on query frequency."""
        normalized = self._normalize_query(query)
        
        # Keywords that indicate popular queries
        popular_keywords = [
            "золотая виза", "golden visa", "инвестиционная виза",
            "бизнес лицензия", "фриз зона", "dubai", "дубай",
            "residence", "резидентство", "инвестиции"
        ]
        
        if any(keyword in normalized for keyword in popular_keywords):
            # Extract key phrase for popular cache
            for keyword in popular_keywords:
                if keyword in normalized:
                    self.popular_cache[keyword] = response
                    break
    
    def _load_popular_cache(self):
        """Load pre-defined popular responses."""
        self.popular_cache = {
            "золотая виза": CachedResponse(
                response="Золотая виза ОАЭ — это долгосрочная резидентская виза сроком до 10 лет...",
                sources=["golden_visa_overview.md"],
                timestamp=time.time(),
                query_hash="popular_golden_visa",
                usage_count=0
            ),
            "инвестиционная виза": CachedResponse(
                response="Инвестиционная виза в ОАЭ предоставляется инвесторам при инвестициях от 2 млн дирхамов...",
                sources=["investment_visa.md"],
                timestamp=time.time(),
                query_hash="popular_investment_visa",
                usage_count=0
            )
        }
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        total = self.stats["total_requests"]
        if total == 0:
            return self.stats
            
        hit_rate = (self.stats["exact_hits"] + self.stats["semantic_hits"]) / total * 100
        
        return {
            **self.stats,
            "hit_rate_percent": round(hit_rate, 2),
            "exact_cache_size": len(self.exact_cache),
            "semantic_cache_size": len(self.semantic_cache.cached_responses),
            "popular_cache_size": len(self.popular_cache)
        }
    
    async def clear_cache(self):
        """Clear all cache levels."""
        self.exact_cache.clear()
        self.semantic_cache.cached_responses.clear()
        self.semantic_cache.query_vectors = []
        self.semantic_cache.is_fitted = False
        
        # Reset stats
        self.stats = {key: 0 for key in self.stats}
    
    async def preload_common_queries(self, queries_and_responses: List[Tuple[str, str, List[str]]]):
        """Preload common queries into cache."""
        for query, response, sources in queries_and_responses:
            await self.cache_response(query, response, sources)


# Global cache instance
_global_cache: Optional[IntelligentChatCache] = None


def get_chat_cache() -> IntelligentChatCache:
    """Get global chat cache instance."""
    global _global_cache
    if _global_cache is None:
        _global_cache = IntelligentChatCache()
    return _global_cache


async def warm_up_cache():
    """Warm up cache with common queries."""
    cache = get_chat_cache()
    
    common_queries = [
        (
            "что такое золотая виза?",
            "Золотая виза ОАЭ — это долгосрочная резидентская виза, которая предоставляется на срок до 10 лет определенным категориям лиц, включая инвесторов, предпринимателей, специалистов высокой квалификации и талантливых личностей.",
            ["golden_visa_overview.md"]
        ),
        (
            "требования для золотой визы",
            "Требования зависят от категории: для инвесторов — инвестиции от 2 млн дирхамов, для предпринимателей — проект стоимостью от 500 тыс. дирхамов, для специалистов — высшее образование и опыт работы.",
            ["golden_visa_requirements.md"]
        )
    ]
    
    await cache.preload_common_queries(common_queries)