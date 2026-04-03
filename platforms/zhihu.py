"""
知乎平台实现
"""

import asyncio
import logging
from platforms.base import PlatformTool, ToolResult

logger = logging.getLogger(__name__)


class ZhihuTool(PlatformTool):
    """知乎发布工具"""
    name = "ZhihuPublisher"
    description = "Publish articles to Zhihu platform"
    platform_type = "zhihu"
    
    async def authenticate(self) -> bool:
        """知乎登录"""
        if not self.page:
            await self.init_browser(headless=False)
        
        # 尝试加载已有会话
        if await self.load_session():
            await self.page.goto("https://www.zhihu.com")
            await asyncio.sleep(2)
            
            # 检查是否已登录
            try:
                await self.page.wait_for_selector('[data-za-detail-view-element_name="UserAvatar"]', timeout=5000)
                self._is_authenticated = True
                logger.info("知乎: 已登录")
                return True
            except:
                pass
        
        # 需要重新登录
        from rich.console import Console
        console = Console()
        console.print("[yellow]请在浏览器中完成知乎登录...[/yellow]")
        await self.page.goto("https://www.zhihu.com/signin")
        
        try:
            await self.page.wait_for_selector('[data-za-detail-view-element_name="UserAvatar"]', timeout=120000)
            self._is_authenticated = True
            await self.save_session()
            logger.info("知乎: 登录成功")
            return True
        except:
            logger.error("知乎: 登录超时")
            return False
    
    async def publish(self, article) -> ToolResult:
        """发布到知乎专栏"""
        if not self._is_authenticated:
            if not await self.authenticate():
                return ToolResult(success=False, error="登录失败")
        
        try:
            # 进入创作页面
            await self.page.goto("https://zhuanlan.zhihu.com/write")
            await asyncio.sleep(3)
            
            # 填写标题
            title_input = await self.page.wait_for_selector('textarea[placeholder*="标题"]')
            await title_input.fill(article.title)
            
            # 填写内容
            content_editor = await self.page.wait_for_selector('.DraftEditor-root')
            await content_editor.click()
            
            # 输入HTML内容
            safe_html = article.html_content.replace('`', '\\`')
            await self.page.evaluate(f"""
                document.querySelector('.DraftEditor-root').innerHTML = `<div class=\"DraftEditor-editorContainer\"><div contenteditable=\"true\" class=\"public-DraftEditor-content\">{safe_html}</div></div>`;
            """)
            
            await asyncio.sleep(2)
            
            # 发布按钮
            publish_btn = await self.page.wait_for_selector('button:has-text("发布")')
            await publish_btn.click()
            
            await asyncio.sleep(5)
            
            # 获取文章链接
            current_url = self.page.url
            if "/p/" in current_url:
                post_id = current_url.split("/p/")[1].split("?")[0]
                return ToolResult(
                    success=True,
                    post_id=post_id,
                    post_url=current_url
                )
            
            return ToolResult(success=True, data={"url": current_url})
            
        except Exception as e:
            logger.exception("知乎发布失败")
            return ToolResult(success=False, error=str(e))
    
    async def check_status(self, post_id: str) -> ToolResult:
        """检查知乎文章状态"""
        try:
            url = f"https://zhuanlan.zhihu.com/p/{post_id}"
            await self.page.goto(url)
            await asyncio.sleep(2)
            
            if await self.page.query_selector('.ErrorPage'):
                return ToolResult(success=False, error="文章不存在")
            
            return ToolResult(success=True, data={"status": "published", "url": url})
        except Exception as e:
            return ToolResult(success=False, error=str(e))
