@echo off
chcp 65001 > nul
echo ==========================================
echo Content Publisher Skill 安装程序
echo ==========================================
echo.

:: 设置安装路径
set "INSTALL_DIR=%USERPROFILE%\.openclaw\skills\content-publisher"
set "PROJECT_DIR=%USERPROFILE%\content-publisher"

:: 检查并创建目录
echo [1/4] 准备安装目录...
if exist "%INSTALL_DIR%" (
    echo   更新现有安装...
    rmdir /s /q "%INSTALL_DIR%"
)
mkdir "%INSTALL_DIR%"
mkdir "%INSTALL_DIR%\scripts"

:: 复制技能文件
echo [2/4] 复制技能文件...
xcopy /y /q "SKILL.md" "%INSTALL_DIR%\" > nul
xcopy /y /q "scripts\*.py" "%INSTALL_DIR%\scripts\" > nul

:: 创建项目结构
echo [3/4] 创建示例项目...
if exist "%PROJECT_DIR%" (
    echo   项目目录已存在，跳过创建
) else (
    mkdir "%PROJECT_DIR%"
    mkdir "%PROJECT_DIR%\platforms"
    mkdir "%PROJECT_DIR%\data\cookies"
    
    :: 复制平台代码
    xcopy /y /q "scripts\*.py" "%PROJECT_DIR%\platforms\" > nul
    
    :: 创建 __init__.py
    (
        echo from platforms.zhihu import ZhihuTool
        echo from platforms.toutiao import ToutiaoTool
        echo from platforms.baijiahao import BaijiahaoTool
        echo.
        echo __all__ = ['ZhihuTool', 'ToutiaoTool', 'BaijiahaoTool']
    ) > "%PROJECT_DIR%\platforms\__init__.py"
    
    :: 创建 base.py
    (
        echo from dataclasses import dataclass
        echo from typing import Optional
        echo.
        echo @dataclass
        echo class ToolResult:
        echo     success: bool
        echo     post_id: Optional[str] = None
        echo     post_url: Optional[str] = None
        echo     error: Optional[str] = None
        echo     data: Optional[dict] = None
        echo.
        echo class PlatformTool:
        echo     def __init__(self, account=None^):
        echo         self.account = account
        echo         self._is_authenticated = False
        echo         self.browser = None
        echo         self.context = None
        echo         self.page = None
        echo.
        echo     async def init_browser(self, headless: bool = True, load_cookie: bool = True^):
        echo         raise NotImplementedError
        echo.
        echo     async def authenticate(self^) -^> bool:
        echo         raise NotImplementedError
        echo.
        echo     async def publish(self, article, file_path: str = None^) -^> ToolResult:
        echo         raise NotImplementedError
    ) > "%PROJECT_DIR%\platforms\base.py"
    
    :: 创建 requirements.txt
    (
        echo playwright>=1.40.0
        echo python-docx>=0.8.11
        echo click>=8.0.0
        echo rich>=13.0.0
    ) > "%PROJECT_DIR%\requirements.txt"
    
    :: 创建主程序
    (
        echo #!/usr/bin/env python3
        echo """Content Publisher - 多平台自媒体内容分发工具"""
        echo.
        echo import asyncio
        echo import os
        echo import sys
        echo from pathlib import Path
        echo from typing import Optional
        echo.
        echo import click
        echo from rich.console import Console
        echo from rich.table import Table
        echo from rich.progress import Progress
        echo.
        echo from platforms import ZhihuTool, ToutiaoTool, BaijiahaoTool
        echo.
        echo console = Console(^)
        echo Path(^"data/cookies"^).mkdir(parents=True, exist_ok=True^)
        echo.
        echo @click.group(^)
        echo def cli(^):
        echo     """多平台自媒体内容分发工具"""
        echo     pass
        echo.
        echo @cli.command(^)
        echo @click.argument('article_path'^)
        echo @click.option('--platform', '-p', multiple=True, help='指定平台'^)
        echo def publish(article_path: str, platform: tuple^):
        echo     """发布文章"""
        echo     if not os.path.exists(article_path^):
        echo         console.print(f"[red]文件不存在: {article_path}[/red]"^)
        echo         return
        echo     platforms_to_publish = list(platform^) if platform else ['zhihu', 'toutiao', 'baijiahao']
        echo     class Article:
        echo         def __init__(self, path^):
        echo             self.source_file = path
        echo             self.title = Path(path^).stem
        echo     article = Article(article_path^)
        echo     results = {}
        echo     with Progress(^) as progress:
        echo         task = progress.add_task("发布文章...", total=len(platforms_to_publish^)^)
        echo         for platform_name in platforms_to_publish:
        echo             progress.update(task, description=f"发布到 {platform_name}..."^)
        echo             if platform_name == 'zhihu':
        echo                 tool = ZhihuTool(^)
        echo             elif platform_name == 'toutiao':
        echo                 tool = ToutiaoTool(^)
        echo             elif platform_name == 'baijiahao':
        echo                 tool = BaijiahaoTool(^)
        echo             else:
        echo                 results[platform_name] = {"status": "失败", "error": "未知平台"}
        echo                 continue
        echo             try:
        echo                 result = asyncio.run(tool.publish(article^)^)
        echo                 if result.success:
        echo                     results[platform_name] = {"status": "成功", "url": result.post_url}
        echo                 else:
        echo                     results[platform_name] = {"status": "失败", "error": result.error}
        echo             except Exception as e:
        echo                 results[platform_name] = {"status": "失败", "error": str(e^)}
        echo             progress.advance(task^)
        echo     table = Table(title="发布结果"^)
        echo     table.add_column("平台", style="cyan"^)
        echo     table.add_column("状态", style="green"^)
        echo     table.add_column("链接", style="blue"^)
        echo     for platform_name, result in results.items(^):
        echo         status = result.get("status", "未知"^)
        echo         url = result.get("url", "N/A"^)
        echo         error = result.get("error", ""^)
        echo         if status == "成功":
        echo             table.add_row(platform_name, f"✓ {status}", url^)
        echo         else:
        echo             table.add_row(platform_name, f"✗ {status}", error^)
        echo     console.print(table^)
        echo.
        echo @cli.command(^)
        echo @click.option('--platform', '-p', required=True, help='平台名称'^)
        echo def login(platform: str^):
        echo     """登录平台"""
        echo     if platform == 'zhihu':
        echo         tool = ZhihuTool(^)
        echo     elif platform == 'toutiao':
        echo         tool = ToutiaoTool(^)
        echo     elif platform == 'baijiahao':
        echo         tool = BaijiahaoTool(^)
        echo     else:
        echo         console.print(f"[red]未知平台: {platform}[/red]"^)
        echo         return
        echo     console.print(f"[yellow]正在登录 {platform}...[/yellow]"^)
        echo     try:
        echo         success = asyncio.run(tool.authenticate(^)^)
        echo         if success:
        echo             console.print(f"[green]✓ {platform} 登录成功！[/green]"^)
        echo         else:
        echo             console.print(f"[red]✗ {platform} 登录失败[/red]"^)
        echo     except Exception as e:
        echo         console.print(f"[red]登录错误: {e}[/red]"^)
        echo.
        echo @cli.command(^)
        echo def status(^):
        echo     """检查状态"""
        echo     table = Table(title="平台状态"^)
        echo     table.add_column("平台", style="cyan"^)
        echo     table.add_column("状态", style="green"^)
        echo     platforms = [("知乎", "zhihu"^), ("头条号", "toutiao"^), ("百家号", "baijiahao"^)]
        echo     for name, key in platforms:
        echo         cookie_file = Path(f"data/cookies/{key}.json"^)
        echo         if cookie_file.exists(^):
        echo             table.add_row(name, "[green]已登录[/green]"^)
        echo         else:
        echo             table.add_row(name, "[red]未登录[/red]"^)
        echo     console.print(table^)
        echo.
        echo if __name__ == '__main__':
        echo     cli(^)
    ) > "%PROJECT_DIR%\publisher.py"
)

:: 安装依赖
echo [4/4] 安装依赖...
cd /d "%PROJECT_DIR%"
python -m pip install -q -r requirements.txt 2> nul
if errorlevel 1 (
    echo   注意：依赖安装可能需要手动执行
    echo   pip install -r requirements.txt
)

echo.
echo ==========================================
echo 安装完成！
echo ==========================================
echo.
echo 项目位置: %PROJECT_DIR%
echo.
echo 使用步骤:
echo   1. cd /d %PROJECT_DIR%
echo   2. playwright install chromium
echo   3. python publisher.py login -p zhihu
echo   4. python publisher.py publish "文章.docx"
echo.
echo 技能已安装到: %INSTALL_DIR%
echo.
pause
