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

CONCURRENCY = 1000
TIMEOUT = 5
MAX_REDIRECTS = 10
DNS_CACHE_TTL = 3600

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

async def get_baseline(session, sem, base_url):
    fake = f"{base_url}/this_should_not_exist_987654"
    async with sem:
        try:
            async with session.get(fake, timeout=TIMEOUT) as r:
                body = await r.read()
                return r.status, len(body), hashlib.md5(body).hexdigest()
        except:
            return None


# ================================
# Check if base domain redirects
# ================================

async def check_base_redirect(session, sem, base_url):
    """Check if base URL redirects and follow the entire redirect chain"""
    redirect_chain = []
    current_url = base_url
    
    try:
        for _ in range(MAX_REDIRECTS):
            async with sem:
                async with session.get(current_url, timeout=TIMEOUT, allow_redirects=False) as r:
                    if 300 <= r.status < 400:
                        # This is a redirect
                        redirect_url = r.headers.get('Location', '')
                        if not redirect_url:
                            break
                        
                        body = await r.read()
                        
                        # Format request
                        req_info = r.request_info
                        req_headers = "".join([f"{k}: {v}\n" for k, v in req_info.headers.items()])
                        request_str = f"{req_info.method} {req_info.url.path_qs} HTTP/1.1\n{req_headers}".strip()
                        
                        # Format response
                        version_str = f"{r.version.major}.{r.version.minor}"
                        resp_headers = "".join([f"{k}: {v}\n" for k, v in r.headers.items()])
                        
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
                            "method": req_info.method,
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
            final_url = redirect_chain[-1]["to"]
            from urllib.parse import urlparse
            parsed = urlparse(final_url)
            final_base = f"{parsed.scheme}://{parsed.netloc}"
            return base_url, redirect_chain, final_base
        
        return base_url, None, None
    except:
        return base_url, None, None


# ================================
# Endpoint fuzzing
# ================================

async def check_endpoint(session, sem, base_url, endpoint, baseline, progress_callback=None, pbar=None):
    url = f"{base_url}/{endpoint}"
    async with sem:
        try:
            async with session.get(url, timeout=TIMEOUT, allow_redirects=True) as r:
                # 1. Optimization: Check headers first if baseline exists
                if baseline:
                    # Content-Length is often present for static error pages
                    if r.status == baseline[0] and r.content_length == baseline[1]:
                        return None

                # 2. Optimization: Only read the body if we really need to check against hash
                # or if we found something interesting (< 400)
                body = await r.read()

                if baseline:
                    if r.status == baseline[0] and len(body) == baseline[1]:
                        return None
                    if hashlib.md5(body).hexdigest() == baseline[2]:
                        return None

                if r.status < 400:
                    
                    # Format Request
                    req_info = r.request_info
                    req_headers = "".join([f"{k}: {v}\n" for k, v in req_info.headers.items()])
                    request_str = f"{req_info.method} {req_info.url.path_qs} HTTP/1.1\n{req_headers}".strip()

                    # Format Response
                    version_str = f"{r.version.major}.{r.version.minor}"
                    resp_headers = "".join([f"{k}: {v}\n" for k, v in r.headers.items()])
                    
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
            pass
        finally:
            if pbar:
                pbar.update(1)
            if progress_callback:
                if asyncio.iscoroutinefunction(progress_callback):
                    await progress_callback(1)
                else:
                    progress_callback(1)
    return None


async def fuzz_single_subdomain(session, sem, base_url, endpoints, pbar=None, progress_callback=None):
    baseline = await get_baseline(session, sem, base_url)
    
    tasks = [
        check_endpoint(session, sem, base_url, ep, baseline, progress_callback, pbar)
        for ep in endpoints
    ]
    
    results = await asyncio.gather(*tasks)
    found = [r for r in results if r]
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
        connector=aiohttp.TCPConnector(
            ssl=ssl_ctx, 
            limit=0,              # Global limit: None (controlled by Semaphore)
            limit_per_host=100,  # Avoid overwhelming a single host too much
            ttl_dns_cache=DNS_CACHE_TTL,
            use_dns_cache=True,
            force_close=False,    # Maintain keep-alive
            enable_cleanup_closed=True
        )
    ) as session:

        print(f"{Fore.CYAN}[*] Checking for base domain redirects...{Style.RESET_ALL}")
        
        # Parallelize redirect checks
        redirect_tasks = [check_base_redirect(session, sem, url) for url in subdomains]
        redirect_results = await asyncio.gather(*redirect_tasks)
        
        for base_url, redirect_chain, final_base in redirect_results:
            if redirect_chain:
                print(f"{Fore.YELLOW}[→] {base_url} has {len(redirect_chain)} redirect(s) to {final_base}{Style.RESET_ALL}")
                
                for redirect_info in redirect_chain:
                    from_url = redirect_info["from"]
                    to_url = redirect_info["to"]
                    parsed_from = urlparse(from_url)
                    from_domain = f"{parsed_from.scheme}://{parsed_from.netloc}"
                    
                    redirect_map[from_domain] = {
                        "status": str(redirect_info["status"]),
                        "method": redirect_info["method"],
                        "redirect": to_url,
                        "request": redirect_info["request"],
                        "response": redirect_info["response"]
                    }
                
                if final_base not in domains_to_fuzz:
                    domains_to_fuzz[final_base] = []
                domains_to_fuzz[final_base].append(base_url)
            else:
                if base_url not in domains_to_fuzz:
                    domains_to_fuzz[base_url] = []
        
        # Calculate total requests
        total_requests = len(domains_to_fuzz) * len(endpoints)
        print(f"{Fore.CYAN}[*] Fuzzing {len(domains_to_fuzz)} domains ({total_requests} total requests)...{Style.RESET_ALL}")
        
        # Now fuzz the final domains in parallel
        fuzz_tasks = []
        
        if progress_callback is None:
            with tqdm(total=total_requests, desc="Fuzzing endpoints", ncols=100) as pbar:
                for domain_to_fuzz in domains_to_fuzz.keys():
                    fuzz_tasks.append(fuzz_single_subdomain(
                        session, sem, domain_to_fuzz, endpoints, pbar=pbar
                    ))
                fuzz_results = await asyncio.gather(*fuzz_tasks)
        else:
            for domain_to_fuzz in domains_to_fuzz.keys():
                fuzz_tasks.append(fuzz_single_subdomain(
                    session, sem, domain_to_fuzz, endpoints, progress_callback=progress_callback
                ))
            fuzz_results = await asyncio.gather(*fuzz_tasks)

        for domain, found_items in fuzz_results:
            if found_items:
                results[domain] = found_items
        
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
