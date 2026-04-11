# 变更记录 / Changelog

## 中文（默认）

### 2026-04-12

#### 已完成

- 合并上游 `v9.0.4`
- 保留并修复以下本地定制能力：
  - LuckMail 私有上传邮箱池模式
  - HTTP 动态代理池
  - HeroSMS 直连开关与价格/余额修复
  - Telegram 直连通知与模板修复
  - Clash 订阅后台一键更新
  - 订阅更新后自动读取实际策略组并生成下拉选择

#### 文档与仓库整理

- 增加中文优先的 README 自定义说明
- 增加 `PR_DESCRIPTION.md`
- 增加 `DEPLOY.md`
- 增加本文件 `CHANGELOG.md`
- 强化 `.gitignore`，避免本地数据、凭据和缓存被误提交

### 2026-04-10 ~ 2026-04-11

#### 本地定制功能引入

- HTTP 动态代理池调度
- LuckMail imported pool 取号/取码
- HeroSMS API 不走全局代理
- Telegram 通知不走全局代理
- 成功/停止消息模板优化

---

## English

### 2026-04-12

- merged upstream `v9.0.4`
- preserved local custom features:
  - LuckMail imported mailbox pool mode
  - HTTP dynamic proxy pool
  - HeroSMS direct API mode
  - Telegram direct-send mode and template fixes
  - Web-based Clash subscription updater
  - auto-detected Clash strategy group dropdown

### 2026-04-10 ~ 2026-04-11

- introduced local deployment-specific customizations
