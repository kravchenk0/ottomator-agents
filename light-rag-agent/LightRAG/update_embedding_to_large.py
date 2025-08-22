#!/usr/bin/env python3
"""
Quick script to update embedding model to text-embedding-3-large
"""
import os
import re

def update_embedding_model():
    """Update embedding model in environment file"""
    
    env_path = "/app/.env" if os.path.exists("/app") else ".env"
    
    if not os.path.exists(env_path):
        print(f"❌ Environment file not found: {env_path}")
        return False
    
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Update embedding model
        updated_content = re.sub(
            r'RAG_EMBEDDING_MODEL=text-embedding-3-small',
            'RAG_EMBEDDING_MODEL=text-embedding-3-large',
            content
        )
        
        if updated_content != content:
            with open(env_path, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            print("✅ Updated embedding model to text-embedding-3-large")
            return True
        else:
            print("📝 Embedding model already set to text-embedding-3-large")
            return False
            
    except Exception as e:
        print(f"❌ Error updating embedding model: {e}")
        return False

if __name__ == "__main__":
    print("=== Updating Embedding Model to text-embedding-3-large ===")
    
    success = update_embedding_model()
    
    if success:
        print()
        print("🎉 Embedding model updated successfully!")
        print("📍 New model: text-embedding-3-large (highest quality)")
        print("📍 Benefits: Better semantic search accuracy")
        print("📍 Note: Slightly higher cost but better results")
        print()
        print("🔄 Restart application to apply changes:")
        if os.path.exists("/app"):
            print("   docker restart lightrag-api")
        else:
            print("   # Restart your local server")
    else:
        print("✅ No changes needed!")