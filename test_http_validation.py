#!/usr/bin/env python3
# test_http_validation.py - Test the HTTP validation integration

import asyncio
import websockets
import json

async def test_websocket():
    """Test WebSocket enumeration with HTTP validation"""
    uri = "ws://localhost:8000/ws/enumerate"
    
    try:
        async with websockets.connect(uri) as websocket:
            # Send enumeration request
            request = {
                "domain": "google.com",
                "wordlist_preset": "1",
                "passive": False,
                "timeout": 3.0,
                "threads": 20
            }
            
            await websocket.send(json.dumps(request))
            print(f"✓ Sent enumeration request for google.com")
            print("-" * 60)
            
            # Receive messages
            subdomain_count = 0
            http_validated_count = 0
            dns_only_count = 0
            
            while True:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=120)
                    data = json.loads(message)
                    
                    msg_type = data.get("type")
                    
                    if msg_type == "progress":
                        print(f"Progress: {data['percentage']:.1f}% ({data['completed']}/{data['total']})")
                    
                    elif msg_type == "subdomain":
                        subdomain_count += 1
                        print(f"DNS Found: {data['host']} -> {data['ips']}")
                    
                    elif msg_type == "http_validated":
                        http_validated_count += 1
                        print(f"✓ HTTP Live: {data['subdomain']} -> {data['url']} (Status: {data['status']})")
                    
                    elif msg_type == "dns_only":
                        dns_only_count += 1
                        print(f"✗ DNS Only: {data['subdomain']} (No web service)")
                    
                    elif msg_type == "complete":
                        print("-" * 60)
                        print(f"✓ Enumeration Complete!")
                        print(f"  Total Subdomains: {data['count']}")
                        print(f"  HTTP Live Services: {http_validated_count}")
                        print(f"  DNS Only: {dns_only_count}")
                        print(f"  Elapsed Time: {data['elapsed_time']:.2f}s")
                        break
                    
                    elif msg_type == "error":
                        print(f"✗ Error: {data['message']}")
                        break
                
                except asyncio.TimeoutError:
                    print("✗ Timeout waiting for response")
                    break
    
    except Exception as e:
        print(f"✗ Connection error: {e}")
        print("\nMake sure the API server is running:")
        print("  uvicorn api:app --reload --host 0.0.0.0 --port 8000")

if __name__ == "__main__":
    print("Testing HTTP Validation Integration")
    print("=" * 60)
    asyncio.run(test_websocket())
