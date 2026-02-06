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

def filter_urls(urls):
    clean = set()

    for url in urls:
        url = url.strip()

        if not url.startswith("http"):
            continue

        if any(url.lower().endswith(ext) for ext in BLACKLIST_EXTENSIONS):
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

        clean_urls = filter_urls(urls)

        if clean_urls:
            results[domain] = clean_urls

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n[✓] Done. Results saved in {OUTPUT_JSON}")

if __name__ == "__main__":
    main()
