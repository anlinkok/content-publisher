#!/usr/bin/env python3
"""
测试套件 - ContentPublisher Pro
"""

import unittest
import asyncio
import json
from datetime import datetime
from pathlib import Path

# 测试配置
TEST_DB = "data/test.db"
TEST_ARTICLE = """
---
title: "测试文章"
platforms: ["zhihu", "toutiao"]
schedule: "2025-12-31 23:59"
tags: ["测试", "自动化"]
---

# 测试标题

这是一篇测试文章的内容。

## 二级标题

- 列表项1
- 列表项2

**粗体文本**

```python
print("Hello, World!")
```
"""


class TestContentOptimizer(unittest.TestCase):
    """测试内容优化器"""
    
    def test_analyze(self):
        from advanced import ContentOptimizer
        
        analysis = ContentOptimizer.analyze(
            "测试文章标题",
            "这是一篇关于人工智能和机器学习的文章。Python是最佳编程语言。"
        )
        
        self.assertIsNotNone(analysis.word_count)
        self.assertIsNotNone(analysis.reading_time)
        self.assertIsInstance(analysis.suggestions, list)
        self.assertGreater(analysis.seo_score, 0)
    
    def test_extract_keywords(self):
        from advanced import ContentOptimizer
        
        keywords = ContentOptimizer._extract_keywords(
            "人工智能和机器学习是热门技术。Python编程很重要。",
            top_n=3
        )
        
        self.assertIsInstance(keywords, dict)
        self.assertLessEqual(len(keywords), 3)


class TestPublishingStrategy(unittest.TestCase):
    """测试发布策略"""
    
    def test_recommend_time(self):
        from advanced import PublishingStrategy
        from datetime import datetime
        
        now = datetime.now()
        recommended = PublishingStrategy.recommend_time('zhihu', now)
        
        self.assertIsInstance(recommended, datetime)
        self.assertGreater(recommended, now)
    
    def test_generate_schedule(self):
        from advanced import PublishingStrategy
        
        platforms = ['zhihu', 'toutiao', 'xiaohongshu']
        schedule = PublishingStrategy.generate_schedule(platforms)
        
        self.assertEqual(len(schedule), 3)
        for platform, time in schedule.items():
            self.assertIn(platform, platforms)
            self.assertIsInstance(time, datetime)


class TestAutoTagger(unittest.TestCase):
    """测试自动标签生成器"""
    
    def test_generate_tags(self):
        from advanced import AutoTagger
        
        tags = AutoTagger.generate_tags(
            "Python教程",
            "本文介绍Python编程的基础知识和进阶技巧。",
            max_tags=5
        )
        
        self.assertIsInstance(tags, list)
        self.assertLessEqual(len(tags), 5)


class TestModels(unittest.TestCase):
    """测试数据模型"""
    
    def test_article_creation(self):
        from models import Article, ArticleStatus
        
        article = Article(
            title="测试文章",
            content="测试内容",
            platforms='["zhihu"]',
            status=ArticleStatus.DRAFT
        )
        
        self.assertEqual(article.title, "测试文章")
        self.assertEqual(article.status, ArticleStatus.DRAFT)


class TestArticleManager(unittest.TestCase):
    """测试文章管理器"""
    
    def test_parse_markdown(self):
        from publisher import ArticleManager
        from models import ArticleStatus
        
        # 写入测试文件
        test_file = "/tmp/test_article.md"
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(TEST_ARTICLE)
        
        article = ArticleManager.parse_markdown(test_file)
        
        self.assertIsNotNone(article)
        self.assertEqual(article.title, "测试文章")
        self.assertIn("zhihu", json.loads(article.platforms))


class TestPlatformTools(unittest.TestCase):
    """测试平台工具"""
    
    def test_tool_registration(self):
        from publisher import PLATFORM_TOOLS
        
        expected_platforms = ['zhihu', 'toutiao', 'xiaohongshu', 'baijiahao', 'wangyi', 'qiehao']
        for platform in expected_platforms:
            self.assertIn(platform, PLATFORM_TOOLS)


class IntegrationTests(unittest.TestCase):
    """集成测试"""
    
    async def async_test_publish_flow(self):
        """测试完整发布流程"""
        # 这里需要模拟浏览器环境，暂时跳过
        pass


def run_tests():
    """运行所有测试"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加测试类
    suite.addTests(loader.loadTestsFromTestCase(TestContentOptimizer))
    suite.addTests(loader.loadTestsFromTestCase(TestPublishingStrategy))
    suite.addTests(loader.loadTestsFromTestCase(TestAutoTagger))
    suite.addTests(loader.loadTestsFromTestCase(TestModels))
    suite.addTests(loader.loadTestsFromTestCase(TestArticleManager))
    suite.addTests(loader.loadTestsFromTestCase(TestPlatformTools))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    exit(0 if success else 1)
