#!/bin/bash
# 完整安装和配置脚本

set -e

echo "=================================="
echo "ContentPublisher Pro 安装脚本"
echo "=================================="

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: Python3 未安装${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo -e "${GREEN}✓ Python 版本: $PYTHON_VERSION${NC}"

# 检查 Node.js (Playwright需要)
if ! command -v node &> /dev/null; then
    echo -e "${YELLOW}警告: Node.js 未安装，Playwright可能需要它${NC}"
fi

# 创建虚拟环境
echo -e "\n${YELLOW}[1/5] 创建虚拟环境...${NC}"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo -e "${GREEN}✓ 虚拟环境已创建${NC}"
else
    echo -e "${GREEN}✓ 虚拟环境已存在${NC}"
fi

source .venv/bin/activate

# 安装依赖
echo -e "\n${YELLOW}[2/5] 安装 Python 依赖...${NC}"
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo -e "${GREEN}✓ Python 依赖安装完成${NC}"

# 安装 Playwright 浏览器
echo -e "\n${YELLOW}[3/5] 安装 Playwright 浏览器...${NC}"
playwright install chromium
echo -e "${GREEN}✓ Chromium 浏览器安装完成${NC}"

# 初始化数据库
echo -e "\n${YELLOW}[4/5] 初始化数据库...${NC}"
python3 -c "from models import init_db; init_db()"
echo -e "${GREEN}✓ 数据库初始化完成${NC}"

# 创建必要目录
echo -e "\n${YELLOW}[5/5] 创建目录结构...${NC}"
mkdir -p data logs articles/images
echo -e "${GREEN}✓ 目录结构创建完成${NC}"

# 创建示例文章
if [ ! -f "articles/example.md" ]; then
cat > articles/example.md << 'EOF'
---
title: "欢迎使用 ContentPublisher Pro"
platforms:
  - zhihu
  - toutiao
  - xiaohongshu
tags:
  - 介绍
  - 教程
---

# 欢迎使用 ContentPublisher Pro

这是一款基于浏览器自动化的多平台内容分发工具。

## 主要特性

- 🚀 **浏览器自动化** - 基于 Playwright 绕过 API 限制
- 🔧 **模块化架构** - 每个平台是独立的 Tool
- 💾 **持久化存储** - SQLite 数据库记录所有数据
- ⏰ **定时发布** - 支持预约发布
- 🎨 **Web 控制面板** - 现代化管理界面

## 使用方法

1. **登录平台**
   ```bash
   python3 publisher.py login --platform zhihu
   ```

2. **创建文章** - 在 `articles/` 目录创建 Markdown 文件

3. **发布文章**
   ```bash
   python3 publisher.py publish articles/example.md
   ```

4. **启动调度器**
   ```bash
   python3 publisher.py scheduler
   ```

## 支持的平_PLATFORM

- 知乎
- 头条号
- 小红书
- 百家号
- 网易号
- 企鹅号

祝你使用愉快！
EOF
fi

# 显示完成信息
echo -e "\n${GREEN}=================================="
echo "安装完成！"
echo "==================================${NC}"
echo ""
echo "快速开始:"
echo "  1. 登录平台:   python3 publisher.py login --platform zhihu"
echo "  2. 查看文章:   python3 publisher.py list"
echo "  3. 发布文章:   python3 publisher.py publish articles/example.md"
echo "  4. 启动调度器: python3 publisher.py scheduler"
echo "  5. Web界面:    python3 web_server.py"
echo ""
echo "或使用快捷脚本:"
echo "  ./run.sh login --platform zhihu"
echo "  ./run.sh publish articles/example.md"
echo "  ./run.sh scheduler"
echo ""
