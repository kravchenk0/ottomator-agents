"""Examples of using the improved LightRAG implementation."""

import asyncio
import os
from pathlib import Path
from typing import List

from common import RAGManager, RAGConfig, validate_file_path
from rag_agent import run_rag_agent
from logger import setup_logger, performance_logger
from config import create_sample_config

# Set up logging
logger = setup_logger("examples", "INFO")

async def example_basic_usage():
    """Basic usage example."""
    logger.info("=== Basic Usage Example ===")
    
    # Create configuration
    config = RAGConfig(
        working_dir="./example-docs",
        rerank_enabled=True,
        batch_size=10
    )
    
    # Initialize RAG manager
    rag_manager = RAGManager(config)
    
    # Insert some sample documents
    sample_docs = [
        "Python is a high-level programming language known for its simplicity and readability.",
        "Machine learning is a subset of artificial intelligence that focuses on algorithms.",
        "Data science combines statistics, programming, and domain expertise to extract insights.",
        "Natural language processing enables computers to understand and generate human language."
    ]
    
    try:
        rag = await rag_manager.initialize()
        
        for i, doc in enumerate(sample_docs):
            await rag.ainsert(doc)
            logger.info(f"Inserted document {i+1}")
        
        # Query the system
        query = "What is Python?"
        logger.info(f"Querying: {query}")
        
        response = await rag.aquery(query, param={"mode": "mix"})
        logger.info(f"Response: {response}")
        
    except Exception as e:
        logger.error(f"Error in basic example: {e}")

async def example_agent_usage():
    """Example using the RAG agent."""
    logger.info("=== Agent Usage Example ===")
    
    try:
        # Run the agent with a question
        question = "Explain machine learning in simple terms"
        logger.info(f"Asking agent: {question}")
        
        response = await run_rag_agent(question)
        logger.info(f"Agent response: {response}")
        
    except Exception as e:
        logger.error(f"Error in agent example: {e}")

async def example_file_processing():
    """Example of processing files from a directory."""
    logger.info("=== File Processing Example ===")
    
    # Create sample files
    sample_dir = Path("./sample-docs")
    sample_dir.mkdir(exist_ok=True)
    
    sample_files = {
        "python.txt": "Python is a versatile programming language used in web development, data science, and AI.",
        "ml.txt": "Machine learning algorithms learn patterns from data to make predictions.",
        "nlp.txt": "Natural language processing helps computers understand human language."
    }
    
    try:
        # Create sample files
        for filename, content in sample_files.items():
            file_path = sample_dir / filename
            file_path.write_text(content)
            logger.info(f"Created sample file: {filename}")
        
        # Process files
        config = RAGConfig(working_dir="./processed-docs")
        rag_manager = RAGManager(config)
        rag = await rag_manager.initialize()
        
        # Insert each file
        for filename in sample_files.keys():
            file_path = sample_dir / filename
            if validate_file_path(str(file_path)):
                content = file_path.read_text()
                await rag.ainsert(content)
                logger.info(f"Processed file: {filename}")
        
        # Query the processed documents
        query = "What are the main applications of Python?"
        response = await rag.aquery(query)
        logger.info(f"Query response: {response}")
        
    except Exception as e:
        logger.error(f"Error in file processing example: {e}")
    finally:
        # Cleanup
        if sample_dir.exists():
            import shutil
            shutil.rmtree(sample_dir)

async def example_performance_monitoring():
    """Example of performance monitoring."""
    logger.info("=== Performance Monitoring Example ===")
    
    try:
        # Start monitoring
        performance_logger.start_timer("example_operation")
        
        # Simulate some work
        await asyncio.sleep(1)
        
        # Log metrics
        performance_logger.log_metric("documents_processed", 100, "docs")
        performance_logger.log_metric("processing_time", 2.5, "seconds")
        
        # End monitoring
        performance_logger.end_timer("example_operation")
        
        # Get summary
        summary = performance_logger.get_summary()
        logger.info(f"Performance summary: {summary}")
        
    except Exception as e:
        logger.error(f"Error in performance monitoring example: {e}")

async def example_configuration_management():
    """Example of configuration management."""
    logger.info("=== Configuration Management Example ===")
    
    try:
        # Create sample configuration
        config_file = "example-config.yaml"
        create_sample_config(config_file)
        
        # Load configuration
        from config import Config
        config = Config(config_file)
        
        # Validate configuration
        if config.validate():
            logger.info("Configuration is valid")
            logger.info(f"Working directory: {config.rag.working_dir}")
            logger.info(f"Rerank enabled: {config.rag.rerank_enabled}")
        else:
            logger.error("Configuration validation failed")
        
        # Cleanup
        if Path(config_file).exists():
            Path(config_file).unlink()
            
    except Exception as e:
        logger.error(f"Error in configuration management example: {e}")

async def example_error_handling():
    """Example of error handling."""
    logger.info("=== Error Handling Example ===")
    
    try:
        # Try to use invalid configuration
        invalid_config = RAGConfig(working_dir="/nonexistent/path")
        rag_manager = RAGManager(invalid_config)
        
        # This should fail gracefully
        await rag_manager.initialize()
        
    except Exception as e:
        logger.info(f"Expected error caught: {e}")
        logger.info("Error handling is working correctly")

def run_all_examples():
    """Run all examples."""
    logger.info("Starting all examples...")
    
    async def main():
        examples = [
            example_basic_usage,
            example_agent_usage,
            example_file_processing,
            example_performance_monitoring,
            example_configuration_management,
            example_error_handling
        ]
        
        for example in examples:
            try:
                await example()
                logger.info(f"Completed: {example.__name__}")
            except Exception as e:
                logger.error(f"Failed: {example.__name__} - {e}")
            
            # Add some separation between examples
            await asyncio.sleep(1)
    
    # Run examples
    asyncio.run(main())
    logger.info("All examples completed!")

if __name__ == "__main__":
    run_all_examples() 