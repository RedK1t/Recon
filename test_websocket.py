#!/usr/bin/env python3
# test_websocket.py - Test WebSocket endpoint for subdomain enumeration

import asyncio
import websockets
import json

async def test_enumerate():
    """Test the WebSocket enumerate endpoint"""
    uri = "ws://localhost:8000/ws/enumerate"
    
    try:
        async with websockets.connect(uri) as websocket:
            # Send enumeration request
            request = {
                "domain": "example.com",
                "wordlist_preset": "1",
                "passive": False,
                "timeout": 5.0,
                "threads": 30
            }
            
            print(f"Sending request: {json.dumps(request, indent=2)}")
            await websocket.send(json.dumps(request))
            
            # Receive and display messages
            subdomain_count = 0
            
            while True:
                try:
                    message = await websocket.recv()
                    data = json.loads(message)
                    
                    if data["type"] == "progress":
                        print(f"Progress: {data['percentage']:.2f}% ({data['completed']}/{data['total']})")
                    
                    elif data["type"] == "subdomain":
                        subdomain_count += 1
                        print(f"\n🎯 Found subdomain #{subdomain_count}: {data['host']}")
                        print(f"   IPs: {', '.join(data['ips'])}\n")
                    
                    elif data["type"] == "complete":
                        print(f"\n{'='*60}")
                        print(f"✓ Enumeration complete!")
                        print(f"  Total subdomains found: {data['count']}")
                        print(f"  Elapsed time: {data['elapsed_time']:.2f} seconds")
                        print(f"{'='*60}")
                        break
                    
                    elif data["type"] == "error":
                        print(f"✗ Error: {data['message']}")
                        break
                
                except websockets.exceptions.ConnectionClosed:
                    print("Connection closed")
                    break
    
    except Exception as e:
        print(f"Connection error: {e}")
        print("\nMake sure the FastAPI server is running:")
        print("  python api.py")

if __name__ == "__main__":
    print("=" * 60)
    print("WebSocket Subdomain Enumeration Test")
    print("=" * 60)
    asyncio.run(test_enumerate())
