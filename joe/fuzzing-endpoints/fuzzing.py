#!/usr/bin/env python3
# endpoint_fuzzer.py

import asyncio
import aiohttp
import ssl
import json
import os
import hashlib
import uuid
from tqdm import tqdm
from colorama import Fore, Style, init

init(autoreset=True)
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LIVE_HTTP_FILE = os.path.join(SCRIPT_DIR, "live_http.json")
ENDPOINTS_FILE = os.path.join(SCRIPT_DIR, "endpoints.txt")
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "fuzzed_endpoints.json")

CONCURRENCY = 40
TIMEOUT = 6

# ================================
# Utilities
# ================================

def load_live_subdomains():
    if not os.path.isfile(LIVE_HTTP_FILE):
        raise FileNotFoundError(f"{LIVE_HTTP_FILE} not found")

    with open(LIVE_HTTP_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    urls = []
    for entry in data:
        url = entry.get("url")
        if url:
            urls.append(url.rstrip("/"))
    return list(set(urls))


def load_endpoints():
    if not os.path.isfile(ENDPOINTS_FILE):
        raise FileNotFoundError(f"{ENDPOINTS_FILE} not found")

    with open(ENDPOINTS_FILE, "r", encoding="utf-8") as f:
        return [x.strip().lstrip("/") for x in f if x.strip()]


def build_tree(base_url, items):
    root = {
        "id": str(uuid.uuid4()),
        "url": base_url,
        "method": None,
        "source": "Active",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "children": []
    }

    for item in items:
        url = item.get("url", "")
        if not url.startswith(base_url):
            continue

        relative_path = url[len(base_url):].strip("/")
        if not relative_path:
            root.update(item)
            continue

        segments = relative_path.split("/")
        current = root
        current_base = base_url

        for i, segment in enumerate(segments):
            target_url = f"{current_base}/{segment}"
            found = None
            for child in current["children"]:
                if child["url"] == target_url:
                    found = child
                    break
            
            if not found:
                found = {
                    "id": str(uuid.uuid4()),
                    "url": target_url,
                    "method": None,
                    "source": "Active",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "children": []
                }
                current["children"].append(found)
            
            current = found
            current_base = target_url

            if i == len(segments) - 1:
                for k, v in item.items():
                    if k != "url":
                        current[k] = v

    return root


# ================================
# Baseline detection
# ================================

async def get_baseline(session, base_url):
    fake = f"{base_url}/this_should_not_exist_987654"
    try:
        async with session.get(fake, timeout=TIMEOUT) as r:
            body = await r.read()
            return r.status, len(body), hashlib.md5(body).hexdigest()
    except:
        return None


# ================================
# Check if base domain redirects
# ================================

async def check_base_redirect(session, base_url):
    """Check if base URL redirects and follow the entire redirect chain"""
    redirect_chain = []
    current_url = base_url
    max_redirects = 10  # Prevent infinite loops
    
    try:
        for _ in range(max_redirects):
            async with session.get(current_url, timeout=TIMEOUT, allow_redirects=False) as r:
                if 300 <= r.status < 400:
                    # This is a redirect
                    redirect_url = r.headers.get('Location', '')
                    if not redirect_url:
                        break
                    
                    body = await r.read()
                    
                    # Format request
                    req_info = r.request_info
                    req_headers = ""
                    for k, v in req_info.headers.items():
                        req_headers += f"{k}: {v}\n"
                    request_str = f"{req_info.method} {req_info.url.path_qs} HTTP/1.1\n{req_headers}".strip()
                    
                    # Format response
                    version_str = f"{r.version.major}.{r.version.minor}"
                    resp_headers = ""
                    for k, v in r.headers.items():
                        resp_headers += f"{k}: {v}\n"
                    
                    try:
                        decoded_body = body.decode('utf-8', errors='replace')
                    except:
                        decoded_body = "<binary_content>"
                    
                    response_str = f"HTTP/{version_str} {r.status} {r.reason}\n{resp_headers}\n{decoded_body}"
                    
                    # Resolve the redirect URL (handle relative URLs)
                    from urllib.parse import urljoin
                    next_url = urljoin(current_url, redirect_url)
                    
                    # Add this redirect to the chain
                    redirect_chain.append({
                        "from": current_url,
                        "to": next_url,
                        "status": r.status,
                        "request": request_str,
                        "response": response_str
                    })
                    
                    # Move to next URL in chain
                    current_url = next_url
                else:
                    # Not a redirect, we've reached the end
                    break
        
        if redirect_chain:
            # Get the final destination from the last redirect
            from urllib.parse import urlparse
            final_url = redirect_chain[-1]["to"]
            parsed = urlparse(final_url)
            final_base = f"{parsed.scheme}://{parsed.netloc}"
            return redirect_chain, final_base
        
        return None, None
    except:
        return None, None


# ================================
# Endpoint fuzzing
# ================================

async def check_endpoint(session, sem, base_url, endpoint, baseline):
    url = f"{base_url}/{endpoint}"
    async with sem:
        try:
            async with session.get(url, timeout=TIMEOUT, allow_redirects=True) as r:
                body = await r.read()

                if baseline:
                    if r.status == baseline[0] and len(body) == baseline[1]:
                        return None
                    if hashlib.md5(body).hexdigest() == baseline[2]:
                        return None

                if r.status < 400:
                    print(f"{Fore.GREEN}[+] {url} [{r.status}]{Style.RESET_ALL}")
                    
                    # Format Request
                    req_info = r.request_info
                    req_headers = ""
                    for k, v in req_info.headers.items():
                        req_headers += f"{k}: {v}\n"
                    
                    request_str = f"{req_info.method} {req_info.url.path_qs} HTTP/1.1\n{req_headers}".strip()

                    # Format Response
                    version_str = f"{r.version.major}.{r.version.minor}"
                    resp_headers = ""
                    for k, v in r.headers.items():
                        resp_headers += f"{k}: {v}\n"
                    
                    try:
                        decoded_body = body.decode('utf-8', errors='replace')
                    except:
                        decoded_body = "<binary_content>"

                    response_str = f"HTTP/{version_str} {r.status} {r.reason}\n{resp_headers}\n{decoded_body}"

                    return {
                        "url": url,
                        "status": r.status,
                        "method": "GET",
                        "request": request_str,
                        "response": response_str
                    }
        except:
            return None
    return None


async def fuzz_single_subdomain(session, sem, base_url, endpoints, pbar=None, progress_callback=None):
    baseline = await get_baseline(session, base_url)
    found = []

    tasks = []
    for ep in endpoints:
        tasks.append(check_endpoint(session, sem, base_url, ep, baseline))

    completed = 0
    total = len(tasks)

    for coro in asyncio.as_completed(tasks):
        res = await coro
        if res:
            found.append(res)
        
        if pbar:
            pbar.update(1)
        
        if progress_callback:
            completed += 1
            # We assume progress_callback handles the "global" progress tracking if possible, 
            # or we just fire it per completion. 
            # But run() handles the global pbar. 
            # Let's simple call it if provided, maybe passing 1 to increment.
            # actually run() iterates domains.
            # Use a simple increment.
            if asyncio.iscoroutinefunction(progress_callback):
                await progress_callback(1)
            else:
                 progress_callback(1)

    return base_url, found


# ================================
# Runner
# ================================

async def run(subdomains=None, endpoints=None, progress_callback=None):
    from urllib.parse import urlparse
    
    if subdomains is None:
        subdomains = load_live_subdomains()
    if endpoints is None:
        endpoints = load_endpoints()

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    sem = asyncio.Semaphore(CONCURRENCY)

    results = {}
    redirect_map = {}  # Map of redirecting domains to their status codes
    domains_to_fuzz = {}  # Map of final domains to fuzz

    timeout = aiohttp.ClientTimeout(total=None)

    async with aiohttp.ClientSession(
        timeout=timeout,
        connector=aiohttp.TCPConnector(ssl=ssl_ctx)
    ) as session:

        print(f"{Fore.CYAN}[*] Checking for base domain redirects...{Style.RESET_ALL}")
        
        # First, check each subdomain for redirects
        for base_url in subdomains:
            redirect_chain, final_base = await check_base_redirect(session, base_url)
            
            if redirect_chain:
                # This domain has a redirect chain
                print(f"{Fore.YELLOW}[→] {base_url} has {len(redirect_chain)} redirect(s) to {final_base}{Style.RESET_ALL}")
                
                # Store each redirect in the chain
                for redirect_info in redirect_chain:
                    from_url = redirect_info["from"]
                    to_url = redirect_info["to"]
                    
                    # Extract base domain from "from" URL
                    from urllib.parse import urlparse
                    parsed_from = urlparse(from_url)
                    from_domain = f"{parsed_from.scheme}://{parsed_from.netloc}"
                    
                    redirect_map[from_domain] = {
                        "status": str(redirect_info["status"]),
                        "redirect": to_url,
                        "request": redirect_info["request"],
                        "response": redirect_info["response"]
                    }
                
                # We'll fuzz the final destination
                if final_base not in domains_to_fuzz:
                    domains_to_fuzz[final_base] = []
                domains_to_fuzz[final_base].append(base_url)  # Track which domains redirect here
            else:
                # No redirect, fuzz this domain normally
                if base_url not in domains_to_fuzz:
                    domains_to_fuzz[base_url] = []
        
        # Calculate total requests
        total_requests = len(domains_to_fuzz) * len(endpoints)
        
        print(f"{Fore.CYAN}[*] Fuzzing {len(domains_to_fuzz)} domains...{Style.RESET_ALL}")
        
        # Now fuzz the final domains
        if progress_callback is None:
            # Use tqdm if no external callback
            with tqdm(total=total_requests, desc="Fuzzing endpoints", ncols=100) as pbar:
                for domain_to_fuzz in domains_to_fuzz.keys():
                    sub, eps = await fuzz_single_subdomain(
                        session, sem, domain_to_fuzz, endpoints, pbar=pbar
                    )
                    if eps:
                        results[domain_to_fuzz] = eps
        else:
            # Use external callback
            for domain_to_fuzz in domains_to_fuzz.keys():
                sub, eps = await fuzz_single_subdomain(
                    session, sem, domain_to_fuzz, endpoints, pbar=None, progress_callback=progress_callback
                )
                if eps:
                    results[domain_to_fuzz] = eps
        
        for redirect_domain, status in redirect_map.items():
            results[redirect_domain] = status

    # Build hierarchical data
    final_data = []

    # 1. Process fuzzed domains
    for domain, found_items in results.items():
        # results contains simple dicts if it came from redirect_map, need to skip those here?
        # partial fix: results was mixing types in previous code?
        # Wait, the previous code lines 285-286: results[redirect_domain] = status (which is a dict)
        # So results contains both lists (from fuzzing) and dicts (from redirects).
        # We should handle them separately or unifyingly.
        
        if isinstance(found_items, list):
            tree = build_tree(domain, found_items)
            final_data.append(tree)
        else:
            # It's a redirect entry (dict)
             node = {
                "id": str(uuid.uuid4()),
                "url": domain,
                "children": [],
                "method": None,
                "source": "Active",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
             node.update(found_items)
             final_data.append(node)

    # If running as script, save to file
    if __name__ == "__main__":
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump({"data": final_data}, f, indent=2)
        print(f"\n[+] Saved results to {OUTPUT_FILE}")

    return {"data": final_data}


# ================================
# Main
# ================================

if __name__ == "__main__":
    asyncio.run(run())
