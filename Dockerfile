FROM python:3.10-slim

WORKDIR /app

# system deps
RUN apt-get update && apt-get install -y --no-install-recommends build-essential git && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

CMD ["python", "-m", "console.app"]
# ==============================================================================
# PIPELINE STEP: CONTAINERIZED ENGINE RUNTIME SPECIFICATION (Dockerfile)
# ==============================================================================
# Operational Goal: Construct a reproducible, isolated runtime environment for the
# Edge-TF Disclosure Agent Engine, incorporating deterministic C-based optimization
# solvers (OSQP, SCS, ECOS), network graph libraries, Streamlit console, and 
# unprivileged security execution.
# ==============================================================================

def generate_dockerfile_specification() -> dict:
    """
    Returns the architectural blueprint for the containerized engine runtime.
    """
    return {
        "base_image": "python:3.11-slim-bookworm",
        "system_dependencies": [
            "gcc", "g++", "gfortran", "libopenblas-dev", "liblapack-dev", "curl"
        ],
        "workdir": "/app",
        "exposed_ports": {
            "console_ui": 8501,     # Streamlit Operator Console
            "service_api": 8000     # FastAPI / Healthcheck Endpoint
        },
        "execution_security": "non-root (edgetf:edgetf)",
        "entrypoint": "uvicorn / streamlit console runner"
    }
