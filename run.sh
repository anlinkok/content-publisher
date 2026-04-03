#!/bin/bash
# ContentPublisher 启动脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python3 not found${NC}"
    exit 1
fi

# 检查虚拟环境
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv .venv
fi

# 激活虚拟环境
source .venv/bin/activate

# 安装依赖
if [ ! -f ".venv/.installed" ] || [ "requirements.txt" -nt ".venv/.installed" ]; then
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install -q -r requirements.txt
    touch .venv/.installed
fi

# 安装 Playwright (如果不存在)
if ! python3 -c "import playwright" 2>/dev/null; then
    echo -e "${YELLOW}Installing Playwright...${NC}"
    playwright install chromium
fi

# 初始化数据库
python3 -c "from models import init_db; init_db()"

# 运行命令
case "${1:-}" in
    publish)
        shift
        python3 publisher.py publish "$@"
        ;;
    login)
        shift
        python3 publisher.py login "$@"
        ;;
    list)
        python3 publisher.py list
        ;;
    status)
        python3 publisher.py status
        ;;
    scheduler)
        echo -e "${GREEN}Starting scheduler...${NC}"
        python3 publisher.py scheduler
        ;;
    *)
        echo "ContentPublisher Pro"
        echo ""
        echo "Usage: $0 {publish|login|list|status|scheduler}"
        echo ""
        echo "Commands:"
        echo "  publish <file>    Publish an article"
        echo "  login            Login to a platform"
        echo "  list            List all articles"
        echo "  status          Show system status"
        echo "  scheduler       Start the scheduler daemon"
        echo ""
        ;;
esac
