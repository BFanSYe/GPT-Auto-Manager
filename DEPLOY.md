# 部署说明 / Deploy Guide

## 中文（默认）

### 目录约定

- 项目目录：`/opt/openai-cpa`
- 数据目录：`/opt/openai-cpa/data`
- Clash 代理池目录：`/opt/mihomo-pool`

### 当前容器启动方式

```bash
sudo docker run -d \
  --name openai-cpa \
  --restart unless-stopped \
  --add-host host.docker.internal:host-gateway \
  -p 127.0.0.1:18000:8000 \
  -v /opt/openai-cpa/data:/app/data \
  -v /opt/mihomo-pool:/opt/mihomo-pool \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /usr/bin/docker:/usr/local/bin/docker:ro \
  openai-cpa:latest
```

### 反向代理

- Nginx 反代到：`127.0.0.1:18000`
- 域名：请替换为你自己的正式域名（例如 `https://your-domain.example`）

### 重要说明

- 不要把 `data/`、`credentials.json`、`token.json`、`.env` 等本地敏感文件提交到仓库
- 不要把你自己的真实域名、API Key、订阅链接、Chat ID、邮箱凭据直接写入文档后再提交
- Clash 订阅更新脚本位于：
  - `/opt/mihomo-pool/update_pool.sh`
- Clash 状态脚本位于：
  - `/opt/mihomo-pool/status_pool.sh`

### 推荐日常更新流程

```bash
cd /opt/openai-cpa
git pull
sudo docker build -t openai-cpa:latest .
sudo docker rm -f openai-cpa
sudo docker run -d \
  --name openai-cpa \
  --restart unless-stopped \
  --add-host host.docker.internal:host-gateway \
  -p 127.0.0.1:18000:8000 \
  -v /opt/openai-cpa/data:/app/data \
  -v /opt/mihomo-pool:/opt/mihomo-pool \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /usr/bin/docker:/usr/local/bin/docker:ro \
  openai-cpa:latest
```

---

## English

### Paths

- app path: `/opt/openai-cpa`
- data path: `/opt/openai-cpa/data`
- clash pool path: `/opt/mihomo-pool`

### Current container run mode

The app is deployed with Docker and mounts local data, clash pool files, Docker socket, and Docker CLI for the Clash subscription self-service feature.
