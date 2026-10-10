FROM postgres:18.6-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends python3 && rm -rf /var/lib/apt/lists/*
COPY docker/backup.py /backup-tool.py
COPY docs/llm_model.json /model-pins.json
COPY backend/app/embedding.py /embedding-pins.py
ENTRYPOINT ["python3", "/backup-tool.py"]
