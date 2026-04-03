"""
百家号发布工具 - 使用文档导入功能
"""

import asyncio
import json
import os
import logging
from pathlib import Path
from platforms.base import PlatformTool, ToolResult
from rich.console import Console

console = Console()
logger = logging.getLogger(__name__)

COOKIE_DIR = Path("data/cookies")
COOKIE_DIR.mkdir(parents=True, exist_ok=True)


def log(msg):
    """写入日志文件"""
    try:
        with open("baijiahao_debug.log", "a", encoding="utf-8") as f:
            f.write(f"{msg}\n")
            f.flush()
    except:
        pass


class BaijiahaoTool(PlatformTool):
    """百家号发布工具"""
    name = "BaijiahaoPublisher"
    description = "Publish articles to Baidu Baijiahao platform"
    platform_type = "baijiahao"
    
    def __init__(self, account=None):
        super().__init__(account)
        self.cookie_file = COOKIE_DIR / "baijiahao.json"
        try:
            with open("baijiahao_debug.log", "w", encoding="utf-8") as f:
                f.write("=== 百家号发布调试日志 ===\n")
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
            await self.page.goto("https://baijiahao.baidu.com/", wait_until="domcontentloaded")
            await asyncio.sleep(3)
            
            current_url = self.page.url
            if "/login" in current_url or "/auth" in current_url:
                log(f"未登录，URL: {current_url}")
                return False
            
            # 检查是否有用户相关元素
            user_selectors = [
                '.user-info',
                '.user-name',
                '.avatar',
                '[class*="user"]',
            ]
            for selector in user_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        log(f"检测到登录状态，选择器: {selector}")
                        return True
                except:
                    continue
            
            # 检查是否有创作入口
            try:
                create_link = await self.page.wait_for_selector('a[href*="builder"], [class*="create"]', timeout=5000)
                if create_link and await create_link.is_visible():
                    log("检测到登录状态：有创作入口")
                    return True
            except:
                pass
            
            log("登录状态不确定，假设已登录")
            return True
            
        except Exception as e:
            log(f"检查登录状态失败: {e}")
            return False
    
    async def authenticate(self) -> bool:
        """自动检测登录状态"""
        if not self.page:
            await self.init_browser(headless=False, load_cookie=True)
        
        console.print("[yellow]检查百家号登录状态...[/yellow]")
        if await self.is_logged_in():
            console.print("[green]✓ 已是登录状态[/green]")
            self._is_authenticated = True
            return True
        
        console.print("[yellow]未登录，请在浏览器中完成百家号登录...[/yellow]")
        await self.page.goto("https://baijiahao.baidu.com/builder/author/register/index")
        
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
                '.ant-modal-close',
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
            
            log("进入百家号创作页面...")
            await self.page.goto("https://baijiahao.baidu.com/builder/rc/edit")
            await self.page.wait_for_load_state("networkidle")
            await asyncio.sleep(5)
            
            # 关闭可能的弹窗
            log("关闭可能的弹窗...")
            await self.close_popup()
            await asyncio.sleep(1)
            
            # 如果有原始文件，尝试文档导入
            if original_file and os.path.exists(original_file):
                log(f"尝试文档导入: {original_file}")
                import_success = await self._import_document(original_file)
                if not import_success:
                    log("文档导入失败，尝试手动填写")
                    await self._fill_content_manually(article)
            else:
                await self._fill_content_manually(article)
            
            await asyncio.sleep(2)
            
            # 填写标题
            if article_title:
                log(f"填写标题: {article_title}")
                await self._fill_title(article_title)
            
            await asyncio.sleep(1)
            
            # 选择分类
            log("选择分类...")
            await self._select_category()
            
            await asyncio.sleep(1)
            
            # 点击发布
            log("点击发布...")
            publish_success = await self._click_publish()
            
            if not publish_success:
                return ToolResult(success=False, error="找不到发布按钮")
            
            # 等待发布完成
            log("等待发布完成...")
            await asyncio.sleep(5)
            
            current_url = self.page.url
            log(f"发布后URL: {current_url}")
            
            # 检查是否发布成功
            success_indicators = [
                '/builder' in current_url,
                '/article' in current_url,
                'id=' in current_url,
            ]
            
            if any(success_indicators):
                log("发布成功")
                # 尝试提取文章ID
                import re
                article_id = None
                match = re.search(r'[?&]id=([^&]+)', current_url)
                if match:
                    article_id = match.group(1)
                
                return ToolResult(success=True, post_id=article_id, post_url=current_url)
            else:
                # 截图查看状态
                try:
                    await self.page.screenshot(path="baijiahao_final_state.png")
                    log("已截图保存到 baijiahao_final_state.png")
                except:
                    pass
                return ToolResult(success=False, error="发布状态不确定")
            
        except Exception as e:
            log(f"百家号发布失败: {e}")
            import traceback
            log(traceback.format_exc())
            return ToolResult(success=False, error=str(e))
    
    async def _import_document(self, file_path: str) -> bool:
        """尝试导入文档"""
        try:
            # 查找导入文档按钮
            import_selectors = [
                'button:has-text("导入")',
                'button:has-text("文档")',
                '[class*="import"]',
                '[class*="upload"]',
            ]
            
            for selector in import_selectors:
                try:
                    btn = await self.page.wait_for_selector(selector, timeout=3000)
                    if btn and await btn.is_visible():
                        await btn.click()
                        log(f"已点击导入按钮: {selector}")
                        await asyncio.sleep(2)
                        break
                except:
                    continue
            else:
                log("未找到导入按钮，尝试直接上传文件")
            
            # 查找文件输入框
            file_input = await self.page.wait_for_selector('input[type="file"]', timeout=5000)
            await file_input.set_input_files(file_path)
            log("文件已上传，等待导入...")
            
            await asyncio.sleep(8)  # 等待文档导入
            return True
            
        except Exception as e:
            log(f"导入文档失败: {e}")
            return False
    
    async def _fill_content_manually(self, article):
        """手动填写内容"""
        try:
            html_content = getattr(article, 'html_content', '')
            content = getattr(article, 'content', '')
            
            # 查找编辑器
            editor_selectors = [
                '[contenteditable="true"]',
                '.editor-content',
                '.ProseMirror',
                '#ueditor_0',
                '[class*="editor"]',
            ]
            
            for selector in editor_selectors:
                try:
                    editor = await self.page.wait_for_selector(selector, timeout=3000)
                    if editor and await editor.is_visible():
                        await editor.click()
                        await self.page.keyboard.press('Control+a')
                        await self.page.keyboard.press('Delete')
                        
                        # 输入HTML内容
                        safe_html = html_content.replace('`', '\`').replace('${', '\${')
                        await self.page.evaluate(f"""
                            const editor = document.querySelector('{selector}');
                            if (editor) {{
                                editor.innerHTML = `{safe_html}`;
                            }}
                        """)
                        log(f"内容已填写 via {selector}")
                        return
                except:
                    continue
            
            log("未找到编辑器")
        except Exception as e:
            log(f"手动填写内容失败: {e}")
    
    async def _fill_title(self, title: str):
        """填写标题"""
        try:
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
                        await title_input.fill(title)
                        log(f"标题已填写 via {selector}")
                        return
                except:
                    continue
            
            # JS 备用方案
            await self.page.evaluate(f"""
                const inputs = document.querySelectorAll('input, textarea');
                for (const input of inputs) {{
                    if (input.placeholder && input.placeholder.includes('标题')) {{
                        input.value = '{title}';
                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        break;
                    }}
                }}
            """)
            log("标题已通过 JS 填写")
        except Exception as e:
            log(f"填写标题失败: {e}")
    
    async def _select_category(self):
        """选择分类"""
        try:
            # 尝试点击分类选择器
            category_selectors = [
                '.category-select',
                '[class*="category"]',
                'button:has-text("分类")',
            ]
            
            for selector in category_selectors:
                try:
                    btn = await self.page.wait_for_selector(selector, timeout=3000)
                    if btn and await btn.is_visible():
                        await btn.click()
                        await asyncio.sleep(1)
                        
                        # 选择第一个选项
                        option_selectors = [
                            '.category-item',
                            '.dropdown-item',
                            '[class*="option"]',
                            'li',
                        ]
                        
                        for opt_selector in option_selectors:
                            try:
                                option = await self.page.wait_for_selector(opt_selector, timeout=2000)
                                if option:
                                    await option.click()
                                    log("分类已选择")
                                    return
                            except:
                                continue
                except:
                    continue
            
            log("未找到分类选择器或已默认")
        except Exception as e:
            log(f"选择分类失败: {e}")
    
    async def _click_publish(self) -> bool:
        """点击发布按钮"""
        try:
            publish_selectors = [
                'button:has-text("发布")',
                'button:has-text("立即发布")',
                '[class*="publish"]',
                '.ant-btn-primary',
            ]
            
            for selector in publish_selectors:
                try:
                    btn = await self.page.wait_for_selector(selector, timeout=5000)
                    if btn and await btn.is_visible():
                        await btn.click()
                        log(f"已点击发布按钮: {selector}")
                        await asyncio.sleep(3)
                        
                        # 处理确认弹窗
                        confirm_selectors = [
                            'button:has-text("确认")',
                            'button:has-text("确定")',
                            '.ant-btn-primary',
                        ]
                        
                        for confirm_selector in confirm_selectors:
                            try:
                                confirm_btn = await self.page.wait_for_selector(confirm_selector, timeout=3000)
                                if confirm_btn and await confirm_btn.is_visible():
                                    await confirm_btn.click()
                                    log("已点击确认")
                                    await asyncio.sleep(2)
                                    break
                            except:
                                continue
                        
                        return True
                except:
                    continue
            
            # JS 备用
            await self.page.evaluate("""
                const btns = document.querySelectorAll('button');
                for (const btn of btns) {
                    if (btn.textContent.includes('发布') || btn.textContent.includes('确认')) {
                        btn.click();
                    }
                }
            """)
            log("通过 JS 点击发布")
            await asyncio.sleep(3)
            return True
            
        except Exception as e:
            log(f"点击发布失败: {e}")
            return False
    
    async def check_status(self, post_id: str) -> ToolResult:
        """检查文章状态"""
        try:
            url = f"https://baijiahao.baidu.com/s?id={post_id}"
            await self.page.goto(url)
            await asyncio.sleep(2)
            
            error_selectors = ['.error-page', '.not-found', '.404']
            for selector in error_selectors:
                if await self.page.query_selector(selector):
                    return ToolResult(success=False, error="文章不存在")
            
            return ToolResult(success=True, data={"status": "published", "url": url})
        except Exception as e:
            return ToolResult(success=False, error=str(e))
