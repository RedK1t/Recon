#!/usr/bin/env python3
# fast_subenum.py - CLI interface for subdomain enumeration

import argparse
import json
import csv
import os
from colorama import Fore, Style, init
import core

init(autoreset=True)


def save_json(path, results):
    """Save results to JSON file"""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({"count": len(results), "subs": results}, f, indent=2, ensure_ascii=False)


def save_csv(path, results):
    """Save results to CSV file"""
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(["subdomain", "ips"])
        for r in results:
            w.writerow([r["host"], ";".join(r["ips"])])


def interactive_choose_preset():
    """Interactive preset selection"""
    print("[+] Available presets:")
    for key, (name, _) in core.PRESET_NAMES.items():
        print(f"  {key}. {name}")
    
    choice = input("Choose preset (1-6): ").strip()
    if choice in core.PRESET_NAMES:
        name, path = core.PRESET_NAMES[choice]
        if path is None:
            custom_path = input("Enter custom wordlist path: ").strip()
            return custom_path
        return path
    else:
        print("[!] Invalid choice, using top1k")
        return core.PRESET_NAMES["1"][1]


def progress_callback(message):
    """Callback for progress updates"""
    if message.startswith("Found:"):
        host = message.replace("Found: ", "")
        print(f"{Fore.GREEN}[+] {host}{Style.RESET_ALL}")
    else:
        print(f"[+] {message}")


def main():
    p = argparse.ArgumentParser(description="Fast subdomain enumerator")
    p.add_argument("-d", "--domain", help="Target domain")
    p.add_argument("-w", "--wordlist", help="Wordlist file")
    p.add_argument("-o", "--output", default="subs.json", help="Output file")
    p.add_argument("-t", "--timeout", type=float, default=5.0)
    p.add_argument("-T", "--threads", type=int, default=30)
    p.add_argument("--passive", action="store_true",
                   help="Enable passive enumeration using crt.sh")

    args = p.parse_args()

    if args.domain:
        domain_input = args.domain.strip()
    else:
        domain_input = input("Target domain: ").strip()

    print(f"[+] Domain: {domain_input}")

    # Determine wordlist
    if args.wordlist:
        wordlist_path = args.wordlist
        if not os.path.isfile(wordlist_path):
            print("[!] Wordlist not found, switching to preset...")
            wordlist_path = interactive_choose_preset()
        preset_id = None
    else:
        wordlist_path = None
        preset_id = interactive_choose_preset()
        if preset_id not in core.PRESET_NAMES:
            wordlist_path = preset_id
            preset_id = "1"

    # Run enumeration using core module
    try:
        if args.passive:
            print(f"[+] Fetching passive subdomains from crt.sh...")
        
        result = core.enumerate_subdomains(
            domain=domain_input,
            wordlist_path=wordlist_path,
            preset_id=preset_id if preset_id else "1",
            passive=args.passive,
            timeout=args.timeout,
            threads=args.threads,
            progress_callback=None  # We'll handle progress differently for CLI
        )
        
        # Display results with colors
        print(f"\n[+] Active scan completed in {result['elapsed_time']:.2f}s")
        print(f"[+] Alive subdomains: {result['count']}")
        
        # Show found subdomains
        for sub in result['subdomains']:
            print(f"{Fore.GREEN}[+] {sub['host']} -> {','.join(sub['ips'])}{Style.RESET_ALL}")
        
        # Save results
        alive_subs = [r["host"] for r in result['subdomains']]
        save_json(args.output, alive_subs)
        print(f"\n[+] Saved alive subdomains to {args.output}")
        
    except Exception as e:
        print(f"{Fore.RED}[!] Error: {e}{Style.RESET_ALL}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
