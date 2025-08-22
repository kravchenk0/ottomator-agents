#!/usr/bin/env python3
"""
Quick fix for UnboundLocalError: cannot access local variable 'phase'
Apply this patch to fix the immediate error.
"""
import sys
import os

def fix_phase_error():
    """Fix the phase variable error in server.py"""
    
    server_path = "/app/app/api/server.py"
    if not os.path.exists(server_path):
        print(f"Server file not found at {server_path}")
        return False
        
    # Read the file
    with open(server_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if already fixed
    if "# Get phase from contextvar early" in content:
        print("✅ Phase error already fixed!")
        return True
        
    # Apply the fix
    original = """    # User id для лимитов
    user_id = request.user_id or (_claims.get("sub") if isinstance(_claims, dict) else None) or "anonymous"
    
    # Check cache first (for identical questions, skip rate limits for cache hits)
    model_name = request.model or os.getenv("OPENAI_MODEL") or os.getenv("RAG_LLM_MODEL") or "gpt-4o-mini"
    cache_key = _get_chat_cache_key(request.message, conv_id, user_id, model_name)
    
    if phase: phase.start("cache_check")"""
    
    replacement = """    # User id для лимитов
    user_id = request.user_id or (_claims.get("sub") if isinstance(_claims, dict) else None) or "anonymous"
    
    # Get phase from contextvar early (used throughout the function)
    phase = _cv_phase.get() or _phase
    
    # Check cache first (for identical questions, skip rate limits for cache hits)
    model_name = request.model or os.getenv("OPENAI_MODEL") or os.getenv("RAG_LLM_MODEL") or "gpt-4o-mini"
    cache_key = _get_chat_cache_key(request.message, conv_id, user_id, model_name)
    
    if phase: phase.start("cache_check")"""
    
    if original in content:
        content = content.replace(original, replacement)
        print("✅ Applied phase variable fix")
    else:
        print("⚠️  Original pattern not found, manual fix may be needed")
        return False
    
    # Also remove duplicate phase assignment
    duplicate_pattern = """    # Формируем history_context (исключая только что добавленное user сообщение)
    # Берём phase из contextvar, а если отсутствует (старый decorator) — используем _phase если передан
    phase = _cv_phase.get() or _phase
    if phase:"""
    
    replacement_pattern = """    # Формируем history_context (исключая только что добавленное user сообщение)
    if phase:"""
    
    if duplicate_pattern in content:
        content = content.replace(duplicate_pattern, replacement_pattern)
        print("✅ Removed duplicate phase assignment")
    
    # Write back the fixed content
    try:
        with open(server_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("✅ Fixed server.py successfully!")
        return True
    except Exception as e:
        print(f"❌ Error writing fixed file: {e}")
        return False

if __name__ == "__main__":
    print("=== Fixing Phase Variable Error ===")
    success = fix_phase_error()
    if success:
        print("\n🎉 Fix applied successfully!")
        print("You can now restart the server or test /chat endpoint")
    else:
        print("\n❌ Fix failed - manual intervention needed")
        sys.exit(1)