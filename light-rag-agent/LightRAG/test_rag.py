"""Basic tests for LightRAG implementation."""

import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from common import RAGManager, RAGConfig, validate_file_path, sanitize_filename
from rag_agent import run_rag_agent, RAGDeps
from logger import setup_logger, PerformanceLogger

# Set up test logging
logger = setup_logger("test", "DEBUG")

class TestRAGConfig:
    """Test RAG configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = RAGConfig()
        assert config.working_dir == "./pydantic-docs"
        assert config.rerank_enabled is True
        assert config.batch_size == 20
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = RAGConfig(
            working_dir="/custom/path",
            rerank_enabled=False,
            batch_size=50
        )
        assert config.working_dir == "/custom/path"
        assert config.rerank_enabled is False
        assert config.batch_size == 50

class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_validate_file_path_valid(self, tmp_path):
        """Test file path validation with valid path."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        assert validate_file_path(str(test_file)) is True
    
    def test_validate_file_path_invalid(self):
        """Test file path validation with invalid path."""
        assert validate_file_path("/nonexistent/file.txt") is False
    
    def test_sanitize_filename(self):
        """Test filename sanitization."""
        unsafe_name = 'file<>:"/\\|?*.txt'
        safe_name = sanitize_filename(unsafe_name)
        assert '<' not in safe_name
        assert '>' not in safe_name
        assert ':' not in safe_name
        assert '"' not in safe_name
        assert '/' not in safe_name
        assert '\\' not in safe_name
        assert '|' not in safe_name
        assert '?' not in safe_name
        assert '*' not in safe_name

class TestRAGManager:
    """Test RAG manager."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def mock_config(self, temp_dir):
        """Create mock configuration."""
        return RAGConfig(working_dir=temp_dir)
    
    @pytest.mark.asyncio
    async def test_initialization(self, mock_config, temp_dir):
        """Test RAG manager initialization."""
        with patch('common.LightRAG') as mock_lightrag:
            mock_instance = Mock()
            mock_lightrag.return_value = mock_instance
            mock_instance.initialize_storages = AsyncMock()
            
            manager = RAGManager(mock_config)
            await manager.initialize()
            
            # Check if working directory was created
            assert Path(temp_dir).exists()
            mock_instance.initialize_storages.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_rag_initialized(self, mock_config):
        """Test getting RAG instance when already initialized."""
        with patch('common.LightRAG') as mock_lightrag:
            mock_instance = Mock()
            mock_lightrag.return_value = mock_instance
            mock_instance.initialize_storages = AsyncMock()
            
            manager = RAGManager(mock_config)
            await manager.initialize()
            
            # Get RAG instance again
            rag = await manager.get_rag()
            assert rag == mock_instance

class TestPerformanceLogger:
    """Test performance logger."""
    
    def test_timer_operations(self):
        """Test timer start/end operations."""
        logger = setup_logger("test_perf", "INFO")
        perf_logger = PerformanceLogger(logger)
        
        perf_logger.start_timer("test_op")
        perf_logger.end_timer("test_op")
        
        summary = perf_logger.get_summary()
        assert "test_op" in summary
        assert summary["test_op"] > 0
    
    def test_metrics_logging(self):
        """Test metrics logging."""
        logger = setup_logger("test_metrics", "INFO")
        perf_logger = PerformanceLogger(logger)
        
        perf_logger.log_metric("test_metric", 42.5, "units")
        # This test mainly checks that no exceptions are raised

class TestRAGAgent:
    """Test RAG agent functionality."""
    
    @pytest.mark.asyncio
    async def test_run_rag_agent_success(self):
        """Test successful RAG agent execution."""
        with patch('rag_agent.RAGManager') as mock_manager_class:
            mock_manager = Mock()
            mock_manager_class.return_value = mock_manager
            
            mock_agent = Mock()
            mock_agent.run = AsyncMock()
            mock_agent.run.return_value.data = "Test response"
            
            # Mock the agent import
            with patch('rag_agent.agent', mock_agent):
                response = await run_rag_agent("Test question")
                assert response == "Test response"
    
    @pytest.mark.asyncio
    async def test_run_rag_agent_error(self):
        """Test RAG agent execution with error."""
        with patch('rag_agent.RAGManager') as mock_manager_class:
            mock_manager_class.side_effect = Exception("Test error")
            
            response = await run_rag_agent("Test question")
            assert "Error running RAG agent" in response

def run_tests():
    """Run all tests."""
    logger.info("Starting tests...")
    
    # Run pytest
    pytest.main([__file__, "-v"])

if __name__ == "__main__":
    run_tests() 