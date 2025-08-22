#!/usr/bin/env python3
"""Performance test for optimized /chat endpoint."""

import asyncio
import time
import aiohttp
import json
from typing import List, Dict, Any
import statistics

# Test configuration
API_URL = "http://localhost:8000"
TEST_QUERIES = [
    "What is Dubai freezone?",  # Simple query
    "How to get visa in Dubai?",  # Medium query
    "Explain the complete process of setting up a company in Dubai freezone with all requirements",  # Complex query
]

async def get_token(session: aiohttp.ClientSession) -> str:
    """Get JWT token for authentication."""
    async with session.post(
        f"{API_URL}/token",
        headers={"X-API-Key": "test_key"},
        json={"user": "test@example.com"}
    ) as resp:
        if resp.status == 200:
            data = await resp.json()
            return data["access_token"]
        else:
            # If auth is not required, return empty token
            return ""

async def test_chat_endpoint(
    session: aiohttp.ClientSession,
    token: str,
    query: str,
    conversation_id: str = None
) -> Dict[str, Any]:
    """Test single chat request and measure performance."""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    payload = {
        "message": query,
        "conversation_id": conversation_id or f"test_{int(time.time())}"
    }
    
    start_time = time.time()
    try:
        async with session.post(
            f"{API_URL}/chat",
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=60)
        ) as resp:
            response_time = time.time() - start_time
            
            result = {
                "query": query[:50] + "..." if len(query) > 50 else query,
                "status": resp.status,
                "response_time": response_time,
                "success": resp.status == 200
            }
            
            if resp.status == 200:
                data = await resp.json()
                result["cached"] = data.get("metadata", {}).get("cached", False)
                result["response_length"] = len(data.get("response", ""))
            else:
                result["error"] = await resp.text()
            
            return result
            
    except asyncio.TimeoutError:
        return {
            "query": query[:50] + "..." if len(query) > 50 else query,
            "status": 504,
            "response_time": time.time() - start_time,
            "success": False,
            "error": "Request timeout"
        }
    except Exception as e:
        return {
            "query": query[:50] + "..." if len(query) > 50 else query,
            "status": 0,
            "response_time": time.time() - start_time,
            "success": False,
            "error": str(e)
        }

async def run_performance_tests():
    """Run performance tests for chat endpoint."""
    print("🚀 Starting Performance Tests")
    print("=" * 60)
    
    async with aiohttp.ClientSession() as session:
        # Check if server is running
        try:
            async with session.get(f"{API_URL}/health", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status != 200:
                    print("❌ Server is not healthy")
                    return
        except:
            print("❌ Server is not running. Please start it with:")
            print("   cd LightRAG && bash start_api.sh")
            return
        
        # Get token if needed
        token = ""
        try:
            token = await get_token(session)
        except:
            print("ℹ️  Authentication not required or not configured")
        
        # Test each query type
        results = []
        
        print("\n📊 Testing Different Query Complexities:")
        print("-" * 60)
        
        for query in TEST_QUERIES:
            print(f"\n🔍 Testing: {query[:50]}...")
            
            # First request (cold cache)
            result1 = await test_chat_endpoint(session, token, query)
            results.append(result1)
            
            print(f"   First request:  {result1['response_time']:.2f}s - Status: {result1['status']}")
            
            # Second request (warm cache)
            await asyncio.sleep(0.5)  # Small delay
            result2 = await test_chat_endpoint(session, token, query, result1.get("conversation_id"))
            results.append(result2)
            
            print(f"   Second request: {result2['response_time']:.2f}s - Status: {result2['status']} {'(cached)' if result2.get('cached') else ''}")
            
            if result1['success'] and result2['success']:
                speedup = result1['response_time'] / result2['response_time']
                print(f"   ⚡ Speedup: {speedup:.1f}x faster with cache")
        
        # Calculate statistics
        print("\n📈 Performance Statistics:")
        print("-" * 60)
        
        successful_results = [r for r in results if r['success']]
        failed_results = [r for r in results if not r['success']]
        
        if successful_results:
            response_times = [r['response_time'] for r in successful_results]
            print(f"✅ Successful requests: {len(successful_results)}/{len(results)}")
            print(f"⏱️  Average response time: {statistics.mean(response_times):.2f}s")
            print(f"⏱️  Median response time:  {statistics.median(response_times):.2f}s")
            print(f"⏱️  Min response time:     {min(response_times):.2f}s")
            print(f"⏱️  Max response time:     {max(response_times):.2f}s")
            
            cached_results = [r for r in successful_results if r.get('cached')]
            if cached_results:
                cached_times = [r['response_time'] for r in cached_results]
                print(f"\n💾 Cache Performance:")
                print(f"   Cache hits: {len(cached_results)}")
                print(f"   Avg cached response: {statistics.mean(cached_times):.2f}s")
        
        if failed_results:
            print(f"\n❌ Failed requests: {len(failed_results)}")
            for failed in failed_results:
                print(f"   - {failed['query']}: {failed.get('error', 'Unknown error')}")
        
        # Recommendations
        print("\n💡 Optimization Results:")
        print("-" * 60)
        
        if not failed_results:
            print("✅ No 504 errors detected - optimization successful!")
        else:
            error_rate = len(failed_results) / len(results) * 100
            if error_rate < 20:
                print(f"⚠️  Some errors detected ({error_rate:.0f}%), but significant improvement")
            else:
                print(f"❌ High error rate ({error_rate:.0f}%) - further optimization needed")
        
        if successful_results:
            avg_time = statistics.mean([r['response_time'] for r in successful_results])
            if avg_time < 10:
                print("🚀 Excellent performance - average response under 10s")
            elif avg_time < 30:
                print("✅ Good performance - average response under 30s")
            else:
                print("⚠️  Performance could be improved - average response over 30s")

if __name__ == "__main__":
    print("LightRAG Chat Endpoint Performance Test")
    print("=" * 60)
    asyncio.run(run_performance_tests())