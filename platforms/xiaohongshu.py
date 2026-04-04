"""
小红书 (Xiaohongshu) 平台适配器
小红书创作者平台
"""
import asyncio
import json
import os
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
        
        # 加载 Cookie（优先使用完整 state）
        if load_cookie:
            # 尝试加载完整 storage state
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
            
            if result and isinstance(result, dict):
                # 检查 data 是否是字典并且有 user_id
                data = result.get('data')
                if isinstance(data, dict) and data.get('user_id'):
                    return {
                        'is_authenticated': True,
                        'user_id': str(data['user_id']),
                        'username': data.get('nickname', ''),
                        'avatar': data.get('avatar', ''),
                    }
                # 登录过期
                if result.get('result') == -100 or result.get('code') == -1:
                    return {'is_authenticated': False, 'error': '登录已过期', 'response': result}
            
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
        """检查是否已登录 - 通过页面跳转检测"""
        try:
            # 尝试访问首页
            await self.page.goto('https://creator.xiaohongshu.com/', wait_until='domcontentloaded')
            await asyncio.sleep(2)
            
            current_url = self.page.url
            print(f"检测登录状态，当前URL: {current_url}")
            
            # 如果被重定向到登录页，说明未登录
            if 'login' in current_url:
                print("未登录 - 被重定向到登录页")
                return False
            
            # 如果能正常访问首页，说明已登录
            if 'creator.xiaohongshu.com' in current_url and 'login' not in current_url:
                print("已登录 - 成功访问首页")
                return True
            
            return False
        except Exception as e:
            print(f"登录检测出错: {e}")
            return False
    
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
                print(f"\n✓ 检测到页面跳转: {current_url}")
                print("页面已从登录页跳转，说明登录成功！")
                print("等待3秒后保存Cookie...")
                await asyncio.sleep(3)
                
                # 直接保存Cookie（页面跳转说明已登录）
                await self.save_cookies()
                print("✓ Cookie保存成功！")
                await self.close()
                return True
            
            # 每10秒显示进度
            if i % 10 == 0 and i > 0:
                print(f"等待登录中... 已等待 {i} 秒")
            
            await asyncio.sleep(1)
        
        print("\n登录超时，请重试")
        await self.close()
        return False
    
    async def save_cookies(self):
        """保存登录状态（包括 cookies 和 localStorage）"""
        os.makedirs('data/cookies', exist_ok=True)
        
        # 保存完整的 storage state（cookies + localStorage + sessionStorage）
        storage = await self.context.storage_state()
        cookie_file = f'data/cookies/{self.platform_id}_state.json'
        with open(cookie_file, 'w', encoding='utf-8') as f:
            json.dump(storage, f, ensure_ascii=False, indent=2)
        print(f"登录状态已保存到: {cookie_file}")
        
        # 同时保存旧格式的 cookies（兼容）
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
            
            # 检查登录状态
            log("检查登录状态...")
            if not await self.is_logged_in():
                log("未登录，请先运行 login 命令")
                return ToolResult(success=False, error="未登录")
            
            log("已登录，进入发布页面...")
            # 小红书创作者平台 - 选择写长文模式
            await self.page.goto('https://creator.xiaohongshu.com/creator/note/create', wait_until='domcontentloaded')
            log("等待页面加载...")
            await asyncio.sleep(5)
            
            # 输出当前页面信息
            current_url = self.page.url
            log(f"当前URL: {current_url}")
            
            # 检查是否被重定向
            if 'login' in current_url:
                log("未登录，被重定向到登录页")
                await self.close()
                return ToolResult(success=False, error="未登录")
            
            # 点击"写长文"选项（如果有的话）
            try:
                # 查找写长文按钮
                long_text_selectors = [
                    'button:has-text("写长文")',
                    'div:has-text("写长文")',
                    '[class*="long"]',
                    '[data-testid*="long"]',
                ]
                for selector in long_text_selectors:
                    try:
                        long_text_btn = await self.page.wait_for_selector(selector, timeout=3000)
                        if long_text_btn:
                            log(f"找到写长文按钮: {selector}")
                            await long_text_btn.click()
                            log("已点击写长文")
                            await asyncio.sleep(3)
                            break
                    except:
                        continue
            except Exception as e:
                log(f"选择写长文模式失败（可能页面直接进入编辑器）: {e}")
            
            # 小红书发布流程：先上传图片，再填写文字
            # 处理图片上传（小红书必须先有图片）
            cover_image = getattr(article, 'cover_image', None)
            if cover_image:
                log(f"上传图片: {cover_image}")
                try:
                    # 等待文件输入框出现
                    await self.page.wait_for_selector('input[type="file"]', timeout=10000)
                    file_inputs = await self.page.query_selector_all('input[type="file"]')
                    if file_inputs:
                        await file_inputs[0].set_input_files(cover_image)
                        log("图片已选择，等待上传...")
                        await asyncio.sleep(5)  # 等待上传完成
                        log("图片上传完成")
                    else:
                        log("未找到文件输入框")
                except Exception as e:
                    log(f"图片上传失败: {e}")
            else:
                log("警告: 没有封面图片，小红书需要至少一张图片")
            
            # 填写标题（限制20字）
            title = getattr(article, 'title', '无标题')[:20]
            log(f"填写标题: {title}")
            
            try:
                # 小红书标题选择器 - 使用多种方式
                title_selectors = [
                    'input[placeholder*="标题"]',
                    'textarea[placeholder*="标题"]',
                    'div[contenteditable="true"]',
                    '[class*="title"]',
                ]
                title_input = None
                for selector in title_selectors:
                    try:
                        title_input = await self.page.wait_for_selector(selector, timeout=3000)
                        if title_input:
                            log(f"找到标题输入框: {selector}")
                            break
                    except:
                        continue
                
                if title_input:
                    await title_input.fill(title)
                    log("标题填写完成")
                else:
                    log("未找到标题输入框")
            except Exception as e:
                log(f"标题输入失败: {e}")
            
            # 填写正文（限制1000字）
            content = getattr(article, 'content', '')[:1000]
            log(f"填写正文: {len(content)} 字")
            
            try:
                # 查找内容编辑器
                content_editors = await self.page.query_selector_all('div[contenteditable="true"]')
                if len(content_editors) >= 2:
                    # 通常第一个是标题，第二个是正文
                    await content_editors[1].fill(content)
                    log("正文填写完成")
                elif len(content_editors) == 1:
                    await content_editors[0].fill(content)
                    log("内容填写完成")
                else:
                    log("未找到内容编辑器")
            except Exception as e:
                log(f"正文输入失败: {e}")
            
            await asyncio.sleep(2)
            
            # 点击发布按钮
            log("点击发布...")
            try:
                # 多种发布按钮选择器
                publish_selectors = [
                    'button:has-text("发布")',
                    'button:has-text("立即发布")',
                    'button.publish-btn',
                    '[class*="publish"] button',
                    'button[type="submit"]',
                ]
                
                publish_btn = None
                for selector in publish_selectors:
                    try:
                        publish_btn = await self.page.wait_for_selector(selector, timeout=3000)
                        if publish_btn:
                            log(f"找到发布按钮: {selector}")
                            break
                    except:
                        continue
                
                if publish_btn:
                    await publish_btn.click()
                    log("已点击发布，等待结果...")
                    await asyncio.sleep(8)
                    
                    # 检查发布结果
                    current_url = self.page.url
                    log(f"发布后URL: {current_url}")
                    
                    if 'success' in current_url or 'published' in current_url or 'note' in current_url:
                        log("✓ 发布成功！")
                        await self.close()
                        return ToolResult(
                            success=True,
                            post_url=current_url,
                            data={'platform': 'xiaohongshu', 'url': current_url}
                        )
                    else:
                        # 截图查看结果
                        result_screenshot = f'data/xiaohongshu_result_{int(asyncio.get_event_loop().time())}.png'
                        await self.page.screenshot(path=result_screenshot, full_page=True)
                        log(f"结果截图: {result_screenshot}")
                        
                        await self.close()
                        return ToolResult(
                            success=True,
                            post_url=current_url,
                            data={'platform': 'xiaohongshu', 'url': current_url, 'note': '请检查截图确认发布状态'}
                        )
                else:
                    log("未找到发布按钮")
                    await self.close()
                    return ToolResult(success=False, error="未找到发布按钮")
                    
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
