# ContentPublisher Pro 配置指南

## 环境要求

- Python 3.11+
- Playwright (Chromium 浏览器)
- SQLite (内置)

## 安装步骤

### 1. 克隆/下载项目

```bash
cd content-publisher
```

### 2. 安装依赖

使用一键脚本（推荐）：
```bash
./run.sh
```

或手动安装：
```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. 初始化数据库

```bash
python3 -c "from models import init_db; init_db()"
```

## 首次使用

### 1. 登录各平台账号

```bash
# 知乎
python3 publisher.py login --platform zhihu

# 头条号
python3 publisher.py login --platform toutiao

# 小红书
python3 publisher.py login --platform xiaohongshu

# 百家号
python3 publisher.py login --platform baijiahao

# 网易号
python3 publisher.py login --platform wangyi

# 企鹅号
python3 publisher.py login --platform qiehao
```

**注意**：首次登录会弹出浏览器窗口，请手动完成登录流程。登录成功后，Cookie 会自动保存。

### 2. 创建文章

在 `articles/` 目录下创建 Markdown 文件：

```markdown
---
title: "文章标题"
platforms:
  - zhihu
  - toutiao
  - xiaohongshu
schedule: "2025-01-20 09:00"
cover: "./images/cover.png"
tags:
  - 标签1
  - 标签2
---

文章内容，支持完整 Markdown 语法...
```

### 3. 发布文章

```bash
# 立即发布
python3 publisher.py publish articles/my-article.md

# 如果设置了 schedule，文章会被加入队列，定时发布
```

### 4. 启动定时调度器

```bash
# 前台运行
python3 publisher.py scheduler

# 或使用脚本
./run.sh scheduler
```

## Docker 部署

### 构建镜像

```bash
docker-compose up -d
```

### 查看日志

```bash
docker-compose logs -f publisher
```

### 停止服务

```bash
docker-compose down
```

## 进阶配置

### 自定义平台

编辑 `publisher.py` 中的 `PLATFORM_TOOLS` 字典添加新平台。

### 定时任务

调度器默认每分钟检查一次。可以修改 `scheduler` 命令中的 `interval` 参数。

### 日志管理

日志保存在 `logs/` 目录，使用 `logging` 模块配置。

## 常见问题

### Q: 登录后Cookie过期怎么办？
A: 重新运行 `login` 命令即可。

### Q: 如何批量发布？
A: 使用 `for` 循环遍历文章目录：
```bash
for f in articles/*.md; do
    python3 publisher.py publish "$f"
done
```

### Q: 发布失败怎么办？
A: 检查日志文件 `logs/publisher.log` 获取详细信息。

### Q: 支持图片上传吗？
A: 支持，在文章 frontmatter 中设置 `cover` 字段。

## 安全提示

1. Cookie 数据存储在本地 SQLite 数据库，请勿泄露
2. 建议定期更换账号密码
3. 遵守各平台发布频率限制
4. 不要在公共环境保存敏感账号信息
