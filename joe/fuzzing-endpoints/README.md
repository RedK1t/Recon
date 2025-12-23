# Fuzzing Endpoints

A powerful, asynchronous directory and endpoint fuzzer designed for security researchers and developers. This tool features intelligent redirect handling, baseline detection to filter false positives, and generates a hierarchical (tree-like) JSON output for easy visualization.

## Features

- **Asynchronous Execution**: Built with `asyncio` and `aiohttp` for high-speed fuzzing.
- **Intelligent Redirect Handling**: Automatically detects and follows redirect chains, mapping fuzzed results to the final destination.
- **Hierarchical Output**: Results are organized into a nested JSON structure (folders and files) with unique IDs for each node.
- **Baseline Detection**: Filters out junk responses by establishing a baseline for 404/not-found pages.
- **FastAPI Integration**: Includes a production-ready API to trigger fuzzing jobs programmatically.

## Installation

1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install aiohttp tqdm colorama fastapi uvicorn
   ```

## Usage

### CLI

You can run the fuzzer directly from the command line:

```bash
python fuzzing.py
```

*Note: Ensure `endpoints.txt` and a target list (like `live_http.json`) are present in the directory.*

### API

Start the FastAPI server:

```bash
python api.py
```

#### API Endpoints

- **POST `/fuzz`**: Trigger a fuzzing job.
  - **Body**:
    ```json
    {
      "domains": ["example.com", "api.example.com"],
      "endpoints": ["public", "api/v1"]
    }
    ```
  - **Normalization**: Domains without a protocol will automatically default to `https://`.
  - **Response**: A hierarchical JSON tree of discovered endpoints.

## File Structure

- `fuzzing.py`: Core fuzzing logic and result tree builder.
- `api.py`: FastAPI implementation.
- `endpoints.txt`: Default wordlist for fuzzing.
- `raft-medium-directories.txt`: Extended wordlist for directory discovery.
- `raft-medium-files.txt`: Extended wordlist for file discovery.

## Output Format

The tool generates a JSON structure like this:

```json
{
  "data": [
    {
      "id": "uuid-v4",
      "url": "https://example.com",
      "children": [
        {
          "id": "uuid-v4",
          "url": "https://example.com/api",
          "status": 200,
          "children": [...]
        }
      ]
    }
  ]
}
```
