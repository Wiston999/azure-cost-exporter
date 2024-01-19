FROM python:3.12-slim-bookworm as compile-image
RUN apt-get update
RUN apt-get install -y --no-install-recommends build-essential gcc

RUN python -m venv /opt/venv
# Make sure we use the virtualenv:
ENV PATH="/opt/venv/bin:$PATH"

COPY . .
RUN pip install .

FROM python:3.12-slim-bookworm AS build-image
COPY --from=compile-image /opt/venv /opt/venv

# Make sure we use the virtualenv:
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED 1
ENTRYPOINT ["azure-cost-exporter"]
