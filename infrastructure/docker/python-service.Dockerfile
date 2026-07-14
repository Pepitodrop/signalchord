FROM python:3.12.11-slim@sha256:47ae396f09c1303b8653019811a8498470603d7ffefc29cb07c88f1f8cb3d19f
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /workspace
RUN useradd --create-home --uid 10001 signalchord
COPY services/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --requirement /tmp/requirements.txt
COPY services/ /workspace/services/
COPY velato/ /workspace/velato/
USER signalchord
