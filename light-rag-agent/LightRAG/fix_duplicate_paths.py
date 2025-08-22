#!/usr/bin/env python3
"""
Script to fix duplicate file paths in the ingestion index.

This script can be run to clean up the existing duplicate paths issue
where the same file appears with both absolute and relative paths.
"""

import os
import sys
from pathlib import Path

# Add the current directory to Python path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent))

from app.utils.ingestion import cleanup_duplicate_paths, list_index
from app.core.rag import get_default_config

def main():
    """Main function to fix duplicate paths."""
    print("🔧 LightRAG Duplicate Paths Fixer")
    print("=" * 40)
    
    # Get the working directory
    config = get_default_config()
    working_dir = config.working_dir
    
    print(f"📁 Working directory: {working_dir}")
    
    # Show current index status
    current_index = list_index(working_dir)
    print(f"📊 Current index: {len(current_index)} entries")
    
    if len(current_index) == 0:
        print("ℹ️  Index is empty, nothing to fix.")
        return
    
    # Show some examples of current paths
    print("\n📋 Current paths (first 5 entries):")
    for i, entry in enumerate(current_index[:5]):
        print(f"  {i+1}. {entry['file']}")
    
    if len(current_index) > 5:
        print(f"  ... and {len(current_index) - 5} more")
    
    # Check for potential duplicates by looking for common patterns
    absolute_paths = [e['file'] for e in current_index if e['file'].startswith('/')]
    relative_paths = [e['file'] for e in current_index if not e['file'].startswith('/')]
    documents_paths = [e['file'] for e in current_index if e['file'].startswith('documents/')]
    
    print(f"\n🔍 Path analysis:")
    print(f"  - Absolute paths: {len(absolute_paths)}")
    print(f"  - Relative paths: {len(relative_paths)}")
    print(f"  - 'documents/' paths: {len(documents_paths)}")
    
    potential_duplicates = len(absolute_paths) > 0 and (len(documents_paths) > 0 or len(relative_paths) > 0)
    
    if not potential_duplicates:
        print("✅ No obvious duplicate patterns found.")
        return
    
    print(f"⚠️  Potential duplicates detected!")
    print(f"   This often happens when files are ingested via both:")
    print(f"   - REST API (creates relative/documents/ paths)")
    print(f"   - ingest_local.py (creates absolute paths)")
    
    # Ask for confirmation
    response = input(f"\n🤔 Do you want to clean up duplicates? (y/N): ").lower().strip()
    
    if response != 'y':
        print("❌ Cleanup cancelled.")
        return
    
    print(f"\n🧹 Running cleanup...")
    
    # Run the cleanup
    result = cleanup_duplicate_paths(working_dir)
    
    print(f"✅ Cleanup completed!")
    print(f"📊 Results:")
    print(f"   - Original entries: {result['original_count']}")
    print(f"   - Duplicates removed: {result['cleaned']}")
    print(f"   - Entries kept: {result['kept']}")
    print(f"   - Final total: {result['total_indexed']}")
    
    if result['cleaned'] > 0:
        print(f"\n🎉 Successfully removed {result['cleaned']} duplicate entries!")
        print(f"💡 The /documents/ingest/list API should now show clean results.")
        
        # Show updated index
        updated_index = list_index(working_dir)
        print(f"\n📋 Updated paths (first 5 entries):")
        for i, entry in enumerate(updated_index[:5]):
            print(f"  {i+1}. {entry['file']}")
    else:
        print(f"\nℹ️  No duplicates were found to remove.")


if __name__ == "__main__":
    main()