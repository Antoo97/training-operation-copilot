# 免费上线配置

本项目可使用 Render 免费 Web Service + Supabase 免费 PostgreSQL。

## Supabase

1. 新建 Supabase 项目。
2. 在项目的 Connect 页面复制 PostgreSQL 连接字符串。
3. 建议选择 Session pooler 连接串；把其中的密码占位符替换为数据库密码。

## Render

1. 在 Render 选择 **New > Blueprint**，连接本 GitHub 仓库。
2. Render 会读取 `render.yaml`。
3. 填写以下两个 Secret：
   - `TRAINING_COPILOT_DATABASE_URL`：Supabase 连接字符串。
   - `TRAINING_COPILOT_PASSWORD`：同事访问工作台时使用的密码。
4. 部署完成后，用户名默认为 `admin`。

本地运行时如果不设置上述变量，仍使用 `training_copilot.db`，且不要求密码。
