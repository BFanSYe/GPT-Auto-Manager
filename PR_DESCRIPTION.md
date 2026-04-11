# PR 说明 / PR Description

## 中文说明（默认）

### 概要

本 PR 将 fork 同步到上游 `v9.0.4`，并保留当前生产环境中已经验证通过的本地定制能力。

### 上游基线

- 上游仓库：`wenfxl/openai-cpa`
- 合并版本：`v9.0.4`

### 本 fork 保留的定制功能

#### 1. LuckMail 私有上传邮箱池模式

- 支持调用用户自行上传到 LuckMail 的邮箱池
- 支持 `specified_email`
- 启用私有池模式后，改为 `order/create` + 按订单取码

#### 2. HTTP 动态代理池

- 支持一个或多个动态 HTTP 代理网关
- 支持多线程队列分发
- 适配“每次连接/请求自动换 IP”的代理服务商

#### 3. HeroSMS 修复

- HeroSMS API 可不走全局注册代理
- 余额与价格面板在注册代理不稳定时仍可正常使用

#### 4. Telegram 修复

- 默认直连发送
- 独立 `use_proxy` 开关
- 优化成功/停止模板
- 修复停止模板变量渲染问题

#### 5. Clash 订阅后台自助更新

- Web 面板更新 Clash 订阅链接
- Web 面板执行代理池刷新脚本
- 订阅更新后显示真实策略组
- 将策略组直接放入下拉选择框

### 运维说明

- 应用路径：`/opt/openai-cpa`
- Clash 代理池路径：`/opt/mihomo-pool`
- 当前容器挂载：
  - `/opt/openai-cpa/data:/app/data`
  - `/opt/mihomo-pool:/opt/mihomo-pool`
  - `/var/run/docker.sock:/var/run/docker.sock`
  - `/usr/bin/docker:/usr/local/bin/docker:ro`

### 分支建议

- 发布分支：`release/bfansye-custom-v9.0.4`
- 主维护分支：`main-bfansye`

---

## English Notes

### Summary

This PR syncs the fork to upstream `v9.0.4` while preserving the local production-ready custom features.

### Upstream base

- Upstream repo: `wenfxl/openai-cpa`
- Merged version: `v9.0.4`

### Custom features preserved

- LuckMail imported mailbox mode
- HTTP dynamic proxy pool
- HeroSMS API stability fixes
- Telegram direct-send and template fixes
- Web-based Clash subscription self-service updater
