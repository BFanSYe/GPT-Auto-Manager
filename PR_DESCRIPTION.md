# Fork 差异说明

## 当前定位

本仓库是基于上游 `wenfxl/openai-cpa` 整理出的公开可复用版本，当前基线为：

- 上游对齐范围：`v10.1.5` 关键注册/邮箱改动（未接入上游 Clash 部署管理）
- 当前公开热修版本：`v10.1.5-bfansye-hotfix1`

## 本次发布重点

- 回补上游 `v10.1.2` 的注册主流程强化
- 修复 takeover 场景 `password_verify` / `login_ctx` 传递链路
- 新增创建阶段命中 `/add-phone` 时的 HeroSMS 补救逻辑
- 识别 `identity_provider_mismatch` 并自动转 takeover / OAuth OTP
- 识别 `been deleted or deactivated` 与 `Failed to create account` 的更细归因
- 回补上游 `v10.1.3` 的微软邮箱 `service abuse mode` 自动停用逻辑
- 新增 `Sub2API` 测活验证模型配置 `test_model`
- 新增 `HeroSMS` 创建阶段接码配置 `verify_on_register`
- 回补上游 `v10.1.5` 的注册主流程优化与邮箱脱敏日志改进
- 修复 `Sub2API` 测活模型配置值大小写不规范问题，并兼容旧配置

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
- 微软邮箱 `service abuse mode` 自动停用与轮询止损

### 3. 注册与古法插件模式

- takeover 流程强化
- 创建阶段 add-phone 补救
- 古法模式主控链路恢复
- 插件 ready / heartbeat 等待
- `create-account` 异常页重试
- Cloudflare 受阻归因
- 任务后站点数据自动清理

### 4. 仓管能力

- CPA 自动补货
- Sub2API 自动补货
- 独立测活与库存管理
- Sub2API 测活模型可配置

### 5. 文档与公开仓库整理

- 中文优先 README
- 独立部署说明
- 变更记录补齐
- 示例配置改为公开友好占位符
- 默认集群密钥改为占位符，避免弱默认值

## 推荐分支

- 默认公开分支：`main`
- 持续开发分支：`main-bfansye`
- 发布分支：`release/bfansye-custom-v10.1.5`
