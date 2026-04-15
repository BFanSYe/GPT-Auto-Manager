# 变更记录

## 2026-04-16

### 已完成

- 注册流程对齐上游 `v10.1.1`
- 修复 takeover 场景中 `passwordless/send-otp` 失败判断对象错误，避免发信失败后仍继续走 OAuth / `get_oai_code` 流程
- 恢复古法浏览器插件模式主控链路（前端模式切换、`/api/ext/*` 接口、运行态统计）
- 古法启动前先等待 `WORKER_READY` 与节点心跳，避免误判插件节点掉线
- 增强古法模式对 `create-account` 异常页的自动重试处理
- 识别 Cloudflare 全页安全验证，并统一归类为 `pwd_blocked`
- 每轮古法任务成功 / 失败 / 停止后自动清理 OpenAI/Auth 站点数据（cookies、localStorage、indexedDB、cacheStorage、service workers 等）
- 浏览器插件安装提示修正为“解压 zip 后加载文件夹”，降低 `Service Worker (invalid)` 误用概率
- 公共发布版本号更新为 `v10.1.1-bfansye-hotfix1`

## 2026-04-15

### 已完成

- 合并上游 `v10.0.8`、`v10.0.9`、`v10.1.0`
- 新增邮箱接入：
  - FviaInboxes
  - Inboxes.com
  - TemporaryMail.com
  - Tmailor.com
- 合入本地微软邮箱旧 IMAP 令牌兼容修复
- 仓库公开整理为可复用基线
- 文档重写为中文优先、步骤化结构
- `docker-compose.yml` 调整为公开仓库更易复用的本地构建方式
- Clash 代理页布局调整：
  - `Clash 订阅自助更新`
  - `Clash 节点智能池`
  - `HTTP 动态代理池`
  三块顺序重新整理
- Clash 面板新增可视化信息：
  - 当前实际生效订阅入口
  - 默认路由对齐状态
  - 各实例当前生效链路
- Clash 订阅自助更新新增自动防呆：
  - 自动清洗空格/换行
  - 自动探测订阅是否为 Mihomo YAML
  - 自动尝试修正为 `?flag=mihomo`
  - 错误订阅在写入前拦截
  - 失败时保留当前可用订阅
- Clash 运行态观测补强：
  - 自动识别业务组
  - 自动对齐默认总组到业务组
  - 测活日志同时展示业务组节点与默认路由状态
- “开启智能切点” 与 “HTTP 动态代理池” 现在双向互斥
- HTTP 动态代理池保存时自动补全缺失的 `http://`
- HTTP 动态代理池开启但无有效代理来源时，后端拒绝保存
- 默认集群密钥改为占位符，避免公共仓库继续带弱默认值

## 2026-04-14

### 已完成

- 合并上游 `v10.0.7`
- 注册逻辑同步到上游最新版
- 清理之前的浏览器补救实验逻辑
- 域名白屏问题修复
- 保留并验证以下能力：
  - LuckMail 私有池
  - HTTP 动态代理池
  - Clash 订阅自助更新
  - 本地微软邮箱模式
  - Temporam 模式

## 2026-04-12

### 已完成

- 合并上游 `v9.0.4`
- 保留并修复以下本地定制能力：
  - LuckMail 私有上传邮箱池模式
  - HTTP 动态代理池
  - HeroSMS 直连开关与价格/余额修复
  - Telegram 直连通知与模板修复
  - Clash 订阅后台一键更新
  - 订阅更新后自动读取实际策略组并生成下拉选择

## 2026-04-10 ~ 2026-04-11

### 本地定制功能引入

- HTTP 动态代理池调度
- LuckMail imported pool 取号/取码
- HeroSMS API 不走全局代理
- Telegram 通知不走全局代理
- 成功/停止消息模板优化
