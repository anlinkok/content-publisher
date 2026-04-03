#!/bin/bash
# Content Publisher Skill 安装脚本

set -e

SKILL_NAME="content-publisher"
INSTALL_DIR="${HOME}/.openclaw/skills/${SKILL_NAME}"

echo "=========================================="
echo "Content Publisher Skill 安装程序"
echo "=========================================="
echo ""

# 检查目录是否存在
if [ -d "$INSTALL_DIR" ]; then
    echo "检测到已存在的安装，正在更新..."
    rm -rf "$INSTALL_DIR"
fi

# 创建目录
mkdir -p "$INSTALL_DIR"

# 复制文件
echo "[1/3] 复制技能文件..."
cp SKILL.md "$INSTALL_DIR/"
cp -r scripts "$INSTALL_DIR/"

# 创建示例项目结构
echo "[2/3] 创建示例项目..."
PROJECT_DIR="${HOME}/content-publisher-example"
mkdir -p "$PROJECT_DIR"
mkdir -p "$PROJECT_DIR/platforms"
mkdir -p "$PROJECT_DIR/data/cookies"

# 复制平台代码
cp scripts/*.py "$PROJECT_DIR/platforms/"

# 创建 __init__.py
cat > "$PROJECT_DIR/platforms/__init__.py" << 'EOF'
from platforms.zhihu import ZhihuTool
from platforms.toutiao import ToutiaoTool
from platforms.baijiahao import BaijiahaoTool

__all__ = ['ZhihuTool', 'ToutiaoTool', 'BaijiahaoTool']
EOF

# 创建 base.py 的简化版本
cat > "$PROJECT_DIR/platforms/base.py" << 'EOF'
from dataclasses import dataclass
from typing import Optional

@dataclass
class ToolResult:
    success: bool
    post_id: Optional[str] = None
    post_url: Optional[str] = None
    error: Optional[str] = None
    data: Optional[dict] = None

class PlatformTool:
    def __init__(self, account=None):
        self.account = account
        self._is_authenticated = False
        self.browser = None
        self.context = None
        self.page = None
    
    async def init_browser(self, headless: bool = True, load_cookie: bool = True):
        raise NotImplementedError
    
    async def authenticate(self) -> bool:
        raise NotImplementedError
    
    async def publish(self, article, file_path: str = None) -> ToolResult:
        raise NotImplementedError
EOF

# 创建 requirements.txt
cat > "$PROJECT_DIR/requirements.txt" << 'EOF'
playwright>=1.40.0
python-docx>=0.8.11
click>=8.0.0
rich>=13.0.0
SQLModel>=0.0.14
EOF

# 创建主程序
cat > "$PROJECT_DIR/publisher.py" << 'EOF'
#!/usr/bin/env python3
"""
Content Publisher - 多平台自媒体内容分发工具
支持：知乎、头条号、百家号
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress

from platforms import ZhihuTool, ToutiaoTool, BaijiahaoTool

console = Console()

# 确保数据目录存在
Path("data/cookies").mkdir(parents=True, exist_ok=True)


@click.group()
def cli():
    """多平台自媒体内容分发工具"""
    pass


@cli.command()
@click.argument('article_path')
@click.option('--platform', '-p', multiple=True, help='指定发布平台 (zhihu/toutiao/baijiahao)')
def publish(article_path: str, platform: tuple):
    """发布文章到指定平台"""
    
    if not os.path.exists(article_path):
        console.print(f"[red]文件不存在: {article_path}[/red]")
        return
    
    # 确定要发布的平台
    platforms_to_publish = list(platform) if platform else ['zhihu', 'toutiao', 'baijiahao']
    
    # 创建文章对象
    class Article:
        def __init__(self, path):
            self.source_file = path
            self.title = Path(path).stem
    
    article = Article(article_path)
    
    # 发布到各平台
    results = {}
    
    with Progress() as progress:
        task = progress.add_task("发布文章...", total=len(platforms_to_publish))
        
        for platform_name in platforms_to_publish:
            progress.update(task, description=f"发布到 {platform_name}...")
            
            if platform_name == 'zhihu':
                tool = ZhihuTool()
            elif platform_name == 'toutiao':
                tool = ToutiaoTool()
            elif platform_name == 'baijiahao':
                tool = BaijiahaoTool()
            else:
                results[platform_name] = {"status": "失败", "error": "未知平台"}
                continue
            
            try:
                result = asyncio.run(tool.publish(article))
                if result.success:
                    results[platform_name] = {"status": "成功", "url": result.post_url}
                else:
                    results[platform_name] = {"status": "失败", "error": result.error}
            except Exception as e:
                results[platform_name] = {"status": "失败", "error": str(e)}
            
            progress.advance(task)
    
    # 显示结果
    table = Table(title="发布结果")
    table.add_column("平台", style="cyan")
    table.add_column("状态", style="green")
    table.add_column("链接", style="blue")
    
    for platform_name, result in results.items():
        status = result.get("status", "未知")
        url = result.get("url", "N/A")
        error = result.get("error", "")
        
        if status == "成功":
            table.add_row(platform_name, f"✓ {status}", url)
        else:
            table.add_row(platform_name, f"✗ {status}", error)
    
    console.print(table)


@cli.command()
@click.option('--platform', '-p', required=True, help='平台名称 (zhihu/toutiao/baijiahao)')
def login(platform: str):
    """登录指定平台"""
    
    if platform == 'zhihu':
        tool = ZhihuTool()
    elif platform == 'toutiao':
        tool = ToutiaoTool()
    elif platform == 'baijiahao':
        tool = BaijiahaoTool()
    else:
        console.print(f"[red]未知平台: {platform}[/red]")
        return
    
    console.print(f"[yellow]正在登录 {platform}...[/yellow]")
    try:
        success = asyncio.run(tool.authenticate())
        if success:
            console.print(f"[green]✓ {platform} 登录成功！[/green]")
        else:
            console.print(f"[red]✗ {platform} 登录失败[/red]")
    except Exception as e:
        console.print(f"[red]登录错误: {e}[/red]")


@cli.command()
def status():
    """检查各平台状态"""
    table = Table(title="平台状态")
    table.add_column("平台", style="cyan")
    table.add_column("状态", style="green")
    
    platforms = [
        ("知乎", "zhihu"),
        ("头条号", "toutiao"),
        ("百家号", "baijiahao")
    ]
    
    for name, key in platforms:
        cookie_file = Path(f"data/cookies/{key}.json")
        if cookie_file.exists():
            table.add_row(name, "[green]已登录[/green]")
        else:
            table.add_row(name, "[red]未登录[/red]")
    
    console.print(table)


if __name__ == '__main__':
    cli()
EOF

chmod +x "$PROJECT_DIR/publisher.py"

echo "[3/3] 安装依赖..."
cd "$PROJECT_DIR"
pip install -q -r requirements.txt 2>/dev/null || echo "请手动运行: pip install -r requirements.txt"

echo ""
echo "=========================================="
echo "安装完成！"
echo "=========================================="
echo ""
echo "示例项目位置: $PROJECT_DIR"
echo ""
echo "使用步骤:"
echo "  1. cd $PROJECT_DIR"
echo "  2. playwright install chromium"
echo "  3. python publisher.py login -p zhihu"
echo "  4. python publisher.py publish '文章.docx'"
echo ""
echo "查看状态: python publisher.py status"
echo ""
