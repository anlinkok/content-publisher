"""
百家号发布工具
使用浏览器自动化方式
"""

import asyncio
from typing import Optional
from .base import PlatformTool, ToolResult
from models import Article, Account


class BaijiahaoTool(PlatformTool):
    """百家号发布工具"""
    name = "BaijiahaoPublisher"
    description = "Publish articles to Baidu Baijiahao platform"
    platform_type = "baijiahao"
    
    async def authenticate(self) -> bool:
        """百家号登录"""
        if not self.page:
            await self.init_browser(headless=False)
        
        # 尝试加载已有会话
        if await self.load_session():
            await self.page.goto("https://baijiahao.baidu.com/")
            await asyncio.sleep(2)
            
            # 检查登录状态
            try:
                await self.page.wait_for_selector('.user-info', timeout=5000)
                self._is_authenticated = True
                logger.info("百家号: 已登录")
                return True
            except:
                pass
        
        console.print("[yellow]请在浏览器中完成百家号登录...[/yellow]")
        await self.page.goto("https://baijiahao.baidu.com/builder/author/register/index")
        
        try:
            await self.page.wait_for_selector('.user-info', timeout=120000)
            self._is_authenticated = True
            await self.save_session()
            logger.info("百家号: 登录成功")
            return True
        except:
            logger.error("百家号: 登录超时")
            return False
    
    async def publish(self, article: Article) -> ToolResult:
        """发布到百家号"""
        if not self._is_authenticated:
            if not await self.authenticate():
                return ToolResult(success=False, error="登录失败")
        
        try:
            # 进入创作页面
            await self.page.goto("https://baijiahao.baidu.com/builder/rc/edit")
            await asyncio.sleep(3)
            
            # 填写标题
            title_input = await self.page.wait_for_selector('input[placeholder*="标题"], textarea[placeholder*="标题"]')
            await title_input.fill(article.title)
            
            # 填写内容 - 百家号使用富文本编辑器
            content_editor = await self.page.wait_for_selector('#ueditor_0, .editor-content, [contenteditable="true"]')
            await content_editor.click()
            
            # 清除默认内容
            await self.page.keyboard.press('Control+a')
            await self.page.keyboard.press('Delete')
            
            # 输入HTML内容
            safe_html = article.html_content.replace('`', '`')
            await self.page.evaluate(f"""
                const editor = document.querySelector('#ueditor_0') || 
                              document.querySelector('.editor-content') ||
                              document.querySelector('[contenteditable=\"true\"]');
                if (editor) {{
                    editor.innerHTML = `{safe_html}`;
                }}
            """)
            
            await asyncio.sleep(2)
            
            # 上传封面图（如果有）
            if article.cover_image:
                try:
                    upload_btn = await self.page.wait_for_selector('.cover-upload, [class*="cover"]', timeout=3000)
                    await upload_btn.click()
                    
                    file_input = await self.page.wait_for_selector('input[type="file"]')
                    await file_input.set_input_files(article.cover_image)
                    await asyncio.sleep(3)
                except:
                    logger.warning("封面图上传失败或不需要")
            
            # 选择分类（默认选第一个）
            try:
                category_btn = await self.page.wait_for_selector('.category-select, [class*="category"]', timeout=3000)
                await category_btn.click()
                await asyncio.sleep(1)
                
                first_option = await self.page.wait_for_selector('.category-item, .dropdown-item')
                await first_option.click()
            except:
                pass
            
            await asyncio.sleep(1)
            
            # 发布按钮
            publish_btn = await self.page.wait_for_selector('button:has-text("发布"), .publish-btn, [class*="publish"]')
            await publish_btn.click()
            
            # 等待发布完成
            await asyncio.sleep(5)
            
            # 获取文章链接
            current_url = self.page.url
            
            # 尝试获取文章ID
            article_id = None
            if "/article/" in current_url or "id=" in current_url:
                import re
                match = re.search(r'[?&]id=([^&]+)', current_url)
                if match:
                    article_id = match.group(1)
            
            return ToolResult(
                success=True,
                post_id=article_id,
                post_url=current_url,
                data={"url": current_url}
            )
            
        except Exception as e:
            logger.exception("百家号发布失败")
            return ToolResult(success=False, error=str(e))
    
    async def check_status(self, post_id: str) -> ToolResult:
        """检查文章状态"""
        try:
            url = f"https://baijiahao.baidu.com/s?id={post_id}"
            await self.page.goto(url)
            await asyncio.sleep(2)
            
            # 检查页面是否存在
            error_selectors = ['.error-page', '.not-found', '.404']
            for selector in error_selectors:
                if await self.page.query_selector(selector):
                    return ToolResult(success=False, error="文章不存在")
            
            return ToolResult(success=True, data={"status": "published", "url": url})
        except Exception as e:
            return ToolResult(success=False, error=str(e))
