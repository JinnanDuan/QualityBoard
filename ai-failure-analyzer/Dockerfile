# AIFA：与 dt-report 使用相同基础镜像（ubuntu:20.04）、同一 docker/sources.list、同一套 apt 安装 Python 的方式
#（系统 python3 为 focal 自带版本，当前为 3.8.x；应用代码兼容 3.8+，见 pyproject.toml）。
#
# 构建必须在仓库根目录执行：
#   docker build -f ai-failure-analyzer/Dockerfile -t aifa:a1 .
#
# 可选 build-arg（与根目录 Dockerfile 对齐）：HTTP_PROXY、HTTPS_PROXY、NO_PROXY、PIP_INDEX_URL、PIP_TRUSTED_HOST

FROM ubuntu:20.04

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ARG PIP_INDEX_URL
ARG PIP_TRUSTED_HOST

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Etc/UTC \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

COPY docker/sources.list /etc/apt/sources.list

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        python3 \
        python3-pip \
        python3-venv \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY ai-failure-analyzer/requirements.txt .
RUN PIP_TRUST=() \
    && if [ -n "${PIP_TRUSTED_HOST}" ]; then PIP_TRUST=(--trusted-host "${PIP_TRUSTED_HOST}"); fi \
    && if [ -n "${PIP_INDEX_URL}" ]; then \
         echo "[docker build] 使用内网 PyPI: ${PIP_INDEX_URL}"; \
         pip install --no-cache-dir --upgrade --default-timeout=180 --retries=5 "${PIP_TRUST[@]}" -i "${PIP_INDEX_URL}" "pip<25"; \
         pip install --no-cache-dir --default-timeout=180 --retries=5 "${PIP_TRUST[@]}" -i "${PIP_INDEX_URL}" -r requirements.txt; \
       else \
         echo "[docker build] 使用默认 PyPI（需容器可访问外网或代理）"; \
         pip install --no-cache-dir --upgrade --default-timeout=180 --retries=5 "pip<25"; \
         pip install --no-cache-dir --default-timeout=180 --retries=5 -r requirements.txt; \
       fi

COPY ai-failure-analyzer/pyproject.toml .
COPY ai-failure-analyzer/ai_failure_analyzer ./ai_failure_analyzer

RUN pip install --no-cache-dir .

EXPOSE 8080

CMD ["uvicorn", "ai_failure_analyzer.main:app", "--host", "0.0.0.0", "--port", "8080"]
