# Hugging Face Spaces (Docker SDK) — serves the React + FastAPI app on port 7860.
# The app.py Streamlit/Tornado proxy is NOT used here; we run the FastAPI app
# (src.app.api:app) directly, which serves the React build at / and the API at /api.
FROM python:3.12-slim

# libgomp1 is the OpenMP runtime required by xgboost at import time.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the project (respects .dockerignore)
COPY . .

# HF Spaces routes external traffic to this port (matches app_port in README).
EXPOSE 7860

# API keys are provided as HF Space secrets -> environment variables
# (GEMINI_API_KEYS / GROQ_API_KEYS), which src/extraction/llm_provider.py reads.
CMD ["python", "-m", "uvicorn", "src.app.api:app", "--host", "0.0.0.0", "--port", "7860"]
