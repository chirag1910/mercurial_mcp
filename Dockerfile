FROM python:3.11-slim

# Install system dependencies
# mercurial: for hg commands
# git: as a common dependency
# php-cli, php-curl, php-json, php-mbstring: required for arcanist
RUN apt-get update && apt-get install -y \
    mercurial \
    git \
    php-cli \
    php-curl \
    php-json \
    php-mbstring \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app/mercurial_mcp

# Copy requirements FIRST to cache dependencies
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create directories for mounts
RUN mkdir -p /app/repo /app/arcanist

# Copy local code to container
COPY . .

# Update ENV variables
ENV HG_REPO_ROOT="/app/repo"
ENV PATH="/app/arcanist/bin:${PATH}"
ENV TOKEN_LIMIT=${TOKEN_LIMIT}
ENV PYTHONUNBUFFERED=1

CMD ["python", "server.py"]
