#!/usr/bin/env python3
"""
Test script for path normalization fixes.
"""

from pathlib import Path
from app.utils.ingestion import _normalize_file_key, cleanup_duplicate_paths, save_index, load_index

def test_normalization():
    """Test the path normalization function."""
    working_dir = "/app/documents"
    
    # Test cases
    test_cases = [
        ("/app/documents/raw_uploads/file.md", "raw_uploads/file.md"),
        ("documents/raw_uploads/file.md", "raw_uploads/file.md"),
        ("/app/documents/file.txt", "file.txt"),
        ("/outside/path/file.txt", "/outside/path/file.txt"),  # Outside working_dir
    ]
    
    print("Testing path normalization:")
    for input_path, expected in test_cases:
        result = _normalize_file_key(Path(input_path), working_dir)
        status = "✅" if result == expected else "❌"
        print(f"{status} {input_path} -> {result} (expected: {expected})")


def test_cleanup_duplicates():
    """Test the duplicate cleanup function."""
    # Use temp dir but test with real paths
    import tempfile
    with tempfile.TemporaryDirectory() as temp_dir:
        working_dir = Path(temp_dir)
        
        # Create test index with duplicates that SHOULD map to same normalized path
        test_index = {
            str(working_dir / "raw_uploads" / "Golden Visa – Skilled Professionals (knowledge workers) (1).md"): {
                "hash": "b58d6eca4a07e6d37452c5184cb9566c757e0bcdf062c4bc313ad9bf380931f7",
                "size": 31699
            },
            "documents/raw_uploads/Golden Visa – Skilled Professionals (knowledge workers) (1).md": {
                "hash": "b58d6eca4a07e6d37452c5184cb9566c757e0bcdf062c4bc313ad9bf380931f7", 
                "size": 31699
            },
            "other_file.txt": {
                "hash": "different_hash",
                "size": 1234
            }
        }
        
        # Save test index
        save_index(working_dir, test_index)
        
        print(f"\nBefore cleanup: {len(test_index)} entries")
        for key in test_index.keys():
            print(f"  - {key}")
        
        # Debug: Test normalization for each key
        print(f"\nNormalization test:")
        for key in test_index.keys():
            normalized = _normalize_file_key(Path(key), working_dir)
            print(f"  {key} -> {normalized}")
        
        # Run cleanup
        result = cleanup_duplicate_paths(working_dir)
        print(f"\nCleanup result: {result}")
        
        # Check result
        cleaned_index = load_index(working_dir)
        print(f"\nAfter cleanup: {len(cleaned_index)} entries")
        for key in cleaned_index.keys():
            print(f"  - {key}")


if __name__ == "__main__":
    test_normalization()
    test_cleanup_duplicates()