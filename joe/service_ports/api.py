from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from main import scan_domain

app = FastAPI(title="Service Ports Scanner API")

# Create a custom thread pool for parallel nmap scans
# 10 workers allows up to 10 concurrent scans
executor = ThreadPoolExecutor(max_workers=10)

# CORS middleware for React app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your React app's URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ScanRequest(BaseModel):
    domains: List[str]


class PortInfo(BaseModel):
    port: int
    protocol: str
    state: str
    service: str
    service_version: str


class ScanResult(BaseModel):
    ip: Optional[str] = None
    state: str
    ports: List[PortInfo]
    error: Optional[str] = None


@app.get("/")
async def root():
    """API health check endpoint"""
    return {
        "status": "online",
        "service": "Service Ports Scanner API",
        "endpoints": {
            "POST /scan": "Scan domains for open ports",
            "WebSocket /ws/scan": "Real-time port scanning with progress updates"
        }
    }


@app.post("/scan", response_model=ScanResult)
async def scan_ports(request: ScanRequest):
    """
    Scan a domain for open ports and services.
    Returns scan data directly without wrapper object.
    Uses custom thread pool for guaranteed parallel processing.
    
    Args:
        request: ScanRequest containing a list of domains (typically one domain)
        
    Returns:
        ScanResult with ip, state, ports, and optional error
    """
    if not request.domains:
        raise HTTPException(status_code=400, detail="No domains provided")
    
    # Get the first domain (React sends one domain per request)
    domain = request.domains[0]
    scan_results = {}
    
    # Run scan in custom thread pool for guaranteed parallel processing
    # This allows multiple concurrent requests to run simultaneously
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(executor, scan_domain, domain, scan_results)
    
    # Return the scan data directly
    result = scan_results.get(domain, {})
    
    return ScanResult(
        ip=result.get("ip"),
        state=result.get("state", "unknown"),
        ports=result.get("ports", []),
        error=result.get("error")
    )


@app.websocket("/ws/scan")
async def websocket_scan(websocket: WebSocket):
    """
    WebSocket endpoint for real-time port scanning with progress updates.
    
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
        
        scan_results = {}
        total = len(domains)
        
        # Send initial status
        await websocket.send_json({
            "type": "status",
            "message": f"Starting scan of {total} domain(s)",
            "total": total,
            "completed": 0
        })
        
        # Scan each domain and send updates
        for idx, domain in enumerate(domains, 1):
            # Send progress update
            await websocket.send_json({
                "type": "progress",
                "current_domain": domain,
                "completed": idx - 1,
                "total": total,
                "percentage": round(((idx - 1) / total) * 100, 2)
            })
            
            # Perform scan
            scan_domain(domain, scan_results)
            
            # Send individual result
            await websocket.send_json({
                "type": "result",
                "domain": domain,
                "data": scan_results[domain]
            })
        
        # Send final summary
        successful = sum(1 for r in scan_results.values() if "error" not in r and r.get("state") == "up")
        failed = total - successful
        
        await websocket.send_json({
            "type": "complete",
            "message": "Scan completed",
            "results": scan_results,
            "total_domains": total,
            "successful_scans": successful,
            "failed_scans": failed
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
            "message": f"Scan error: {str(e)}"
        })
    finally:
        await websocket.close()


if __name__ == "__main__":
    import uvicorn
    # Note: Multiple workers don't work on Windows
    # Parallel processing is achieved via asyncio.to_thread() instead
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=9000,
        log_level="info"
    )
