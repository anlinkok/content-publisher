"""
小红书 (Xiaohongshu) 平台适配器 - 基于 Playwright Codegen 精确选择器
"""
import asyncio
import json
import os
import re
from typing import Optional
from playwright.async_api import Page

from platforms.base import PlatformTool, ToolResult


class XiaohongshuTool(PlatformTool):
    """小红书平台适配器 - 长文模式"""
    
    platform_name = "xiaohongshu"
    platform_id = "xiaohongshu"
    platform_type = "article"
    
    # 小红书长文模式支持 Word 直接上传
    output_format = "docx"
    
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
            'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        
        # 加载登录状态
        if load_cookie:
            state_file = f"data/cookies/{self.platform_id}_state.json"
            cookie_file = f"data/cookies/{self.platform_id}.json"
            
            try:
                if os.path.exists(state_file):
                    with open(state_file, 'r', encoding='utf-8') as f:
                        storage = json.load(f)
                        context_options['storage_state'] = storage
                        print(f"已加载完整登录状态: {state_file}")
                elif os.path.exists(cookie_file):
                    with open(cookie_file, 'r', encoding='utf-8') as f:
                        cookies = json.load(f)
                        context_options['storage_state'] = {'cookies': cookies}
                        print(f"已加载Cookie: {cookie_file}")
            except Exception as e:
                print(f"加载登录状态失败: {e}")
        
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
                        const res = await fetch('https://creator.xiaohongshu.com/api/galaxy/creator/info', {
                            method: 'GET',
                            credentials: 'include',
                            headers: {
                                'Origin': 'https://creator.xiaohongshu.com',
                                'Referer': 'https://creator.xiaohongshu.com/',
                            }
                        });
                        return await res.json();
                    } catch (e) {
                        return {error: e.message};
                    }
                }
            """)
            
            if result and isinstance(result, dict):
                data = result.get('data')
                if isinstance(data, dict) and data.get('user_id'):
                    return {
                        'is_authenticated': True,
                        'user_id': str(data['user_id']),
                        'username': data.get('nickname', ''),
                        'avatar': data.get('avatar', ''),
                    }
                if result.get('result') == -100 or result.get('code') == -1:
                    return {'is_authenticated': False, 'error': '登录已过期', 'response': result}
            
            return {'is_authenticated': False, 'response': result}
        except Exception as e:
            return {'is_authenticated': False, 'error': str(e)}
    
    async def is_logged_in(self) -> bool:
        """检查是否已登录"""
        try:
            await self.page.goto('https://creator.xiaohongshu.com/', wait_until='domcontentloaded')
            await asyncio.sleep(2)
            
            current_url = self.page.url
            if 'login' in current_url:
                return False
            
            if 'creator.xiaohongshu.com' in current_url and 'login' not in current_url:
                return True
            
            return False
        except Exception as e:
            return False
    
    async def authenticate(self) -> bool:
        """登录小红书"""
        await self.init_browser(headless=False)
        
        print("打开小红书登录页面...")
        await self.page.goto('https://creator.xiaohongshu.com/login')
        print("请在浏览器中扫码或输入账号密码登录...")
        print("登录成功后会自动检测并保存...")
        
        # 等待页面跳转
        max_wait = 300
        for i in range(max_wait):
            current_url = self.page.url
            
            if 'creator.xiaohongshu.com/login' not in current_url and 'creator.xiaohongshu.com' in current_url:
                print(f"\n✓ 检测到页面跳转: {current_url}")
                print("页面已从登录页跳转，说明登录成功！")
                print("等待3秒后保存Cookie...")
                await asyncio.sleep(3)
                
                await self.save_cookies()
                print("✓ Cookie保存成功！")
                await self.close()
                return True
            
            if i % 10 == 0 and i > 0:
                print(f"等待登录中... 已等待 {i} 秒")
            
            await asyncio.sleep(1)
        
        print("\n登录超时，请重试")
        await self.close()
        return False
    
    async def save_cookies(self):
        """保存登录状态"""
        os.makedirs('data/cookies', exist_ok=True)
        
        storage = await self.context.storage_state()
        state_file = f'data/cookies/{self.platform_id}_state.json'
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(storage, f, ensure_ascii=False, indent=2)
        print(f"登录状态已保存到: {state_file}")
        
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
    
    async def publish(self, article, file_path: str = None) -> ToolResult:
        """发布长文到小红书 - 使用 Codegen 精确选择器"""
        debug_log = []
        
        def log(msg):
            debug_log.append(msg)
            print(msg)
        
        try:
            await self.init_browser(headless=False)
            
            # 检查登录
            log("检查登录状态...")
            if not await self.is_logged_in():
                log("未登录，请先运行 login 命令")
                return ToolResult(success=False, error="未登录")
            
            log("✓ 已登录")
            
            # Step 1: 访问首页并点击"发布笔记"
            log("Step 1: 点击发布笔记...")
            await self.page.goto('https://creator.xiaohongshu.com/new/home', wait_until='domcontentloaded')
            await asyncio.sleep(3)
            
            try:
                await self.page.get_by_text("发布笔记").click()
                log("✓ 已点击发布笔记")
            except Exception as e:
                log(f"点击发布笔记失败: {e}")
                # 直接访问创建页面
                await self.page.goto('https://creator.xiaohongshu.com/creator/note/create')
            
            await asyncio.sleep(3)
            
            # Step 2: 选择"写长文"
            log("Step 2: 选择写长文...")
            try:
                # 使用 first 避免严格模式冲突
                await self.page.get_by_text("写长文").first.click()
                log("✓ 已选择写长文")
                await asyncio.sleep(3)
            except Exception as e:
                log(f"选择写长文失败: {e}")
            
            # Step 3: 点击"新的创作"
            log("Step 3: 点击新的创作...")
            try:
                # 使用 first 并增加超时
                await self.page.get_by_role("button", name="新的创作").first.click()
                log("✓ 已点击新的创作")
                await asyncio.sleep(3)
            except Exception as e:
                log(f"点击新的创作失败: {e}")
                # 如果失败，可能是页面没跳转，直接访问创建页
                log("尝试直接访问创建页面...")
                await self.page.goto('https://creator.xiaohongshu.com/creator/note/create?from=publish')
                await asyncio.sleep(5)
            
            # Step 4: 上传 Word 文件
            if file_path:
                log(f"Step 4: 上传文件 {file_path}...")
                try:
                    # 直接找 input 上传（不点按钮）
                    file_input = self.page.locator('input[type="file"]').first
                    await file_input.set_input_files(file_path)
                    log(f"✓ 文件已上传")
                    
                    # 关键：等待解析完成（看标题是否自动填入）
                    log("等待文档解析（最多30秒）...")
                    for i in range(30):
                        await asyncio.sleep(1)
                        # 检查标题是否已自动填入
                        try:
                            title_val = await self.page.locator('[placeholder*="标题"]').first.input_value()
                            if title_val and len(title_val) > 0:
                                log(f"✓ 文档解析完成，自动标题: {title_val}")
                                break
                        except:
                            pass
                        if i % 5 == 0:
                            log(f"  解析中... {i}s")
                    
                except Exception as e:
                    log(f"文件上传失败: {e}")
                    # 截图看问题
                    ss = f'data/xiaohongshu_upload_error_{int(asyncio.get_event_loop().time())}.png'
                    await self.page.screenshot(path=ss, full_page=True)
                    log(f"错误截图: {ss}")
            
            # 截图看当前状态
            ss = f'data/xiaohongshu_step4_{int(asyncio.get_event_loop().time())}.png'
            await self.page.screenshot(path=ss, full_page=True)
            log(f"Step 4 完成截图: {ss}")
            
            # Step 5: 修改标题（如果需要）
            title = getattr(article, 'title', '')[:20]
            if title:
                log(f"Step 5: 修改标题为: {title}")
                try:
                    title_input = self.page.locator('[placeholder*="标题"]').first
                    await title_input.fill(title)
                    log("✓ 标题修改完成")
                except Exception as e:
                    log(f"标题修改失败（可能已自动填入）: {e}")
            
            # Step 6: 一键排版
            log("Step 6: 一键排版...")
            try:
                # 等待页面稳定
                await asyncio.sleep(2)
                
                # 尝试点击一键排版
                one_click_btn = self.page.get_by_role("button", name="一键排版").first
                try:
                    await one_click_btn.click(timeout=5000)
                except:
                    # 强制点击
                    await one_click_btn.evaluate("el => el.click()")
                
                log("✓ 已点击一键排版")
                await asyncio.sleep(3)
                
                # 选择样式
                style_btn = self.page.locator("div").filter(has_text=re.compile(r"^清晰明朗$")).first
                await style_btn.click()
                log("✓ 已选择排版样式")
                await asyncio.sleep(2)
            except Exception as e:
                log(f"一键排版失败: {e}")
            
            # Step 7: 下一步
            log("Step 7: 点击下一步...")
            try:
                await self.page.get_by_role("button", name="下一步").click()
                log("✓ 已点击下一步")
                await asyncio.sleep(5)
            except Exception as e:
                log(f"点击下一步失败: {e}")
            
            # Step 8: 发布
            log("Step 8: 点击发布...")
            try:
                await self.page.get_by_role("button", name="发布").click()
                log("✓ 已点击发布按钮")
                log("等待发布完成...")
                await asyncio.sleep(10)
                
                current_url = self.page.url
                log(f"发布后URL: {current_url}")
                
                await self.close()
                return ToolResult(
                    success=True,
                    post_url=current_url,
                    data={'platform': 'xiaohongshu', 'url': current_url}
                )
                
            except Exception as e:
                log(f"点击发布失败: {e}")
                await self.close()
                return ToolResult(success=False, error=f"发布失败: {e}")
            
        except Exception as e:
            log(f"发布失败: {str(e)}")
            await self.close()
            return ToolResult(success=False, error=str(e))
    
    async def check_status(self, post_id: str) -> ToolResult:
        """检查笔记发布状态"""
        try:
            await self.init_browser()
            
            if not await self.is_logged_in():
                return ToolResult(success=False, error='未登录')
            
            # 访问创作者中心查看笔记状态
            await self.page.goto('https://creator.xiaohongshu.com/new/note-manager')
            await asyncio.sleep(3)
            
            await self.close()
            return ToolResult(success=True, data={'status': 'unknown', 'note': '请访问创作者中心查看笔记状态'})
            
        except Exception as e:
            await self.close()
            return ToolResult(success=False, error=str(e))
