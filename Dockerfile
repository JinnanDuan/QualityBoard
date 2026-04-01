# dt-report：镜像内构建前端 + 运行后端，监听 8000（与单端口部署一致）
#
# Ubuntu apt 源：编辑 docker/sources.list（COPY 到 /etc/apt/sources.list），与同事实体镜像部署方式一致。
#
# 离线构建（勿提交 Git，见 .gitignore）：
#   - Node：官方 node-v*-linux-x64.tar.xz → docker/nodejs-offline.tar.xz
#   - pnpm：从 https://github.com/pnpm/pnpm/releases 下载 pnpm-linuxstatic-x64（建议 10.x，与 lockfile 一致）
#           保存为 docker/pnpm-offline（无扩展名即可，COPY 后安装为 /usr/local/bin/pnpm）
# pip：通过 PIP_INDEX_URL（内网 PyPI）或默认可访问的 PyPI 在线安装
#
# 仅「安装 Playwright Chromium」一步需要外网代理拉浏览器时，传入：
#   --build-arg HTTP_PROXY=... --build-arg HTTPS_PROXY=... --build-arg NO_PROXY=...
# 注意：传入代理后 pip/pnpm 也会走代理。若 PIP_INDEX_URL / npm 源为内网域名，必须把该域名写入 NO_PROXY
#（例如 mirrors.tools.huawei.com），否则 pip 经代理访问内网 PyPI 会极慢或卡住（表现为卡在 pip install 一步）。
#
# 其他可选 build-arg：PIP_INDEX_URL、PIP_TRUSTED_HOST、NPM_REGISTRY（见 docs/03_deployment_guide.md）
#
# 运行示例：
#   docker run --rm -p 8000:8000 \
#     -e DATABASE_URL='mysql+aiomysql://用户:密码@主机:3306/dt_infra?charset=utf8mb4' \
#     -e SECRET_KEY='...' \
#     dt-report:local

# 若使用 docker load 导入的基础镜像，将下面一行改为该镜像在 docker images 中的名称，例如：FROM ubuntu:20.04
FROM ubuntu:20.04

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ARG PIP_INDEX_URL
ARG PIP_TRUSTED_HOST
ARG NPM_REGISTRY

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Etc/UTC \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

COPY docker/sources.list /etc/apt/sources.list

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        python3 python3-pip python3-venv \
        xz-utils \
    && rm -rf /var/lib/apt/lists/*

COPY docker/nodejs-offline.tar.xz /tmp/node.tar.xz
COPY docker/pnpm-offline /usr/local/bin/pnpm
RUN tar -xJf /tmp/node.tar.xz -C /usr/local --strip-components=1 \
    && rm -f /tmp/node.tar.xz \
    && chmod +x /usr/local/bin/pnpm

RUN npm config set registry https://mirrors.tools.huawei.com/npm/
RUN npm config set strict-ssl false

WORKDIR /app

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY backend/requirements.txt backend/requirements.txt
RUN PIP_TRUST=() \
    && if [ -n "${PIP_TRUSTED_HOST}" ]; then PIP_TRUST=(--trusted-host "${PIP_TRUSTED_HOST}"); fi \
    && if [ -n "${PIP_INDEX_URL}" ]; then \
         echo "[docker build] 使用内网 PyPI: ${PIP_INDEX_URL}"; \
         pip install --no-cache-dir --upgrade --default-timeout=180 --retries=5 "${PIP_TRUST[@]}" -i "${PIP_INDEX_URL}" "pip<25"; \
         pip install --no-cache-dir --default-timeout=180 --retries=5 "${PIP_TRUST[@]}" -i "${PIP_INDEX_URL}" -r backend/requirements.txt; \
       else \
         echo "[docker build] 使用默认 PyPI（需容器可访问外网或代理）"; \
         pip install --no-cache-dir --upgrade --default-timeout=180 --retries=5 "pip<25"; \
         pip install --no-cache-dir --default-timeout=180 --retries=5 -r backend/requirements.txt; \
       fi

# WeLink 一键通知：仅本步建议配置 HTTP_PROXY/HTTPS_PROXY 以下载 Chromium；镜像体积显著增大
RUN export http_proxy="$HTTP_PROXY" https_proxy="$HTTPS_PROXY" no_proxy="$NO_PROXY" \
    && python -m playwright install-deps chromium \
    && python -m playwright install chromium

COPY frontend/package.json frontend/pnpm-lock.yaml ./frontend/
WORKDIR /app/frontend
RUN if [ -n "${NPM_REGISTRY}" ]; then \
         export npm_config_registry="${NPM_REGISTRY}"; \
       fi \
    && pnpm install --frozen-lockfile

COPY frontend .
RUN if [ -n "${NPM_REGISTRY}" ]; then \
         export npm_config_registry="${NPM_REGISTRY}"; \
       fi \
    && pnpm run build

WORKDIR /app
COPY backend ./backend
COPY database ./database

EXPOSE 8000

CMD ["/opt/venv/bin/python", "-m", "backend.run"]
