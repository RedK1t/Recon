#!/usr/bin/env python3

import json
import subprocess

INPUT_JSON = "live_http.json"
OUTPUT_JSON = "passive_results.json"

BLACKLIST_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".ico",
    ".css", ".woff", ".woff2", ".ttf", ".eot",
    ".mp4", ".mp3", ".avi", ".mov", ".webm",
    ".pdf", ".zip", ".rar", ".7z",
    ".map"
)

def load_domains(json_file):
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    domains = set()

    for entry in data:
        # case: ["example.com"]
        if isinstance(entry, str):
            domains.add(entry.strip())

        # case: [{"subdomain": "example.com"}]
        elif isinstance(entry, dict) and "subdomain" in entry:
            domains.add(entry["subdomain"].strip())

    return list(domains)

def run_command(command, timeout=30):
    """Run a command with timeout to prevent hanging."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout
        )
        return result.stdout.splitlines()
    except subprocess.TimeoutExpired:
        print(f"[!] Command timeout after {timeout}s: {' '.join(command)}")
        return []
    except Exception as e:
        print(f"[!] Command error: {e}")
        return []

def filter_urls(urls, strict_domain=None):
    clean = set()
    
    # Pre-process strict_domain for comparison
    if strict_domain:
        strict_domain = strict_domain.lower().strip()
        # Remove protocol if present
        if "://" in strict_domain:
             from urllib.parse import urlparse
             strict_domain = urlparse(strict_domain).netloc
        # Remove port from strict_domain if present (e.g. user passed example.com:80)
        if ":" in strict_domain:
            strict_domain = strict_domain.split(":")[0]

    from urllib.parse import urlparse

    for url in urls:
        url = url.strip()

        if not url.startswith("http"):
            continue

        if any(url.lower().endswith(ext) for ext in BLACKLIST_EXTENSIONS):
            continue
            
        if strict_domain:
            try:
                parsed = urlparse(url)
                netloc = parsed.netloc.lower()
                
                # Strip port if present in URL hostname
                if ":" in netloc:
                    netloc = netloc.split(":")[0]
                
                # Check strict equality of hostname
                if netloc != strict_domain:
                    continue
            except:
                continue

        clean.add(url)

    return sorted(clean)

def wayback(domain):
    print(f"[+] Waybackurls -> {domain}")
    return run_command(["waybackurls", domain], timeout=60)

def katana_crawl(domain):
    """Katana active crawling with shallow depth (passive mode not supported in this version)."""
    print(f"[+] Katana -> {domain}")
    return run_command([
        "katana",
        "-u", f"https://{domain}",
        "-d", "2",  # Shallow depth crawling
        "-silent",
        "-jc",  # JavaScript crawling
        "-kf", "all"  # Known files
    ], timeout=60)

def gospider_passive(domain):
    print(f"[+] GoSpider -> {domain}")
    return run_command([
        "gospider",
        "-s", f"https://{domain}",
        "-t", "5",
        "--quiet"
    ])

def main():
    domains = load_domains(INPUT_JSON)
    results = {}

    print(f"[i] Loaded {len(domains)} domains")

    for domain in domains:
        print(f"\n[*] Processing {domain}")
        urls = set()

        # urls.update(wayback(domain))  # Disabled - very slow for large domains, often times out
        # urls.update(katana_crawl(domain))  # Disabled - slow active crawling, can timeout
        urls.update(gospider_passive(domain))  # Fast and reliable

        clean_urls = filter_urls(urls, strict_domain=domain)

        if clean_urls:
            results[domain] = clean_urls

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n[✓] Done. Results saved in {OUTPUT_JSON}")

if __name__ == "__main__":
    main()
