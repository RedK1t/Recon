#!/usr/bin/env python3
# http_validator.py - HTTP/HTTPS validation for discovered subdomains

import asyncio
import aiohttp
from typing import List, Dict, Optional


async def fetch_status(session: aiohttp.ClientSession, url: str) -> Optional[int]:
    """
    Fetch HTTP status code for a URL
    
    Args:
        session: aiohttp ClientSession
        url: URL to check
        
    Returns:
        HTTP status code or None if request fails
    """
    try:
        async with session.get(url, timeout=5) as resp:
            return resp.status
    except:
        return None


async def check_http(subdomain: str, ips: List[str]) -> Dict:
    """
    Check HTTP/HTTPS availability for a subdomain
    
    Args:
        subdomain: Subdomain to check
        ips: List of IP addresses from DNS resolution
        
    Returns:
        Dict with subdomain, url, status, and ips
    """
    urls = [f"http://{subdomain}", f"https://{subdomain}"]

    timeout = aiohttp.ClientTimeout(total=6)
    connector = aiohttp.TCPConnector(ssl=False)

    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        for url in urls:
            status = await fetch_status(session, url)
            if status:
                return {
                    "subdomain": subdomain,
                    "url": url,
                    "status": status,
                    "ips": ips
                }

    return {
        "subdomain": subdomain,
        "url": None,
        "status": None,
        "ips": ips
    }


async def validate_subdomains(subdomain_results: List[Dict], 
                             validation_callback=None,
                             progress_callback=None) -> Dict:
    """
    Validate HTTP/HTTPS availability for a list of subdomains
    
    Args:
        subdomain_results: List of dicts with 'host' and 'ips' keys
        validation_callback: Optional callback function called for each validated subdomain
        progress_callback: Optional callback for progress updates (percentage, completed, total)
        
    Returns:
        Dict with 'live_web_services' and 'dns_only' arrays
    """
    total = len(subdomain_results)
    if total == 0:
        return {"live_web_services": [], "dns_only": []}
    
    # Create tasks for all subdomains
    tasks = []
    for result in subdomain_results:
        host = result["host"]
        ips = result["ips"]
        tasks.append(check_http(host, ips))
    
    # Process results as they complete (real-time streaming)
    live_web_services = []
    dns_only = []
    completed = 0
    last_reported_percentage = 45  # Start from 50% (DNS was 0-50%)
    
    # Use as_completed to process results as soon as they're ready
    for coro in asyncio.as_completed(tasks):
        result = await coro
        completed += 1
        
        # Calculate progress: 50% + (completed/total * 50%)
        # This makes HTTP validation go from 50% to 100%
        http_percentage = 50 + (completed / total) * 50
        
        # Report progress every 5% or at completion
        if progress_callback and (http_percentage >= last_reported_percentage + 5 or completed == total):
            progress_callback(http_percentage, completed, total)
            last_reported_percentage = http_percentage
        
        if result["status"]:
            # Has web service - send immediately
            live_web_services.append(result)
            if validation_callback:
                validation_callback({
                    "type": "http_validated",
                    "subdomain": result["subdomain"],
                    "url": result["url"],
                    "status": result["status"],
                    "ips": result["ips"]
                })
        else:
            # DNS only, no web service - send immediately
            dns_only.append({
                "subdomain": result["subdomain"],
                "ips": result["ips"]
            })
            if validation_callback:
                validation_callback({
                    "type": "dns_only",
                    "subdomain": result["subdomain"],
                    "ips": result["ips"]
                })
    
    return {
        "live_web_services": live_web_services,
        "dns_only": dns_only
    }

