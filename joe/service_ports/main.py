import json
import nmap
import os

RESULTS_FILE = "scan_results.json"

def load_subdomains(json_file):
    if not os.path.exists(json_file):
        print(f"File {json_file} not found.")
        return []

    with open(json_file, "r") as f:
        data = json.load(f)

        # case 1: {"subs": [...]}
        if isinstance(data, dict) and "subs" in data:
            return data["subs"]

        # case 2: {"sub.domain.com": []}
        if isinstance(data, dict):
            return list(data.keys())

    return []


def scan_domain(domain, results):
    nm = nmap.PortScanner()
    print(f"\n[*] Scanning: {domain}")

    try:
        nm.scan(
            hosts=domain,
            arguments="--top-ports 2000 -sV"
        )
    except Exception as e:
        print(f"Error scanning {domain}: {e}")
        results[domain] = {"error": str(e)}
        return

    if not nm.all_hosts():
        print(f"[!] No host found for {domain}")
        results[domain] = {
            "state": "down",
            "ports": []
        }
        return

    for host in nm.all_hosts():
        print(f"\nHost: {host}")
        print(f"State: {nm[host].state()}")

        results[domain] = {
            "ip": host,
            "state": nm[host].state(),
            "ports": []
        }

        for proto in nm[host].all_protocols():
            print(f"\nProtocol: {proto}")

            for port in sorted(nm[host][proto].keys()):
                port_data = nm[host][proto][port]

                state = port_data.get("state", "unknown")
                service = port_data.get("name", "unknown")
                product = port_data.get("product", "")
                version = port_data.get("version", "")
                extrainfo = port_data.get("extrainfo", "")

                service_version = " ".join(
                    x for x in [product, version, extrainfo] if x
                )

                print(
                    f"Port {port}: {state} | "
                    f"Service: {service} | "
                    f"Version: {service_version or 'N/A'}"
                )

                results[domain]["ports"].append({
                    "port": port,
                    "protocol": proto,
                    "state": state,
                    "service": service,
                    "service_version": service_version or "N/A"
                })


def save_results(results):
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=4)

    print(f"\n[+] Results saved to {RESULTS_FILE}")


def main():
    json_file = "subs.json"
    scan_results = {}

    subdomains = load_subdomains(json_file)

    if not subdomains:
        print("No subdomains found in subs.json.")
        return

    print(f"Loaded {len(subdomains)} subdomains.\n")

    for sub in subdomains:
        scan_domain(sub, scan_results)

    save_results(scan_results)


if __name__ == "__main__":
    main()
