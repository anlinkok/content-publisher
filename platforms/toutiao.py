"""
头条号平台实现 - 使用文档导入功能
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
        with open("toutiao_debug.log", "a", encoding="utf-8") as f:
            f.write(f"{msg}\n")
            f.flush()
    except:
        pass


class ToutiaoTool(PlatformTool):
    """头条号发布工具"""
    name = "ToutiaoPublisher"
    description = "Publish articles to Toutiao platform"
    platform_type = "toutiao"
    
    def __init__(self, account=None):
        super().__init__(account)
        self.cookie_file = COOKIE_DIR / "toutiao.json"
        try:
            with open("toutiao_debug.log", "w", encoding="utf-8") as f:
                f.write("=== 头条号发布调试日志 ===\n")
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
    
    async def is_logged_in(self) -> bool:
        """检查当前是否已登录"""
        try:
            await self.page.goto("https://mp.toutiao.com/profile_v4/index", wait_until="domcontentloaded")
            await asyncio.sleep(3)
            
            # 检查是否跳转到登录页
            current_url = self.page.url
            if "/login" in current_url or "/auth/page/login" in current_url:
                log(f"未登录，URL: {current_url}")
                return False
            
            # 检查是否有"文章"链接（已登录用户才有创作入口）
            try:
                article_link = await self.page.wait_for_selector('a[href*="graphic/publish"], [role="link"]:has-text("文章")', timeout=5000)
                if article_link:
                    is_visible = await article_link.is_visible()
                    if is_visible:
                        log("检测到登录状态：有文章创作入口")
                        return True
            except:
                pass
            
            # 检查用户名/头像
            user_selectors = [
                '.user-name',
                '.avatar',
                '.user-info',
                '[class*="userName"]',
            ]
            for selector in user_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        log(f"检测到登录状态，选择器: {selector}")
                        return True
                except:
                    continue
            
            log("登录状态不确定，假设已登录")
            return True
            
        except Exception as e:
            log(f"检查登录状态失败: {e}")
            return False
    
    async def authenticate(self) -> bool:
        """自动检测登录状态，需要时引导登录"""
        from rich.console import Console
        console = Console()
        
        if not self.page:
            await self.init_browser(headless=False, load_cookie=True)
        
        console.print("[yellow]检查头条号登录状态...[/yellow]")
        if await self.is_logged_in():
            console.print("[green]✓ 已是登录状态[/green]")
            self._is_authenticated = True
            return True
        
        console.print("[yellow]未登录，请在浏览器中扫码或账号密码登录...[/yellow]")
        await self.page.goto("https://mp.toutiao.com/auth/page/login")
        
        console.print("[cyan]等待登录完成（请在浏览器中操作）...[/cyan]")
        start_time = asyncio.get_event_loop().time()
        timeout = 120
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            await asyncio.sleep(2)
            
            if await self.is_logged_in():
                console.print("[green]✓ 登录成功！[/green]")
                await self.save_cookie()
                self._is_authenticated = True
                return True
            
            elapsed = int(asyncio.get_event_loop().time() - start_time)
            console.print(f"[dim]等待中... {elapsed}s/{timeout}s[/dim]", end="\r")
        
        console.print("\n[red]登录超时，请重试[/red]")
        return False
    
    async def close_popup(self):
        """关闭可能的弹窗"""
        try:
            # 尝试点击关闭按钮
            close_selectors = [
                '.close-btn',
                '.modal-close',
                '[class*="close"]',
                'button:has-text("×")',
                'button:has-text("关闭")',
            ]
            for selector in close_selectors:
                try:
                    btn = await self.page.query_selector(selector)
                    if btn and await btn.is_visible():
                        await btn.click()
                        log(f"已关闭弹窗: {selector}")
                        await asyncio.sleep(0.5)
                        return
                except:
                    continue
        except Exception as e:
            log(f"关闭弹窗时出错: {e}")
    
    async def publish(self, article, file_path: str = None) -> ToolResult:
        """使用文档导入功能发布"""
        if not self._is_authenticated:
            if not await self.authenticate():
                return ToolResult(success=False, error="登录失败")
        
        try:
            original_file = file_path or getattr(article, 'source_file', None)
            article_title = getattr(article, 'title', '')
            
            if not original_file or not os.path.exists(original_file):
                return ToolResult(success=False, error=f"找不到原始文件: {original_file}")
            
            log("进入头条号创作页面...")
            await self.page.goto("https://mp.toutiao.com/profile_v4/index")
            await self.page.wait_for_load_state("networkidle")
            await asyncio.sleep(3)
            
            # 第1步：点击"文章"
            log("点击'文章'...")
            try:
                await self.page.get_by_role("link", name="文章").click()
                log("已点击'文章'")
            except Exception as e:
                log(f"点击文章失败: {e}")
                # 备用：直接访问创作页面
                await self.page.goto("https://mp.toutiao.com/profile_v4/graphic/publish")
            
            await asyncio.sleep(3)
            
            # 第2步：关闭可能的弹窗
            log("关闭可能的弹窗...")
            await self.close_popup()
            
            # 第3步：点击文档导入按钮
            log("点击文档导入按钮...")
            try:
                # 根据录制代码，选择器是 .syl-toolbar-tool.doc-import
                await self.page.locator(".syl-toolbar-tool.doc-import > div > .syl-toolbar-button").click()
                log("已点击文档导入")
            except Exception as e:
                log(f"点击文档导入失败: {e}")
                # 备用：尝试其他选择器
                try:
                    await self.page.click('text=导入文档', timeout=5000)
                    log("已点击'导入文档'（备用）")
                except:
                    return ToolResult(success=False, error="找不到文档导入按钮")
            
            await asyncio.sleep(2)
            
            # 第4步：上传文件
            log(f"上传文件: {original_file}")
            try:
                # 直接操作 file input
                file_input = await self.page.wait_for_selector('input[type="file"]', timeout=10000)
                await file_input.set_input_files(original_file)
                log("文件已上传")
            except Exception as e:
                log(f"上传文件失败: {e}")
                return ToolResult(success=False, error=f"上传文件失败: {e}")
            
            # 第5步：等待文档导入完成（内容出现在编辑器中）
            log("等待文档导入完成...")
            await asyncio.sleep(5)
            
            # 第6步：填写标题
            if article_title:
                log(f"填写标题: {article_title}")
                try:
                    title_input = await self.page.get_by_role(
                        "textbox", 
                        name="请输入文章标题（2～30个字）"
                    )
                    await title_input.fill(article_title)
                    log("标题已填写")
                except Exception as e:
                    log(f"填写标题失败: {e}")
            
            # 第7步：设置广告（选择无广告或默认）
            log("设置广告选项...")
            try:
                # 选择第一个广告选项（无广告或默认）
                await self.page.locator(".byte-radio.article-ad-radio > span > .byte-radio-inner").first.click()
                log("广告选项已设置")
            except Exception as e:
                log(f"设置广告选项失败（可能已默认）: {e}")
            
            # 第8步：选择分类（可选，尝试选择第一个）
            log("选择分类...")
            try:
                # 尝试选择第一个分类
                checkboxes = await self.page.locator(".byte-checkbox-group > label > .byte-checkbox-wrapper > .byte-checkbox-mask").all()
                if len(checkboxes) > 0:
                    await checkboxes[0].click()
                    log("分类已选择")
            except Exception as e:
                log(f"选择分类失败: {e}")
            
            # 第9步：点击"预览并发布"
            log("点击'预览并发布'...")
            try:
                await self.page.get_by_role("button", name="预览并发布").click()
                log("已点击'预览并发布'")
            except Exception as e:
                log(f"点击预览并发布失败: {e}")
                return ToolResult(success=False, error="找不到预览并发布按钮")
            
            await asyncio.sleep(3)
            
            # 第10步：点击"确认发布"
            log("点击'确认发布'...")
            try:
                await self.page.get_by_role("button", name="确认发布").click()
                log("已点击'确认发布'")
            except Exception as e:
                log(f"点击确认发布失败: {e}")
                # 备用：尝试其他按钮
                try:
                    await self.page.click('button:has-text("确认")', timeout=5000)
                    log("已点击'确认'（备用）")
                except:
                    return ToolResult(success=False, error="找不到确认发布按钮")
            
            # 第11步：等待发布完成
            log("等待发布完成...")
            await asyncio.sleep(5)
            
            current_url = self.page.url
            log(f"发布后URL: {current_url}")
            
            # 检查发布结果
            if "/graphic/publish" in current_url or "/article" in current_url:
                log("发布成功")
                return ToolResult(success=True, post_url=current_url)
            else:
                return ToolResult(success=False, error="发布可能未完成，请检查")
            
        except Exception as e:
            log(f"头条号发布失败: {e}")
            return ToolResult(success=False, error=str(e))
    
    async def check_status(self, post_id: str) -> ToolResult:
        """检查文章状态"""
        try:
            url = f"https://www.toutiao.com/article/{post_id}"
            await self.page.goto(url)
            await asyncio.sleep(2)
            
            error_selectors = ['.error-page', '.not-found', '.404']
            for selector in error_selectors:
                if await self.page.query_selector(selector):
                    return ToolResult(success=False, error="文章不存在或未通过审核")
            
            return ToolResult(success=True, data={"status": "published", "url": url})
        except Exception as e:
            return ToolResult(success=False, error=str(e))
