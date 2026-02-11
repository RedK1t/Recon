#!/usr/bin/env python3
# api.py

import sys
import os
import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Add sibling directories to sys.path to allow imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(os.path.join(parent_dir, "passive_url"))
sys.path.append(os.path.join(parent_dir, "fuzzing-endpoints"))

# Import from passive_url
try:
    from main import gospider_passive, filter_urls, wayback, katana_crawl
except ImportError as e:
    print(f"Error importing from passive_url: {e}")
    # Fallback or mock if needed
    def gospider_passive(domain): return []
    def wayback(domain): return []
    def katana_crawl(domain): return []
    def filter_urls(urls, strict_domain=None): return list(urls)

# Import from fuzzing-endpoints
try:
    import fuzzing
except ImportError as e:
    print(f"Error importing from fuzzing-endpoints: {e}")
    # Fallback
    fuzzing = None

app = FastAPI(
    title="Unified Recon API",
    description="Unified API for Passive and Active Endpoint Discovery",
    version="1.0.0"
)

# CORS validation
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class UnifiedScanRequest(BaseModel):
    domains: List[str] = Field(..., description="List of domains to scan")
    endpoints: Optional[List[str]] = Field(None, description="Custom list of endpoints to fuzz")

@app.get("/")
async def root():
    return {
        "service": "Unified Recon API",
        "version": "1.0.0",
        "endpoints": {
            "scan": "POST /scan"
        }
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

async def verify_passive_urls(session, sem, base_url, passive_urls):
    """
    Verify passive URLs by making requests to them to get status, request, and response.
    Returns a list of result objects compatible with the fuzzing output.
    """
    results = []
    
    # helper from fuzzing.py (need to ensure we can use it or replicate it)
    # We will replicate check_endpoint logic simplified here or use fuzzing.check_endpoint if possible
    
    tasks = []
    for url in passive_urls:
         # We need to extract the endpoint part relative to base_url for check_endpoint, 
         # but passive URLs are full URLs.
         # So we can just use a similar logic to check_endpoint but taking full URL.
         tasks.append(verify_single_url(session, sem, url))
    
    verified_results = await asyncio.gather(*tasks)
    return [r for r in verified_results if r]

async def verify_single_url(session, sem, url):
    TIMEOUT = 10
    async with sem:
        try:
            async with session.get(url, timeout=TIMEOUT, allow_redirects=True) as r:
                if r.status == 404:
                    return None
                # Read body
                try:
                    body = await r.read()
                except:
                    body = b""
                
                # Format Request
                req_info = r.request_info
                req_headers = "".join([f"{k}: {v}\n" for k, v in req_info.headers.items()])
                request_str = f"{req_info.method} {req_info.url.path_qs} HTTP/1.1\n{req_headers}".strip()

                # Format Response
                version_str = f"{r.version.major}.{r.version.minor}" if r.version else "1.1"
                resp_headers = "".join([f"{k}: {v}\n" for k, v in r.headers.items()])
                
                # Use fuzzing.format_response if available, else simple decode
                if fuzzing:
                    try:
                        content_type = r.headers.get("Content-Type", "").lower()
                        decoded_body = fuzzing.format_response(body, content_type)
                    except:
                        decoded_body = "<binary_content>"
                else:
                     decoded_body = body.decode('utf-8', errors='replace')

                response_str = f"HTTP/{version_str} {r.status} {r.reason}\n{resp_headers}\n{decoded_body}"

                return {
                    "url": str(r.url),
                    "status": r.status,
                    "method": "GET",
                    "source": "Passive",
                    "request": request_str,
                    "response": response_str
                }
        except Exception as e:
            # If verification fails, return basic info with error or skip? 
            # User wants "request and response", if we can't get it, maybe return empty/error.
            # But let's return a basic structure saying it failed or just the URL.
            # For now, if we can't reach it, it might not be interesting for "Active" verification of passive source.
            # But let's verify if user wants ALL passive URLs even if dead.
            # "return the request and response and all the data... source is Passive"
            # If it's dead, we can't get request/response.
            # We will return it with error status perhaps?
            return {
                "url": url,
                "status": 0,
                "method": "GET",
                "source": "Passive",
                "request": None,
                "response": f"Error verifying: {str(e)}"
            }

@app.post("/scan")
async def unified_scan(request: UnifiedScanRequest):
    """
    Perform both passive and active scanning.
    """
    if not fuzzing:
        raise HTTPException(status_code=500, detail="Fuzzing module not loaded")

    import aiohttp
    import ssl

    results = []

    # 1. Start all discovery tasks in parallel
    print("[*] Starting Parallel Discovery (Passive + Active)...")
    loop = asyncio.get_event_loop()
    
    # Prep Active Fuzzing task
    normalized_domains = []
    for d in request.domains:
        if not d.startswith(("http://", "https://")):
            normalized_domains.append(f"https://{d}")
        else:
            normalized_domains.append(d)
    
    active_task = fuzzing.run(subdomains=normalized_domains, endpoints=request.endpoints)
    
    # Prep Passive tasks (gospider and wayback per domain)
    passive_tasks = []
    for domain in request.domains:
        passive_tasks.append(loop.run_in_executor(None, gospider_passive, domain))
        passive_tasks.append(loop.run_in_executor(None, wayback, domain))
        
    # Run everything together
    all_discovery_results = await asyncio.gather(*passive_tasks, active_task)
    
    active_results_data = all_discovery_results[-1]
    passive_raw_results = all_discovery_results[:-1]
    
    # Process passive results into map
    passive_urls_map = {}
    for i, domain in enumerate(request.domains):
        urls = set()
        # i*2 is gospider result, i*2 + 1 is wayback result
        urls.update(passive_raw_results[i*2])
        urls.update(passive_raw_results[i*2 + 1])
        
        # Filter URLs (still using executor for this utility)
        clean = await loop.run_in_executor(None, filter_urls, urls, domain)
        passive_urls_map[domain] = clean

    # 2. Active Fuzzing results are already in active_results_data
    # Now verify passive URLs
    print("[*] Verifying Passive URLs...")
    
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    
    timeout = aiohttp.ClientTimeout(total=None)
    sem = asyncio.Semaphore(100) # Concurrency for verification

    async with aiohttp.ClientSession(
        timeout=timeout,
        connector=aiohttp.TCPConnector(ssl=ssl_ctx, limit=0, ttl_dns_cache=300)
    ) as session:
        
        verified_passive_items = []
        
        for domain, urls in passive_urls_map.items():
            # Verify these URLs
            # Note: urls are full URLs like http://param...
            verified_list = await verify_passive_urls(session, sem, domain, urls)
            verified_passive_items.extend(verified_list)
            
    # 3. Merge Results
    # active_results_data["data"] is a list of root nodes (per domain).
    # We need to inject passive items into these trees or add new nodes.
    
    # We can use fuzzing.build_tree to rebuild trees if we have all flat items.
    # But active results are already trees.
    # We can verify if we can extract flat items from active results? 
    # Or just add passive items to the existing tree (if functions allowed).
    
    # fuzzing.build_tree(base_url, items) takes flat items.
    # Maybe it's easier to:
    # 1. Get flat "Active" items (we'd need to modify fuzzing.py or parse the tree).
    # 2. Get flat "Passive" items.
    # 3. Re-build tree.
    
    # Parsing the tree to flat items:
    flat_active_items = []
    
    def flatten_tree(node, domain_root):
        # Extract relevant fields
        method = node.get("method")
        request = node.get("request")
        response = node.get("response")
        source = node.get("source", "Active")

        # Set source to None if no request/response and method is null
        if method is None and request is None and response is None:
            source = None

        item = {
            "url": node.get("url"),
            "method": method,
            "source": source,
            "status": node.get("status"),
            "request": request,
            "response": response
        }
        # Only add if it has a status (meaning it's a found endpoint, not just a folder node? 
        # Actually folder nodes are created by build_tree. We only want real results.)
        # But wait, build_tree creates intermediate nodes.
        # If we re-build tree, we only need the leaf nodes (or nodes that were actually found).
        # Found nodes have "status". Intermediate nodes might not?
        # In fuzzing.py, build_tree:
        # if not found: create dict with defaults.
        # if i == len(segments) - 1: update with item items.
        
        # So essentially, we want all items that have "status" or "request".
        status = node.get("status")
        if status and status != 404:
            flat_active_items.append(item)
            
        for child in node.get("children", []):
            flatten_tree(child, domain_root)

    for root_node in active_results_data.get("data", []):
        flatten_tree(root_node, root_node.get("url"))

    # Combine
    all_items = flat_active_items + verified_passive_items
    
    # Group by domain to build trees
    # We need to know which domain an item belongs to.
    # passive items have "url".
    # active items have "url".
    
    # We can group by base domain.
    from urllib.parse import urlparse
    # Filter all items strictly against requested domains
    # We need to extract the set of allowed strict domains (hostnames)
    from urllib.parse import urlparse
    allowed_hosts = set()
    for d in request.domains:
        d_clean = d.lower().strip()
        if "://" in d_clean:
            d_clean = urlparse(d_clean).netloc
        if ":" in d_clean:
            d_clean = d_clean.split(":")[0]
        allowed_hosts.add(d_clean)
        
    filtered_items = []
    for item in all_items:
        u = item.get("url", "")
        try:
            parsed = urlparse(u)
            netloc = parsed.netloc.lower()
            if ":" in netloc:
                netloc = netloc.split(":")[0]
            
            if netloc in allowed_hosts:
                filtered_items.append(item)
        except:
            continue
            
    # Group by domain to build trees
    domain_groups = {}
    
    for item in filtered_items:
        # Extract base (scheme://netloc)
        u = item.get("url", "")
        parsed = urlparse(u)
        base = f"{parsed.scheme}://{parsed.netloc}"
        
        if base not in domain_groups:
            domain_groups[base] = []
        domain_groups[base].append(item)
        
    final_tree_data = []
    for base, items in domain_groups.items():
        # Use fuzzing.build_tree
        tree = fuzzing.build_tree(base, items)
        final_tree_data.append(tree)
        
    return {"data": final_tree_data}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
