# Service Ports Scanner API

A FastAPI-based REST and WebSocket API for scanning domains and discovering open ports and services using nmap.

## Features

- **REST API**: Scan multiple domains and get complete results
- **WebSocket API**: Real-time scanning with progress updates
- **Service Detection**: Identifies services and versions running on open ports
- **CORS Enabled**: Ready to use with React applications

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Make sure nmap is installed on your system:
   - **Windows**: Download from https://nmap.org/download.html
   - **Linux**: `sudo apt-get install nmap`
   - **macOS**: `brew install nmap`

## Running the API

Start the API server:
```bash
python api.py
```

Or use uvicorn directly:
```bash
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

## API Documentation

Once running, visit:
- **Interactive API docs**: http://localhost:8000/docs
- **Alternative docs**: http://localhost:8000/redoc

## Endpoints

### 1. Health Check
```
GET /
```

Returns API status and available endpoints.

### 2. Scan Domains (REST)
```
POST /scan
Content-Type: application/json

{
  "domains": ["example.com", "google.com"]
}
```

**Response:**
```json
{
  "results": {
    "example.com": {
      "ip": "93.184.216.34",
      "state": "up",
      "ports": [
        {
          "port": 80,
          "protocol": "tcp",
          "state": "open",
          "service": "http",
          "service_version": "Apache 2.4.1"
        }
      ]
    }
  },
  "total_domains": 2,
  "successful_scans": 1,
  "failed_scans": 1
}
```

### 3. Scan Domains (WebSocket)
```
WebSocket: ws://localhost:8000/ws/scan
```

**Send:**
```json
{
  "domains": ["example.com", "google.com"]
}
```

**Receive (multiple messages):**

Progress update:
```json
{
  "type": "progress",
  "current_domain": "example.com",
  "completed": 0,
  "total": 2,
  "percentage": 0
}
```

Individual result:
```json
{
  "type": "result",
  "domain": "example.com",
  "data": {
    "ip": "93.184.216.34",
    "state": "up",
    "ports": [...]
  }
}
```

Completion:
```json
{
  "type": "complete",
  "message": "Scan completed",
  "results": {...},
  "total_domains": 2,
  "successful_scans": 1,
  "failed_scans": 1
}
```

## React Integration Example

### REST API Example
```javascript
const scanDomains = async (domains) => {
  const response = await fetch('http://localhost:8000/scan', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ domains }),
  });
  
  const data = await response.json();
  return data;
};

// Usage
scanDomains(['example.com', 'google.com'])
  .then(results => console.log(results));
```

### WebSocket Example
```javascript
const scanDomainsRealtime = (domains, onProgress, onResult, onComplete) => {
  const ws = new WebSocket('ws://localhost:8000/ws/scan');
  
  ws.onopen = () => {
    ws.send(JSON.stringify({ domains }));
  };
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    switch(data.type) {
      case 'progress':
        onProgress(data);
        break;
      case 'result':
        onResult(data);
        break;
      case 'complete':
        onComplete(data);
        ws.close();
        break;
      case 'error':
        console.error(data.message);
        ws.close();
        break;
    }
  };
  
  ws.onerror = (error) => {
    console.error('WebSocket error:', error);
  };
  
  return ws;
};

// Usage
scanDomainsRealtime(
  ['example.com', 'google.com'],
  (progress) => console.log(`Progress: ${progress.percentage}%`),
  (result) => console.log(`Result for ${result.domain}:`, result.data),
  (complete) => console.log('All scans complete:', complete)
);
```

## Original Functionality

The original `main.py` script remains unchanged and can still be run standalone:
```bash
python main.py
```

This will read domains from `subs.json` and save results to `scan_results.json`.

## Notes

- Nmap scans require appropriate permissions. Some scans may need administrator/root privileges.
- The API uses `--top-ports 2000 -sV` for comprehensive service detection.
- Scans can take time depending on the number of domains and ports.
- For production use, update CORS settings to restrict origins to your React app's domain.
