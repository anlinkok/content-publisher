"""
小红书 (Xiaohongshu) 平台适配器
小红书创作者平台
"""
import asyncio
import json
import re
from typing import Optional
from playwright.async_api import Page

from platforms.base import PlatformTool, ToolResult


class XiaohongshuTool(PlatformTool):
    """小红书平台适配器"""
    
    platform_name = "xiaohongshu"
    platform_id = "xiaohongshu"
    platform_type = "article"
    
    # 小红书使用图文模式
    output_format = "markdown"
    
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
            # 方法1: 检查页面是否有用户信息元素
            user_info = await self.page.evaluate("""
                () => {
                    // 尝试从 window 对象获取用户信息
                    if (window.__INITIAL_STATE__ && window.__INITIAL_STATE__.user) {
                        return window.__INITIAL_STATE__.user;
                    }
                    // 尝试从 localStorage 获取
                    try {
                        const user = localStorage.getItem('user_info');
                        if (user) return JSON.parse(user);
                    } catch(e) {}
                    return null;
                }
            """)
            
            if user_info and (user_info.get('user_id') or user_info.get('id')):
                return {
                    'is_authenticated': True,
                    'user_id': str(user_info.get('user_id') or user_info.get('id')),
                    'username': user_info.get('nickname', ''),
                }
            
            # 方法2: 调用 API 检测
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
            
            print(f"API 检测响应: {result}")
            
            if result.get('data') and result.get('data', {}).get('user_id'):
                return {
                    'is_authenticated': True,
                    'user_id': str(result['data']['user_id']),
                    'username': result['data'].get('nickname', ''),
                    'avatar': result['data'].get('avatar', ''),
                }
            
            # 方法3: 简单检查是否还在登录页
            current_url = self.page.url
            if 'login' not in current_url and 'creator.xiaohongshu.com' in current_url:
                # 页面已跳转，大概率已登录
                return {
                    'is_authenticated': True,
                    'user_id': 'unknown',
                    'username': 'unknown',
                    'note': '页面已跳转，假设已登录'
                }
            
            return {'is_authenticated': False, 'response': result}
        except Exception as e:
            print(f"登录检测出错: {e}")
            return {'is_authenticated': False, 'error': str(e)}
    
    async def is_logged_in(self) -> bool:
        """检查是否已登录"""
        result = await self.check_auth()
        return result.get('is_authenticated', False)
    
    async def authenticate(self) -> bool:
        """登录小红书"""
        await self.init_browser(headless=False)
        
        # 打开登录页
        print("打开小红书登录页面...")
        await self.page.goto('https://creator.xiaohongshu.com/login')
        print("请在浏览器中扫码或输入账号密码登录...")
        print("登录成功后会自动检测并保存...")
        
        # 等待页面跳转到首页（说明登录成功）
        max_wait = 300  # 5分钟
        for i in range(max_wait):
            current_url = self.page.url
            
            # 检测到已跳转到首页或其他创作者页面
            if 'creator.xiaohongshu.com/login' not in current_url and 'creator.xiaohongshu.com' in current_url:
                print(f"\n检测到页面跳转: {current_url}")
                print("等待页面加载完成...")
                await asyncio.sleep(3)  # 等待页面完全加载
                
                # 检测登录状态
                auth_result = await self.check_auth()
                if auth_result.get('is_authenticated'):
                    print(f"✓ 登录成功！用户: {auth_result.get('username', 'unknown')}")
                    # 保存 Cookie
                    await self.save_cookies()
                    await self.close()
                    return True
                else:
                    print(f"登录检测详情: {auth_result}")
                    # 如果页面已跳转，大概率已登录，直接保存
                    if 'login' not in current_url:
                        print("✓ 页面已跳转，假设登录成功，保存Cookie...")
                        await self.save_cookies()
                        await self.close()
                        return True
                    print("页面已跳转但登录检测失败，继续等待...")
            
            # 每10秒显示进度
            if i % 10 == 0 and i > 0:
                print(f"等待登录中... 已等待 {i} 秒")
            
            await asyncio.sleep(1)
        
        print("\n登录超时，请重试")
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
        """上传图片到小红书"""
        try:
            # 小红书图片上传需要通过创作者平台的 API
            # 这里返回原始路径，实际使用时需要在前端处理
            return image_path
        except Exception as e:
            print(f"小红书图片上传失败: {e}")
            return image_path
    
    async def publish(self, article, file_path: str = None) -> ToolResult:
        """发布笔记到小红书
        
        注意：小红书是图文笔记形式，标题限制20字，正文限制1000字
        """
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
            
            # 进入发布页面
            log("进入发布页面...")
            await self.page.goto('https://creator.xiaohongshu.com/publish/publish')
            await asyncio.sleep(3)
            
            # 处理封面图片上传
            cover_image = getattr(article, 'cover_image', None)
            if cover_image and file_path:
                log(f"上传封面图片: {cover_image}")
                try:
                    # 查找文件输入框
                    file_input = await self.page.wait_for_selector('input[type="file"]', timeout=5000)
                    await file_input.set_input_files(cover_image)
                    await asyncio.sleep(3)
                    log("封面上传完成")
                except Exception as e:
                    log(f"封面上传失败: {e}")
            
            # 填写标题（限制20字）
            title = getattr(article, 'title', '无标题')[:20]
            log(f"填写标题: {title}")
            
            try:
                title_input = await self.page.wait_for_selector('textarea[placeholder*="标题"], input[placeholder*="标题"]', timeout=5000)
                await title_input.fill(title)
            except Exception as e:
                log(f"标题输入失败: {e}")
            
            # 填写正文（限制1000字）
            content = getattr(article, 'content', '')[:1000]
            log(f"填写正文: {len(content)} 字")
            
            try:
                content_input = await self.page.wait_for_selector('textarea[placeholder*="正文"], [contenteditable="true"]', timeout=5000)
                await content_input.fill(content)
            except Exception as e:
                log(f"正文输入失败: {e}")
            
            await asyncio.sleep(1)
            
            # 点击发布按钮
            log("点击发布...")
            try:
                publish_btn = await self.page.wait_for_selector('button:has-text("发布"), button:has-text("立即发布")', timeout=5000)
                await publish_btn.click()
                await asyncio.sleep(5)
                
                # 检查发布结果
                current_url = self.page.url
                if 'success' in current_url or 'published' in current_url:
                    log("发布成功")
                    await self.close()
                    return ToolResult(
                        success=True,
                        post_url=current_url,
                        data={'platform': 'xiaohongshu', 'url': current_url}
                    )
                else:
                    log(f"发布完成，当前URL: {current_url}")
                    await self.close()
                    return ToolResult(
                        success=True,
                        post_url=current_url,
                        data={'platform': 'xiaohongshu', 'url': current_url}
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
        """检查笔记发布状态"""
        try:
            await self.init_browser()
            
            if not await self.is_logged_in():
                return {'success': False, 'error': '未登录'}
            
            # 访问创作者中心检查状态
            await self.page.goto('https://creator.xiaohongshu.com/publish/publish')
            await asyncio.sleep(3)
            
            await self.close()
            return {'success': True, 'status': 'unknown', 'note': '小红书状态检查需要具体笔记ID接口'}
            
        except Exception as e:
            await self.close()
            return {'success': False, 'error': str(e)}
