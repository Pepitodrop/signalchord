FROM python:3.12.13-slim-bookworm@sha256:d50fb7611f86d04a3b0471b46d7557818d88983fc3136726336b2a4c657aa30b
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/workspace/services
WORKDIR /workspace
RUN apt-get update \
 && apt-get upgrade -y \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 10001 signalchord
COPY services/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --requirement /tmp/requirements.txt
COPY services/ /workspace/services/
COPY velato/ /workspace/velato/
USER signalchord
