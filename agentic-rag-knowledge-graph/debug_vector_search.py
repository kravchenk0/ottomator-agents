#!/usr/bin/env python3
"""
Debug script to test vector search issues.
"""

import asyncio
import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

async def debug_vector_search():
    """Debug vector search to identify the issue."""
    try:
        # Import required modules
        from agent.db_utils import initialize_database, close_database, db_pool
        from agent.tools import generate_embedding, vector_search_tool, VectorSearchInput
        
        # Initialize database
        await initialize_database()
        
        # Check database connection and data
        async with db_pool.acquire() as conn:
            # Check total documents and chunks
            doc_count = await conn.fetchval("SELECT COUNT(*) FROM documents")
            chunk_count = await conn.fetchval("SELECT COUNT(*) FROM chunks")
            chunk_with_embedding_count = await conn.fetchval("SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL")
            
            print(f"Database statistics:")
            print(f"  Documents: {doc_count}")
            print(f"  Total chunks: {chunk_count}")
            print(f"  Chunks with embeddings: {chunk_with_embedding_count}")
            
            if chunk_with_embedding_count > 0:
                # Get a sample chunk to inspect embedding format
                sample_chunk = await conn.fetchrow(
                    "SELECT id, content, embedding FROM chunks WHERE embedding IS NOT NULL LIMIT 1"
                )
                
                if sample_chunk:
                    print(f"\nSample chunk:")
                    print(f"  ID: {sample_chunk['id']}")
                    print(f"  Content preview: {sample_chunk['content'][:100]}...")
                    print(f"  Embedding type: {type(sample_chunk['embedding'])}")
                    print(f"  Embedding preview: {str(sample_chunk['embedding'])[:200]}...")
                    
                    # Test if the embedding can be used in vector operations
                    try:
                        test_result = await conn.fetchval(
                            "SELECT 1 - (embedding <=> embedding) as self_similarity FROM chunks WHERE id = $1",
                            sample_chunk['id']
                        )
                        print(f"  Self-similarity test: {test_result}")
                    except Exception as e:
                        print(f"  ERROR in self-similarity test: {e}")
        
        # Test embedding generation
        print(f"\nTesting embedding generation...")
        test_query = "Google main AI initiatives"
        try:
            embedding = await generate_embedding(test_query)
            print(f"  Generated embedding for '{test_query}'")
            print(f"  Embedding type: {type(embedding)}")
            print(f"  Embedding dimensions: {len(embedding)}")
            print(f"  First 5 values: {embedding[:5]}")
        except Exception as e:
            print(f"  ERROR generating embedding: {e}")
            return
        
        # Test vector search tool
        print(f"\nTesting vector search...")
        
        # First test the embedding format conversion
        print(f"Testing embedding format conversion...")
        embedding_str = '[' + ','.join(map(str, embedding)) + ']'
        print(f"  Converted embedding format: {embedding_str[:100]}...")
        print(f"  Format matches stored data pattern: {embedding_str.startswith('[') and ',' in embedding_str and embedding_str.endswith(']')}")
        
        # Test direct database query with correct format (no threshold!)
        print(f"\nTesting direct database query WITHOUT threshold...")
        try:
            async with db_pool.acquire() as conn:
                # Test raw similarity calculation
                print("  Testing raw similarity calculation...")
                raw_similarity = await conn.fetchval(
                    "SELECT 1 - (embedding <=> $1::vector) as similarity FROM chunks WHERE embedding IS NOT NULL LIMIT 1",
                    embedding_str
                )
                print(f"    Raw similarity to first chunk: {raw_similarity}")
                
                # Test new match_chunks function (no threshold!)
                print("  Testing new match_chunks function (no threshold)...")
                direct_results = await conn.fetch(
                    "SELECT * FROM match_chunks($1::vector, $2)",
                    embedding_str,
                    5
                )
                print(f"  Direct database query returned {len(direct_results)} results")
                
                if direct_results:
                    print(f"  SUCCESS! Got results:")
                    for i, result in enumerate(direct_results[:3]):
                        print(f"    Result {i+1}: similarity={result['similarity']:.6f}, content={result['content'][:50]}...")
                else:
                    print(f"  Still no results - there's another issue")
                        
        except Exception as e:
            print(f"  ERROR in direct database query: {e}")
            import traceback
            traceback.print_exc()
        
        try:
            input_data = VectorSearchInput(
                query=test_query,
                limit=5
            )
            
            results = await vector_search_tool(input_data)
            print(f"  Vector search returned {len(results)} results")
            
            if results:
                for i, result in enumerate(results[:2]):
                    print(f"  Result {i+1}:")
                    print(f"    Score: {result.score}")
                    print(f"    Content preview: {result.content[:100]}...")
            else:
                print("  No results returned - this is the problem!")
                
                # No threshold to adjust - should always return results now!
                print(f"\nThreshold removed - vector search should always return results!")
                
        except Exception as e:
            print(f"  ERROR in vector search: {e}")
            import traceback
            traceback.print_exc()
        
        # Close database
        await close_database()
        
    except Exception as e:
        print(f"ERROR in debug script: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_vector_search())