# SSH-SCP-SSH Pipeline Action
A modern, secure, and efficient GitHub Action that connects to a remote server to perform a sequence of operations:

1. Execute initial SSH commands.
2. Copy files/directories securely using SCP.
3. Execute final SSH commands.

This action is built with security and efficiency as top priorities, using a single, persistent SSH connection for all stages.

## Why Use This Action?
While there are many ways to SSH into a server, this action is designed to be robust and secure for automated CI/CD environments.

⚡ **Efficient:** It establishes one single SSH connection and reuses it for all operations. This is significantly faster and less resource-intensive than actions that reconnect for every step.

🛡️ **Secure by Default:** It forces you to verify the server's identity using its known_hosts public key. This prevents Man-in-the-Middle (MITM) attacks, a critical vulnerability that many simpler scripts ignore.

📦 **Self-Contained:** Built on a pure-Python SSH implementation (paramiko), it doesn't rely on system-level SSH clients, leading to a smaller and more reliable container.

**Modern:** Uses modern Python features and a slim, up-to-date Docker base image for better performance and security.

## Usage
Here is an example workflow that runs on every push to the main branch. It connects to a server, copies the README.md file, and then lists the contents of the remote directory.

First, you must add your server credentials as secrets in your repository settings.

Required Secrets
- **SSH_HOST:** The IP address or hostname of your server.
- **SSH_USER:** The username to connect with.
- **SSH_PRIVATE_KEY:** The private SSH key for authentication.
- **SSH_KNOWN_HOSTS:** The public key of the server. You can get this by running ssh-keyscan your server ip on your local machine.

Example Workflow: ```.github/workflows/deploy.yml```
```yaml
name: Deploy to Server

on:
  push:
    branches:
      - main
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Run SSH/SCP Pipeline
        uses: YourGitHubUsername/your-action-repo-name@v2 # Use your action's repo and version
        with:
          # --- Connection Details (from Secrets) ---
          host: ${{ secrets.SSH_HOST }}
          user: ${{ secrets.SSH_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          known_hosts: ${{ secrets.SSH_KNOWN_HOSTS }}

          # --- Pipeline Commands ---
          first_ssh: |
            echo "Starting deployment..."
            echo "Connected from a GitHub Actions runner!"

          scp: |
            # Copy build artifacts or other files
            # Format: 'local/path => remote/path'
            README.md => /tmp/

          last_ssh: |
            echo "File transfer complete."
            echo "Verifying file on remote server:"
            ls -l /tmp/README.md
```

## Inputs
The following inputs can be used to configure the action:

| Input         | Description                                                                                       | Required | Default    |
|---------------|---------------------------------------------------------------------------------------------------|----------|------------|
| host          | Remote server hostname or IP address.                                                            | true     |            |
| port          | SSH port on the remote server.                                                                   | false    | 22         |
| user          | SSH username for the remote server.                                                              | true     |            |
| key           | The SSH private key content for authentication. (Use a secret!)                                   | false    |            |
| pass          | The SSH password for authentication. (Use a secret!)                                              | false    |            |
| known_hosts   | The public host key of the remote server to prevent MITM attacks. (Use a secret!)                  | true     |            |
| connect_timeout| Connection timeout. Use 's' for seconds, 'm' for minutes. Ex: '60s' or '1m'.                       | false    | 30s        |
| first_ssh     | Multiline block of shell commands to run before the SCP transfer.                                  | false    |            |
| scp           | Multiline block of files/directories to copy. Format: 'local/path => remote/path'                  | false    |            |
| last_ssh      | Multiline block of shell commands to run after the SCP transfer.                                   | false    |            |

## Local Development & Testing
You can test this action locally without needing to push to GitHub.
1. Build the Docker image:
```docker build -t ssh-action-test .```
2. Run the container with environment variables:
Simulate the GitHub Actions environment by passing inputs as INPUT_ prefixed environment variables.

```bash
docker run --rm \
  -e INPUT_HOST='YOUR_SERVER_IP' \
  -e INPUT_PORT='22' \
  -e INPUT_USER='YOUR_USERNAME' \
  -e INPUT_KEY="$(cat ~/.ssh/id_rsa)" \
  -e INPUT_KNOWN_HOSTS="$(ssh-keyscan YOUR_SERVER_IP)" \
  -e "INPUT_FIRST_SSH=echo 'Hello from a local test!'" \
  -e "INPUT_SCP=./README.md => /tmp/" \
  -e "INPUT_LAST_SSH=ls -l /tmp/" \
  ssh-action-test
```