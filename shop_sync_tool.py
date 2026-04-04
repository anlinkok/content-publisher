"""
店群铺货工具 - 自家店铺商品同步 + 图片处理 + 多平台上架
"""
import os
import json
import time
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from typing import List, Dict, Optional
import hashlib


class ProductSyncTool:
    """店铺商品同步工具"""
    
    def __init__(self, config_path: str = "sync_config.json"):
        self.config = self._load_config(config_path)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
    def _load_config(self, path: str) -> dict:
        """加载配置文件"""
        default_config = {
            "source_shop": {
                "platform": "taobao",  # taobao/pdd/douyin
                "shop_name": "",
                "cookie": ""
            },
            "target_shops": [
                {"platform": "pdd", "shop_name": "", "cookie": ""},
                {"platform": "douyin", "shop_name": "", "cookie": ""}
            ],
            "image_processing": {
                "add_watermark": True,
                "watermark_text": "",
                "watermark_position": "bottom-right",  # bottom-right/bottom-left/center
                "resize": True,
                "target_width": 800,
                "compress": True,
                "quality": 85
            },
            "output_dir": "sync_output"
        }
        
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return {**default_config, **json.load(f)}
        return default_config
    
    def fetch_from_source(self, product_url: str = None) -> List[Dict]:
        """
        从源店铺采集商品
        支持：淘宝、拼多多、抖音
        """
        products = []
        platform = self.config["source_shop"]["platform"]
        
        if platform == "taobao":
            products = self._fetch_taobao(product_url)
        elif platform == "pdd":
            products = self._fetch_pdd(product_url)
        elif platform == "douyin":
            products = self._fetch_douyin(product_url)
        
        print(f"✓ 采集到 {len(products)} 个商品")
        return products
    
    def _fetch_taobao(self, url: str) -> List[Dict]:
        """采集淘宝店铺商品"""
        # 方案1：用淘宝开放平台API（需要申请）
        # 方案2：用爬虫（需要处理反爬）
        # 这里用方案1的模拟结构
        
        products = []
        # TODO: 实现淘宝商品采集
        # 可以用 taobao.item.get API
        
        print("淘宝采集需要：")
        print("1. 申请淘宝开放平台 API 权限")
        print("2. 使用 item.get 接口获取商品详情")
        print("3. 或使用 selenium/playwright 爬虫采集")
        
        return products
    
    def _fetch_pdd(self, url: str) -> List[Dict]:
        """采集拼多多店铺商品"""
        print("拼多多采集需要：")
        print("1. 申请拼多多开放平台 API")
        print("2. 使用 pdd.goods.info.get 接口")
        return []
    
    def _fetch_douyin(self, url: str) -> List[Dict]:
        """采集抖音店铺商品"""
        print("抖音采集需要：")
        print("1. 申请抖店开放平台 API")
        print("2. 使用 product.detail 接口")
        return []
    
    def process_images(self, product: Dict) -> Dict:
        """
        处理商品图片
        - 加水印
        - 改尺寸
        - 压缩
        """
        processed_images = []
        config = self.config["image_processing"]
        
        for img_url in product.get("images", []):
            try:
                # 下载图片
                response = self.session.get(img_url, timeout=30)
                img = Image.open(BytesIO(response.content))
                
                # 转换为RGB（处理RGBA）
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                
                # 1. 调整尺寸
                if config.get("resize"):
                    target_width = config.get("target_width", 800)
                    ratio = target_width / img.width
                    target_height = int(img.height * ratio)
                    img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
                
                # 2. 加水印
                if config.get("add_watermark"):
                    img = self._add_watermark(img, config.get("watermark_text", ""))
                
                # 3. 保存
                output_path = os.path.join(
                    self.config["output_dir"], 
                    "images",
                    f"{product['id']}_{len(processed_images)}.jpg"
                )
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                quality = config.get("quality", 85)
                img.save(output_path, "JPEG", quality=quality, optimize=True)
                processed_images.append(output_path)
                
            except Exception as e:
                print(f"  ! 处理图片失败: {e}")
                continue
        
        product["processed_images"] = processed_images
        return product
    
    def _add_watermark(self, img: Image.Image, text: str) -> Image.Image:
        """给图片加水印"""
        if not text:
            return img
        
        # 创建水印层
        watermark = Image.new('RGBA', img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(watermark)
        
        # 字体大小（根据图片尺寸调整）
        font_size = int(img.width * 0.05)
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            font = ImageFont.load_default()
        
        # 计算文字位置
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        position = self.config["image_processing"].get("watermark_position", "bottom-right")
        
        if position == "bottom-right":
            x = img.width - text_width - 20
            y = img.height - text_height - 20
        elif position == "bottom-left":
            x = 20
            y = img.height - text_height - 20
        else:  # center
            x = (img.width - text_width) // 2
            y = (img.height - text_height) // 2
        
        # 半透明黑色背景
        padding = 10
        draw.rectangle(
            [x - padding, y - padding, x + text_width + padding, y + text_height + padding],
            fill=(0, 0, 0, 128)
        )
        
        # 白色文字
        draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))
        
        # 合并图层
        result = Image.alpha_composite(img.convert('RGBA'), watermark)
        return result.convert('RGB')
    
    def publish_to_target(self, product: Dict, target_shop: Dict) -> bool:
        """
        发布商品到目标店铺
        """
        platform = target_shop["platform"]
        
        if platform == "taobao":
            return self._publish_taobao(product, target_shop)
        elif platform == "pdd":
            return self._publish_pdd(product, target_shop)
        elif platform == "douyin":
            return self._publish_douyin(product, target_shop)
        
        return False
    
    def _publish_taobao(self, product: Dict, shop: Dict) -> bool:
        """发布到淘宝"""
        # 需要淘宝API权限
        # item.add 接口
        print(f"  发布到淘宝: {product['title']}")
        print("  需要：淘宝开放平台 item.add API")
        return False
    
    def _publish_pdd(self, product: Dict, shop: Dict) -> bool:
        """发布到拼多多"""
        # pdd.goods.add 接口
        print(f"  发布到拼多多: {product['title']}")
        print("  需要：拼多多开放平台 goods.add API")
        return False
    
    def _publish_douyin(self, product: Dict, shop: Dict) -> bool:
        """发布到抖音"""
        # product.add 接口
        print(f"  发布到抖音: {product['title']}")
        print("  需要：抖店开放平台 product.add API")
        return False
    
    def run(self, product_urls: List[str] = None):
        """
        完整流程：采集 → 处理 → 发布
        """
        print("=" * 50)
        print("店群铺货工具")
        print("=" * 50)
        
        # 1. 采集商品
        print("\n[1/3] 采集源店铺商品...")
        products = []
        for url in product_urls or []:
            products.extend(self.fetch_from_source(url))
        
        if not products:
            print("! 未采集到商品，请检查配置")
            return
        
        # 2. 处理图片
        print("\n[2/3] 处理商品图片...")
        for i, product in enumerate(products):
            print(f"  处理 [{i+1}/{len(products)}] {product.get('title', 'Unknown')}")
            self.process_images(product)
        
        # 3. 发布到目标店铺
        print("\n[3/3] 发布到目标店铺...")
        for target in self.config["target_shops"]:
            print(f"\n  目标: {target['platform']} - {target['shop_name']}")
            for product in products:
                self.publish_to_target(product, target)
                time.sleep(2)  # 避免频繁请求
        
        print("\n✓ 同步完成")
        
    def generate_csv_template(self):
        """
        生成CSV模板（用于批量导入）
        各平台都支持CSV批量上传
        """
        import csv
        
        template = [
            ["商品标题", "价格", "库存", "主图路径", "详情图路径", "类目", "运费模板"],
            ["示例商品", "99.00", "100", "images/1.jpg", "images/detail.jpg", "女装", "包邮"]
        ]
        
        csv_path = os.path.join(self.config["output_dir"], "upload_template.csv")
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerows(template)
        
        print(f"✓ CSV模板已生成: {csv_path}")
        return csv_path


if __name__ == "__main__":
    # 使用示例
    tool = ProductSyncTool()
    
    # 生成配置模板
    if not os.path.exists("sync_config.json"):
        with open("sync_config.json", 'w', encoding='utf-8') as f:
            json.dump(tool.config, f, ensure_ascii=False, indent=2)
        print("✓ 配置文件模板已生成: sync_config.json")
        print("  请编辑配置文件后重新运行")
    else:
        # 运行同步
        tool.run()
