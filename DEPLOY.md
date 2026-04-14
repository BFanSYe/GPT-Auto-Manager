# 部署说明

本文档面向“第一次部署”和“后续升级”两个场景，尽量保持中文步骤清晰、可直接照做。

---

## 1. 推荐部署方式

**推荐优先级：**

1. Docker Compose（最推荐）
2. Docker 手工运行
3. 本地 Python 直接运行

如果你准备启用以下功能，建议用 Docker：

- Clash 订阅自助更新
- Mihomo 多实例代理池
- CPA / Sub2API 长时间运行
- 反向代理到域名

---

## 2. 最简可用部署（Docker Compose）

### 2.1 克隆仓库

```bash
git clone https://github.com/BFanSYe/GPT-Auto-Manager.git
cd GPT-Auto-Manager
```

### 2.2 启动

```bash
docker compose up -d --build
```

### 2.3 访问

```text
http://127.0.0.1:18000
```

### 2.4 首次启动后的行为

- 自动创建 `data/`
- 自动根据 `config.example.yaml` 生成 `data/config.yaml`
- 默认 Web 密码为 `admin`

首次登录后请至少修改：

- Web 密码
- 集群密钥
- 各类 API Token / 订阅链接 / 邮箱凭据

---

## 3. 当前公开版默认 docker-compose.yml 说明

当前仓库自带的 `docker-compose.yml` 默认采用本地构建：

- 优点：
  - 不依赖外部预构建镜像
  - 代码和运行版本一致
  - 更适合公开仓库直接复用

默认只强依赖：

- `./data:/app/data`

如果你 **不使用 Clash 订阅自助更新**，这样就够了。

---

## 4. 如果你要启用 Clash 订阅自助更新

### 4.1 宿主机需要准备的目录

默认约定：

```text
/opt/mihomo-pool
```

该目录至少应包含：

```text
/opt/mihomo-pool/
├── pool.env
├── update_pool.sh
├── status_pool.sh
├── config_1/config.yaml
├── config_2/config.yaml
└── ...
```

### 4.2 需要额外挂载的内容

在容器中启用以下挂载：

```yaml
- /opt/mihomo-pool:/opt/mihomo-pool
- /var/run/docker.sock:/var/run/docker.sock
- /usr/bin/docker:/usr/local/bin/docker:ro
```

### 4.3 功能效果

启用后，Web 面板可以做到：

- 一键更新订阅
- 自动重载代理池
- 自动识别真实策略组
- 自动给每个实例分配不同节点
- 自动检查并展示默认总路由是否对齐业务组
- 自动修正错误订阅入口（例如自动补 `?flag=mihomo`）

---

## 5. 推荐的反向代理方式

推荐将应用只监听在本机，再由 Nginx/Caddy 反代。

例如映射：

```text
127.0.0.1:18000 -> 容器 8000
```

Nginx 示例：

```nginx
server {
    listen 80;
    server_name your-domain.example;

    location / {
        proxy_pass http://127.0.0.1:18000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

如需 HTTPS，建议额外配合：

- Let's Encrypt
- Caddy 自动签证书
- 或你自己的网关层

---

## 6. 本地 Python 运行方式

### 6.1 Python 版本建议

- Linux / macOS：`Python 3.11`
- Windows：`Python 3.12`

### 6.2 安装依赖

```bash
pip install -r requirements.txt
```

### 6.3 启动

```bash
python wfxl_openai_regst.py
```

默认地址：

```text
http://127.0.0.1:8000
```

---

## 7. 升级步骤

### 7.1 Docker Compose 升级

```bash
cd GPT-Auto-Manager
git pull
docker compose up -d --build
```

### 7.2 Docker 手工运行升级

```bash
git pull
docker build -t gpt-auto-manager:latest .
docker rm -f gpt-auto-manager || true
docker run -d \
  --name gpt-auto-manager \
  --restart unless-stopped \
  --add-host host.docker.internal:host-gateway \
  -p 127.0.0.1:18000:8000 \
  -v $(pwd)/data:/app/data \
  gpt-auto-manager:latest
```

如果你启用了 Clash 订阅自助更新，再补上对应挂载即可。

---

## 8. 公共仓库发布时的注意事项

发布/同步到 GitHub 前，建议确认：

- `data/` 没有被提交
- 真实 `config.yaml` 没有被提交
- 邮箱凭据未出现在文档
- 订阅链接未出现在文档
- Token / Key / Chat ID 未出现在文档
- 截图没有暴露敏感信息

本仓库已经默认忽略：

- `data/`
- `config.yaml`
- `.env`
- `token.json`
- `credentials.json`
- 本地数据库与日志

---

## 9. 常见问题

### 9.1 页面打开白屏

优先检查：

- 前端 JS 是否缓存
- 容器是否已重建
- 反向代理是否还在指向旧实例

建议先执行：

```bash
docker compose up -d --build
```

然后浏览器强刷。

### 9.2 一键更新订阅失败

优先检查：

- 宿主机 `/opt/mihomo-pool` 是否挂载进去
- `update_pool.sh` / `status_pool.sh` 是否存在
- 订阅链接返回的是不是 Mihomo YAML

当前项目已经内置：

- 自动探测订阅格式
- 自动尝试 `?flag=mihomo`
- 错误订阅写入前拦截

### 9.3 明明节点名不同，但日志地区看起来不一致

现在新版测活日志会额外输出：

- 业务组当前节点
- 默认总组当前值
- 默认总组是否已对齐业务组

因此应优先以“业务组当前节点 + 默认路由对齐状态”判断真实链路，而不是只看单一 Cloudflare 地区值。

---

## 10. 建议的生产目录结构

```text
/opt/gpt-auto-manager/
├── data/
├── docker-compose.yml
└── .env（可选，不提交）
```

如果启用 Clash 订阅自助更新：

```text
/opt/mihomo-pool/
├── pool.env
├── update_pool.sh
├── status_pool.sh
└── config_1 ... config_n
```

---

## 11. 相关文档

- 总览：[`README.md`](./README.md)
- 配置模板：[`config.example.yaml`](./config.example.yaml)
- 变更记录：[`CHANGELOG.md`](./CHANGELOG.md)
