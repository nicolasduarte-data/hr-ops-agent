# HF Spaces runs the container as non-root uid 1000. BGE-M3 needs to
# write at runtime: the model cache (~/.cache/huggingface, ~2.2 GB) and the
# ChromaDB index it builds (data/retrieval_index/). Both fail with PermissionError
# unless HOME is writable and /app is owned by the runtime user. (v0.1–v0.3 ran
# keyword-only with no writes, so this never surfaced until the retrieval deps
# landed.)
FROM python:3.11-slim

# Create the uid-1000 user HF Spaces runs as, with a writable home.
RUN useradd -m -u 1000 user

WORKDIR /app

# Install deps as root → system-wide (streamlit on PATH for all users).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app, then hand /app to the runtime user so it can write data/.
COPY . .
RUN chown -R user:user /app

USER user

# HF_HOME points the HuggingFace model cache at the user's writable home so the
# BGE-M3 weight download succeeds on the non-root runtime.
ENV HOME=/home/user \
    HF_HOME=/home/user/.cache/huggingface \
    PATH=/home/user/.local/bin:$PATH

EXPOSE 7860

CMD ["streamlit", "run", "app.py", \
     "--server.port=7860", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
