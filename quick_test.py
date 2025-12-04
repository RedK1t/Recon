#!/usr/bin/env python3
# quick_test.py - Quick test to show the 5% progress updates

import asyncio
import websockets
import json

async def test():
    uri = "ws://localhost:8000/ws/enumerate"
    
    async with websockets.connect(uri) as ws:
        # Send request
        await ws.send(json.dumps({
            "domain": "example.com",
            "wordlist_preset": "1",
            "passive": False,
            "timeout": 5.0,
            "threads": 30
        }))
        
        print("Progress updates (every 5%):")
        print("-" * 50)
        
        # Receive messages
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            
            if data["type"] == "progress":
                print(f"  {data['percentage']:.1f}% - {data['completed']}/{data['total']}")
            elif data["type"] == "subdomain":
                print(f"\n  ✓ Found: {data['host']}")
                print(f"    IPs: {', '.join(data['ips'])}\n")
            elif data["type"] == "complete":
                print("-" * 50)
                print(f"Complete! Found {data['count']} subdomains in {data['elapsed_time']:.2f}s")
                break

asyncio.run(test())
