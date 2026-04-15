# Fork 差异说明

## 当前定位

本仓库是基于上游 `wenfxl/openai-cpa` 整理出的公开可复用版本，当前基线为：

- 上游版本：`v10.1.0`
- 当前公开热修版本：`v10.1.0-bfansye-hotfix1`

## 与上游相比保留/增强的重点

### 1. 代理与网络

- Clash 订阅自助更新
- Clash 多实例分流
- 默认总路由自动对齐业务组
- 订阅入口自动探测与 `?flag=mihomo` 自动修正
- HTTP 动态代理池
- 智能切点 / HTTP 动态代理池双向互斥
- 更贴近业务链路的代理测活日志

### 2. 邮箱能力

- LuckMail 私有上传邮箱池模式
- 本地微软邮箱库 / Graph 支持
- Temporam 支持
- Fvia / Inboxes / TemporaryMail / Tmailor 支持

### 3. 仓管能力

- CPA 自动补货
- Sub2API 自动补货
- 独立测活与库存管理

### 4. 文档与公开仓库整理

- 中文优先 README
- 独立部署说明
- 变更记录补齐
- 示例配置改为公开友好占位符
- 默认集群密钥改为占位符，避免弱默认值

## 推荐分支

- 默认公开分支：`main`
- 持续开发分支：`main-bfansye`
- 发布分支：`release/bfansye-custom-v10.1.0`
