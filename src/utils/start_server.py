import os
import sys
import time
import socket
import argparse
import subprocess
import urllib.error
import urllib.request


def get_project_root():
    home_dir = os.path.expanduser("~")
    return str(home_dir)


def is_web_server_running(port):
    try:
        response = urllib.request.urlopen(f"http://localhost:{port}", timeout=1)
        return response.status == 200
    except (urllib.error.URLError, ConnectionRefusedError):
        return False
    except Exception:
        return False


def kill_server_by_port_(port):
    """Kill a server running on the specified port"""
    # Find processes using the specified port
    cmd = f"lsof -i :{port} -t"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.stdout:
        pids = result.stdout.strip().split("\n")
        print(f"Found {len(pids)} process(es) using port {port}")

        for pid in pids:
            try:
                # Kill the process
                subprocess.run(["kill", "-9", pid], check=True)
                print(f"Successfully killed process {pid} using port {port}")
            except subprocess.SubprocessError as e:
                print(f"Failed to kill process {pid}: {e}")
        return True
    else:
        print(f"No processes found using port {port}")
        return False


def kill_server_by_port(port):
    cmd = f"lsof -nP -ti tcp:{port} -sTCP:LISTEN"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    pids = result.stdout.strip().splitlines()

    http_pids = []
    for pid in pids:
        try:
            cmd = ["ps", "-p", pid, "-o", "args="]
            args = subprocess.check_output(cmd, text=True).strip()
            if "python" in args and "http.server" in args:
                http_pids.append(pid)
        except subprocess.SubprocessError:
            pass

    if not http_pids:
        print(f"No Python HTTP server found listening on port {port}")
        return False

    for pid in http_pids:
        try:
            subprocess.run(["kill", "-9", pid], check=True)
            print(f"Killed HTTP server PID {pid} on port {port}")
        except subprocess.SubprocessError as e:
            print(f"Failed to kill PID {pid}: {e}")
    return True


def kill_all_server():
    # pkill -f "python -m http.server"
    cmd = ["pkill", "-f", "python -m http.server"]
    subprocess.run(cmd, check=True)


def find_server_pids():
    cmd = "ps -ef | grep '[p]ython -m http.server'"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    pids = []
    if result.returncode == 0:
        lines = result.stdout.strip().split("\n")
        for line in lines:
            parts = line.split()
            if len(parts) > 1:
                pid = parts[1]
                pids.append(pid)
    return pids


def run_server_in_background(port=8000, directory=None):
    port_in_use = False
    try:
        os.getenv("HOME")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", port))
    except socket.error:
        port_in_use = True

    if port_in_use:
        if is_web_server_running(port):
            print(f"A web server is already running on port {port}.")
            print(f"You can access it at: http://localhost:{port}/")
            return True
        else:
            print(f"Port {port} is in use but doesn't appear to be a web server.")
            print("Please choose a different port.")
            return False

    cmd = [sys.executable, "-m", "http.server", str(port), "--bind", "0.0.0.0"]

    if directory:
        cmd.extend(["-d", directory])
    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception as e:
        print(f"Error starting server: {e}")
        return False

    time.sleep(1)

    print("Waiting for server to start...")
    max_attempts = 5
    for i in range(max_attempts):
        time.sleep(1)
        if is_web_server_running(port):
            print(f"Server started successfully in the background on port {port}.")
            print(f"You can access it at: http://localhost:{port}/")
            return True
        else:
            print(f"Attempt {i+1}/{max_attempts}: Server not responding yet...")

    print(f"Server may not have started correctly after {max_attempts} attempts.")
    return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run or kill a Python HTTP server")
    parser.add_argument(
        "port",
        nargs="?",
        type=int,
        default=8086,
        help="Port to run the server on (default: 8086)",
    )
    parser.add_argument(
        "directory",
        nargs="?",
        type=str,
        help="Directory to serve (default: project root)",
    )
    parser.add_argument(
        "-k",
        "--kill_port",
        type=int,
        metavar="PORT",
        help="Kill server running on the specified port",
    )

    args = parser.parse_args()

    # Handle kill_port argument if provided
    if args.kill_port:
        print(f"Attempting to kill server on port {args.kill_port}")
        killed = kill_server_by_port(args.kill_port)
        if killed:
            print(f"Server on port {args.kill_port} has been terminated")
        sys.exit(0 if killed else 1)

    # Default behavior: start a server
    port = args.port

    # Use provided directory or get project root
    if args.directory:
        directory = args.directory
    else:
        directory = get_project_root()

    print(f"Starting server in directory: {directory}")
    run_server_in_background(port, directory)
