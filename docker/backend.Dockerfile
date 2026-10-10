FROM python:3.12.14-slim-bookworm AS ocr-build
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl g++ make autoconf automake libtool pkg-config libleptonica-dev && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL https://github.com/tesseract-ocr/tesseract/archive/refs/tags/5.4.0.tar.gz -o /tmp/tesseract.tar.gz && echo '30ceffd9b86780f01cbf4eaf9b7fc59abddfcbaf5bbd52f9a633c6528cb183fd  /tmp/tesseract.tar.gz' | sha256sum -c - && tar -xf /tmp/tesseract.tar.gz -C /tmp && cd /tmp/tesseract-5.4.0 && ./autogen.sh && ./configure --disable-openmp --disable-static --without-curl && make -j2 && make install

FROM ollama/ollama:0.17.1 AS ollama
FROM python:3.12.14-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates liblept5 libgomp1 libstdc++6 && rm -rf /var/lib/apt/lists/*
COPY --from=ocr-build /usr/local/bin/tesseract /usr/local/bin/tesseract
COPY --from=ocr-build /usr/local/lib/libtesseract.so* /usr/local/lib/
COPY --from=ollama /bin/ollama /usr/local/bin/ollama
COPY --from=ollama /usr/lib/ollama /usr/lib/ollama
RUN ldconfig && useradd --uid 10001 --create-home app && mkdir -p /state/data /state/models /state/vectors /state/ollama /state/ocr /state/locks && chown -R app:app /state
WORKDIR /app
COPY backend/requirements.lock /app/backend/requirements.lock
RUN python -m pip install --no-cache-dir pip==26.2 && python -m pip install --no-cache-dir -r backend/requirements.lock && python -m pip check
COPY docker/requirements-linux.lock docker/check_lock.py /app/docker/
RUN python -m pip install --no-cache-dir --no-deps -r docker/requirements-linux.lock && python docker/check_lock.py && python -m pip check
# Keep the recovered dependency layers reusable; complete the official runtime layout afterward.
RUN apt-get update && apt-get install -y --no-install-recommends libopenblas0 libvulkan1 && rm -rf /var/lib/apt/lists/* && mv /usr/local/bin/ollama /usr/bin/ollama
COPY --chown=app:app backend /app/backend
COPY --chown=app:app docs/llm_model.json docs/SOURCES.md /app/docs/
COPY --chown=app:app docker /app/docker
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HOME=/tmp PYTHONPATH=/app/backend NVIDIA_DRIVER_CAPABILITIES=compute,utility NVIDIA_VISIBLE_DEVICES=all
USER app
ENTRYPOINT ["python", "docker/entrypoint.py"]
CMD ["api"]
