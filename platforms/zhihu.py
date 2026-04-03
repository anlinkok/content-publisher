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
            await asyncio.sleep(3)
            
            # 第1步：点击"导入"按钮
            log("点击'导入'按钮...")
            try:
                await self.page.get_by_role("button", name="导入").click()
                log("已点击'导入'")
            except:
                await self.page.click('text=导入', timeout=5000)
                log("已点击'导入'（备用）")
            await asyncio.sleep(2)
            
            # 第2步：点击"导入文档"
            log("点击'导入文档'...")
            try:
                await self.page.get_by_role("button", name="导入文档").click()
                log("已点击'导入文档'")
            except:
                await self.page.click('text=导入文档', timeout=5000)
                log("已点击'导入文档'（备用）")
            await asyncio.sleep(3)
            
            # 第3步：直接找到弹窗中的 file input 并上传
            # 不需要点击按钮，直接操作 input
            log("查找弹窗中的文件上传框...")
            
            # 等待弹窗出现
            try:
                await self.page.wait_for_selector('.Modal, [role="dialog"]', timeout=10000)
                log("弹窗已出现")
            except:
                log("等待弹窗超时，继续尝试上传...")
            
            # 查找所有 file input，找包含 docx 的那个
            log("查找 file input...")
            file_inputs = await self.page.query_selector_all('input[type="file"]')
            log(f"找到 {len(file_inputs)} 个 file input")
            
            target_input = None
            for i, inp in enumerate(file_inputs):
                try:
                    accept = await inp.get_attribute('accept')
                    log(f"  input {i}: accept={accept}")
                    if accept and ('.docx' in accept or '.doc' in accept):
                        target_input = inp
                        log(f"  选中 input {i}")
                        break
                except:
                    pass
            
            if not target_input and len(file_inputs) > 0:
                target_input = file_inputs[0]
                log("使用第一个 input")
            
            if not target_input:
                return ToolResult(success=False, error="找不到文件上传框")
            
            # 上传文件
            log(f"上传文件: {original_file}")
            await target_input.set_input_files(original_file)
            log("文件已上传，等待导入...")
            
            # 第4步：等待导入完成（页面跳转到 /p/xxx/edit）
            log("等待导入完成，最多2分钟...")
            try:
                await self.page.wait_for_url("**/p/**/edit", timeout=120000)
                log(f"导入完成，当前URL: {self.page.url}")
            except Exception as e:
                log(f"等待跳转超时: {e}")
                current_url = self.page.url
                log(f"当前URL: {current_url}")
                if "/p/" in current_url and "/edit" in current_url:
                    log("已在编辑页，继续")
                elif "/p/" in current_url:
                    log("已在文章页，可能已发布")
                    post_id = current_url.split("/p/")[1].split("?")[0]
                    return ToolResult(success=True, post_id=post_id, post_url=current_url)
                else:
                    return ToolResult(success=False, error="文档导入超时")
            
            # 第5步：获取文章ID
            current_url = self.page.url
            post_id = current_url.split("/p/")[1].split("/")[0]
            log(f"文章ID: {post_id}")
            
            # 第6步：点击发布
            log("点击发布...")
            try:
                publish_btn = await self.page.wait_for_selector('button:has-text("发布")', timeout=10000)
                await publish_btn.click()
                log("已点击发布")
            except Exception as e:
                log(f"点击发布失败: {e}")
                return ToolResult(success=False, error=f"点击发布按钮失败: {e}")
            
            await asyncio.sleep(3)
            
            # 确认弹窗
            try:
                confirm_btn = await self.page.wait_for_selector('button:has-text("发布"):visible', timeout=5000)
                await confirm_btn.click()
                log("已点击确认发布")
            except:
                log("没有确认弹窗")
            
            # 第7步：等待完成
            log("等待发布完成...")
            try:
                await self.page.wait_for_url("**/p/**", timeout=60000)
                await asyncio.sleep(2)
                current_url = self.page.url
            except:
                current_url = self.page.url
            
            if "/p/" in current_url and "/edit" not in current_url:
                post_id = current_url.split("/p/")[1].split("?")[0]
                log(f"发布成功，文章ID: {post_id}")
                return ToolResult(success=True, post_id=post_id, post_url=current_url)
            elif "/p/" in current_url:
                post_id = current_url.split("/p/")[1].split("/")[0]
                post_url = f"https://zhuanlan.zhihu.com/p/{post_id}"
                log(f"发布成功，文章ID: {post_id}")
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
