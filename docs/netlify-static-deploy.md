# Netlify 静态部署说明

本文档说明如何把 `daily_stock_analysis` 作为静态研究报告站点部署到 Netlify。

## 目标

该链路只用于生成和展示每日研究报告：

- 不自动交易
- 不连接券商 API
- 不构成投资建议
- 不提交 `.env`
- 不把 API Key 或 Token 写入仓库

页面固定展示：

> 仅供研究，不构成投资建议；不自动交易；不连接券商 API。

## 需要的 GitHub Secrets

进入仓库：

`Settings -> Secrets and variables -> Actions`

至少配置：

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_MODEL`
- `STOCK_LIST`
- `NETLIFY_SITE_ID`
- `NETLIFY_AUTH_TOKEN`

说明：

- `OPENAI_API_KEY` 可替换为你实际使用的 OpenAI-compatible 服务密钥
- `OPENAI_BASE_URL` 例如 `https://api.deepseek.com`
- `OPENAI_MODEL` 例如 `deepseek-v4-flash`
- `STOCK_LIST` 例如 `600519,300750,000333,510300,159915`
- `NETLIFY_SITE_ID` 来自 Netlify 站点设置
- `NETLIFY_AUTH_TOKEN` 来自 Netlify 用户 Token

## Netlify 配置

### 1. 创建站点

在 Netlify 中创建一个站点，发布目录为 `public`。

### 2. 获取站点参数

在 Netlify 后台记录：

- Site ID
- Personal Access Token

然后把它们配置到 GitHub Secrets。

## GitHub Actions Workflow

新增 workflow：

- `.github/workflows/daily-netlify-report.yml`

行为如下：

1. 每个工作日 UTC 10:00 自动运行
2. 支持手动 `Run workflow`
3. 执行 `python main.py --no-notify`
4. 即使分析失败，也继续执行静态导出
5. 执行 `python scripts/export_static_site.py --output public`
6. 发布 `public/` 到 Netlify

## 手动运行方法

进入：

`Actions -> Daily Stock Fund Netlify Report -> Run workflow`

检查：

- 依赖安装是否成功
- `main.py` 是否成功；失败也允许继续
- `public/index.html` 是否生成
- `public/reports/latest.html` 是否生成
- Netlify 部署是否成功

## 定时运行时间

当前 cron：

```yaml
schedule:
  - cron: "0 10 * * 1-5"
```

含义：

- UTC 10:00
- 周一到周五
- 对应北京时间 18:00

若需调整，直接修改 workflow 中的 cron 表达式。

## 常见问题

### `requirements.txt` 安装失败

检查仓库依赖是否与当前 workflow 一致，必要时先在 PR 中修正依赖源或锁定版本。

### `main.py --no-notify` 失败

该 workflow 已做兜底：

- 失败会写入 `logs/analysis-error.txt`
- 后续仍会生成占位页并部署

### Netlify deploy 报错 `Not authorized`

检查：

- `NETLIFY_AUTH_TOKEN` 是否正确
- `NETLIFY_SITE_ID` 是否来自目标站点
- workflow 中 deploy 命令是否显式传入 `--site` 和 `--auth`

### 页面是空白的

检查：

- `public/index.html` 是否存在
- `public/reports/latest.html` 是否存在
- `netlify.toml` 的 `publish = "public"` 是否已生效

### 页面暴露了敏感信息

立即处理：

1. 删除部署
2. 轮换 `OPENAI_API_KEY`
3. 轮换 `NETLIFY_AUTH_TOKEN`
4. 检查导出脚本是否输出环境变量或日志原文

## 验收标准

部署完成后确认：

- 首页可打开
- 有最新报告入口
- 页面展示运行时间
- 页面展示 `STOCK_LIST`
- 页面展示免责声明
- 页面不显示 API Key、Token、Webhook
- 页面不包含自动交易或券商接入描述
