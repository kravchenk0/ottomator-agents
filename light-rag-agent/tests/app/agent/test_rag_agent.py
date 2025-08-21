"""
Unit tests for RAG agent functionality.
"""
import pytest
from unittest.mock import AsyncMock, patch
from app.agent.rag_agent import (
    create_agent,
    resolve_agent_model,
    _get_cache_key,
    _get_cached_result,
    _cache_result,
    RAG_CACHE_TTL
)


class TestAgentCreation:
    """Tests for agent creation and caching."""
    
    def test_resolve_agent_model_default(self):
        """
        Test default model resolution.
        
        Expected behavior: Returns default model with openai: prefix.
        """
        model = resolve_agent_model()
        assert model.startswith("openai:")
        assert "gpt" in model or "mini" in model
    
    def test_resolve_agent_model_explicit(self):
        """
        Test explicit model resolution.
        
        Expected behavior: Adds openai: prefix to model name.
        """
        model = resolve_agent_model("gpt-4")
        assert model == "openai:gpt-4"
    
    def test_resolve_agent_model_with_prefix(self):
        """
        Test model resolution with existing prefix.
        
        Expected behavior: Does not add duplicate prefix.
        """
        model = resolve_agent_model("openai:gpt-4")
        assert model == "openai:gpt-4"
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test_key'})
    def test_create_agent_caching(self):
        """
        Test agent creation uses LRU cache.
        
        Expected behavior: Same parameters return same agent instance.
        """
        agent1 = create_agent("gpt-4", "test prompt")
        agent2 = create_agent("gpt-4", "test prompt")
        assert agent1 is agent2  # Same object due to caching
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test_key'})
    def test_create_agent_different_params(self):
        """
        Test agent creation with different parameters.
        
        Expected behavior: Different parameters create different agents.
        """
        agent1 = create_agent("gpt-4", "prompt1")
        agent2 = create_agent("gpt-4", "prompt2")
        assert agent1 is not agent2  # Different objects


class TestRAGCaching:
    """Tests for RAG result caching."""
    
    def test_get_cache_key_consistent(self):
        """
        Test cache key generation is consistent.
        
        Expected behavior: Same query produces same cache key.
        """
        query = "test query"
        key1 = _get_cache_key(query)
        key2 = _get_cache_key(query)
        assert key1 == key2
        assert len(key1) == 32  # MD5 hash length
    
    def test_get_cache_key_different_queries(self):
        """
        Test different queries produce different cache keys.
        
        Expected behavior: Different queries have different cache keys.
        """
        key1 = _get_cache_key("query1")
        key2 = _get_cache_key("query2")
        assert key1 != key2
    
    def test_cache_result_and_retrieve(self):
        """
        Test caching and retrieving results.
        
        Expected behavior: Cached result can be retrieved.
        """
        query = "test cache query"
        result = "test cache result"
        
        # Cache the result
        _cache_result(query, result)
        
        # Retrieve from cache
        cached = _get_cached_result(query)
        assert cached == result
    
    def test_cache_miss(self):
        """
        Test cache miss scenario.
        
        Expected behavior: Returns None for uncached query.
        """
        cached = _get_cached_result("uncached_query_12345")
        assert cached is None
    
    @patch('time.time')
    def test_cache_expiration(self, mock_time):
        """
        Test cache expiration functionality.
        
        Expected behavior: Expired cache entries return None.
        """
        # Setup: Cache a result
        mock_time.return_value = 1000
        query = "expiry_test_query"
        result = "expiry_test_result"
        _cache_result(query, result)
        
        # Test: Check result is cached
        cached = _get_cached_result(query)
        assert cached == result
        
        # Test: Fast forward time beyond TTL
        mock_time.return_value = 1000 + RAG_CACHE_TTL + 1
        cached_expired = _get_cached_result(query)
        assert cached_expired is None