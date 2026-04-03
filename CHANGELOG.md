# 更新日志

## v2.0.0 (2025-01-20)

### 新增功能

- 🌐 **Web 控制面板** - FastAPI 提供现代化 Web 界面
- 📊 **高级分析模块** - 内容优化、智能标签、发布策略
- 🧪 **测试套件** - 完整的单元测试覆盖
- 🐳 **Docker 支持** - 一键容器化部署
- 🚀 **一键安装脚本** - 自动化环境配置

### 架构升级

- 参考 Claude Code Tool 架构重构
- 模块化设计，每个平台独立 Tool
- SQLModel 数据库 ORM
- Playwright 浏览器自动化

### 支持平台

- ✅ 知乎
- ✅ 头条号
- ✅ 小红书
- ✅ 百家号
- ✅ 网易号
- ✅ 企鹅号

### API 新增

- `POST /api/articles` - 创建文章
- `POST /api/articles/{id}/publish` - 发布文章
- `POST /api/platforms/{platform}/login` - 平台登录

---

## v1.0.0 (2025-01-15)

### 初始版本

- 基础多平台发布功能
- CLI 命令行界面
- 定时发布调度器
- SQLite 数据存储
