#!/usr/bin/env python3
"""
Test script to verify ingestion speed improvements.
Creates test files and measures ingestion performance.
"""
import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from app.utils.ingestion import ingest_files, scan_directory
    print("✅ Import successful")
except ImportError as e:
    print(f"❌ Failed to import modules: {e}")
    sys.exit(1)


def create_test_files(test_dir: Path, num_files: int = 20, file_size: int = 1000):
    """Create test files for ingestion testing."""
    test_dir.mkdir(exist_ok=True)
    
    for i in range(num_files):
        content = f"Test document {i}\n" + ("Lorem ipsum dolor sit amet. " * (file_size // 30))
        file_path = test_dir / f"test_doc_{i:03d}.txt"
        file_path.write_text(content, encoding='utf-8')
    
    return list(test_dir.glob("*.txt"))


async def test_ingestion_performance():
    """Test ingestion performance with different configurations."""
    print("🚀 LightRAG Ingestion Performance Test")
    print("=" * 60)
    
    # Create test directory and files
    with tempfile.TemporaryDirectory() as temp_dir:
        test_dir = Path(temp_dir) / "test_docs"
        working_dir = Path(temp_dir) / "rag_working"
        working_dir.mkdir(exist_ok=True)
        
        # Create test files
        num_files = 30
        print(f"📝 Creating {num_files} test files...")
        test_files = create_test_files(test_dir, num_files)
        print(f"✅ Created {len(test_files)} test files")
        
        # Mock RAG for testing (avoid actual OpenAI calls)
        class MockRAG:
            async def ainsert(self, text: str):
                # Simulate processing time like real RAG
                await asyncio.sleep(0.05)  # 50ms per insert
                
        rag = MockRAG()
        
        # Test configurations
        test_configs = [
            {"name": "Sequential (Legacy)", "batch_size": 1, "max_workers": 1, "concurrent_inserts": 1},
            {"name": "Small Batches", "batch_size": 5, "max_workers": 2, "concurrent_inserts": 2},
            {"name": "Medium Batches", "batch_size": 10, "max_workers": 4, "concurrent_inserts": 3},
            {"name": "Large Batches", "batch_size": 20, "max_workers": 6, "concurrent_inserts": 5},
        ]
        
        results = []
        
        for config in test_configs:
            print(f"\n📊 Testing: {config['name']}")
            print(f"   Batch size: {config['batch_size']}, Workers: {config['max_workers']}, Concurrent: {config['concurrent_inserts']}")
            
            start_time = time.time()
            
            result = await ingest_files(
                rag=rag,
                files=test_files,
                working_dir=working_dir,
                batch_size=config['batch_size'],
                max_workers=config['max_workers'],
                concurrent_inserts=config['concurrent_inserts']
            )
            
            elapsed = time.time() - start_time
            
            print(f"   ⏱️  Time: {elapsed:.2f}s")
            print(f"   📈 Speed: {result['performance']['files_per_second']:.2f} files/sec")
            print(f"   ✅ Added: {result['added']}, Skipped: {result['skipped']}")
            
            results.append({
                "config": config['name'],
                "time": elapsed,
                "files_per_second": result['performance']['files_per_second'],
                "added": result['added']
            })
            
            # Reset index for next test
            from app.utils.ingestion import clear_index
            clear_index(working_dir)
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 PERFORMANCE SUMMARY")
        print("=" * 60)
        
        for result in results:
            print(f"{result['config']:<20} | {result['time']:>6.2f}s | {result['files_per_second']:>8.2f} files/sec")
        
        # Calculate improvement
        if len(results) >= 2:
            baseline = results[0]['time']
            best = min(r['time'] for r in results[1:])
            improvement = ((baseline - best) / baseline) * 100
            print(f"\n🚀 Best improvement: {improvement:.1f}% faster than sequential")


if __name__ == "__main__":
    try:
        asyncio.run(test_ingestion_performance())
    except KeyboardInterrupt:
        print("\n⛔ Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Test failed: {e}")
        import traceback
        traceback.print_exc()