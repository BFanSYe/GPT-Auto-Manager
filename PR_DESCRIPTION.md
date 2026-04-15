# Fork 差异说明

## 当前定位

本仓库是基于上游 `wenfxl/openai-cpa` 整理出的公开可复用版本，当前基线为：

- 上游版本：`v10.1.1`
- 当前公开热修版本：`v10.1.1-bfansye-hotfix1`

## 本次发布重点

- 同步上游 `v10.1.1` 注册流程优化
- 修复 takeover 场景 `passwordless/send-otp` 失败判断 bug
- 恢复古法浏览器插件模式主控链路
- 增强 `create-account` 异常页自动重试
- 识别 Cloudflare 全页安全验证并归类为 `pwd_blocked`
- 每轮古法任务结束后自动清理 OpenAI/Auth 站点数据
- 古法启动前等待 `WORKER_READY` 与节点心跳
- 修正插件安装提示：必须加载解压后的插件目录

## 与上游相比保留/增强的重点

### 1. 代理与网络

- Clash 订阅自助更新
- Clash 多实例分流
- 默认总路由自动对齐业务组
- 订阅入口自动探测与 `?flag=mihomo` 自动修正
- HTTP 动态代理池
- “开启智能切点” / “HTTP 动态代理池” 双向互斥
- 更贴近业务链路的代理测活日志

### 2. 邮箱能力

- LuckMail 私有上传邮箱池模式
- 本地微软邮箱库 / Graph 支持
- Temporam 支持
- Fvia / Inboxes / TemporaryMail / Tmailor 支持

### 3. 古法插件模式

- 古法模式主控链路恢复
- 插件 ready / heartbeat 等待
- `create-account` 异常页重试
- Cloudflare 受阻归因
- 任务后站点数据自动清理

### 4. 仓管能力

- CPA 自动补货
- Sub2API 自动补货
- 独立测活与库存管理

### 5. 文档与公开仓库整理

- 中文优先 README
- 独立部署说明
- 变更记录补齐
- 示例配置改为公开友好占位符
- 默认集群密钥改为占位符，避免弱默认值

## 推荐分支

- 默认公开分支：`main`
- 持续开发分支：`main-bfansye`
- 发布分支：`release/bfansye-custom-v10.1.1`
