FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPYCACHEPREFIX=/tmp/pycache \
    DEBIAN_FRONTEND=noninteractive \
    TZ=Etc/UTC

WORKDIR /workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /workspace/requirements.txt
RUN pip install --no-cache-dir -r /workspace/requirements.txt

# Non-root runtime user.
RUN useradd --create-home --uid 10001 appuser

COPY . /workspace
RUN chown -R appuser:appuser /workspace

USER appuser

CMD ["python", "-m", "app.jobs.scheduler"]
