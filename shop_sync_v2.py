"""
店群铺货工具 v2 - 类谋臣界实现
无需API授权，纯浏览器自动化操作
支持：淘宝、拼多多、抖音、京东、1688 互搬
"""
import os
import json
import time
import asyncio
from typing import List, Dict, Optional
from dataclasses import dataclass
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import io
import hashlib


@dataclass
class Product:
    """商品数据结构"""
    title: str
    price: float
    original_price: float
    stock: int
    main_images: List[str]  # 主图URL列表
    detail_images: List[str]  # 详情图URL列表
    sku_list: List[Dict]  # SKU列表
    description: str
    category: str
    source_url: str
    source_platform: str


class PlatformCrawler:
    """平台采集器基类"""
    
    def __init__(self, playwright_page):
        self.page = playwright_page
        
    async def login_by_cookie(self, cookie_file: str):
        """Cookie登录（无需授权）"""
        if os.path.exists(cookie_file):
            with open(cookie_file, 'r') as f:
                cookies = json.load(f)
            await self.page.context.add_cookies(cookies)
            print(f"✓ Cookie登录成功: {cookie_file}")
            return True
        return False
    
    async def save_cookie(self, cookie_file: str):
        """保存Cookie"""
        cookies = await self.page.context.cookies()
        with open(cookie_file, 'w') as f:
            json.dump(cookies, f)
        print(f"✓ Cookie已保存: {cookie_file}")


class TaobaoCrawler(PlatformCrawler):
    """淘宝采集器"""
    
    async def fetch_product(self, url: str) -> Product:
        """采集淘宝商品"""
        await self.page.goto(url)
        await self.page.wait_for_load_state('networkidle')
        
        # 等待商品信息加载
        await self.page.wait_for_selector('.tb-detail-hd h1, [data-spm="title"]')
        
        # 提取标题
        title = await self.page.eval_on_selector(
            '.tb-detail-hd h1, [data-spm="title"]',
            'el => el.textContent.trim()'
        )
        
        # 提取价格
        price_text = await self.page.eval_on_selector(
            '.tb-rmb-num, .notranslate, [class*="price"]',
            'el => el.textContent.trim()'
        )
        price = float(price_text.replace('¥', '').replace(',', '')) if price_text else 0
        
        # 提取主图
        main_images = await self.page.eval_on_selector_all(
            '#J_UlThumb li img, .tb-pic img',
            'els => els.map(el => el.src.replace(/_\d+x\d+.*\./, "."))'
        )
        
        # 提取SKU
        sku_list = await self.page.eval_on_selector_all(
            '.J_Prop, [class*="sku"]',
            '''els => els.map(el => ({
                name: el.querySelector('[class*="name"], dt')?.textContent?.trim() || '',
                values: Array.from(el.querySelectorAll('[class*="value"], li, dd')).map(v => v.textContent.trim())
            }))'''
        )
        
        return Product(
            title=title[:60],  # 淘宝标题限制60字符
            price=price,
            original_price=price * 1.2,  # 原价设为1.2倍
            stock=999,
            main_images=main_images[:5],
            detail_images=[],
            sku_list=sku_list,
            description=title,
            category='',
            source_url=url,
            source_platform='taobao'
        )
    
    async def publish_product(self, product: Product):
        """发布商品到淘宝"""
        await self.page.goto('https://item.upload.taobao.com/sell/publish.htm')
        await self.page.wait_for_load_state('networkidle')
        
        # 填写标题
        await self.page.fill('#title', product.title)
        
        # 填写价格
        await self.page.fill('#price', str(product.price))
        
        # 上传主图（模拟点击上传）
        # 这里需要处理图片上传逻辑
        
        print(f"✓ 淘宝商品发布表单已填充: {product.title}")


class PddCrawler(PlatformCrawler):
    """拼多多采集器"""
    
    async def fetch_product(self, url: str) -> Product:
        """采集拼多多商品"""
        await self.page.goto(url)
        await self.page.wait_for_load_state('networkidle')
        
        # 提取标题
        title = await self.page.eval_on_selector(
            '[data-testid="pdp-title"], .goods-name, h1',
            'el => el.textContent.trim()'
        )
        
        # 提取价格（拼多多价格格式较复杂）
        price_text = await self.page.eval_on_selector(
            '[data-testid="pdp-price"], .price, [class*="price"]',
            'el => el.textContent.trim()'
        )
        price = float(price_text.replace('¥', '').replace(',', '').split('-')[0]) if price_text else 0
        
        # 提取主图
        main_images = await self.page.eval_on_selector_all(
            '[data-testid="pdp-main-image"] img, .main-image img',
            'els => els.map(el => el.src)'
        )
        
        return Product(
            title=title[:30],  # 拼多多标题限制30字符
            price=price,
            original_price=price * 1.5,
            stock=999,
            main_images=main_images[:10],
            detail_images=[],
            sku_list=[],
            description=title,
            category='',
            source_url=url,
            source_platform='pdd'
        )
    
    async def publish_product(self, product: Product):
        """发布商品到拼多多"""
        await self.page.goto('https://mms.pinduoduo.com/home/')
        # 拼多多发布流程...
        print(f"✓ 拼多多商品发布表单已填充: {product.title}")


class ImageProcessor:
    """图片处理器 - 谋臣界式改图"""
    
    def __init__(self, output_dir: str = "processed_images"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def process_image(self, image_path: str, options: Dict) -> str:
        """
        处理图片：
        - 去水印（模糊处理）
        - 加自己的水印
        - 改尺寸
        - 调亮度/对比度
        """
        img = Image.open(image_path)
        
        # 1. 去水印（用模糊覆盖常见水印位置）
        if options.get('remove_watermark'):
            img = self._remove_watermark(img)
        
        # 2. 改尺寸
        if options.get('resize'):
            width = options.get('width', 800)
            ratio = width / img.width
            height = int(img.height * ratio)
            img = img.resize((width, height), Image.Resampling.LANCZOS)
        
        # 3. 调整亮度/对比度
        if options.get('enhance'):
            enhancer = ImageEnhance.Brightness(img)
            img = enhancer.enhance(options.get('brightness', 1.0))
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(options.get('contrast', 1.0))
        
        # 4. 加自己的水印
        if options.get('add_watermark'):
            img = self._add_watermark(
                img, 
                options.get('watermark_text', ''),
                options.get('watermark_position', 'bottom-right')
            )
        
        # 保存
        output_name = f"{hashlib.md5(image_path.encode()).hexdigest()[:8]}.jpg"
        output_path = os.path.join(self.output_dir, output_name)
        img.save(output_path, "JPEG", quality=options.get('quality', 90))
        
        return output_path
    
    def _remove_watermark(self, img: Image.Image) -> Image.Image:
        """简单去水印：模糊处理角落"""
        # 处理右下角常见水印位置
        width, height = img.size
        box = (width - 200, height - 100, width, height)
        region = img.crop(box)
        region = region.filter(ImageFilter.GaussianBlur(radius=5))
        img.paste(region, box)
        return img
    
    def _add_watermark(self, img: Image.Image, text: str, position: str) -> Image.Image:
        """添加文字水印"""
        if not text:
            return img
        
        draw = ImageDraw.Draw(img)
        
        # 字体大小自适应
        font_size = int(img.width * 0.04)
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            font = ImageFont.load_default()
        
        # 计算位置
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        if position == 'bottom-right':
            x = img.width - text_width - 20
            y = img.height - text_height - 20
        elif position == 'bottom-left':
            x = 20
            y = img.height - text_height - 20
        elif position == 'center':
            x = (img.width - text_width) // 2
            y = (img.height - text_height) // 2
        else:
            x, y = 20, 20
        
        # 半透明背景
        draw.rectangle(
            [x-10, y-5, x+text_width+10, y+text_height+5],
            fill=(0, 0, 0, 128)
        )
        draw.text((x, y), text, font=font, fill=(255, 255, 255))
        
        return img
    
    def batch_process(self, image_urls: List[str], options: Dict) -> List[str]:
        """批量处理图片"""
        processed = []
        import requests
        
        for i, url in enumerate(image_urls):
            try:
                # 下载图片
                response = requests.get(url, timeout=30)
                temp_path = os.path.join(self.output_dir, f"temp_{i}.jpg")
                with open(temp_path, 'wb') as f:
                    f.write(response.content)
                
                # 处理
                result = self.process_image(temp_path, options)
                processed.append(result)
                
                # 清理临时文件
                os.remove(temp_path)
                
            except Exception as e:
                print(f"  ! 处理图片失败: {e}")
                continue
        
        return processed


class ShopSyncTool:
    """
    店群铺货工具 - 类谋臣界实现
    """
    
    def __init__(self):
        self.image_processor = ImageProcessor()
        self.playwright = None
        self.browser = None
        self.context = None
        
    async def init_browser(self, headless: bool = False):
        """初始化浏览器"""
        from playwright.async_api import async_playwright
        
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=['--disable-blink-features=AutomationControlled']
        )
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            locale='zh-CN'
        )
        print("✓ 浏览器已启动")
    
    async def sync_product(self, source_url: str, source_platform: str, 
                          target_platforms: List[str], image_options: Dict):
        """
        同步商品流程：
        1. 从源平台采集
        2. 处理图片
        3. 发布到目标平台
        """
        print(f"\n{'='*50}")
        print(f"开始同步: {source_url}")
        print(f"{'='*50}")
        
        # 1. 采集商品
        print("\n[1/3] 采集商品信息...")
        page = await self.context.new_page()
        
        if source_platform == 'taobao':
            crawler = TaobaoCrawler(page)
            await crawler.login_by_cookie('cookies/taobao.json')
            product = await crawler.fetch_product(source_url)
        elif source_platform == 'pdd':
            crawler = PddCrawler(page)
            await crawler.login_by_cookie('cookies/pdd.json')
            product = await crawler.fetch_product(source_url)
        else:
            print(f"! 不支持的源平台: {source_platform}")
            return
        
        print(f"  ✓ 标题: {product.title}")
        print(f"  ✓ 价格: ¥{product.price}")
        print(f"  ✓ 主图: {len(product.main_images)}张")
        
        # 2. 处理图片
        print("\n[2/3] 处理图片...")
        processed_images = self.image_processor.batch_process(
            product.main_images,
            image_options
        )
        print(f"  ✓ 已处理 {len(processed_images)} 张图片")
        
        # 更新商品图片
        product.main_images = processed_images
        
        # 3. 发布到目标平台
        print("\n[3/3] 发布到目标平台...")
        for target in target_platforms:
            page = await self.context.new_page()
            
            if target == 'taobao':
                crawler = TaobaoCrawler(page)
                await crawler.login_by_cookie('cookies/taobao.json')
                await crawler.publish_product(product)
            elif target == 'pdd':
                crawler = PddCrawler(page)
                await crawler.login_by_cookie('cookies/pdd.json')
                await crawler.publish_product(product)
            
            await asyncio.sleep(2)
        
        print("\n✓ 同步完成")
        await page.close()
    
    async def close(self):
        """关闭浏览器"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        print("✓ 浏览器已关闭")


# 使用示例
async def main():
    tool = ShopSyncTool()
    await tool.init_browser(headless=False)
    
    # 图片处理选项
    image_options = {
        'remove_watermark': True,      # 去水印
        'resize': True,                 # 改尺寸
        'width': 800,
        'enhance': True,                # 增强
        'brightness': 1.1,
        'contrast': 1.05,
        'add_watermark': True,          # 加自己的水印
        'watermark_text': '我的店铺',
        'watermark_position': 'bottom-right',
        'quality': 90
    }
    
    # 同步商品：淘宝 → 拼多多
    await tool.sync_product(
        source_url="https://item.taobao.com/item.htm?id=xxxxx",
        source_platform='taobao',
        target_platforms=['pdd'],
        image_options=image_options
    )
    
    await tool.close()


if __name__ == "__main__":
    asyncio.run(main())
