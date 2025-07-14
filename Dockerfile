# Stage 1: Builder - Install dependencies
# Use a modern, secure base image. Python 3.12 is way faster.
FROM python:3.12-bookworm AS builder

# Set the working directory
WORKDIR /app

# Install only the build dependencies needed.
# --no-install-recommends keeps it minimal.
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libc-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy only the requirements file to leverage Docker cache
COPY requirements.txt .

# Install python dependencies into a specific folder
# Using --no-cache-dir reduces image size.
RUN pip install --no-cache-dir --prefix="/install" -r requirements.txt


# Stage 2: Final Image - The lean, mean, running machine
FROM python:3.12-bookworm

# Create a non-root user for better security
RUN useradd --create-home appuser
WORKDIR /home/appuser

# Copy installed packages from the builder stage
COPY --from=builder /install /usr/local

# Copy the application code and the entrypoint script
COPY app.py .
COPY entrypoint.sh .

# Make entrypoint executable and change ownership
RUN chmod +x entrypoint.sh && chown -R appuser:appuser /home/appuser

# Switch to the non-root user
USER appuser

# Set the entrypoint
ENTRYPOINT ["./entrypoint.sh"]

# Add labels for GitHub Actions
LABEL "maintainer"="Kangketik <pratamapriadi96@gmail.com>"
LABEL "repository"="https://github.com/cross-the-world/ssh-scp-ssh-pipelines"
LABEL "com.github.actions.name"="ssh-scp-ssh-pipelines"
LABEL "com.github.actions.description"="Pipeline: ssh -> scp -> ssh"
LABEL "com.github.actions.icon"="terminal"
LABEL "com.github.actions.color"="gray-dark"