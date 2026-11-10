# Sandbox image used by the evaluator's "docker" execution mode.
# Build from the repository root:
#   docker build -t acb-evaluator:1.0 -f docker/evaluator.Dockerfile .
# The image contains only Python and pytest. Submitted code and hidden tests are bind-mounted at
# run time into /work; the container runs with --network none, a read-only root filesystem,
# no capabilities and a non-root user (see evaluator/runner.py).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN pip install "pytest==8.3.5" \
 && useradd --uid 10001 --create-home --shell /usr/sbin/nologin runner

USER 10001:10001
WORKDIR /work
CMD ["python", "-c", "import pytest, sys; print(sys.version, pytest.__version__)"]
