#!/usr/bin/env python3
"""
ContentPublisher 高级功能模块
- 内容优化
- 智能标签生成
- 发布策略
- 数据分析
"""

import json
import re
import asyncio
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import defaultdict

import httpx
from rich.console import Console
from rich.table import Table

console = Console()


@dataclass
class ContentAnalysis:
    """内容分析结果"""
    word_count: int
    reading_time: int  # 分钟
    keyword_density: Dict[str, float]
    sentiment: str
    suggestions: List[str]
    seo_score: int


class ContentOptimizer:
    """内容优化器"""
    
    # 各平台标题长度限制
    TITLE_LIMITS = {
        'zhihu': 100,
        'toutiao': 30,
        'xiaohongshu': 20,
        'baijiahao': 30,
        'wangyi': 30,
        'qiehao': 30,
    }
    
    # 各平台内容长度限制
    CONTENT_LIMITS = {
        'zhihu': 50000,
        'toutiao': 100000,
        'xiaohongshu': 1000,
        'baijiahao': 100000,
        'wangyi': 50000,
        'qiehao': 50000,
    }
    
    @classmethod
    def analyze(cls, title: str, content: str) -> ContentAnalysis:
        """分析内容质量"""
        word_count = len(content)
        reading_time = max(1, word_count // 300)  # 假设300字/分钟
        
        # 关键词密度分析
        keywords = cls._extract_keywords(content)
        keyword_density = {k: v/word_count*100 for k, v in keywords.items()}
        
        # 简单情感判断
        positive_words = ['好', '优秀', '成功', '创新', '突破', '提升']
        negative_words = ['失败', '问题', '困难', '风险', '挑战']
        
        pos_count = sum(1 for w in positive_words if w in content)
        neg_count = sum(1 for w in negative_words if w in content)
        
        if pos_count > neg_count * 2:
            sentiment = "积极"
        elif neg_count > pos_count:
            sentiment = "中性偏谨慎"
        else:
            sentiment = "中性"
        
        # 生成建议
        suggestions = []
        if word_count < 500:
            suggestions.append("内容较短，建议增加深度")
        if len(title) < 10:
            suggestions.append("标题较短，建议增加吸引力")
        if not re.search(r'\d+', title):
            suggestions.append("标题可考虑加入数字，提高点击率")
        
        # SEO评分
        seo_score = 70
        if 15 <= len(title) <= 25:
            seo_score += 10
        if word_count > 1000:
            seo_score += 10
        if keywords:
            seo_score += 10
        
        return ContentAnalysis(
            word_count=word_count,
            reading_time=reading_time,
            keyword_density=keyword_density,
            sentiment=sentiment,
            suggestions=suggestions,
            seo_score=min(100, seo_score)
        )
    
    @classmethod
    def _extract_keywords(cls, content: str, top_n: int = 5) -> Dict[str, int]:
        """提取关键词"""
        # 简单的词频统计（中文）
        words = re.findall(r'[\u4e00-\u9fa5]{2,4}', content)
        freq = defaultdict(int)
        for w in words:
            if len(w) >= 2 and not cls._is_stop_word(w):
                freq[w] += 1
        return dict(sorted(freq.items(), key=lambda x: x[1], reverse=True)[:top_n])
    
    @staticmethod
    def _is_stop_word(word: str) -> bool:
        """判断是否为停用词"""
        stops = ['我们', '你们', '他们', '这个', '那个', '什么', '可以', '进行', '需要', '通过', '使用', '就是', '不是', '没有', '这样', '这些', '那些']
        return word in stops
    
    @classmethod
    def optimize_for_platform(cls, title: str, content: str, platform: str) -> Tuple[str, str]:
        """针对平台优化内容"""
        title_limit = cls.TITLE_LIMITS.get(platform, 30)
        content_limit = cls.CONTENT_LIMITS.get(platform, 50000)
        
        # 优化标题
        opt_title = title[:title_limit]
        if len(title) > title_limit:
            opt_title = opt_title[:-3] + '...'
        
        # 优化内容
        opt_content = content[:content_limit]
        if len(content) > content_limit:
            opt_content = opt_content[:content_limit-3] + '...'
        
        return opt_title, opt_content


class PublishingStrategy:
    """发布策略"""
    
    # 各平台最佳发布时间（24小时制，时区+8）
    BEST_TIMES = {
        'zhihu': [8, 12, 18, 21],      # 通勤、午休、下班、睡前
        'toutiao': [7, 12, 18, 22],    # 早新闻、午休、晚高峰、睡前
        'xiaohongshu': [8, 12, 20, 22], # 早妆、午休、晚休闲、睡前
        'baijiahao': [9, 12, 18, 21],   # 工作间隙
        'wangyi': [8, 12, 18, 21],
        'qiehao': [7, 12, 18, 21],
    }
    
    @classmethod
    def recommend_time(cls, platform: str, base_time: datetime = None) -> datetime:
        """推荐发布时间"""
        if base_time is None:
            base_time = datetime.now()
        
        best_hours = cls.BEST_TIMES.get(platform, [9, 12, 18, 21])
        
        # 找到下一个最佳时间
        for hour in sorted(best_hours):
            recommended = base_time.replace(hour=hour, minute=0, second=0)
            if recommended > base_time:
                return recommended
        
        # 如果今天没有合适的时间，推到明天第一个时段
        tomorrow = base_time + timedelta(days=1)
        return tomorrow.replace(hour=best_hours[0], minute=0, second=0)
    
    @classmethod
    def generate_schedule(cls, platforms: List[str], start_time: datetime = None) -> Dict[str, datetime]:
        """为多个平台生成错峰发布计划"""
        if start_time is None:
            start_time = datetime.now()
        
        schedule = {}
        current_time = start_time
        
        for i, platform in enumerate(platforms):
            # 每个平台间隔15-30分钟，避免同时发布
            offset_minutes = i * 20
            platform_time = current_time + timedelta(minutes=offset_minutes)
            schedule[platform] = cls.recommend_time(platform, platform_time)
        
        return schedule


class PerformanceTracker:
    """性能追踪器"""
    
    def __init__(self):
        self.metrics = defaultdict(lambda: defaultdict(int))
    
    def record_publish(self, platform: str, success: bool, duration: float):
        """记录发布指标"""
        self.metrics[platform]['total'] += 1
        if success:
            self.metrics[platform]['success'] += 1
        else:
            self.metrics[platform]['failed'] += 1
        
        # 平均耗时
        avg_key = 'avg_duration'
        current_avg = self.metrics[platform].get(avg_key, 0)
        count = self.metrics[platform]['total']
        self.metrics[platform][avg_key] = (current_avg * (count - 1) + duration) / count
    
    def get_report(self) -> Table:
        """生成性能报告"""
        table = Table(title="发布性能报告")
        table.add_column("平台", style="cyan")
        table.add_column("总发布", style="blue")
        table.add_column("成功", style="green")
        table.add_column("失败", style="red")
        table.add_column("成功率", style="yellow")
        table.add_column("平均耗时", style="dim")
        
        for platform, data in self.metrics.items():
            total = data['total']
            success = data['success']
            failed = data['failed']
            avg_duration = data.get('avg_duration', 0)
            
            success_rate = f"{(success/total*100):.1f}%" if total > 0 else "N/A"
            avg_time = f"{avg_duration:.1f}s"
            
            table.add_row(
                platform,
                str(total),
                str(success),
                str(failed),
                success_rate,
                avg_time
            )
        
        return table


class AutoTagger:
    """自动标签生成器"""
    
    # 领域关键词映射
    DOMAIN_KEYWORDS = {
        '科技': ['AI', '人工智能', '算法', '编程', 'Python', '代码', '软件', '硬件', '芯片'],
        '互联网': ['互联网', '产品', '运营', '用户', '数据', '流量', '增长', '商业模式'],
        '财经': ['股票', '基金', '投资', '理财', '经济', '金融', '市场', '企业'],
        '生活': ['生活', '美食', '旅行', '健康', '家居', '穿搭', '美妆'],
        '职场': ['职场', '管理', '领导', '团队', '沟通', '效率', '简历', '面试'],
        '教育': ['学习', '教育', '考试', '知识', '课程', '读书', '成长'],
    }
    
    @classmethod
    def generate_tags(cls, title: str, content: str, max_tags: int = 5) -> List[str]:
        """生成标签"""
        full_text = title + ' ' + content
        tags = []
        
        # 基于领域匹配
        for domain, keywords in cls.DOMAIN_KEYWORDS.items():
            for kw in keywords:
                if kw in full_text and domain not in tags:
                    tags.append(domain)
                    break
        
        # 基于关键词提取
        optimizer = ContentOptimizer()
        keywords = optimizer._extract_keywords(full_text, top_n=max_tags)
        tags.extend(list(keywords.keys())[:max_tags - len(tags)])
        
        return tags[:max_tags]


class ContentEnricher:
    """内容增强器"""
    
    @staticmethod
    def generate_summary(content: str, max_length: int = 100) -> str:
        """生成摘要"""
        # 简单的摘要提取：取前几句
        sentences = re.split(r'[。！？]', content)
        summary = ''
        for sent in sentences:
            if len(summary) + len(sent) < max_length:
                summary += sent + '。'
            else:
                break
        return summary[:max_length] + '...' if len(content) > max_length else content
    
    @staticmethod
    def extract_images(content: str) -> List[str]:
        """提取内容中的图片链接"""
        pattern = r'!\[.*?\]\((.+?)\)'
        return re.findall(pattern, content)
    
    @classmethod
    def format_for_platform(cls, content: str, platform: str) -> str:
        """格式化内容为平台特定格式"""
        formatters = {
            'xiaohongshu': cls._format_xiaohongshu,
            'zhihu': cls._format_zhihu,
            'toutiao': cls._format_toutiao,
        }
        
        formatter = formatters.get(platform, lambda x: x)
        return formatter(content)
    
    @staticmethod
    def _format_xiaohongshu(content: str) -> str:
        """小红书格式：添加emoji，分段"""
        lines = content.split('\n')
        formatted = []
        for line in lines:
            if line.strip():
                formatted.append(line)
                formatted.append('')  # 空行
        return '\n'.join(formatted)
    
    @staticmethod
    def _format_zhihu(content: str) -> str:
        """知乎格式：标准Markdown"""
        return content
    
    @staticmethod
    def _format_toutiao(content: str) -> str:
        """头条号格式：简洁段落"""
        return content.replace('\n\n', '\n')


# ============================================================================
# CLI 命令扩展
# ============================================================================

import click

@click.group()
def advanced():
    """高级功能命令"""
    pass


@advanced.command()
@click.argument('file_path')
def analyze(file_path: str):
    """分析文章质量"""
    import frontmatter
    
    with open(file_path, 'r', encoding='utf-8') as f:
        post = frontmatter.load(f)
    
    title = post.get('title', '')
    content = post.content
    
    analysis = ContentOptimizer.analyze(title, content)
    
    console.print(f"\n[bold cyan]文章分析: {title}[/bold cyan]\n")
    console.print(f"字数: {analysis.word_count}")
    console.print(f"阅读时间: {analysis.reading_time} 分钟")
    console.print(f"情感倾向: {analysis.sentiment}")
    console.print(f"SEO评分: {analysis.seo_score}/100")
    
    if analysis.suggestions:
        console.print("\n[bold yellow]优化建议:[/bold yellow]")
        for s in analysis.suggestions:
            console.print(f"  • {s}")
    
    if analysis.keyword_density:
        console.print("\n[bold green]关键词密度:[/bold green]")
        for k, v in analysis.keyword_density.items():
            console.print(f"  {k}: {v:.2f}%")


@advanced.command()
@click.argument('file_path')
def suggest_tags(file_path: str):
    """智能推荐标签"""
    import frontmatter
    
    with open(file_path, 'r', encoding='utf-8') as f:
        post = frontmatter.load(f)
    
    tags = AutoTagger.generate_tags(post.get('title', ''), post.content)
    
    console.print(f"\n[bold green]推荐标签:[/bold green]")
    for tag in tags:
        console.print(f"  • {tag}")


@advanced.command()
@click.argument('platforms')
def schedule_plan(platforms: str):
    """生成发布计划"""
    platform_list = [p.strip() for p in platforms.split(',')]
    
    schedule = PublishingStrategy.generate_schedule(platform_list)
    
    console.print(f"\n[bold cyan]推荐发布计划[/bold cyan]\n")
    
    table = Table()
    table.add_column("平台", style="cyan")
    table.add_column("建议发布时间", style="green")
    
    for platform, time in schedule.items():
        table.add_row(platform, time.strftime('%Y-%m-%d %H:%M'))
    
    console.print(table)


if __name__ == '__main__':
    advanced()
