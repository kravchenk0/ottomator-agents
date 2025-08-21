"""
Unit tests for RAG core functionality.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path

from app.core.rag import RAGManager, dynamic_openai_complete, get_temperature_adjustment_state
from app.core.config import RAGConfig


class TestRAGManager:
    """Tests for RAG manager functionality."""
    
    def test_rag_manager_init_with_valid_config(self):
        """
        Test RAG manager initialization with valid config.
        
        Expected behavior: Creates manager with specified working directory.
        """
        config = RAGConfig(working_dir="/tmp/test_rag")
        manager = RAGManager(config)
        assert manager.config == config
        assert manager._rag is None
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': ''})
    @patch.dict('os.environ', {'ALLOW_START_WITHOUT_OPENAI_KEY': '0'})
    def test_rag_manager_init_no_api_key_strict(self):
        """
        Test RAG manager initialization without API key in strict mode.
        
        Expected behavior: Raises ValueError when API key missing.
        """
        config = RAGConfig(working_dir="/tmp/test_rag")
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            RAGManager(config)
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': ''})
    @patch.dict('os.environ', {'ALLOW_START_WITHOUT_OPENAI_KEY': '1'})
    def test_rag_manager_init_no_api_key_permissive(self):
        """
        Test RAG manager initialization without API key in permissive mode.
        
        Expected behavior: Creates manager in degraded mode.
        """
        config = RAGConfig(working_dir="/tmp/test_rag")
        manager = RAGManager(config)  # Should not raise
        assert manager.config == config
    
    @patch('app.core.rag.LightRAG')
    @patch('app.core.rag.initialize_pipeline_status')
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test_key'})
    async def test_rag_manager_initialize(self, mock_pipeline, mock_lightrag):
        """
        Test RAG manager initialization process.
        
        Expected behavior: Initializes LightRAG and pipeline status.
        """
        # Setup mocks
        mock_rag_instance = AsyncMock()
        mock_lightrag.return_value = mock_rag_instance
        
        config = RAGConfig(working_dir="/tmp/test_rag")
        manager = RAGManager(config)
        
        # Test initialization
        result = await manager.initialize()
        
        assert result == mock_rag_instance
        assert manager._rag == mock_rag_instance
        mock_rag_instance.initialize_storages.assert_called_once()
        mock_pipeline.assert_called_once()
    
    @patch('app.core.rag.LightRAG')
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test_key'})
    async def test_rag_manager_get_rag_already_initialized(self, mock_lightrag):
        """
        Test getting RAG instance when already initialized.
        
        Expected behavior: Returns existing instance without re-initialization.
        """
        mock_rag_instance = AsyncMock()
        
        config = RAGConfig(working_dir="/tmp/test_rag")
        manager = RAGManager(config)
        manager._rag = mock_rag_instance  # Pre-initialize
        
        result = await manager.get_rag()
        
        assert result == mock_rag_instance
        mock_lightrag.assert_not_called()  # Should not create new instance


class TestDynamicOpenAIComplete:
    """Tests for dynamic OpenAI completion functionality."""
    
    @patch('app.core.rag.AsyncOpenAI')
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test_key'})
    async def test_dynamic_openai_complete_success(self, mock_openai_class):
        """
        Test successful OpenAI completion.
        
        Expected behavior: Returns completion content.
        """
        # Setup mock
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test completion response"
        mock_client.chat.completions.create.return_value = mock_response
        
        # Test
        result = await dynamic_openai_complete("test prompt")
        
        assert result == "Test completion response"
        mock_client.chat.completions.create.assert_called_once()
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': ''})
    async def test_dynamic_openai_complete_no_api_key(self):
        """
        Test OpenAI completion without API key.
        
        Expected behavior: Raises ValueError about missing API key.
        """
        with pytest.raises(ValueError, match="OPENAI_API_KEY is required"):
            await dynamic_openai_complete("test prompt")
    
    @patch('app.core.rag.AsyncOpenAI')
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test_key'})
    async def test_dynamic_openai_complete_empty_response(self, mock_openai_class):
        """
        Test OpenAI completion with empty response.
        
        Expected behavior: Raises RuntimeError for empty content.
        """
        # Setup mock for empty response
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = ""
        mock_client.chat.completions.create.return_value = mock_response
        
        # Test
        with pytest.raises(RuntimeError, match="Empty response content"):
            await dynamic_openai_complete("test prompt")


class TestTemperatureAdjustment:
    """Tests for temperature adjustment state."""
    
    def test_get_temperature_adjustment_state_initial(self):
        """
        Test initial temperature adjustment state.
        
        Expected behavior: Returns default state values.
        """
        state = get_temperature_adjustment_state()
        
        assert isinstance(state, dict)
        assert "auto_adjusted" in state
        assert "rejected_models" in state
        assert "current_temperature" in state
        assert isinstance(state["rejected_models"], list)