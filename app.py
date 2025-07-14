import os
import sys
import re
import time
import tempfile
import paramiko
from scp import SCPClient, SCPException
from pathlib import Path
from typing import Optional, Dict, Any

# --- Configuration from Environment Variables ---
# A dictionary to hold config for clarity and easy access.
CONFIG: Dict[str, Any] = {
    "host": os.getenv("INPUT_HOST"),
    "port": int(os.getenv("INPUT_PORT", "22")),
    "user": os.getenv("INPUT_USER"),
    "password": os.getenv("INPUT_PASS"),
    "private_key": os.getenv("INPUT_KEY"),
    "known_hosts": os.getenv("INPUT_KNOWN_HOSTS"), # <-- Security Improvement!
    "connect_timeout": os.getenv("INPUT_CONNECT_TIMEOUT", "30s"),
    "scp_commands": os.getenv("INPUT_SCP"),
    "first_ssh": os.getenv("INPUT_FIRST_SSH"),
    "last_ssh": os.getenv("INPUT_LAST_SSH"),
}

def parse_time_to_seconds(time_str: Optional[str]) -> int:
    """Converts a time string (e.g., '30s', '5m', '1h') to seconds."""
    if not isinstance(time_str, str):
        return 30 # Default value

    time_str = time_str.lower().strip()
    unit_multipliers = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
    
    match = re.match(r'^(\d+)([smhd])$', time_str)
    if not match:
        raise ValueError(f"Invalid time format: '{time_str}'. Use formats like '30s', '5m', '1h'.")

    value, unit = match.groups()
    return int(value) * unit_multipliers[unit]

def expand_path(p_str: Optional[str]) -> Optional[str]:
    """Cleans, strips, and expands environment variables in a path string."""
    if not p_str:
        return None
    
    # More robust stripping
    cleaned_path = p_str.strip().strip("'\"")
    
    # Using pathlib for a more modern object-oriented approach to paths
    if cleaned_path == ".":
        return str(Path.cwd().resolve() / "*")
        
    return os.path.expandvars(cleaned_path)

def execute_remote_commands(ssh_client: paramiko.SSHClient, commands: str, stage_name: str):
    """Executes a block of commands on the remote server and streams the output."""
    print(f"Executing commands for: {stage_name}")
    
    command_list = [line.strip() for line in commands.splitlines() if line.strip() and not line.strip().startswith('#')]
    if not command_list:
        print("No commands to execute.")
        return

    full_command = " && ".join(command_list)
    print(f"--> Running: {full_command}\n")

    # --- REAL-TIME STREAMING LOGIC ---
    # Use invoke_shell() to get an interactive session
    channel = ssh_client.invoke_shell()
    
    # Send the command to the channel
    channel.send(full_command + '\n')
    
    # We need to send an exit command to properly close the shell
    channel.send('exit\n')

    exit_status = -1
    while not channel.closed:
        # Read from stdout
        if channel.recv_ready():
            output = channel.recv(1024).decode('utf-8')
            sys.stdout.write(output)
            sys.stdout.flush()

        # Read from stderr
        if channel.recv_stderr_ready():
            error = channel.recv_stderr(1024).decode('utf-8')
            sys.stderr.write(error)
            sys.stderr.flush()
        
        # Check if the command has finished
        if channel.exit_status_ready():
            exit_status = channel.recv_exit_status()
            break
        
        time.sleep(0.1) # Small sleep to prevent busy-waiting

    # Final check for any remaining output
    while channel.recv_ready():
        sys.stdout.write(channel.recv(1024).decode('utf-8'))
        sys.stdout.flush()

    while channel.recv_stderr_ready():
        sys.stderr.write(channel.recv_stderr(1024).decode('utf-8'))
        sys.stderr.flush()
    
    # --- END OF STREAMING LOGIC ---

    if exit_status != 0:
        print(f"\n🚨 Command failed with exit status: {exit_status}")
        sys.exit(1)
    
    print("\n" + "-" * 20)


def perform_scp_transfer(ssh_client: paramiko.SSHClient, scp_def: str):
    """Parses SCP definitions and transfers files."""
    copy_jobs = []
    for line in scp_def.splitlines():
        stripped_line = line.strip()
        # IMPROVEMENT: Ignore empty lines and comments starting with '#'
        if not stripped_line or stripped_line.startswith('#'):
            continue

        if "=>" not in stripped_line:
            print(f"⚠️ SCP Ignored (missing '=>'): {stripped_line}")
            continue
        
        local_part, remote_part = [part.strip() for part in stripped_line.split("=>", 1)]
        local_path = expand_path(local_part)
        remote_path = expand_path(remote_part)

        if local_path and remote_path:
            copy_jobs.append({"local": local_path, "remote": remote_path})
        else:
            print(f"⚠️ SCP Ignored (invalid path): {stripped_line}")

    if not copy_jobs:
        print("No valid SCP jobs found.")
        return
        
    # Progress bar callback
    def progress(filename, size, sent):
        # FIX: The 'filename' from scp is bytes, so we must decode it to a string.
        filename_str = filename.decode('utf-8', 'replace')
        percent_done = float(sent) / float(size) * 100
        # Now we use the decoded string with Path()
        sys.stdout.write(f"\r  -> Uploading {Path(filename_str).name}: {percent_done:.2f}%")
        sys.stdout.flush()

    try:
        # Re-using the existing transport is key!
        with SCPClient(ssh_client.get_transport(), progress=progress) as scp:
            for job in copy_jobs:
                local, remote = job["local"], job["remote"]
                
                # Ensure remote directory exists
                ssh_client.exec_command(f"mkdir -p {remote}")
                
                # Pathlib makes globbing cleaner
                files_to_copy = list(Path().glob(local))
                if not files_to_copy:
                    print(f"\n⚠️ No local files found matching: {local}")
                    continue

                for file_path in files_to_copy:
                    scp.put(str(file_path), remote_path=remote, recursive=True)
                    print(f"\n✅ Copied: {file_path.name} -> {remote}")

    except SCPException as e:
        print(f"\n🚨 SCP Error: Failed to copy files. Details: {e}")
        sys.exit(1)


def main():
    """Main execution function."""
    if not CONFIG["host"] or not CONFIG["user"]:
        print("🚨 Error: Host and User must be provided.")
        sys.exit(1)

    if not CONFIG["private_key"] and not CONFIG["password"]:
        print("🚨 Error: You must provide an SSH Key or a Password.")
        sys.exit(1)
    
    # --- Single, Reusable Connection Block ---
    # Using with statements ensures resources are closed automatically.
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as key_file, \
         tempfile.NamedTemporaryFile(mode='w+', delete=False) as known_hosts_file:
        
        pkey = None
        if CONFIG["private_key"]:
            key_file.write(CONFIG["private_key"])
            key_file.flush()
            pkey = paramiko.RSAKey.from_private_key_file(key_file.name)
            
        known_hosts_path = None
        if CONFIG["known_hosts"]:
            known_hosts_file.write(CONFIG["known_hosts"])
            known_hosts_file.flush()
            known_hosts_path = known_hosts_file.name

        ssh = paramiko.SSHClient()
        
        # This is the SECURE way. It will fail if the host key is not in known_hosts.
        # It prevents Man-in-the-Middle (MITM) attacks.
        ssh.load_system_host_keys()
        if known_hosts_path:
            ssh.load_host_keys(known_hosts_path)
        
        try:
            print(f"Connecting to {CONFIG['user']}@{CONFIG['host']}...")
            ssh.connect(
                hostname=CONFIG["host"],
                port=CONFIG["port"],
                username=CONFIG["user"],
                password=CONFIG["password"],
                pkey=pkey,
                timeout=parse_time_to_seconds(CONFIG["connect_timeout"]),
            )
            print("Connection successful! ✨\n")

            # --- Pipeline Execution using ONE connection ---
            if CONFIG["first_ssh"]:
                print("+++++++++++++++++++ Pipeline: RUNNING FIRST SSH +++++++++++++++++++")
                execute_remote_commands(ssh, CONFIG["first_ssh"], "pre-scp")

            if CONFIG["scp_commands"]:
                print("\n+++++++++++++++++++++ Pipeline: RUNNING SCP +++++++++++++++++++++")
                perform_scp_transfer(ssh, CONFIG["scp_commands"])

            if CONFIG["last_ssh"]:
                print("\n++++++++++++++++++++ Pipeline: RUNNING LAST SSH +++++++++++++++++++")
                execute_remote_commands(ssh, CONFIG["last_ssh"], "post-scp")

        except Exception as e:
            print(f"🚨 An error occurred: {e}")
            sys.exit(1)
        finally:
            print("\nClosing connection.")
            ssh.close()
            os.unlink(key_file.name)
            os.unlink(known_hosts_file.name)
            
    print("\nPipeline finished successfully! 🎉")


if __name__ == '__main__':
    main()
