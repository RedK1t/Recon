import subprocess
import os
import sys
import signal
import time
import socket
from dotenv import load_dotenv
load_dotenv()

# Define the APIs to run
# Path to script, working directory, and port
APIS = [
    {
        "name": "Subdomain Enumerator API",
        "path": "api.py",
        "cwd": ".",
        "port": os.getenv('SUB_DOMAIN_PORT')
    },
    {
        "name": "Service Ports API",
        "path": "joe/service_ports/api.py",
        "cwd": "joe/service_ports",
        "port": os.getenv('SERVICE_PORTS_PORT')
    },
    {
        "name": "Unified Recon API",
        "path": "joe/unified_api/api.py",
        "cwd": "joe/unified_api",
        "port": os.getenv('UNIFIED_API_PORT')
    }
]

processes = []

def kill_process_on_port(port):
    """Kill process using a specific port on Windows or Linux."""
    try:
        if sys.platform == 'win32':
            # Windows: Find PID using the port
            output = subprocess.check_output(f'netstat -ano | findstr :{port}', shell=True).decode()
            for line in output.strip().split('\n'):
                if 'LISTENING' in line:
                    pid = line.strip().split()[-1]
                    print(f"[!] Port {port} is in use by PID {pid}. Killing it...")
                    subprocess.run(f'taskkill /F /PID {pid}', shell=True, capture_output=True)
                    time.sleep(1) # Give it a moment to release the port
        else:
            # Linux/macOS: Use lsof or fuser to find and kill process on port
            try:
                output = subprocess.check_output(['lsof', '-t', f'-i:{port}'], stderr=subprocess.DEVNULL).decode().strip()
                if output:
                    for pid in output.split('\n'):
                        if pid:
                            print(f"[!] Port {port} is in use by PID {pid}. Killing it...")
                            subprocess.run(['kill', '-9', pid], capture_output=True)
                            time.sleep(1)
            except subprocess.CalledProcessError:
                # No process using this port
                pass
    except subprocess.CalledProcessError:
        # findstr returns exit code 1 if no matches found
        pass
    except Exception as e:
        print(f"[!] Error killing process on port {port}: {e}")

def signal_handler(sig, frame):
    print("\n[!] Stopping all APIs...")
    for p in processes:
        p.terminate()
    sys.exit(0)

def main():
    signal.signal(signal.SIGINT, signal_handler)
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Get the absolute path to the virtual environment python if it exists
    if sys.platform == 'win32':
        venv_python = os.path.join(base_dir, "venv", "Scripts", "python.exe")
    else:
        venv_python = os.path.join(base_dir, "venv", "bin", "python")
    python_exe = venv_python if os.path.exists(venv_python) else sys.executable

    print(f"[*] Using Python: {python_exe}")
    print("[*] Starting all APIs...")

    for api in APIS:
        # Check and kill any existing process on the port
        if "port" in api:
            kill_process_on_port(api["port"])

        abs_path = os.path.abspath(os.path.join(base_dir, api["path"]))
        abs_cwd = os.path.abspath(os.path.join(base_dir, api["cwd"]))
        
        print(f"[+] Starting {api['name']} at {api['path']}...")
        
        # Start the process
        p = subprocess.Popen(
            [python_exe, abs_path],
            cwd=abs_cwd
        )
        processes.append(p)
        
        # Small delay to prevent port binding race conditions
        time.sleep(1)

    print("\n[+] All APIs are running!")
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
