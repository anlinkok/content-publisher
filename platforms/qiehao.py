"""
企鹅号(腾讯内容开放平台)发布工具
"""

import asyncio
import logging
from typing import Optional
from .base import PlatformTool, ToolResult
from models import Article, Account
from rich.console import Console

console = Console()
logger = logging.getLogger(__name__)


class QiehaoTool(PlatformTool):
    """企鹅号发布工具"""
    name = "QiehaoPublisher"
    description = "Publish articles to Tencent Qiehao platform"
    platform_type = "qiehao"
    
    async def authenticate(self) -> bool:
        """企鹅号登录"""
        if not self.page:
            await self.init_browser(headless=False)
        
        if await self.load_session():
            await self.page.goto("https://om.qq.com/")
            await asyncio.sleep(2)
            
            try:
                await self.page.wait_for_selector('.user-info, .user-name, .avatar', timeout=5000)
                self._is_authenticated = True
                logger.info("企鹅号: 已登录")
                return True
            except:
                pass
        
        console.print("[yellow]请在浏览器中完成企鹅号登录...[/yellow]")
        await self.page.goto("https://om.qq.com/userAuth/index")
        
        try:
            await self.page.wait_for_selector('.user-info, .user-name, .avatar', timeout=120000)
            self._is_authenticated = True
            await self.save_session()
            logger.info("企鹅号: 登录成功")
            return True
        except:
            logger.error("企鹅号: 登录超时")
            return False
    
    async def publish(self, article: Article) -> ToolResult:
        """发布到企鹅号"""
        if not self._is_authenticated:
            if not await self.authenticate():
                return ToolResult(success=False, error="登录失败")
        
        try:
            # 进入创作页面
            await self.page.goto("https://om.qq.com/main/information")
            await asyncio.sleep(3)
            
            # 点击写文章按钮（如果需要）
            try:
                write_btn = await self.page.wait_for_selector('a:has-text("写文章"), button:has-text("写文章")', timeout=3000)
                await write_btn.click()
                await asyncio.sleep(2)
            except:
                pass
            
            # 填写标题
            title_input = await self.page.wait_for_selector('input[name="title"], input[placeholder*="标题"], .title-input')
            await title_input.fill(article.title)
            
            # 填写内容
            content_editor = await self.page.wait_for_selector('.ql-editor, [contenteditable="true"], .editor-content')
            await content_editor.click()
            
            # 清除默认内容
            await self.page.keyboard.press('Control+a')
            await self.page.keyboard.press('Delete')
            
            # 输入HTML内容
            safe_html = article.html_content.replace('`', '`')
            await self.page.evaluate(f"""
                const editor = document.querySelector('.ql-editor') || 
                              document.querySelector('[contenteditable=\"true\"]') ||
                              document.querySelector('.editor-content');
                if (editor) {{
                    editor.innerHTML = `{safe_html}`;
                }}
            """)
            
            await asyncio.sleep(2)
            
            # 选择分类
            try:
                category_btn = await self.page.wait_for_selector('.category-select, [class*="category"]', timeout=3000)
                await category_btn.click()
                await asyncio.sleep(1)
                first_cat = await self.page.wait_for_selector('.category-item, .dropdown-item')
                await first_cat.click()
            except:
                pass
            
            # 发布
            publish_btn = await self.page.wait_for_selector('button:has-text("发布"), .publish-btn, [class*="publish"]')
            await publish_btn.click()
            
            await asyncio.sleep(5)
            
            return ToolResult(success=True, data={"url": self.page.url})
            
        except Exception as e:
            logger.exception("企鹅号发布失败")
            return ToolResult(success=False, error=str(e))
    
    async def check_status(self, post_id: str) -> ToolResult:
        return ToolResult(success=True)
