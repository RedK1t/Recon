#!/usr/bin/env python3
# api.py - FastAPI application for subdomain enumeration

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import core
import json
import asyncio

app = FastAPI(
    title="Subdomain Enumerator API",
    description="Fast subdomain enumeration API with passive and active scanning",
    version="1.0.0"
)

# Configure CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your React app's URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response Models
class EnumerateRequest(BaseModel):
    domain: str = Field(..., description="Target domain to enumerate")
    wordlist_preset: str = Field("1", description="Wordlist preset ID (1-6)")
    custom_wordlist: Optional[str] = Field(None, description="Path to custom wordlist")
    passive: bool = Field(False, description="Enable passive enumeration via crt.sh")
    timeout: float = Field(5.0, description="DNS timeout in seconds", ge=0.1, le=30.0)
    threads: int = Field(30, description="Number of concurrent threads", ge=1, le=100)


class SubdomainResult(BaseModel):
    host: str
    ips: List[str]


class LiveWebService(BaseModel):
    subdomain: str
    url: str
    status: int
    ips: List[str]


class DnsOnlyResult(BaseModel):
    subdomain: str
    ips: List[str]


class EnumerateResponse(BaseModel):
    count: int
    live_web_services: List[LiveWebService]
    dns_only: List[DnsOnlyResult]
    elapsed_time: float


class PassiveRequest(BaseModel):
    domain: str = Field(..., description="Target domain for passive enumeration")


class PassiveResponse(BaseModel):
    count: int
    subdomains: List[str]


class PresetInfo(BaseModel):
    id: str
    name: str
    filename: Optional[str]


class PresetsResponse(BaseModel):
    presets: List[PresetInfo]


# API Endpoints
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Subdomain Enumerator API",
        "version": "1.0.0",
        "endpoints": {
            "enumerate": "/api/enumerate",
            "passive": "/api/passive",
            "presets": "/api/presets"
        }
    }


@app.get("/api/presets", response_model=PresetsResponse)
async def get_presets():
    """Get available wordlist presets"""
    presets = []
    for preset_id, (name, filename) in core.PRESET_NAMES.items():
        presets.append({
            "id": preset_id,
            "name": name,
            "filename": filename
        })
    return {"presets": presets}


@app.post("/api/passive", response_model=PassiveResponse)
async def passive_enumerate(request: PassiveRequest):
    """
    Perform passive subdomain enumeration using crt.sh
    
    This endpoint fetches subdomains from certificate transparency logs
    without performing active DNS queries.
    """
    try:
        subdomains = core.fetch_crtsh_subdomains(request.domain)
        return {
            "count": len(subdomains),
            "subdomains": subdomains
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Passive enumeration failed: {str(e)}")


@app.post("/api/enumerate", response_model=EnumerateResponse)
async def enumerate(request: EnumerateRequest):
    """
    Perform active subdomain enumeration
    
    This endpoint performs DNS resolution on subdomains using a wordlist.
    Optionally includes passive enumeration results from crt.sh.
    """
    try:
        # Validate inputs
        if not request.domain:
            raise HTTPException(status_code=400, detail="Domain is required")
        
        # Run enumeration
        result = core.enumerate_subdomains(
            domain=request.domain,
            wordlist_path=request.custom_wordlist,
            preset_id=request.wordlist_preset,
            passive=request.passive,
            timeout=request.timeout,
            threads=request.threads
        )
        
        return {
            "count": result["count"],
            "live_web_services": result["live_web_services"],
            "dns_only": result["dns_only"],
            "elapsed_time": result["elapsed_time"]
        }
    
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Enumeration failed: {str(e)}")


@app.websocket("/ws/enumerate")
async def websocket_enumerate(websocket: WebSocket):
    """
    WebSocket endpoint for real-time subdomain enumeration
    
    Accepts JSON with enumeration parameters and streams results:
    - Progress updates with percentage completion
    - Discovered subdomains in real-time
    - Completion message with total count and elapsed time
    
    Message format:
    Input: {"domain": "example.com", "wordlist_preset": "1", "passive": false, "timeout": 5.0, "threads": 30}
    
    Output messages:
    - Progress: {"type": "progress", "percentage": 45.5, "completed": 455, "total": 1000}
    - HTTP Validated: {"type": "http_validated", "subdomain": "api.example.com", "url": "https://api.example.com", "status": 200, "ips": ["192.168.1.1"]}
    - DNS Only: {"type": "dns_only", "subdomain": "mail.example.com", "ips": ["192.168.1.2"]}
    - Complete: {"type": "complete", "count": 25, "elapsed_time": 12.5}
    - Error: {"type": "error", "message": "Error description"}
    """
    await websocket.accept()
    
    try:
        # Receive enumeration parameters
        data = await websocket.receive_text()
        params = json.loads(data)
        
        domain = params.get("domain")
        if not domain:
            await websocket.send_json({
                "type": "error",
                "message": "Domain is required"
            })
            await websocket.close()
            return
        
        wordlist_preset = params.get("wordlist_preset", "1")
        custom_wordlist = params.get("custom_wordlist")
        passive = params.get("passive", False)
        timeout = params.get("timeout", 5.0)
        threads = params.get("threads", 30)
        
        # Create a thread-safe queue for real-time message streaming
        message_queue = asyncio.Queue()
        enumeration_complete = asyncio.Event()
        
        # Run enumeration in a thread pool
        def run_enumeration():
            def sync_progress_callback(percentage, completed, total):
                # Put message in queue for async sending
                asyncio.run_coroutine_threadsafe(
                    message_queue.put({
                        "type": "progress",
                        "percentage": round(percentage, 2),
                        "completed": completed,
                        "total": total
                    }),
                    loop
                )
            
            def sync_http_validation_callback(result):
                # Put HTTP validation message in queue
                asyncio.run_coroutine_threadsafe(
                    message_queue.put(result),
                    loop
                )
            
            try:
                result = core.enumerate_subdomains(
                    domain=domain,
                    wordlist_path=custom_wordlist,
                    preset_id=wordlist_preset,
                    passive=passive,
                    timeout=timeout,
                    threads=threads,
                    progress_callback=sync_progress_callback,
                    http_validation_callback=sync_http_validation_callback
                )
                
                # Signal completion
                asyncio.run_coroutine_threadsafe(
                    message_queue.put({
                        "type": "complete",
                        "count": result["count"],
                        "elapsed_time": round(result["elapsed_time"], 2)
                    }),
                    loop
                )
            except Exception as e:
                asyncio.run_coroutine_threadsafe(
                    message_queue.put({
                        "type": "error",
                        "message": str(e)
                    }),
                    loop
                )
            finally:
                # Set the event directly (it's not a coroutine)
                loop.call_soon_threadsafe(enumeration_complete.set)
        
        # Start enumeration in background thread
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, run_enumeration)
        
        # Stream messages in real-time as they arrive
        while not enumeration_complete.is_set() or not message_queue.empty():
            try:
                # Wait for message with timeout to check completion status
                message = await asyncio.wait_for(message_queue.get(), timeout=0.1)
                await websocket.send_json(message)
                
                # Break if this was the completion or error message
                if message["type"] in ["complete", "error"]:
                    break
            except asyncio.TimeoutError:
                # No message available, continue waiting
                continue
        
    except WebSocketDisconnect:
        pass
    except json.JSONDecodeError:
        try:
            await websocket.send_json({
                "type": "error",
                "message": "Invalid JSON format"
            })
        except:
            pass
    except Exception as e:
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
