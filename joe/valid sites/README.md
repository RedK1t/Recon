# Subdomain Validator FastAPI

This API validates subdomains by checking DNS resolution and HTTP/HTTPS availability.

## Installation

```bash
pip install fastapi uvicorn dnspython aiohttp
```

## Running the API

```bash
cd "c:\Users\GAMING.SX401\OneDrive\Desktop\Recon\joe\valid sites"
uvicorn valid_site_api:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoint

### POST /validate

Validates a list of subdomains and returns live HTTP/HTTPS results.

**Request:**
```json
{
  "subs": [
    "example.com",
    "test.example.com",
    "api.example.com"
  ]
}
```

**Response:**
```json
{
  "live_results": [
    {
      "subdomain": "example.com",
      "url": "https://example.com",
      "status": 200
    },
    {
      "subdomain": "api.example.com",
      "url": "https://api.example.com",
      "status": 200
    }
  ],
  "total_subdomains": 3,
  "alive_dns": 2,
  "live_web_services": 2
}
```

## React Example

```javascript
// Example React component
import { useState } from 'react';

function SubdomainValidator() {
  const [subdomains, setSubdomains] = useState([]);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);

  const validateSubdomains = async () => {
    setLoading(true);
    try {
      const response = await fetch('http://localhost:8000/validate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          subs: subdomains
        })
      });
      
      const data = await response.json();
      setResults(data);
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2>Subdomain Validator</h2>
      <textarea
        placeholder="Enter subdomains (one per line)"
        onChange={(e) => setSubdomains(e.target.value.split('\n').filter(s => s.trim()))}
      />
      <button onClick={validateSubdomains} disabled={loading}>
        {loading ? 'Validating...' : 'Validate'}
      </button>
      
      {results && (
        <div>
          <h3>Results</h3>
          <p>Total: {results.total_subdomains}</p>
          <p>Alive DNS: {results.alive_dns}</p>
          <p>Live Web Services: {results.live_web_services}</p>
          
          <h4>Live Services:</h4>
          <ul>
            {results.live_results.map((result, idx) => (
              <li key={idx}>
                <a href={result.url} target="_blank" rel="noopener noreferrer">
                  {result.subdomain}
                </a> - Status: {result.status}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default SubdomainValidator;
```

## Using with Axios

```javascript
import axios from 'axios';

const validateSubdomains = async (subdomainList) => {
  try {
    const response = await axios.post('http://localhost:8000/validate', {
      subs: subdomainList
    });
    return response.data;
  } catch (error) {
    console.error('Validation error:', error);
    throw error;
  }
};

// Usage
const subdomains = ['example.com', 'test.example.com'];
const results = await validateSubdomains(subdomains);
console.log(results.live_results);
```

## API Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
