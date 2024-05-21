# Python version can be changed, e.g.
# FROM python:3.8
# FROM ghcr.io/mamba-org/micromamba:1.5.1-focal-cuda-11.3.1
FROM docker.io/python:latest

LABEL org.opencontainers.image.authors="FNNDSC <dev@babyMRI.org>" \
      org.opencontainers.image.title="A ChRIS plugin to analyze the result produced by an LLD analysis " \
      org.opencontainers.image.description="A ChRIS plugin to analyze the result produced by an LLD analysis "

ARG SRCDIR=/usr/local/src/pl-lld_chxr
WORKDIR ${SRCDIR}

COPY requirements.txt .
RUN --mount=type=cache,sharing=private,target=/root/.cache/pip pip install -r requirements.txt
RUN apt-get update ; apt-get install docker.io -y ; bash

COPY . .
ARG extras_require=none
RUN pip install ".[${extras_require}]" \
    && cd / && rm -rf ${SRCDIR}
WORKDIR /

CMD ["lld_chxr"]
