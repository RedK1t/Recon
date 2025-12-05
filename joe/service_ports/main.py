import json
import nmap
import time
import sys
import os # Import os for environment check (optional but good practice)

# Constants for file names
WORDLIST_FILE = "subs.json"
OUTPUT_FILE = "scan_results.json"

def load_subdomains(filename):
    """Load the list of subdomains from a JSON file."""
    try:
        if not os.path.exists(filename):
            print(f"❌ Error: Wordlist file not found: {filename}")
            return []
            
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            # Use data.get() for safe access to 'subs'
            subs_list = data.get("subs", [])
            
            if isinstance(subs_list, list):
                # Critical Correction: Force conversion to string and filter out any empty strings
                cleaned_subs = []
                for sub in subs_list:
                    # Explicitly convert to string and strip whitespace
                    target = str(sub).strip()
                    
                    # Ensure the converted string is not empty and is not just a number (which might cause the error)
                    # We accept targets that look like valid domain names
                    if target and (not target.isdigit() or len(target) > 3): 
                        cleaned_subs.append(target)
                    elif target.isdigit():
                         print(f"⚠️ Warning: Skipping numeric target '{target}' in JSON file.")
                
                return cleaned_subs
            else:
                print(f"❌ Error: 'subs' key is not a list in {filename}")
                return []
                
    except json.JSONDecodeError:
        print(f"❌ Error: Failed to parse JSON file: {filename}. Check formatting.")
        return []
    except Exception as e:
        print(f"❌ An unexpected error occurred during file loading: {e}")
        return []

def scan_subdomains(subdomains):
    """
    Execute a comprehensive Nmap scan (Service Version Detection and Default Scripting) 
    for vulnerability and version detection.
    """
    try:
        nm = nmap.PortScanner()
    except nmap.PortScannerError as e:
        print(f"❌ Nmap Initialization Error: {e}")
        print("Please ensure Nmap is installed and accessible in your system's PATH.")
        return []

    results = []
    total_subs = len(subdomains)

    if total_subs == 0:
        print("No valid subdomains to scan. Exiting.")
        return results

    print(f"🔍 Starting scan on {total_subs} subdomains...")
    print("-" * 50)

    for i, target in enumerate(subdomains):
        
        # FINAL GUARD: Ensure the target is a string and not empty before proceeding
        if not isinstance(target, str) or not target.strip():
            print(f"\n⚠️ Skipping invalid or empty target at index {i}.")
            continue
            
        target = target.strip() # Re-strip just in case

        try:
            # Calculate progress
            progress_percent = ((i + 1) / total_subs) * 100
            
            # 1. Display progress (%)
            progress_message = f"[{i + 1}/{total_subs}] Scanning: {target} | Progress: {progress_percent:.2f}%"
            sys.stdout.write(f"\r{progress_message}{' ' * (80 - len(progress_message))}") 
            sys.stdout.flush()

            # 2. Execute Nmap scan
            # Arguments: -sV (Version Detection), -sC (Default Scripts - includes vulns check), -T4, -p 1-1000
            nm.scan(hosts=target, arguments='-sV -sC -T4 -p 1-1000')

            # 3. Process the results
            scan_data = {
                "target": target,
                "host_state": nm[target].state() if target in nm else "unknown",
                "open_ports": []
            }

            if target in nm.all_hosts() and 'tcp' in nm[target]:
                for port, port_data in nm[target]['tcp'].items():
                    if port_data['state'] == 'open':
                        
                        # Extract Nmap Script Output for Vulns/CVEs
                        script_output = port_data.get('script', {})
                        
                        vulnerability_warning = ""
                        # Check for common keywords in script output
                        for script_name, output in script_output.items():
                            if any(kw in str(output).lower() for kw in ["vulnerable", "cve", "exploit", "unsupported"]):
                                vulnerability_warning += f"[{script_name}: {str(output).splitlines()[0][:50]}...]" 
                        
                        port_entry = {
                            "port_id": port,
                            "protocol": "tcp",
                            "state": port_data['state'],
                            "service": port_data.get('name', ''),
                            "product": port_data.get('product', ''),
                            "version": port_data.get('version', ''),
                            "vulnerability_warning": vulnerability_warning if vulnerability_warning else "None Detected by Default Scripts",
                            "nmap_script_output": script_output 
                        }
                        scan_data["open_ports"].append(port_entry)
            
            results.append(scan_data)

        except nmap.PortScannerError as e:
            # Nmap specific errors (e.g., failed to resolve host, or internal library error)
            print(f"\n⚠️ Nmap Scanner Error on {target}: {e}")
            results.append({"target": target, "error": f"Nmap Scanner Error: {e}"})
        except Exception as e:
            # General errors
            print(f"\n⚠️ Failed to scan {target}: {e}")
            results.append({"target": target, "error": str(e)})
            
    # Clear the progress line and show completion message
    sys.stdout.write(f"\r{' ' * 80}\r") 
    print("=" * 50)
    print("✅ Scan Complete!")
    print("=" * 50)
    return results

def save_results(filename, data):
    """Save the results to a JSON file."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"💾 Results saved successfully to: {filename}")
    except Exception as e:
        print(f"❌ Failed to save results: {e}")

if __name__ == "__main__":
    # 1. Load subdomains
    subdomains_list = load_subdomains(WORDLIST_FILE)
    
    # 2. Start scanning automatically
    if subdomains_list:
        scan_results = scan_subdomains(subdomains_list)
        
        # 3. Save the results
        if scan_results:
            save_results(OUTPUT_FILE, scan_results)