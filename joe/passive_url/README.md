# Passive URL Discovery API

FastAPI wrapper for passive URL discovery using Waybackurls, Katana, and GoSpider.

## Overview

This API provides endpoints to discover URLs for target domains using passive reconnaissance tools without actively crawling the target websites.

## Features

- **Three URL Discovery Tools**: 
  - **Waybackurls**: Queries Wayback Machine archives (60s timeout)
  - **Katana**: Active shallow crawling with JavaScript support (depth 2, 60s timeout)
  - **GoSpider**: Passive URL discovery
- **Parallel Processing**: Processes multiple domains concurrently using thread pools
- **Smart Filtering**: Automatically filters out common static assets (images, CSS, fonts, etc.)
- **Timeout Protection**: All tools have configurable timeouts to prevent hanging
- **Real-time Updates**: WebSocket support for live progress tracking
- **CORS Enabled**: Ready for integration with React applications

## Installation

### Prerequisites

Make sure you have the following tools installed:
- `waybackurls`
- `katana`
- `gospider`

### Python Dependencies

```bash
pip install -r requirements.txt
```

## Running the API

### Standalone

```bash
python api.py
```

The API will start on `http://0.0.0.0:8002`

### With All APIs

```bash
# From the Recon root directory
python run_all.py
```

## API Endpoints

### 1. Health Check

**GET** `/`

Returns API status and available endpoints.

**Response:**
```json
{
  "status": "online",
  "service": "Passive URL Discovery API",
  "version": "1.0.0",
  "endpoints": {
    "POST /discover": "Discover URLs for domains using passive reconnaissance",
    "WebSocket /ws/discover": "Real-time URL discovery with progress updates"
  }
}
```

### 2. Discover URLs (POST)

**POST** `/discover`

Discover URLs for one or more domains using passive tools.

**Request Body:**
```json
{
  "domains": ["example.com", "test.com"]
}
```

**Response:**
```json
{
  "results": {
    "example.com": {
      "domain": "example.com",
      "urls": [
        "https://example.com/api/users",
        "https://example.com/admin/login",
        "https://example.com/dashboard"
      ],
      "total_urls": 3,
      "error": null
    },
    "test.com": {
      "domain": "test.com",
      "urls": ["https://test.com/api/v1/data"],
      "total_urls": 1,
      "error": null
    }
  },
  "total_domains": 2,
  "successful": 2,
  "failed": 0
}
```

### 3. Discover URLs (WebSocket)

**WebSocket** `/ws/discover`

Real-time URL discovery with progress updates.

**Send:**
```json
{
  "domains": ["example.com", "test.com"]
}
```

**Receive (Progress Updates):**

```json
{
  "type": "status",
  "message": "Starting URL discovery for 2 domain(s)",
  "total": 2,
  "completed": 0
}
```

```json
{
  "type": "progress",
  "current_domain": "example.com",
  "completed": 0,
  "total": 2,
  "percentage": 0.0
}
```

```json
{
  "type": "result",
  "domain": "example.com",
  "data": {
    "domain": "example.com",
    "urls": ["https://example.com/api/users"],
    "total_urls": 1,
    "error": null
  }
}
```

```json
{
  "type": "complete",
  "message": "URL discovery completed",
  "results": { ... },
  "total_domains": 2,
  "successful": 2,
  "failed": 0,
  "total_urls_discovered": 150
}
```

## React Integration Example

### Using Fetch (POST)

```typescript
const discoverURLs = async (domains: string[]) => {
  const response = await fetch('http://localhost:8002/discover', {
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
const results = await discoverURLs(['example.com', 'test.com']);
console.log(results.results['example.com'].urls);
```

### Using WebSocket

```typescript
const ws = new WebSocket('ws://localhost:8002/ws/discover');

ws.onopen = () => {
  ws.send(JSON.stringify({ domains: ['example.com', 'test.com'] }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch (data.type) {
    case 'status':
      console.log(`Status: ${data.message}`);
      break;
    case 'progress':
      console.log(`Processing: ${data.current_domain} (${data.percentage}%)`);
      break;
    case 'result':
      console.log(`Found ${data.data.total_urls} URLs for ${data.domain}`);
      break;
    case 'complete':
      console.log(`Total URLs discovered: ${data.total_urls_discovered}`);
      ws.close();
      break;
    case 'error':
      console.error(`Error: ${data.message}`);
      break;
  }
};
```

## TypeScript Types

```typescript
interface PassiveURLRequest {
  domains: string[];
}

interface PassiveURLResult {
  domain: string;
  urls: string[];
  total_urls: number;
  error: string | null;
}

interface PassiveURLResponse {
  results: {
    [domain: string]: PassiveURLResult;
  };
  total_domains: number;
  successful: number;
  failed: number;
}

// WebSocket message types
type WSMessage = 
  | { type: 'status'; message: string; total: number; completed: number }
  | { type: 'progress'; current_domain: string; completed: number; total: number; percentage: number }
  | { type: 'result'; domain: string; data: PassiveURLResult }
  | { type: 'complete'; message: string; results: { [domain: string]: PassiveURLResult }; total_domains: number; successful: number; failed: number; total_urls_discovered: number }
  | { type: 'error'; message: string };
```

## Filtered Extensions

The API automatically filters out URLs ending with these extensions:
- Images: `.jpg`, `.jpeg`, `.png`, `.gif`, `.svg`, `.ico`
- Styles: `.css`, `.woff`, `.woff2`, `.ttf`, `.eot`
- Media: `.mp4`, `.mp3`, `.avi`, `.mov`, `.webm`
- Archives: `.pdf`, `.zip`, `.rar`, `.7z`
- Source maps: `.map`

## Port Configuration

Default port: **8002**

To change the port, modify the `uvicorn.run()` call in `api.py`:

```python
uvicorn.run(
    app,
    host="0.0.0.0",
    port=YOUR_PORT,  # Change this
    log_level="info"
)
```

## Error Handling

If a domain fails to process, the API will return an error in the result:

```json
{
  "domain": "example.com",
  "urls": [],
  "total_urls": 0,
  "error": "Connection timeout"
}
```

The overall response will still include successful results for other domains.
