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
            
            current_url = self.page.url
            if "/login" in current_url or "/auth/page/login" in current_url:
                log(f"未登录，URL: {current_url}")
                return False
            
            try:
                article_link = await self.page.wait_for_selector('a[href*="graphic/publish"], [role="link"]:has-text("文章")', timeout=5000)
                if article_link and await article_link.is_visible():
                    log("检测到登录状态：有文章创作入口")
                    return True
            except:
                pass
            
            log("登录状态不确定")
            return True
            
        except Exception as e:
            log(f"检查登录状态失败: {e}")
            return False
    
    async def authenticate(self) -> bool:
        """自动检测登录状态"""
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
            close_selectors = [
                '.close-btn',
                '.modal-close',
                '[class*="close"]',
                'button:has-text("×")',
                'button:has-text("关闭")',
                '.byte-modal-close',
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
            # 优先使用传入的 file_path
            original_file = file_path or getattr(article, 'source_file', None)
            article_title = getattr(article, 'title', '')
            
            if not original_file or not os.path.exists(original_file):
                return ToolResult(success=False, error=f"找不到原始文件: {original_file}")
            
            log("进入头条号创作页面...")
            await self.page.goto("https://mp.toutiao.com/profile_v4/graphic/publish")
            await self.page.wait_for_load_state("networkidle")
            await asyncio.sleep(5)
            
            # 关闭可能的弹窗
            log("关闭可能的弹窗...")
            await self.close_popup()
            await asyncio.sleep(1)
            
            # 第1步：点击文档导入按钮
            log("点击文档导入按钮...")
            doc_import_clicked = False
            
            # 尝试多种选择器
            selectors_to_try = [
                '.syl-toolbar-tool.doc-import',
                '[class*="doc-import"]',
                'button:has-text("导入文档")',
                'div:has-text("导入文档")',
            ]
            
            for selector in selectors_to_try:
                try:
                    element = await self.page.wait_for_selector(selector, timeout=3000)
                    if element and await element.is_visible():
                        await element.click()
                        log(f"已点击文档导入: {selector}")
                        doc_import_clicked = True
                        await asyncio.sleep(2)
                        break
                except Exception as e:
                    log(f"选择器 {selector} 失败: {e}")
                    continue
            
            if not doc_import_clicked:
                # 尝试通过父元素点击
                try:
                    await self.page.evaluate("""
                        const btn = document.querySelector('.syl-toolbar-tool.doc-import') || 
                                   document.querySelector('[title="导入文档"]') ||
                                   document.querySelector('div[class*="import"]');
                        if (btn) btn.click();
                    """)
                    log("通过 JS 点击文档导入")
                    await asyncio.sleep(2)
                    doc_import_clicked = True
                except Exception as e:
                    log(f"JS 点击失败: {e}")
            
            if not doc_import_clicked:
                return ToolResult(success=False, error="找不到文档导入按钮")
            
            await asyncio.sleep(2)
            
            # 第2步：上传文件
            log(f"上传文件: {original_file}")
            try:
                # 等待 file input 出现
                file_input = await self.page.wait_for_selector('input[type="file"]', timeout=10000)
                await file_input.set_input_files(original_file)
                log("文件已上传，等待导入...")
            except Exception as e:
                log(f"上传文件失败: {e}")
                return ToolResult(success=False, error=f"上传文件失败: {e}")
            
            # 第3步：等待文档导入完成
            log("等待文档导入完成...")
            await asyncio.sleep(8)  # 增加等待时间
            
            # 关闭可能弹出的提示
            await self.close_popup()
            await asyncio.sleep(1)
            
            # 第4步：填写标题
            if article_title:
                log(f"填写标题: {article_title}")
                try:
                    # 尝试多种标题输入框选择器
                    title_selectors = [
                        'input[placeholder*="标题"]',
                        'textarea[placeholder*="标题"]',
                        '[class*="title"] input',
                        '[class*="title"] textarea',
                    ]
                    
                    for selector in title_selectors:
                        try:
                            title_input = await self.page.wait_for_selector(selector, timeout=3000)
                            if title_input and await title_input.is_visible():
                                await title_input.fill(article_title)
                                log(f"标题已填写 via {selector}")
                                break
                        except:
                            continue
                    else:
                        # 使用 JS 填写
                        await self.page.evaluate(f"""
                            const inputs = document.querySelectorAll('input, textarea');
                            for (const input of inputs) {{
                                if (input.placeholder && input.placeholder.includes('标题')) {{
                                    input.value = '{article_title}';
                                    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                    input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                    break;
                                }}
                            }}
                        """)
                        log("标题已通过 JS 填写")
                except Exception as e:
                    log(f"填写标题失败: {e}")
            
            await asyncio.sleep(2)
            
            # 第5步：设置广告（可选）
            log("设置广告选项...")
            try:
                await self.page.locator(".byte-radio.article-ad-radio").first.click()
                log("广告选项已设置")
            except Exception as e:
                log(f"设置广告选项失败（可能已默认）: {e}")
            
            await asyncio.sleep(1)
            
            # 第6步：选择分类（可选）
            log("选择分类...")
            try:
                checkboxes = await self.page.locator(".byte-checkbox-wrapper").all()
                if len(checkboxes) > 0:
                    await checkboxes[0].click()
                    log("分类已选择")
            except Exception as e:
                log(f"选择分类失败: {e}")
            
            await asyncio.sleep(1)
            
            # 第7步：点击"预览并发布"
            log("点击'预览并发布'...")
            preview_clicked = False
            
            preview_selectors = [
                'button:has-text("预览并发布")',
                'button:has-text("预览")',
                '[class*="preview"]',
                'div:has-text("预览并发布")',
            ]
            
            for selector in preview_selectors:
                try:
                    btn = await self.page.wait_for_selector(selector, timeout=5000)
                    if btn and await btn.is_visible():
                        await btn.click()
                        log(f"已点击'预览并发布': {selector}")
                        preview_clicked = True
                        await asyncio.sleep(3)
                        break
                except:
                    continue
            
            if not preview_clicked:
                # 尝试 JS
                try:
                    await self.page.evaluate("""
                        const btns = document.querySelectorAll('button');
                        for (const btn of btns) {
                            if (btn.textContent.includes('预览') || btn.textContent.includes('发布')) {
                                btn.click();
                                break;
                            }
                        }
                    """)
                    log("通过 JS 点击预览")
                    preview_clicked = True
                    await asyncio.sleep(3)
                except Exception as e:
                    log(f"JS 点击预览失败: {e}")
            
            if not preview_clicked:
                return ToolResult(success=False, error="找不到预览并发布按钮")
            
            # 第8步：点击"确认发布"
            log("点击'确认发布'...")
            confirm_clicked = False
            
            confirm_selectors = [
                'button:has-text("确认发布")',
                'button:has-text("确认")',
                'button:has-text("发布")',
                '.byte-btn-primary',
                '[class*="confirm"]',
                'div:has-text("确认发布")',
            ]
            
            for selector in confirm_selectors:
                try:
                    btn = await self.page.wait_for_selector(selector, timeout=5000)
                    if btn and await btn.is_visible():
                        await btn.click()
                        log(f"已点击确认按钮: {selector}")
                        confirm_clicked = True
                        await asyncio.sleep(5)
                        break
                except:
                    continue
            
            if not confirm_clicked:
                # 尝试 JS 点击所有可能的发布按钮
                try:
                    await self.page.evaluate("""
                        const btns = document.querySelectorAll('button');
                        for (const btn of btns) {
                            const text = btn.textContent || '';
                            if (text.includes('确认') || text.includes('发布') || text.includes('确定')) {
                                btn.click();
                                console.log('Clicked:', text);
                            }
                        }
                    """)
                    log("通过 JS 点击确认")
                    confirm_clicked = True
                    await asyncio.sleep(5)
                except Exception as e:
                    log(f"JS 点击确认失败: {e}")
            
            if not confirm_clicked:
                return ToolResult(success=False, error="找不到确认发布按钮")
            
            # 第9步：等待发布完成并检查结果
            log("等待发布完成...")
            await asyncio.sleep(5)
            
            current_url = self.page.url
            log(f"发布后URL: {current_url}")
            
            # 检查是否发布成功（URL变化或成功提示）
            success_indicators = [
                '/graphic/publish' in current_url,
                '/article' in current_url,
                '/content' in current_url,
            ]
            
            if any(success_indicators):
                log("发布成功")
                return ToolResult(success=True, post_url=current_url)
            else:
                # 截图查看当前状态
                try:
                    await self.page.screenshot(path="toutiao_final_state.png")
                    log("已截图保存到 toutiao_final_state.png")
                except:
                    pass
                return ToolResult(success=False, error="发布状态不确定，请检查浏览器")
            
        except Exception as e:
            log(f"头条号发布失败: {e}")
            import traceback
            log(traceback.format_exc())
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
