import dns.resolver
import concurrent.futures
import asyncio
import aiohttp
import json
import os
from colorama import Fore, Style, init
init(autoreset=True)

# ------------------------------------
# Load Subdomains from subs.json in same folder
# ------------------------------------
def load_subdomains():

    # مكان السكربت نفسه
    base_path = os.path.dirname(os.path.abspath(__file__))
    file_name = os.path.join(base_path, "subs.json")

    try:
        with open(file_name, "r") as f:
            data = json.load(f)

        if "subs" in data:
            print(f"[+] Loaded {len(data['subs'])} subdomains")
            return data["subs"]
        else:
            print("[-] JSON missing 'subs' key!")
            return []

    except FileNotFoundError:
        print(f"[-] subs.json not found in: {file_name}")
        return []

# ------------------------------------
# DNS Resolve
# ------------------------------------
def resolve_domain(sub):
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
async def fetch_status(session, url):
    try:
        async with session.get(url, timeout=5) as resp:
            return resp.status
    except:
        return None

async def check_http(sub):
    urls = [f"http://{sub}", f"https://{sub}"]

    timeout = aiohttp.ClientTimeout(total=6)
    connector = aiohttp.TCPConnector(ssl=False)

    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        for url in urls:
            status = await fetch_status(session, url)
            if status:
                return {"subdomain": sub, "url": url, "status": status}

    return {"subdomain": sub, "url": None, "status": None}

# ------------------------------------
# Save results - in same folder
# ------------------------------------
def save_results(data):
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "live_http.json")
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"[+] Saved results to {output_path}")

# ------------------------------------
# Main
# ------------------------------------
async def main():

    subs = load_subdomains()
    if not subs:
        return

    print("\n[+] Resolving DNS...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as exe:
        results = list(exe.map(resolve_domain, subs))

    alive = [r[0] for r in results if r[1]]
    print(f"[+] Alive DNS: {len(alive)}")

    print("\n[+] Checking HTTP/HTTPS...")
    tasks = [check_http(sub) for sub in alive]
    http_results = await asyncio.gather(*tasks)

    live_results = [r for r in http_results if r["status"]]
    print(f"[+] Live Web Services: {len(live_results)}")

    save_results(live_results)

# ------------------------------------
# Runner
# ------------------------------------
if __name__ == "__main__":
    asyncio.run(main())
