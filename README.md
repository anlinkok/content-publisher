# ContentPublisher Pro

基于浏览器自动化的多平台内容分发工具，参考 Claude Code Tool 架构设计。

## 核心特性

| 特性 | 说明 |
|------|------|
| 🚀 **浏览器自动化** | Playwright 模拟真实用户操作，绕过 API 限制 |
| 🔧 **Tool 架构** | 每个平台是独立的 Tool，可插拔可扩展 |
| 💾 **持久化存储** | SQLite 数据库记录文章、账号、发布记录 |
| ⏰ **定时发布** | APScheduler 每分钟检查待发布文章 |
| 🎨 **现代化 CLI** | Rich 库提供美观的命令行界面 |
| 🌐 **Web 控制面板** | FastAPI 提供 HTTP API 和 Web 界面 |
| 📊 **数据分析** | 内容优化、智能标签、发布策略 |
| 📄 **Word 支持** | 自动解析 .docx 文件，提取文字和图片 |

## 支持平台

- ✅ 知乎
- ✅ 头条号  
- ✅ 小红书
- ✅ 百家号
- ✅ 网易号
- ✅ 企鹅号

## 快速开始

### 一键安装

```bash
cd content-publisher
./install.sh
```

### 手动安装

```bash
# 1. 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt
playwright install chromium

# 3. 初始化数据库
python3 -c "from models import init_db; init_db()"
```

### 使用方法

```bash
# 登录平台（会弹出浏览器窗口）
python3 publisher.py login --platform zhihu

# 创建文章（articles/ 目录下创建 Markdown 或 Word 文件）
# 参考 articles/example.md

# 发布 Markdown 文章
python3 publisher.py publish articles/my-article.md

# 发布 Word 文档（自动提取文字和图片）
python3 publisher.py publish articles/my-article.docx

# 启动定时调度器
python3 publisher.py scheduler

# 启动 Web 控制面板
python3 web_server.py
# 访问 http://localhost:8080
```

### 文章格式

支持两种格式：

**1. Markdown 格式**

```markdown
---
title: "文章标题"
platforms:
  - zhihu
  - toutiao
  - xiaohongshu
schedule: "2025-01-20 09:00"  # 定时发布，留空立即发布
cover: "./images/cover.png"     # 封面图路径
tags:
  - 标签1
  - 标签2
---

正文内容，支持完整 Markdown 语法...
```

**2. Word 文档 (.docx)**

直接上传 `.docx` 文件：
- 自动提取文档标题（从文档属性或第一个大字号段落）
- 自动提取所有图片并上传到平台图床
- 自动转换格式为平台支持的样式
- 保留粗体、斜体、表格等格式

```bash
python3 publisher.py publish articles/document.docx
```

## 项目结构

```
content-publisher/
├── publisher.py          # 主程序入口 (CLI)
├── web_server.py         # Web 控制面板 (FastAPI)
├── advanced.py           # 高级功能模块
├── word_parser.py        # Word 文档解析器
├── tests.py              # 测试套件
├── models.py             # 数据模型 (SQLModel)
├── platforms/            # 平台工具目录
│   ├── base.py          # Tool 基类
│   ├── zhihu.py         # 知乎
│   ├── toutiao.py       # 头条号
│   ├── xiaohongshu.py   # 小红书
│   ├── baijiahao.py     # 百家号
│   ├── wangyi.py        # 网易号
│   └── qiehao.py        # 企鹅号
├── articles/            # 文章目录（支持 .md 和 .docx）
├── data/                # 数据库文件
├── logs/                # 日志文件
├── install.sh           # 一键安装脚本
├── run.sh               # 快捷运行脚本
├── Dockerfile           # Docker 构建
└── docker-compose.yml   # Docker 编排
```

## CLI 命令

```bash
# 发布文章
python3 publisher.py publish <文件路径>

# 登录平台
python3 publisher.py login --platform <平台名>

# 查看文章列表
python3 publisher.py list

# 查看系统状态
python3 publisher.py status

# 启动调度器
python3 publisher.py scheduler

# 高级功能
python3 advanced.py analyze <文件>        # 分析文章质量
python3 advanced.py suggest-tags <文件>  # 智能推荐标签
python3 advanced.py schedule-plan <平台列表>  # 生成发布计划
```

## Web API

启动 Web 服务器:
```bash
python3 web_server.py
```

API 端点:
- `GET /` - Web 控制面板
- `GET /api/stats` - 统计数据
- `GET /api/platforms` - 平台状态
- `GET /api/articles` - 文章列表
- `POST /api/articles` - 创建文章
- `POST /api/articles/{id}/publish` - 发布文章

## Docker 部署

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f publisher

# 停止服务
docker-compose down
```

## 架构说明

### Tool 模式 (参考 Claude Code)

每个平台是一个独立的 Tool，继承 `PlatformTool` 基类:

```python
class ZhihuTool(PlatformTool):
    name = "ZhihuPublisher"
    platform_type = "zhihu"
    
    async def authenticate(self) -> bool:
        # 登录逻辑
        pass
    
    async def publish(self, article: Article) -> ToolResult:
        # 发布逻辑
        pass
```

### 浏览器自动化

- 使用 Playwright 实现真实浏览器操作
- Cookie 持久化，一次登录长期有效
- 反检测注入，避免被识别为爬虫

### 数据模型

- **Account**: 存储各平台账号和 Cookie
- **Article**: 存储文章内容和发布状态
- **PublishRecord**: 记录每次发布的详细结果

## 高级功能

### 内容优化器

```python
from advanced import ContentOptimizer

analysis = ContentOptimizer.analyze(title, content)
print(f"字数: {analysis.word_count}")
print(f"阅读时间: {analysis.reading_time}分钟")
print(f"SEO评分: {analysis.seo_score}")
```

### 智能标签生成

```python
from advanced import AutoTagger

tags = AutoTagger.generate_tags(title, content, max_tags=5)
```

### 发布策略

```python
from advanced import PublishingStrategy

# 生成错峰发布计划
schedule = PublishingStrategy.generate_schedule(['zhihu', 'toutiao'])
```

## 测试

```bash
# 运行测试
python3 tests.py
```

## 注意事项

1. **Cookie 有效期**: 各平台的 Cookie 会过期，需要定期重新登录
2. **发布频率**: 各平台有限制，避免频繁发布触发风控
3. **内容合规**: 遵守各平台的内容规范
4. **网络环境**: 部分平台对 IP 敏感，建议使用固定 IP

## 开发计划

- [ ] 支持更多平台 (抖音、快手、B站)
- [ ] AI 内容生成集成
- [ ] 数据统计分析面板
- [ ] 多账号管理
- [ ] 团队协作功能

## 免责声明

本工具仅供学习和个人使用。请遵守各平台的使用条款和相关法律法规。
