"""
知乎平台实现 - 使用文档导入功能
根据 Playwright 录制脚本重写
"""

import asyncio
import json
import os
from pathlib import Path
from platforms.base import PlatformTool, ToolResult

COOKIE_DIR = Path("data/cookies")
COOKIE_DIR.mkdir(parents=True, exist_ok=True)


def log(msg):
    """写入日志文件"""
    try:
        with open("zhihu_debug.log", "a", encoding="utf-8") as f:
            f.write(f"{msg}\n")
            f.flush()
    except:
        pass


class ZhihuTool(PlatformTool):
    """知乎发布工具"""
    name = "ZhihuPublisher"
    description = "Publish articles to Zhihu platform"
    platform_type = "zhihu"
    
    def __init__(self, account=None):
        super().__init__(account)
        self.cookie_file = COOKIE_DIR / "zhihu.json"
        try:
            with open("zhihu_debug.log", "w", encoding="utf-8") as f:
                f.write("=== 知乎发布调试日志 ===\n")
        except:
            pass
    
    async def init_browser(self, headless: bool = True, load_cookie: bool = True):
        from playwright.async_api import async_playwright
        
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
        )
        
        context_options = {
            'viewport': {'width': 1920, 'height': 1080},
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'locale': 'zh-CN',
        }
        
        if load_cookie and self.cookie_file.exists():
            try:
                with open(self.cookie_file, 'r', encoding='utf-8') as f:
                    context_options['storage_state'] = json.load(f)
            except:
                pass
        
        self.context = await self.browser.new_context(**context_options)
        await self.context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.page = await self.context.new_page()
    
    async def save_cookie(self):
        if self.context:
            storage = await self.context.storage_state()
            with open(self.cookie_file, 'w', encoding='utf-8') as f:
                json.dump(storage, f, ensure_ascii=False, indent=2)
    
    async def authenticate(self) -> bool:
        if not self.page:
            await self.init_browser(headless=False, load_cookie=True)
            await self.page.goto("https://www.zhihu.com")
            await asyncio.sleep(2)
            
            try:
                await self.page.wait_for_selector('.AppHeader-profile img', timeout=5000)
                self._is_authenticated = True
                return True
            except:
                pass
        
        from rich.console import Console
        Console().print("[yellow]请在浏览器中完成知乎登录...[/yellow]")
        await self.page.goto("https://www.zhihu.com/signin")
        input("登录完成后请按回车键继续...")
        await self.save_cookie()
        self._is_authenticated = True
        return True
    
    async def publish(self, article, file_path: str = None) -> ToolResult:
        """使用文档导入功能发布"""
        if not self._is_authenticated:
            if not await self.authenticate():
                return ToolResult(success=False, error="登录失败")
        
        try:
            original_file = file_path or getattr(article, 'source_file', None)
            
            if not original_file or not os.path.exists(original_file):
                return ToolResult(success=False, error=f"找不到原始文件: {original_file}")
            
            log("进入知乎创作页面...")
            await self.page.goto("https://zhuanlan.zhihu.com/write")
            await self.page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)
            
            # 第1步：点击"导入"按钮
            log("点击'导入'按钮...")
            await self.page.get_by_role("button", name="导入").click()
            log("已点击'导入'")
            await asyncio.sleep(1)
            
            # 第2步：点击"导入文档"
            log("点击'导入文档'...")
            await self.page.get_by_role("button", name="导入文档").click()
            log("已点击'导入文档'")
            await asyncio.sleep(2)
            
            # 第3步：点击上传区域
            log("点击上传区域...")
            upload_btn = await self.page.wait_for_selector(
                'button:has-text("点击选择本地文档或拖动文件到窗口上传")',
                timeout=10000
            )
            await upload_btn.click()
            log("已点击上传区域")
            await asyncio.sleep(2)
            
            # 第4步：上传文件（根据录制脚本，这里用 set_input_files）
            log(f"上传文件: {original_file}")
            # 找到 file input 并上传
            file_input = await self.page.wait_for_selector('input[type="file"]', timeout=10000)
            await file_input.set_input_files(original_file)
            log("文件已上传")
            
            # 第5步：等待导入完成（页面会跳转到 /p/xxx/edit）
            log("等待导入完成（页面跳转）...")
            try:
                await self.page.wait_for_url("**/p/**/edit", timeout=120000)
                log(f"导入完成，当前URL: {self.page.url}")
            except Exception as e:
                log(f"等待跳转超时: {e}")
                # 检查是否在编辑页
                current_url = self.page.url
                log(f"当前URL: {current_url}")
                if "/p/" not in current_url:
                    return ToolResult(success=False, error="文档导入超时，未跳转到编辑页")
            
            # 第6步：获取文章ID
            current_url = self.page.url
            post_id = current_url.split("/p/")[1].split("/")[0]
            log(f"文章ID: {post_id}")
            
            # 第7步：检查标题（可选：从文章对象获取或从页面获取）
            log("检查编辑器标题...")
            try:
                title_input = await self.page.wait_for_selector(
                    'textarea[placeholder*="标题"], input[placeholder*="标题"]',
                    timeout=10000
                )
                title_value = await title_input.input_value()
                log(f"当前标题: '{title_value}'")
                
                # 如果文章对象有标题且编辑器标题为空，则填写标题
                article_title = getattr(article, 'title', None)
                if article_title and (not title_value or not title_value.strip()):
                    log(f"填写标题: {article_title}")
                    await title_input.fill(article_title)
            except Exception as e:
                log(f"处理标题时出错: {e}")
            
            # 第8步：发布
            log("点击发布按钮...")
            try:
                publish_btn = await self.page.wait_for_selector('button:has-text("发布")', timeout=10000)
                await publish_btn.click()
                log("已点击发布")
            except Exception as e:
                log(f"点击发布按钮失败: {e}")
                return ToolResult(success=False, error=f"点击发布按钮失败: {e}")
            
            await asyncio.sleep(3)
            
            # 确认弹窗（如果有）
            try:
                confirm_btn = await self.page.wait_for_selector(
                    'button:has-text("发布"):visible',
                    timeout=5000
                )
                await confirm_btn.click()
                log("已点击确认发布")
            except:
                log("没有确认弹窗或已自动确认")
            
            # 第9步：等待跳转到文章页
            log("等待发布完成...")
            try:
                await self.page.wait_for_url("**/p/**", timeout=60000)
                # 确保不是 /edit 结尾
                await asyncio.sleep(2)
                current_url = self.page.url
                log(f"发布后URL: {current_url}")
            except:
                log("等待跳转超时，检查当前URL")
                current_url = self.page.url
                log(f"当前URL: {current_url}")
            
            if "/p/" in current_url and "/edit" not in current_url:
                post_id = current_url.split("/p/")[1].split("?")[0]
                log(f"发布成功，文章ID: {post_id}")
                return ToolResult(success=True, post_id=post_id, post_url=current_url)
            elif "/p/" in current_url:
                # 还在编辑页，可能发布成功了但没跳转
                post_id = current_url.split("/p/")[1].split("/")[0]
                post_url = f"https://zhuanlan.zhihu.com/p/{post_id}"
                log(f"可能在编辑页，文章ID: {post_id}")
                return ToolResult(success=True, post_id=post_id, post_url=post_url)
            else:
                log("发布未成功")
                return ToolResult(success=False, error="发布未完成")
            
        except Exception as e:
            log(f"知乎发布失败: {e}")
            return ToolResult(success=False, error=str(e))
    
    async def check_status(self, post_id: str) -> ToolResult:
        try:
            url = f"https://zhuanlan.zhihu.com/p/{post_id}"
            await self.page.goto(url)
            await asyncio.sleep(2)
            if await self.page.query_selector('.ErrorPage'):
                return ToolResult(success=False, error="文章不存在")
            return ToolResult(success=True, data={"status": "published", "url": url})
        except Exception as e:
            return ToolResult(success=False, error=str(e))
