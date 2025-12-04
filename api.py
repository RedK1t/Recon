#!/usr/bin/env python3
# api.py - FastAPI application for subdomain enumeration

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import core

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


class EnumerateResponse(BaseModel):
    count: int
    subdomains: List[SubdomainResult]
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
            "subdomains": result["subdomains"],
            "elapsed_time": result["elapsed_time"]
        }
    
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Enumeration failed: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
