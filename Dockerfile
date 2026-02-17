FROM python:3.10.11-slim

WORKDIR /code

# Install system dependencies including nmap, net-tools, and build tools
RUN apt-get update && apt-get install -y \
    nmap \
    net-tools \
    git \
    wget \
    ca-certificates \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install modern Go version (1.21)
RUN wget -q https://go.dev/dl/go1.21.6.linux-amd64.tar.gz && \
    tar -C /usr/local -xzf go1.21.6.linux-amd64.tar.gz && \
    rm go1.21.6.linux-amd64.tar.gz

# Set Go environment variables
ENV GOPATH=/root/go
ENV PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/local/go/bin:/root/go/bin"

# Install Go tools needed by the APIs
RUN go install github.com/tomnomnom/waybackurls@latest && \
    go install github.com/projectdiscovery/katana/cmd/katana@latest && \
    go install github.com/jaeles-project/gospider@latest && \
    ls -la /root/go/bin/ && \
    waybackurls -h && \
    gospider -h && \
    katana -h

# Install dependencies first to leverage Docker cache
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Also install requirements from subdirectories
COPY ./joe/passive_url/requirements.txt /code/joe/passive_url/requirements.txt
COPY ./joe/fuzzing-endpoints/requirements.txt /code/joe/fuzzing-endpoints/requirements.txt
RUN pip install --no-cache-dir -r /code/joe/passive_url/requirements.txt && \
    pip install --no-cache-dir -r /code/joe/fuzzing-endpoints/requirements.txt

# Install urless (Python tool from xnl-h4ck3r)
RUN pip install --no-cache-dir urless

COPY . /code/app/

EXPOSE 3003 3004 3005

ENV SUB_DOMAIN_PORT=3003 \
    SERVICE_PORTS_PORT=3004 \
    UNIFIED_API_PORT=3005 \
    CORS_ORIGIN=* \
    PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/local/go/bin:/root/go/bin"

# Run Uvicorn directly (standard practice for modern FastAPI)
CMD ["python", "app/run_all.py"]
