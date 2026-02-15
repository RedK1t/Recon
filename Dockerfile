FROM python:3.10.11-slim

WORKDIR /code

RUN apt-get update && apt-get install -y net-tools && rm -rf /var/lib/apt/lists/*

# Install dependencies first to leverage Docker cache
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY . /code/app/

EXPOSE 3003 3004 3005

ENV SUB_DOMAIN_PORT=3003 \
    SERVICE_PORTS_PORT=3004 \
    UNIFIED_API_PORT=3005

# Run Uvicorn directly (standard practice for modern FastAPI)
CMD ["python", "app/run_all.py"]