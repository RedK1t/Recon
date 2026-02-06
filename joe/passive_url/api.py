#!/usr/bin/env python3
# api.py

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from main import wayback, katana_crawl, gospider_passive, filter_urls

app = FastAPI(
    title="Passive URL Discovery API",
    description="API for discovering URLs using passive reconnaissance tools (Waybackurls, Katana, GoSpider)",
    version="1.0.0"
)

# Create a custom thread pool for parallel processing
executor = ThreadPoolExecutor(max_workers=10)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your React app's URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PassiveURLRequest(BaseModel):
    domains: List[str] = Field(..., description="List of domains to discover URLs for")


class PassiveURLResult(BaseModel):
    domain: str
    urls: List[str]
    total_urls: int
    error: Optional[str] = None


class PassiveURLResponse(BaseModel):
    results: Dict[str, PassiveURLResult]
    total_domains: int
    successful: int
    failed: int


@app.get("/")
async def root():
    """API health check endpoint"""
    return {
        "status": "online",
        "service": "Passive URL Discovery API",
        "version": "1.0.0",
        "endpoints": {
            "POST /discover": "Discover URLs for domains using passive reconnaissance",
            "WebSocket /ws/discover": "Real-time URL discovery with progress updates"
        }
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


def process_domain(domain: str) -> Dict:
    """
    Process a single domain to discover URLs using passive tools.
    This function runs in a thread pool to allow parallel processing.
    """
    try:
        print(f"[*] Processing {domain}")
        urls = set()
        
        # Run URL discovery tools
        # urls.update(wayback(domain))  # Disabled - very slow for large domains, often times out
        # urls.update(katana_crawl(domain))  # Disabled - slow active crawling, can timeout
        urls.update(gospider_passive(domain))  # Fast and reliable
        
        # Filter URLs
        clean_urls = filter_urls(urls)
        
        return {
            "domain": domain,
            "urls": clean_urls,
            "total_urls": len(clean_urls),
            "error": None
        }
    except Exception as e:
        print(f"[!] Error processing {domain}: {e}")
        return {
            "domain": domain,
            "urls": [],
            "total_urls": 0,
            "error": str(e)
        }


@app.post("/discover", response_model=PassiveURLResponse)
async def discover_urls(request: PassiveURLRequest):
    """
    Discover URLs for the provided domains using passive reconnaissance tools.
    
    Args:
        request: PassiveURLRequest containing a list of domains
        
    Returns:
        PassiveURLResponse with results for each domain
    """
    if not request.domains:
        raise HTTPException(status_code=400, detail="No domains provided")
    
    # Process all domains in parallel using thread pool
    loop = asyncio.get_event_loop()
    tasks = [
        loop.run_in_executor(executor, process_domain, domain)
        for domain in request.domains
    ]
    
    # Wait for all tasks to complete
    results_list = await asyncio.gather(*tasks)
    
    # Build response
    results = {}
    successful = 0
    failed = 0
    
    for result in results_list:
        domain = result["domain"]
        results[domain] = PassiveURLResult(**result)
        
        if result["error"] is None:
            successful += 1
        else:
            failed += 1
    
    return PassiveURLResponse(
        results=results,
        total_domains=len(request.domains),
        successful=successful,
        failed=failed
    )


@app.websocket("/ws/discover")
async def websocket_discover(websocket: WebSocket):
    """
    WebSocket endpoint for real-time URL discovery with progress updates.
    
    Expects JSON message: {"domains": ["domain1.com", "domain2.com"]}
    Sends progress updates and results in real-time.
    """
    await websocket.accept()
    
    try:
        # Receive domains list from client
        data = await websocket.receive_text()
        request_data = json.loads(data)
        domains = request_data.get("domains", [])
        
        if not domains:
            await websocket.send_json({
                "type": "error",
                "message": "No domains provided"
            })
            await websocket.close()
            return
        
        total = len(domains)
        results = {}
        
        # Send initial status
        await websocket.send_json({
            "type": "status",
            "message": f"Starting URL discovery for {total} domain(s)",
            "total": total,
            "completed": 0
        })
        
        # Process each domain and send updates
        for idx, domain in enumerate(domains, 1):
            # Send progress update
            await websocket.send_json({
                "type": "progress",
                "current_domain": domain,
                "completed": idx - 1,
                "total": total,
                "percentage": round(((idx - 1) / total) * 100, 2)
            })
            
            # Process domain in thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(executor, process_domain, domain)
            results[domain] = result
            
            # Send individual result
            await websocket.send_json({
                "type": "result",
                "domain": domain,
                "data": result
            })
        
        # Send final summary
        successful = sum(1 for r in results.values() if r.get("error") is None)
        failed = total - successful
        total_urls = sum(r.get("total_urls", 0) for r in results.values())
        
        await websocket.send_json({
            "type": "complete",
            "message": "URL discovery completed",
            "results": results,
            "total_domains": total,
            "successful": successful,
            "failed": failed,
            "total_urls_discovered": total_urls
        })
        
    except WebSocketDisconnect:
        print("Client disconnected")
    except json.JSONDecodeError:
        await websocket.send_json({
            "type": "error",
            "message": "Invalid JSON format"
        })
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": f"Discovery error: {str(e)}"
        })
    finally:
        await websocket.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8002,
        log_level="info"
    )
