# GPT Auto Manager

一个基于上游 `wenfxl/openai-cpa` 深度整理的 **中文增强版 Web 控制台项目**。

当前公开整理版本已对齐上游 `v10.1.1` 注册流程更新，并保留了已经在实际环境中验证过的增强能力，重点优化了：

- 中文使用体验与文档
- Web 面板可维护性
- Clash / Mihomo 代理池能力
- HTTP 动态代理池调度
- LuckMail 私有池 / 本地微软邮箱 / Temporam 兼容
- Fvia / Inboxes / TemporaryMail / Tmailor 邮箱接入
- CPA / Sub2API 仓管与巡检

> 当前仓库适合作为“可二次复用的公开源码基线”。
> 私有配置、账号、订阅、数据库、Token、邮箱凭据等敏感内容均不应提交到仓库。

---

## 1. 项目定位

这个项目不是单纯的脚本，而是一套围绕 **Web 控制台** 展开的自动化管理面板，核心用途包括：

- 邮箱接码 / 验证码收取
- 注册任务调度
- 代理池切换与测活
- Clash / Mihomo 多实例代理池管理
- CPA / Sub2API 仓库补货与巡检
- 本地账号库存管理
- Web 实时日志、统计、导出、删除

---

## 2. 本公开版相对上游保留/增强的能力

### 2.1 代理与网络

- **Clash 订阅自助更新**
  - 可在 Web 面板直接更新订阅
  - 可触发宿主机 Mihomo 代理池重载
  - 自动读取真实策略组
  - 自动给各实例分流不同节点
  - 自动把默认总路由组对齐到业务组
  - 自动识别并修正错误订阅入口（如原始订阅串自动补 `?flag=mihomo`）
  - 错误订阅会在写入前被拦截，避免污染当前可用配置

- **Clash 节点智能池**
  - 支持单机模式与多实例独享池模式
  - 支持黑名单过滤
  - 支持随机切点 / 延迟优选
  - 测活日志会同时展示：
    - 当前业务组
    - 当前业务组真实节点
    - 默认总路由是否已对齐

- **HTTP 动态代理池**
  - 支持一个或多个 `http://user:pass@host:port` 动态网关
  - 适合“每次连接自动换出口 IP”的代理商
  - 多线程时自动按通道队列分发

### 2.2 邮箱与验证码

- LuckMail 私有上传邮箱池模式
- 本地微软邮箱库 / Graph 取码
- Temporam 支持
- Fvia / Inboxes / TemporaryMail / Tmailor 支持
- DuckMail / IMAP / freemail / cloudmail / mail_curl / Gmail OAuth 等多后端
- 多域名轮换与多级子域名生成

### 2.3 仓管与任务调度

- CPA 自动补货
- Sub2API 自动补货
- 独立测活
- 本地 SQLite 库存管理
- 选中导出 / 删除 / 推送
- 实时日志与统计

### 2.4 浏览器 / 古法插件模式

- 恢复古法浏览器插件模式主控链路
- 前端模式切换与后端 `/api/ext/*` 配套恢复
- 启动前等待 `WORKER_READY` 与节点心跳
- `create-account` 异常页自动重试
- Cloudflare 安全验证归类为 `pwd_blocked`
- 每轮任务结束后自动清理 OpenAI / Auth 站点数据

---

## 3. 当前整理版本

当前公开整理基线：

- 上游基础：`v10.1.1`
- 当前公开热修版本：`v10.1.1-bfansye-hotfix1`

本轮整理额外完成：

- 对齐上游 `v10.1.1` 注册流程优化
- 修复 takeover 场景 `passwordless/send-otp` 失败后误判继续执行的问题
- 恢复古法浏览器插件模式主控链路
- 增强 `create-account` 异常页自动重试
- 识别 Cloudflare 全页安全验证并归类为 `pwd_blocked`
- 每轮古法任务结束后自动清理 OpenAI / Auth 站点数据
- 古法启动前等待 `WORKER_READY` 与心跳，避免误报“插件节点未连接”
- 修正浏览器插件安装提示：必须加载解压后的插件目录

详见：[`CHANGELOG.md`](./CHANGELOG.md)

---

## 4. 目录说明

```text
.
├── assets/                # 界面截图
├── data/                  # 运行时数据目录（不提交）
├── luckmail/              # LuckMail 相关客户端
├── routers/               # FastAPI 路由
├── static/                # 前端 JS / 静态资源
├── utils/                 # 核心逻辑、代理、邮箱、仓管
├── config.example.yaml    # 配置模板
├── docker-compose.yml     # 公开版示例编排
├── Dockerfile             # 本地构建镜像
├── DEPLOY.md              # 详细部署说明
├── CHANGELOG.md           # 变更记录
└── wfxl_openai_regst.py   # 启动入口
```

---

## 5. 快速开始（推荐 Docker）

### 5.1 克隆仓库

```bash
git clone https://github.com/BFanSYe/GPT-Auto-Manager.git
cd GPT-Auto-Manager
```

### 5.2 启动

```bash
docker compose up -d --build
```

### 5.3 访问面板

默认访问地址：

```text
http://127.0.0.1:18000
```

首次启动时如果 `data/config.yaml` 不存在，系统会自动根据 `config.example.yaml` 生成默认配置。

默认 Web 密码：

```text
admin
```

> **首次登录后请立即修改 Web 密码与关键密钥。**

---

## 6. 首次配置建议顺序

建议第一次使用时按下面顺序配置：

1. **邮箱配置**
   - 先确认你选择的邮箱后端能正常收码
2. **网络代理**
   - 先决定使用：
     - 普通单代理
     - HTTP 动态代理池
     - Clash / Mihomo 节点池
3. **手机接码**
   - 如果使用 HeroSMS，先确认余额、价格和国家策略
4. **并发与系统**
   - `reg_threads` 不建议一开始开太高
5. **中转管仓**
   - 如果启用 CPA / Sub2API，再配置补货逻辑

---

## 7. Clash / Mihomo 使用说明

### 7.1 什么时候用 Clash 订阅自助更新

当你有一套宿主机维护的 Mihomo 多实例代理池，并且希望在 Web 面板中：

- 一键替换订阅
- 自动重载代理池
- 自动识别业务组
- 自动把不同实例分流到不同节点
- 自动检查默认总路由是否对齐

就使用这一套功能。

### 7.2 这套功能依赖什么

宿主机需要提供一个目录（默认约定为 `/opt/mihomo-pool`），其中至少包含：

- `pool.env`
- `update_pool.sh`
- `status_pool.sh`
- `config_1/config.yaml` ... `config_n/config.yaml`

容器需要挂载：

- `/opt/mihomo-pool:/opt/mihomo-pool`
- `/var/run/docker.sock:/var/run/docker.sock`
- `/usr/bin/docker:/usr/local/bin/docker:ro`

### 7.3 现在已经内置的自动防呆

- 自动清洗订阅链接中的空格 / 换行
- 自动探测原始链接是不是 Mihomo YAML
- 如果不是，会自动尝试补成 `?flag=mihomo`
- 错误订阅会在写入前被拦截
- 更新后会自动检查：
  - 策略组是否存在
  - 默认总组是否能到达业务组
  - 各实例是否已分配不同节点
  - 当前运行态是否全部对齐

---

## 8. HTTP 动态代理池与 Clash 池怎么选

### 用 HTTP 动态代理池的情况

适合你拿到的是这种代理：

```text
http://user:pass@gateway.example.com:10000
```

并且代理商本身就支持“每次连接自动换出口”。

### 用 Clash 节点池的情况

适合你已经有：

- Mihomo / Clash 控制器
- 策略组
- 节点订阅
- 多实例多端口池

并且你需要：

- 指定业务组
- 节点筛选
- 延迟优选
- 默认总组对齐
- 多实例不同出口

---

## 9. 本地源码运行（非 Docker）

### 9.1 Python 版本

建议：

- Linux / macOS：`Python 3.11`
- Windows：`Python 3.12`

### 9.2 安装依赖

```bash
pip install -r requirements.txt
```

### 9.3 启动

```bash
python wfxl_openai_regst.py
```

默认监听：

```text
http://127.0.0.1:8000
```

---

## 10. Docker Compose 示例说明

仓库自带的 `docker-compose.yml` 默认采用 **本地源码构建**，更适合公开仓库直接复用。

如果你暂时不需要 Clash 订阅自助更新，只保留：

- `./data:/app/data`

即可。

如果需要 Clash 订阅自助更新，再额外挂载：

- `/opt/mihomo-pool:/opt/mihomo-pool`
- `/var/run/docker.sock:/var/run/docker.sock`
- `/usr/bin/docker:/usr/local/bin/docker:ro`

详细步骤见：[`DEPLOY.md`](./DEPLOY.md)

---

## 11. 升级建议

推荐升级流程：

```bash
git pull
docker compose up -d --build
```

如果你使用了宿主机反向代理，通常不需要改 Nginx，只需要重建容器即可。

---

## 12. 公共仓库使用注意

请不要提交以下内容：

- `data/`
- `.env`
- `credentials.json`
- `token.json`
- 真实邮箱账号 / 密码
- 真实订阅链接
- 真实 API Key / TG Token / Chat ID
- 真实数据库备份

建议你只提交：

- 代码
- 文档
- 示例配置
- 脱敏截图

---

## 13. 截图预览

<details>
<summary><strong>点击展开界面截图</strong></summary>

- 登录页：`assets/manager1.png`
- 主页：`assets/manager2.png`
- 账号库存：`assets/manager3.png`
- 邮箱配置：`assets/manager4.png`
- 网络代理：`assets/manager6.png`
- 中转管仓：`assets/manager7.png`
- 并发与系统：`assets/manager8.png`

</details>

---

## 14. 上游来源与说明

本仓库基于：

- 上游项目：`https://github.com/wenfxl/openai-cpa`

当前仓库的目标不是“完全替代上游”，而是提供一个：

- 更适合中文用户直接部署
- 更适合公开分享复用
- 保留已验证增强特性的整理版基线

---

## 15. 相关文档

- [部署说明 DEPLOY.md](./DEPLOY.md)
- [变更记录 CHANGELOG.md](./CHANGELOG.md)
- [示例配置 config.example.yaml](./config.example.yaml)

---

## 16. English Summary

This repository is a Chinese-enhanced public-ready fork of `wenfxl/openai-cpa`, focused on practical web-based operations, Clash/Mihomo proxy-pool management, HTTP dynamic proxy pooling, mailbox backends, and CPA/Sub2API inventory workflows.
