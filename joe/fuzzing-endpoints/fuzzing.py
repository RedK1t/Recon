#!/usr/bin/env python3
# endpoint_fuzzer.py

import asyncio
import aiohttp
import ssl
import json
import os
import hashlib
from tqdm import tqdm
from colorama import Fore, Style, init

init(autoreset=True)

LIVE_HTTP_FILE = "live_http.json"
ENDPOINTS_FILE = "endpoints.txt"
OUTPUT_FILE = "fuzzed_endpoints.json"

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
                        "request": request_str,
                        "response": response_str
                    }
        except:
            return None
    return None


async def fuzz_single_subdomain(session, sem, base_url, endpoints, pbar):
    baseline = await get_baseline(session, base_url)
    found = []

    tasks = []
    for ep in endpoints:
        tasks.append(check_endpoint(session, sem, base_url, ep, baseline))

    for coro in asyncio.as_completed(tasks):
        res = await coro
        if res:
            found.append(res)
        pbar.update(1)

    return base_url, found


# ================================
# Runner
# ================================

async def run():
    subdomains = load_live_subdomains()
    endpoints = load_endpoints()

    total_requests = len(subdomains) * len(endpoints)

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    sem = asyncio.Semaphore(CONCURRENCY)

    results = {}

    timeout = aiohttp.ClientTimeout(total=None)

    async with aiohttp.ClientSession(
        timeout=timeout,
        connector=aiohttp.TCPConnector(ssl=ssl_ctx)
    ) as session:

        with tqdm(total=total_requests, desc="Fuzzing endpoints", ncols=100) as pbar:
            for base_url in subdomains:
                sub, eps = await fuzz_single_subdomain(
                    session, sem, base_url, endpoints, pbar
                )
                if eps:
                    results[sub] = eps

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\n[+] Saved results to {OUTPUT_FILE}")


# ================================
# Main
# ================================

if __name__ == "__main__":
    asyncio.run(run())
