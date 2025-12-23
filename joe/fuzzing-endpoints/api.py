#!/usr/bin/env python3
# api.py

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import asyncio
import fuzzing

app = FastAPI(
    title="Fuzzing API",
    description="API for directory fuzzing and endpoint discovery",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class FuzzRequest(BaseModel):
    domains: List[str] = Field(..., description="List of domains to fuzz")
    endpoints: Optional[List[str]] = Field(None, description="Custom list of endpoints to check")


@app.get("/")
async def root():
    return {
        "service": "Fuzzing API",
        "version": "1.0.0",
        "endpoints": {
            "fuzz": "POST /fuzz"
        }
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/fuzz")
async def trigger_fuzz(request: FuzzRequest):
    """
    Trigger fuzzing for the provided domains.
    Returns the hierarchical result tree.
    """
    try:
        # Normalize domains: Add https:// if protocol is missing
        normalized_domains = []
        for d in request.domains:
            if not d.startswith(("http://", "https://")):
                normalized_domains.append(f"https://{d}")
            else:
                normalized_domains.append(d)

        # If no endpoints provided, passing None will make run() load from file default
        results = await fuzzing.run(
            subdomains=normalized_domains,
            endpoints=request.endpoints
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
