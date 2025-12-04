#!/usr/bin/env python3
# core.py - Core subdomain enumeration logic

import dns.resolver
import concurrent.futures
import time
import os
import requests

PRESET_NAMES = {
    "1": ("top1k", "top1k.txt"),
    "2": ("top10k", "top10k.txt"),
    "3": ("top25k", "top25k.txt"),
    "4": ("top50k", "top50k.txt"),
    "5": ("top100k", "top100k.txt"),
    "6": ("custom", None)
}


def fetch_crtsh_subdomains(domain):
    """
    Fetch subdomains from crt.sh (passive enumeration)
    
    Args:
        domain: Target domain
        
    Returns:
        List of discovered subdomains
    """
    url = f"https://crt.sh/?q=%25.{domain}&output=json"
    
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return []
        data = r.json()

        subs = set()
        for entry in data:
            name = entry.get("name_value")
            if not name:
                continue
            for s in name.split("\n"):
                s = s.strip().lower()
                if "*" in s:
                    s = s.replace("*.", "")
                if s.endswith(domain):
                    subs.add(s)
        return list(subs)
    except Exception as e:
        return []


def resolve_a(host, timeout):
    """
    Resolve A records for a host
    
    Args:
        host: Hostname to resolve
        timeout: DNS timeout in seconds
        
    Returns:
        Dict with host and IPs, or None if resolution fails
    """
    try:
        answers = dns.resolver.resolve(host, 'A', lifetime=timeout)
        ips = [r.to_text() for r in answers]
        return {"host": host, "ips": ips}
    except:
        return None


def worker(prefix, domain, timeout):
    """Worker function for concurrent subdomain resolution"""
    host = f"{prefix}.{domain}".strip().lower()
    return resolve_a(host, timeout)


def load_wordlist(path):
    """
    Load wordlist from file
    
    Args:
        path: Path to wordlist file
        
    Returns:
        List of prefixes
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Wordlist not found: {path}")
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith('#')]
    return lines


def get_preset_path(preset_id):
    """
    Get wordlist path from preset ID
    
    Args:
        preset_id: Preset identifier (1-6)
        
    Returns:
        Tuple of (preset_name, wordlist_path)
    """
    if preset_id in PRESET_NAMES:
        return PRESET_NAMES[preset_id]
    return PRESET_NAMES["1"]  # Default to top1k


def enumerate_subdomains(domain, wordlist_path=None, preset_id="1", 
                        passive=False, timeout=5.0, threads=30, 
                        progress_callback=None, subdomain_callback=None):
    """
    Main subdomain enumeration function
    
    Args:
        domain: Target domain
        wordlist_path: Path to custom wordlist (optional)
        preset_id: Preset wordlist ID (1-6)
        passive: Enable passive enumeration via crt.sh
        timeout: DNS timeout in seconds
        threads: Number of concurrent threads
        progress_callback: Optional callback function for progress updates (percentage, completed, total)
        subdomain_callback: Optional callback function called when a subdomain is discovered
        
    Returns:
        Dict with results: {
            "subdomains": [{"host": str, "ips": [str]}],
            "count": int,
            "elapsed_time": float
        }
    """
    # Normalize domain
    try:
        domain_ascii = domain.encode('idna').decode('ascii')
    except:
        domain_ascii = domain.lower()
    
    domain = domain_ascii.lower()
    
    # Load wordlist
    if wordlist_path and os.path.isfile(wordlist_path):
        prefixes = load_wordlist(wordlist_path)
    else:
        preset_name, preset_path = get_preset_path(preset_id)
        if preset_path:
            prefixes = load_wordlist(preset_path)
        else:
            raise ValueError("Invalid preset or wordlist path")
    
    # Add passive enumeration results
    if passive:
        passive_subs = fetch_crtsh_subdomains(domain)
        extracted = []
        for sub in passive_subs:
            if sub.endswith(domain):
                prefix = sub.replace(f".{domain}", "")
                if prefix and prefix != domain:
                    extracted.append(prefix)
        prefixes = list(set(prefixes + extracted))
    
    total_prefixes = len(prefixes)
    
    # Active enumeration
    results = []
    completed = 0
    last_reported_percentage = -5  # Track last reported percentage to send every 5%
    start = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as ex:
        futures = {ex.submit(worker, pfx, domain, timeout): pfx for pfx in prefixes}
        for fut in concurrent.futures.as_completed(futures):
            try:
                res = fut.result()
            except:
                res = None
            
            completed += 1
            
            # Send progress update every 5% or at completion
            if progress_callback:
                percentage = (completed / total_prefixes) * 100
                # Send if we've crossed a 5% threshold or reached 100%
                if percentage >= last_reported_percentage + 5 or percentage == 100:
                    progress_callback(percentage, completed, total_prefixes)
                    last_reported_percentage = percentage
            
            # Send subdomain discovery update
            if res:
                results.append(res)
                if subdomain_callback:
                    subdomain_callback(res)
    
    elapsed = time.time() - start
    
    return {
        "subdomains": results,
        "count": len(results),
        "elapsed_time": elapsed
    }
