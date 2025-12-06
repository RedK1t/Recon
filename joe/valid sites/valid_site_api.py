from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import dns.resolver
import concurrent.futures
import asyncio
import aiohttp
from typing import List, Optional

app = FastAPI(title="Subdomain Validator API")

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your React app's URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------
# Request/Response Models
# ------------------------------------
class SubdomainRequest(BaseModel):
    subs: List[str]

class LiveResult(BaseModel):
    subdomain: str
    url: Optional[str]
    status: Optional[int]
    ips: List[str]

class DnsOnlyResult(BaseModel):
    subdomain: str
    ips: List[str]

class ValidationResponse(BaseModel):
    live_web_services: List[LiveResult]
    dns_only: List[DnsOnlyResult]
    total_subdomains: int
    alive_dns: int
    live_web_services_count: int
    dns_only_count: int

# ------------------------------------
# DNS Resolve
# ------------------------------------
def resolve_domain(sub: str):
    resolver = dns.resolver.Resolver()
    resolver.timeout = 2
    resolver.lifetime = 2
    try:
        answers = resolver.resolve(sub, "A")
        return sub, True, [a.to_text() for a in answers]
    except:
        return sub, False, []

# ------------------------------------
# HTTP Check
# ------------------------------------
async def fetch_status(session, url: str):
    try:
        async with session.get(url, timeout=5) as resp:
            return resp.status
    except:
        return None

async def check_http(sub: str, ips: List[str]):
    urls = [f"http://{sub}", f"https://{sub}"]

    timeout = aiohttp.ClientTimeout(total=6)
    connector = aiohttp.TCPConnector(ssl=False)

    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        for url in urls:
            status = await fetch_status(session, url)
            if status:
                return {"subdomain": sub, "url": url, "status": status, "ips": ips}

    return {"subdomain": sub, "url": None, "status": None, "ips": ips}

# ------------------------------------
# Main Processing Logic
# ------------------------------------
async def process_subdomains(subs: List[str]):
    if not subs:
        raise HTTPException(status_code=400, detail="No subdomains provided")

    # DNS Resolution
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as exe:
        results = list(exe.map(resolve_domain, subs))

    # Create a mapping of subdomain -> IPs
    dns_map = {r[0]: r[2] for r in results if r[1]}
    alive = list(dns_map.keys())

    # HTTP/HTTPS Check
    tasks = [check_http(sub, dns_map[sub]) for sub in alive]
    http_results = await asyncio.gather(*tasks)

    # Separate into two categories
    live_web_services = [r for r in http_results if r["status"]]
    
    # Get subdomains that have DNS but no web service
    web_service_subdomains = {r["subdomain"] for r in live_web_services}
    dns_only = [{"subdomain": sub, "ips": dns_map[sub]} for sub in alive if sub not in web_service_subdomains]

    return {
        "live_web_services": live_web_services,
        "dns_only": dns_only,
        "total_subdomains": len(subs),
        "alive_dns": len(alive),
        "live_web_services_count": len(live_web_services),
        "dns_only_count": len(dns_only)
    }

# ------------------------------------
# API Endpoints
# ------------------------------------
@app.post("/validate", response_model=ValidationResponse)
async def validate_subdomains(request: SubdomainRequest):
    """
    Validate subdomains by checking DNS resolution and HTTP/HTTPS availability.
    
    Request body:
    {
        "subs": ["example.com", "test.example.com", ...]
    }
    
    Response:
    {
        "live_web_services": [
            {"subdomain": "example.com", "url": "https://example.com", "status": 200, "ips": ["93.184.216.34"]}
        ],
        "dns_only": [
            {"subdomain": "mail.example.com", "ips": ["192.168.1.1"]}
        ],
        "total_subdomains": 10,
        "alive_dns": 8,
        "live_web_services_count": 5,
        "dns_only_count": 3
    }
    """
    return await process_subdomains(request.subs)

@app.get("/")
async def root():
    return {
        "message": "Subdomain Validator API",
        "endpoints": {
            "/validate": "POST - Validate subdomains",
            "/docs": "GET - API documentation"
        }
    }

# ------------------------------------
# Run with: uvicorn valid_site_api:app --reload
# ------------------------------------
