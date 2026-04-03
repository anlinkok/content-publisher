"""
网易号发布工具
"""

import asyncio
from typing import Optional
from .base import PlatformTool, ToolResult
from models import Article, Account


class WangyiTool(PlatformTool):
    """网易号发布工具"""
    name = "WangyiPublisher"
    description = "Publish articles to NetEase Wangyi platform"
    platform_type = "wangyi"
    
    async def authenticate(self) -> bool:
        """网易号登录"""
        if not self.page:
            await self.init_browser(headless=False)
        
        if await self.load_session():
            await self.page.goto("https://mp.163.com/")
            await asyncio.sleep(2)
            
            try:
                await self.page.wait_for_selector('.user-name, .user-info', timeout=5000)
                self._is_authenticated = True
                logger.info("网易号: 已登录")
                return True
            except:
                pass
        
        console.print("[yellow]请在浏览器中完成网易号登录...[/yellow]")
        await self.page.goto("https://mp.163.com/login.html")
        
        try:
            await self.page.wait_for_selector('.user-name, .user-info', timeout=120000)
            self._is_authenticated = True
            await self.save_session()
            logger.info("网易号: 登录成功")
            return True
        except:
            logger.error("网易号: 登录超时")
            return False
    
    async def publish(self, article: Article) -> ToolResult:
        """发布到网易号"""
        if not self._is_authenticated:
            if not await self.authenticate():
                return ToolResult(success=False, error="登录失败")
        
        try:
            # 进入创作页面
            await self.page.goto("https://mp.163.com/submit.html")
            await asyncio.sleep(3)
            
            # 填写标题
            title_input = await self.page.wait_for_selector('input[name="title"], input[placeholder*="标题"], #title')
            await title_input.fill(article.title)
            
            # 填写内容
            content_editor = await self.page.wait_for_selector('#ueditor_0, .edui-editor-iframeholder iframe, [contenteditable="true"]')
            await content_editor.click()
            
            # 清除默认内容
            await self.page.keyboard.press('Control+a')
            await self.page.keyboard.press('Delete')
            
            # 输入HTML内容
            safe_html = article.html_content.replace('`', '`')
            await self.page.evaluate(f"""
                const editor = document.querySelector('#ueditor_0') || 
                              document.querySelector('.edui-editor-iframeholder iframe') ||
                              document.querySelector('[contenteditable=\"true\"]');
                if (editor) {{
                    if (editor.contentDocument) {{
                        editor.contentDocument.body.innerHTML = `{safe_html}`;
                    }} else {{
                        editor.innerHTML = `{safe_html}`;
                    }}
                }}
            """)
            
            await asyncio.sleep(2)
            
            # 选择分类
            try:
                category_select = await self.page.wait_for_selector('select[name="category"], .category-select', timeout=3000)
                await category_select.select_option(index=1)  # 选择第一个非默认选项
            except:
                pass
            
            # 发布
            publish_btn = await self.page.wait_for_selector('#submit, button:has-text("发布"), .submit-btn')
            await publish_btn.click()
            
            await asyncio.sleep(5)
            
            return ToolResult(success=True, data={"url": self.page.url})
            
        except Exception as e:
            logger.exception("网易号发布失败")
            return ToolResult(success=False, error=str(e))
    
    async def check_status(self, post_id: str) -> ToolResult:
        return ToolResult(success=True)
