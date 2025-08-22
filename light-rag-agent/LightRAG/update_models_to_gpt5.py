#!/usr/bin/env python3
"""
Update all OpenAI models to use gpt-5-mini as primary with gpt-4.1 as fallback
"""
import os
import re
import sys

def update_file_models(file_path: str, description: str) -> bool:
    """Update OpenAI models in a specific file"""
    
    if not os.path.exists(file_path):
        print(f"⚠️  File not found: {file_path}")
        return False
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Replace old model defaults with gpt-5-mini
        content = re.sub(r'"gpt-4o-mini"', '"gpt-5-mini"', content)
        content = re.sub(r"'gpt-4o-mini'", "'gpt-5-mini'", content)
        content = re.sub(r'"gpt-4\.1-mini"', '"gpt-5-mini"', content)
        content = re.sub(r"'gpt-4\.1-mini'", "'gpt-5-mini'", content)
        
        # Update fallback models
        content = re.sub(r'"gpt-4o-mini"', '"gpt-4.1"', content)
        content = re.sub(r"'gpt-4o-mini'", "'gpt-4.1'", content)
        
        # Environment variable updates
        content = re.sub(r'OPENAI_MODEL=gpt-4o-mini', 'OPENAI_MODEL=gpt-5-mini', content)
        content = re.sub(r'RAG_LLM_MODEL=gpt-4o-mini', 'RAG_LLM_MODEL=gpt-5-mini', content)
        content = re.sub(r'OPENAI_FALLBACK_MODELS=gpt-4o-mini,gpt-3\.5-turbo', 
                        'OPENAI_FALLBACK_MODELS=gpt-4.1,gpt-4o-mini', content)
        content = re.sub(r'RAG_EMBEDDING_MODEL=text-embedding-3-small', 
                        'RAG_EMBEDDING_MODEL=text-embedding-3-large', content)
        
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Updated {description}")
            return True
        else:
            print(f"📝 No changes needed in {description}")
            return False
            
    except Exception as e:
        print(f"❌ Error updating {file_path}: {e}")
        return False

def main():
    print("=== Updating OpenAI Models to gpt-5-mini ===")
    print()
    
    updates_made = 0
    
    # Files to update
    files_to_update = [
        ("/app/app/core/rag.py", "RAG Core Module"),
        ("/app/app/agent/rag_agent.py", "RAG Agent Module"),  
        ("/app/app/api/server.py", "API Server"),
        ("/app/.env", "Environment Configuration"),
    ]
    
    # Check if we're in container or local development
    if not os.path.exists("/app"):
        # Local development - update local files
        base_path = os.path.dirname(os.path.abspath(__file__))
        files_to_update = [
            (os.path.join(base_path, "app/core/rag.py"), "RAG Core Module"),
            (os.path.join(base_path, "app/agent/rag_agent.py"), "RAG Agent Module"),
            (os.path.join(base_path, "app/api/server.py"), "API Server"),
            (os.path.join(base_path, ".env"), "Environment Configuration"),
        ]
    
    for file_path, description in files_to_update:
        if update_file_models(file_path, description):
            updates_made += 1
    
    print()
    if updates_made > 0:
        print(f"🎉 Successfully updated {updates_made} files to use gpt-5-mini!")
        print()
        print("Model Configuration:")
        print("📍 Primary Model: gpt-5-mini (latest, fastest)")
        print("📍 Fallback Chain: gpt-4.1 → gpt-4o-mini")
        print("📍 Embedding Model: text-embedding-3-large")
        print()
        print("🔄 Restart your application to apply changes:")
        if os.path.exists("/app"):
            print("   docker restart lightrag-api")
        else:
            print("   # Restart your local server")
    else:
        print("✅ All files already using latest model configuration!")

if __name__ == "__main__":
    main()