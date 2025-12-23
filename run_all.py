import subprocess
import os
import sys
import signal
import time

# Define the APIs to run
# Path to script, working directory
APIS = [
    {
        "name": "Subdomain Enumerator API",
        "path": "api.py",
        "cwd": "."
    },
    {
        "name": "Service Ports API",
        "path": "joe/service_ports/api.py",
        "cwd": "joe/service_ports"
    },
    {
        "name": "Fuzzing API",
        "path": "joe/fuzzing-endpoints/api.py",
        "cwd": "joe/fuzzing-endpoints"
    }
]

processes = []

def signal_handler(sig, frame):
    print("\n[!] Stopping all APIs...")
    for p in processes:
        p.terminate()
    sys.exit(0)

def main():
    signal.signal(signal.SIGINT, signal_handler)
    
    # Get the absolute path to the virtual environment python if it exists
    venv_python = os.path.join(os.getcwd(), "venv", "Scripts", "python.exe")
    python_exe = venv_python if os.path.exists(venv_python) else sys.executable

    print(f"[*] Using Python: {python_exe}")
    print("[*] Starting all APIs...")

    for api in APIS:
        abs_path = os.path.abspath(os.path.join(os.getcwd(), api["path"]))
        abs_cwd = os.path.abspath(os.path.join(os.getcwd(), api["cwd"]))
        
        print(f"[+] Starting {api['name']} at {api['path']}...")
        
        # Start the process
        p = subprocess.Popen(
            [python_exe, abs_path],
            cwd=abs_cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        processes.append(p)
        
        # Small delay to prevent port binding race conditions
        time.sleep(1)

    print("\n[✔] All APIs are running!")
    print("[*] Press Ctrl+C to stop all services.\n")

    # Keep the main script alive and echo output
    try:
        while True:
            for p in processes:
                if p.poll() is not None:
                    print(f"[!] Process {p.args} exited unexpectedly.")
                    signal_handler(None, None)
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(None, None)

if __name__ == "__main__":
    main()
