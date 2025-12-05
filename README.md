# Subdomain Enumerator API

A FastAPI-based REST API for subdomain enumeration with passive and active scanning capabilities.
Python version: 3.13.7
## Features

- 🚀 Fast concurrent subdomain enumeration
- 🔍 Passive enumeration via crt.sh (certificate transparency logs)
- 🎯 Active DNS resolution with customizable wordlists
- 📊 Multiple preset wordlists (top1k, top10k, top25k, top50k, top100k)
- 🌐 CORS-enabled for React/frontend integration
- 📝 Full API documentation via Swagger UI

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Ensure you have wordlist files in the same directory:
   - `top1k.txt`
   - `top10k.txt`
   - `top25k.txt`
   - `top50k.txt`
   - `top100k.txt`

## Running the API

### Development Server

```bash
uvicorn api:app --reload
```

The API will be available at `http://localhost:8000`

### Production Server

```bash
uvicorn api:app --host 0.0.0.0 --port 8000 --workers 4
```

### Custom Host/Port

```bash
uvicorn api:app --host 0.0.0.0 --port 3001
```

## API Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### 1. Get Available Presets

**GET** `/api/presets`

Returns list of available wordlist presets.

**Response:**
```json
{
  "presets": [
    {"id": "1", "name": "top1k", "filename": "top1k.txt"},
    {"id": "2", "name": "top10k", "filename": "top10k.txt"}
  ]
}
```

### 2. Passive Enumeration

**POST** `/api/passive`

Fetch subdomains from certificate transparency logs (crt.sh).

**Request:**
```json
{
  "domain": "example.com"
}
```

**Response:**
```json
{
  "count": 15,
  "subdomains": [
    "www.example.com",
    "mail.example.com",
    "api.example.com"
  ]
}
```

### 3. Active Enumeration

**POST** `/api/enumerate`

Perform active DNS resolution with optional passive enumeration.

**Request:**
```json
{
  "domain": "example.com",
  "wordlist_preset": "1",
  "passive": false,
  "timeout": 5.0,
  "threads": 30
}
```

**Parameters:**
- `domain` (required): Target domain to enumerate
- `wordlist_preset` (optional): Preset ID (1-6), default: "1"
- `custom_wordlist` (optional): Path to custom wordlist file
- `passive` (optional): Enable passive enumeration, default: false
- `timeout` (optional): DNS timeout in seconds (0.1-30.0), default: 5.0
- `threads` (optional): Number of concurrent threads (1-100), default: 30

**Response:**
```json
{
  "count": 5,
  "subdomains": [
    {
      "host": "www.example.com",
      "ips": ["93.184.216.34"]
    },
    {
      "host": "mail.example.com",
      "ips": ["93.184.216.35"]
    }
  ],
  "elapsed_time": 12.45
}
```

### 4. Health Check

**GET** `/health`

Check if the API is running.

**Response:**
```json
{
  "status": "healthy"
}
```

## React Integration Examples

### Using Fetch API

```javascript
// Get presets
async function getPresets() {
  const response = await fetch('http://localhost:8000/api/presets');
  const data = await response.json();
  return data.presets;
}

// Passive enumeration
async function passiveEnumerate(domain) {
  const response = await fetch('http://localhost:8000/api/passive', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ domain }),
  });
  return await response.json();
}

// Active enumeration
async function enumerate(domain, options = {}) {
  const response = await fetch('http://localhost:8000/api/enumerate', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      domain,
      wordlist_preset: options.preset || '1',
      passive: options.passive || false,
      timeout: options.timeout || 5.0,
      threads: options.threads || 30,
    }),
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail);
  }
  
  return await response.json();
}
```

### Using Axios

```javascript
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

// Create axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Get presets
export const getPresets = async () => {
  const { data } = await api.get('/api/presets');
  return data.presets;
};

// Passive enumeration
export const passiveEnumerate = async (domain) => {
  const { data } = await api.post('/api/passive', { domain });
  return data;
};

// Active enumeration
export const enumerate = async (domain, options = {}) => {
  const { data } = await api.post('/api/enumerate', {
    domain,
    wordlist_preset: options.preset || '1',
    passive: options.passive || false,
    timeout: options.timeout || 5.0,
    threads: options.threads || 30,
  });
  return data;
};
```

### React Component Example

```jsx
import React, { useState } from 'react';

function SubdomainScanner() {
  const [domain, setDomain] = useState('');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleScan = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('http://localhost:8000/api/enumerate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          domain,
          wordlist_preset: '1',
          passive: true,
          threads: 50,
        }),
      });
      
      if (!response.ok) {
        throw new Error('Scan failed');
      }
      
      const data = await response.json();
      setResults(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <input
        type="text"
        value={domain}
        onChange={(e) => setDomain(e.target.value)}
        placeholder="Enter domain (e.g., example.com)"
      />
      <button onClick={handleScan} disabled={loading}>
        {loading ? 'Scanning...' : 'Scan'}
      </button>
      
      {error && <div className="error">{error}</div>}
      
      {results && (
        <div>
          <h3>Found {results.count} subdomains in {results.elapsed_time.toFixed(2)}s</h3>
          <ul>
            {results.subdomains.map((sub, idx) => (
              <li key={idx}>
                {sub.host} → {sub.ips.join(', ')}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default SubdomainScanner;
```

## CORS Configuration

The API is configured to allow all origins by default. For production, update the CORS settings in `api.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-react-app.com"],  # Specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## CLI Usage (Original)

The original CLI interface is still available via `main.py`:

```bash
# Interactive mode
python main.py

# With arguments
python main.py -d example.com -w top1k.txt --passive -T 50

# Help
python main.py --help
```

## Error Handling

The API returns standard HTTP status codes:

- `200`: Success
- `400`: Bad request (invalid parameters)
- `404`: Resource not found (e.g., wordlist file)
- `500`: Internal server error

Error responses include a `detail` field with the error message:

```json
{
  "detail": "Wordlist not found: custom.txt"
}
```

## Performance Tips

1. **Adjust thread count**: Increase `threads` for faster scanning (default: 30, max: 100)
2. **Set appropriate timeout**: Lower timeout for faster scans, higher for reliability
3. **Use smaller wordlists**: Start with top1k for quick results
4. **Combine passive + active**: Use `passive: true` to discover more subdomains

## License

This project is provided as-is for educational and security research purposes.


## This is for Joe

```bash
pip freeze > requirements.txt
```