#!/usr/bin/env python3
"""
ContentPublisher Pro
基于浏览器自动化的多平台内容分发工具
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import List, Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress

# 确保models先加载
from models import init_db, Article, Account, PublishRecord, ArticleStatus, engine
from sqlmodel import Session, select

# 导入平台工具
from platforms import (
    ZhihuTool, ToutiaoTool, XiaohongshuTool,
    BaijiahaoTool, WangyiTool, QiehaoTool,
    ToolResult
)

console = Console()

# 工具映射
PLATFORM_TOOLS = {
    'zhihu': ZhihuTool,
    'toutiao': ToutiaoTool,
    'xiaohongshu': XiaohongshuTool,
    'baijiahao': BaijiahaoTool,
    'wangyi': WangyiTool,
    'qiehao': QiehaoTool,
}


# ============================================================================
# Article Manager
# ============================================================================

class ArticleManager:
    """文章管理器"""
    
    @staticmethod
    def parse_file(file_path: str) -> Optional[Article]:
        """解析文件（支持 Markdown 和 Word）"""
        file_path = Path(file_path)
        
        if file_path.suffix.lower() in ['.docx', '.doc']:
            return ArticleManager.parse_word(str(file_path))
        else:
            return ArticleManager.parse_markdown(str(file_path))
    
    @staticmethod
    def parse_markdown(file_path: str) -> Optional[Article]:
        """解析Markdown文件"""
        try:
            import frontmatter
            import markdown
            
            with open(file_path, 'r', encoding='utf-8') as f:
                post = frontmatter.load(f)
            
            md = markdown.Markdown(extensions=['tables', 'fenced_code', 'toc'])
            html_content = md.convert(post.content)
            
            scheduled_at = None
            if post.get('schedule'):
                scheduled_at = datetime.strptime(post['schedule'], '%Y-%m-%d %H:%M')
            
            return Article(
                title=post.get('title', '无标题'),
                content=post.content,
                html_content=html_content,
                platforms=json.dumps(post.get('platforms', [])),
                cover_image=post.get('cover'),
                tags=json.dumps(post.get('tags', [])),
                scheduled_at=scheduled_at,
                status=ArticleStatus.SCHEDULED if scheduled_at else ArticleStatus.QUEUED
            )
        except Exception as e:
            console.print(f"[red]解析Markdown失败: {e}[/red]")
            return None
    
    @staticmethod
    def parse_word(file_path: str) -> Optional[Article]:
        """解析Word文件"""
        try:
            from word_parser import WordParser
            
            # 解析 Word 文档
            parser = WordParser(file_path)
            word_content = parser.parse()
            
            # 保存图片
            images_dir = Path('articles/images')
            images_dir.mkdir(parents=True, exist_ok=True)
            saved_images = parser.save_images(str(images_dir))
            
            # 确定封面图
            cover_image = None
            if saved_images:
                cover_image = saved_images[0]
                # 更新内容中的图片路径为相对路径
                for img in word_content.images:
                    old_path = f"./images/{img.filename}"
                    new_path = f"./images/{img.hash}.{img.format}"
                    word_content.content = word_content.content.replace(old_path, new_path)
                    word_content.html_content = word_content.html_content.replace(old_path, new_path)
            
            console.print(f"[green]✓ 提取了 {len(saved_images)} 张图片[/green]")
            
            # 默认平台：知乎（Word文档不指定平台）
            platforms = ['zhihu']
            
            return Article(
                title=word_content.title,
                content=word_content.content,
                html_content=word_content.html_content,
                platforms=json.dumps(platforms),
                cover_image=cover_image,
                tags=json.dumps(word_content.tags),
                status=ArticleStatus.QUEUED,
                source_file=file_path
            )
        except Exception as e:
            console.print(f"[red]解析Word文件失败: {e}[/red]")
            import traceback
            traceback.print_exc()
            return None
    
    @staticmethod
    def save_article(article: Article) -> int:
        """保存文章"""
        with Session(engine) as session:
            session.add(article)
            session.commit()
            return article.id
    
    @staticmethod
    def scan_date_folder(date: Optional[datetime] = None) -> List[Article]:
        """扫描指定日期的文件夹，返回所有文章"""
        if date is None:
            date = datetime.now()
        
        # 构建文件夹路径 articles/YYYY-MM-DD/
        date_str = date.strftime('%Y-%m-%d')
        folder_path = Path('articles') / date_str
        
        if not folder_path.exists():
            console.print(f"[yellow]文件夹不存在: {folder_path}[/yellow]")
            return []
        
        articles = []
        
        # 支持的文件扩展名
        extensions = ['*.md', '*.docx', '*.doc']
        
        for ext in extensions:
            for file_path in folder_path.glob(ext):
                console.print(f"[blue]发现文件: {file_path.name}[/blue]")
                article = ArticleManager.parse_file(str(file_path))
                if article:
                    # 如果文章没有指定平台，使用默认平台
                    if not json.loads(article.platforms):
                        article.platforms = json.dumps(['zhihu', 'toutiao'])
                    articles.append(article)
        
        return articles
    
    @staticmethod
    def list_articles(status: Optional[str] = None) -> List[Article]:
        """列出文章"""
        with Session(engine) as session:
            query = select(Article)
            if status:
                query = query.where(Article.status == status)
            return session.exec(query.order_by(Article.created_at.desc())).all()
    
    @staticmethod
    def get_pending_articles() -> List[Article]:
        """获取待发布文章"""
        with Session(engine) as session:
            now = datetime.now()
            query = select(Article).where(
                (Article.status == ArticleStatus.QUEUED) |
                ((Article.status == ArticleStatus.SCHEDULED) & (Article.scheduled_at <= now))
            )
            return session.exec(query).all()


# ============================================================================
# Content Publisher
# ============================================================================

class ContentPublisher:
    """内容分发核心"""
    
    def __init__(self):
        self.active_tools = {}
    
    async def get_or_create_tool(self, platform: str):
        """获取或创建工具"""
        if platform in self.active_tools:
            return self.active_tools[platform]
        
        tool_class = PLATFORM_TOOLS.get(platform)
        if not tool_class:
            console.print(f"[red]未知平台: {platform}[/red]")
            return None
        
        # 加载账号
        with Session(engine) as session:
            account = session.exec(
                select(Account).where(Account.platform == platform)
            ).first()
        
        tool = tool_class(account)
        self.active_tools[platform] = tool
        return tool
    
    async def publish_article(self, article: Article, platforms: List[str] = None, file_path: str = None) -> dict:
        """发布文章"""
        if platforms is None:
            platforms = json.loads(article.platforms)
        
        results = {}
        
        with Progress() as progress:
            task = progress.add_task("[cyan]发布文章...", total=len(platforms))
            
            for platform in platforms:
                progress.update(task, description=f"[cyan]发布到 {platform}...")
                
                tool = await self.get_or_create_tool(platform)
                if not tool:
                    results[platform] = ToolResult(success=False, error="工具未找到")
                    continue
                
                try:
                    result = await tool.publish(article, file_path=file_path)
                    results[platform] = result
                    
                    # 保存记录
                    with Session(engine) as session:
                        record = PublishRecord(
                            article_id=article.id,
                            platform=platform,
                            status="success" if result.success else "failed",
                            post_id=result.post_id,
                            post_url=result.post_url,
                            error_message=result.error,
                            published_at=datetime.now() if result.success else None
                        )
                        session.add(record)
                        session.commit()
                    
                except Exception as e:
                    console.print(f"[red]发布到 {platform} 失败: {e}[/red]")
                    results[platform] = ToolResult(success=False, error=str(e))
                
                progress.update(task, advance=1)
                await asyncio.sleep(2)
        
        return results
    
    async def close_all(self):
        """关闭所有工具"""
        for tool in self.active_tools.values():
            await tool.close()
        self.active_tools.clear()


# ============================================================================
# CLI Commands
# ============================================================================

@click.group()
def cli():
    """ContentPublisher Pro - 多平台内容分发工具"""
    pass


@cli.command()
@click.argument('file_path')
@click.option('--platform', '-p', help='指定平台 (如: zhihu, toutiao, xiaohongshu, baijiahao, wangyi, qiehao)')
def publish(file_path: str, platform: str = None):
    """发布单篇文章（支持 Markdown 和 Word）"""
    if not os.path.exists(file_path):
        console.print(f"[red]文件不存在: {file_path}[/red]")
        return
    
    # 检测文件类型
    file_ext = Path(file_path).suffix.lower()
    if file_ext in ['.docx', '.doc']:
        console.print(f"[blue]检测到 Word 文档，正在解析...[/blue]")
    
    article = ArticleManager.parse_file(file_path)
    if not article:
        return
    
    article_id = ArticleManager.save_article(article)
    article.id = article_id
    
    # 确保 source_file 存在（用于文档导入）
    if not getattr(article, 'source_file', None):
        article.source_file = file_path
    
    # 如果指定了平台，覆盖默认平台
    if platform:
        article.platforms = json.dumps([platform])
        console.print(f"[yellow]指定发布平台: {platform}[/yellow]")
    
    console.print(Panel(f"[green]{article.title}[/green]", title="准备发布"))
    console.print(f"平台: {', '.join(json.loads(article.platforms))}")
    if article.cover_image:
        console.print(f"封面图: {article.cover_image}")
    
    async def do_publish():
        publisher = ContentPublisher()
        try:
            results = await publisher.publish_article(article, file_path=file_path)
            
            table = Table(title="发布结果")
            table.add_column("平台", style="cyan")
            table.add_column("状态", style="green")
            table.add_column("链接", style="blue")
            
            for platform, result in results.items():
                status = "✓ 成功" if result.success else f"✗ 失败: {result.error}"
                url = result.post_url or "N/A"
                table.add_row(platform, status, url)
            
            console.print(table)
        finally:
            await publisher.close_all()
    
    asyncio.run(do_publish())


@cli.command()
@click.option('--date', '-d', help='指定日期 (格式: YYYY-MM-DD, 默认今天)')
def publish_today(date: str = None):
    """发布指定日期文件夹里的所有文章"""
    # 解析日期
    if date:
        target_date = datetime.strptime(date, '%Y-%m-%d')
    else:
        target_date = datetime.now()
    
    date_str = target_date.strftime('%Y-%m-%d')
    console.print(Panel(f"[bold green]发布 {date_str} 的文章[/bold green]"))
    
    # 扫描日期文件夹
    articles = ArticleManager.scan_date_folder(target_date)
    
    if not articles:
        console.print("[yellow]没有发现文章，请确保文件夹存在: articles/{}[/yellow]".format(date_str))
        return
    
    console.print(f"[green]发现 {len(articles)} 篇文章\n[/green]")
    
    async def do_publish():
        publisher = ContentPublisher()
        try:
            for article in articles:
                # 保存到数据库
                article_id = ArticleManager.save_article(article)
                article.id = article_id
                
                console.print(Panel(f"[cyan]正在发布: {article.title}[/cyan]"))
                console.print(f"平台: {', '.join(json.loads(article.platforms))}")
                
                results = await publisher.publish_article(article)
                
                # 显示结果
                table = Table(title="发布结果")
                table.add_column("平台", style="cyan")
                table.add_column("状态", style="green")
                table.add_column("链接", style="blue")
                
                for platform, result in results.items():
                    status = "✓ 成功" if result.success else f"✗ 失败: {result.error}"
                    url = result.post_url or "N/A"
                    table.add_row(platform, status, url)
                
                console.print(table)
                console.print()
                await asyncio.sleep(5)
        finally:
            await publisher.close_all()
    
    asyncio.run(do_publish())


@cli.command()
@click.option('--platform', '-p', required=True, help='平台名称')
def login(platform: str):
    """登录平台账号"""
    tool_class = PLATFORM_TOOLS.get(platform)
    if not tool_class:
        console.print(f"[red]未知平台: {platform}[/red]")
        console.print(f"可用平台: {', '.join(PLATFORM_TOOLS.keys())}")
        return
    
    async def do_login():
        tool = tool_class()
        await tool.init_browser(headless=False)
        
        try:
            success = await tool.authenticate()
            if success:
                console.print(f"[green]{platform} 登录成功![/green]")
            else:
                console.print(f"[red]{platform} 登录失败[/red]")
        finally:
            await tool.close()
    
    asyncio.run(do_login())


@cli.command()
def list():
    """列出所有文章"""
    articles = ArticleManager.list_articles()
    
    table = Table(title="文章列表")
    table.add_column("ID", style="dim")
    table.add_column("标题", style="cyan")
    table.add_column("状态", style="green")
    table.add_column("平台", style="blue")
    table.add_column("创建时间", style="dim")
    
    for article in articles:
        platforms = ', '.join(json.loads(article.platforms))
        title = article.title[:30] + '...' if len(article.title) > 30 else article.title
        table.add_row(
            str(article.id),
            title,
            article.status,
            platforms,
            article.created_at.strftime('%Y-%m-%d %H:%M')
        )
    
    console.print(table)


@cli.command()
def status():
    """查看系统状态"""
    with Session(engine) as session:
        total = len(session.exec(select(Article)).all())
        published = len(session.exec(select(Article).where(Article.status == ArticleStatus.PUBLISHED)).all())
        pending = len(session.exec(select(Article).where(Article.status == ArticleStatus.QUEUED)).all())
        failed = len(session.exec(select(Article).where(Article.status == ArticleStatus.FAILED)).all())
    
    console.print(Panel(f"""
[bold]文章统计[/bold]
总文章数: {total}
已发布: {published}
待发布: {pending}
失败: {failed}
    """, title="系统状态"))


@cli.command()
@click.option('--date', '-d', help='指定日期文件夹 (格式: YYYY-MM-DD, 默认今天)')
def scheduler(date: str = None):
    """启动定时发布调度器"""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    
    # 解析日期
    if date:
        target_date = datetime.strptime(date, '%Y-%m-%d')
    else:
        target_date = datetime.now()
    
    async def process_daily_articles():
        """处理当天日期文件夹里的文章"""
        console.print(f"\n[bold cyan]===== 扫描 {target_date.strftime('%Y-%m-%d')} 的文章 =====[/bold cyan]")
        
        # 扫描日期文件夹
        articles = ArticleManager.scan_date_folder(target_date)
        
        if not articles:
            console.print("[yellow]没有发现文章[/yellow]")
            return
        
        console.print(f"[green]发现 {len(articles)} 篇文章[/green]\n")
        
        publisher = ContentPublisher()
        try:
            for article in articles:
                # 保存到数据库
                article_id = ArticleManager.save_article(article)
                article.id = article_id
                
                console.print(Panel(f"[cyan]正在发布: {article.title}[/cyan]"))
                console.print(f"平台: {', '.join(json.loads(article.platforms))}")
                
                results = await publisher.publish_article(article)
                
                # 显示结果
                for platform, result in results.items():
                    status = "✓ 成功" if result.success else f"✗ 失败"
                    console.print(f"  {platform}: {status}")
                
                console.print()
                await asyncio.sleep(5)
        finally:
            await publisher.close_all()
    
    async def main():
        scheduler = AsyncIOScheduler()
        # 每天指定时间运行 (默认早上8点)
        scheduler.add_job(process_daily_articles, 'cron', hour=8, minute=0)
        scheduler.start()
        
        console.print(f"[green]定时调度器已启动[/green]")
        console.print(f"每天早上 8:00 自动扫描 {target_date.strftime('%Y-%m-%d')} 文件夹的文章")
        console.print("按 Ctrl+C 停止\n")
        
        # 立即执行一次
        await process_daily_articles()
        
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            scheduler.shutdown()
            console.print("[yellow]调度器已停止[/yellow]")
    
    asyncio.run(main())


# ============================================================================
# Main Entry
# ============================================================================

def main():
    # 确保目录存在
    Path('data').mkdir(exist_ok=True)
    Path('logs').mkdir(exist_ok=True)
    Path('articles').mkdir(exist_ok=True)
    
    # 初始化数据库
    init_db()
    
    cli()


if __name__ == '__main__':
    main()
