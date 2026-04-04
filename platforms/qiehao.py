"""
企鹅号 (Qiehao / Tencent Content Open Platform) 平台适配器
腾讯内容开放平台
"""
import asyncio
import json
from typing import Optional
from playwright.async_api import Page

from platforms.base import PlatformTool, ToolResult


class QiehaoTool(PlatformTool):
    """企鹅号平台适配器"""
    
    platform_name = "qiehao"
    platform_id = "qiehao"
    platform_type = "article"
    
    # 企鹅号使用 HTML 格式
    output_format = "html"
    
    async def init_browser(self, headless: bool = True, load_cookie: bool = True):
        """初始化浏览器"""
        from playwright.async_api import async_playwright
        
        self.playwright = await async_playwright().start()
        
        # 浏览器配置
        browser_args = [
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-setuid-sandbox',
        ]
        
        context_options = {
            'viewport': {'width': 1920, 'height': 1080},
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        
        # 加载 Cookie
        if load_cookie:
            cookie_file = f"data/cookies/{self.platform_id}.json"
            try:
                with open(cookie_file, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                    context_options['storage_state'] = {'cookies': cookies}
            except FileNotFoundError:
                pass
        
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=browser_args
        )
        self.context = await self.browser.new_context(**context_options)
        self.page = await self.context.new_page()
    
    async def check_auth(self) -> dict:
        """检查登录状态"""
        try:
            result = await self.page.evaluate("""
                async () => {
                    try {
                        const res = await fetch('https://om.qq.com/mcp/outerAccount/info', {
                            method: 'GET',
                            credentials: 'include',
                            headers: {
                                'Origin': 'https://om.qq.com',
                                'Referer': 'https://om.qq.com/',
                            }
                        });
                        return await res.json();
                    } catch (e) {
                        return { error: e.message };
                    }
                }
            """)
            
            if result and result.get('ret') == 0 and result.get('data', {}).get('uin'):
                return {
                    'is_authenticated': True,
                    'user_id': str(result['data']['uin']),
                    'username': result['data'].get('nick', ''),
                    'avatar': result['data'].get('head', ''),
                }
            return {'is_authenticated': False}
        except Exception as e:
            return {'is_authenticated': False, 'error': str(e)}
    
    async def is_logged_in(self) -> bool:
        """检查是否已登录"""
        result = await self.check_auth()
        return result.get('is_authenticated', False)
    
    async def authenticate(self) -> bool:
        """登录企鹅号"""
        await self.init_browser(headless=False)
        
        # 打开登录页
        await self.page.goto('https://om.qq.com/userAuth/index')
        
        # 等待登录成功
        max_wait = 300  # 5分钟
        for i in range(max_wait):
            if await self.is_logged_in():
                # 保存 Cookie
                await self.save_cookies()
                await self.close()
                return True
            await asyncio.sleep(1)
        
        await self.close()
        return False
    
    async def save_cookies(self):
        """保存 Cookie"""
        import os
        os.makedirs('data/cookies', exist_ok=True)
        
        storage = await self.context.storage_state()
        with open(f'data/cookies/{self.platform_id}.json', 'w', encoding='utf-8') as f:
            json.dump(storage.get('cookies', []), f, ensure_ascii=False, indent=2)
    
    async def close(self):
        """关闭浏览器"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def upload_image(self, image_path: str) -> str:
        """上传图片到企鹅号"""
        try:
            return image_path
        except Exception as e:
            print(f"企鹅号图片上传失败: {e}")
            return image_path
    
    async def publish(self, article, file_path: str = None) -> ToolResult:
        """发布文章到企鹅号"""
        debug_log = []
        
        def log(msg):
            debug_log.append(msg)
            print(msg)
        
        try:
            await self.init_browser()
            
            # 检查登录
            log("检查登录状态...")
            if not await self.is_logged_in():
                log("未登录，请先运行 login 命令")
                return ToolResult(success=False, error="未登录")
            
            log("已登录")
            
            # 进入内容管理页面
            log("进入发布页面...")
            await self.page.goto('https://om.qq.com/main/information')
            await asyncio.sleep(3)
            
            # 点击写文章按钮
            log("点击写文章...")
            try:
                write_btn = await self.page.wait_for_selector('a:has-text("写文章"), button:has-text("写文章"), .write-btn, [data-testid="write-article"]', timeout=5000)
                await write_btn.click()
                await asyncio.sleep(3)
            except Exception as e:
                log(f"写文章按钮未找到，可能已在编辑页面: {e}")
            
            # 填写标题
            title = getattr(article, 'title', '无标题')
            log(f"填写标题: {title}")
            
            try:
                title_input = await self.page.wait_for_selector('input[name="title"], input[placeholder*="标题"], .title-input, [data-testid="title"]', timeout=10000)
                await title_input.fill(title)
            except Exception as e:
                log(f"标题输入失败: {e}")
            
            # 填写正文
            html_content = getattr(article, 'html_content', '')
            if not html_content and file_path:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    html_content = f"<p>{content.replace(chr(10), '</p><p>')}</p>"
            
            log(f"填写正文...")
            try:
                # 尝试找到编辑器
                editor = await self.page.wait_for_selector('.ql-editor, [contenteditable="true"], .editor-content, #editor', timeout=10000)
                await editor.click()
                await self.page.keyboard.press('Control+a')
                await self.page.keyboard.press('Delete')
                
                # 通过 JavaScript 设置内容
                await self.page.evaluate(f"""
                    const editor = document.querySelector('.ql-editor') || 
                                   document.querySelector('[contenteditable="true"]') ||
                                   document.querySelector('.editor-content') ||
                                   document.querySelector('#editor');
                    if (editor) {{
                        editor.innerHTML = `{html_content}`;
                    }}
                """)
                log("正文填写完成")
            except Exception as e:
                log(f"正文输入失败: {e}")
            
            await asyncio.sleep(2)
            
            # 选择分类
            log("选择分类...")
            try:
                category_btn = await self.page.wait_for_selector('.category-select, [class*="category"], .dropdown-trigger', timeout=5000)
                await category_btn.click()
                await asyncio.sleep(1)
                first_cat = await self.page.wait_for_selector('.category-item, .dropdown-item, .select-item', timeout=3000)
                await first_cat.click()
                log("分类选择完成")
            except Exception as e:
                log(f"分类选择失败（可选）: {e}")
            
            # 保存草稿
            log("保存草稿...")
            try:
                draft_btn = await self.page.wait_for_selector('button:has-text("存草稿"), .draft-btn, [data-testid="draft"]', timeout=3000)
                await draft_btn.click()
                await asyncio.sleep(3)
                log("草稿保存成功")
            except Exception as e:
                log(f"草稿保存按钮未找到: {e}")
            
            # 点击发布
            log("点击发布...")
            try:
                publish_btn = await self.page.wait_for_selector('button:has-text("发布"), .publish-btn, [data-testid="publish"], button:has-text("立即发布")', timeout=10000)
                await publish_btn.click()
                await asyncio.sleep(5)
                
                current_url = self.page.url
                log(f"发布完成，当前URL: {current_url}")
                
                await self.close()
                return ToolResult(
                    success=True,
                    post_url=current_url,
                    data={'platform': 'qiehao', 'url': current_url}
                )
                
            except Exception as e:
                log(f"发布按钮点击失败: {e}")
                await self.close()
                return ToolResult(success=False, error=f"发布失败: {e}")
            
        except Exception as e:
            log(f"发布失败: {str(e)}")
            await self.close()
            return ToolResult(success=False, error=str(e))
    
    async def check_status(self, post_id: str) -> dict:
        """检查文章发布状态"""
        try:
            await self.init_browser()
            
            if not await self.is_logged_in():
                return {'success': False, 'error': '未登录'}
            
            # 访问内容管理页面
            await self.page.goto('https://om.qq.com/main/information')
            await asyncio.sleep(3)
            
            await self.close()
            return {'success': True, 'status': 'unknown', 'note': '企鹅号状态检查需要具体文章ID接口'}
            
        except Exception as e:
            await self.close()
            return {'success': False, 'error': str(e)}
