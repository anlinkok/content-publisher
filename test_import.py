import sys
sys.path.insert(0, '.')

try:
    print("1. 导入 models...")
    from models import init_db, Article, Account, PublishRecord, ArticleStatus, engine
    print("   ✓ models OK")
    
    print("2. 导入 platforms.base...")
    from platforms import PlatformTool, ToolResult
    print("   ✓ base OK")
    
    print("3. 导入所有平台...")
    from platforms import ZhihuTool, ToutiaoTool
    print("   ✓ ZhihuTool, ToutiaoTool OK")
    
    print("4. 导入 publisher 模块...")
    import publisher
    print("   ✓ publisher OK")
    
    print("\n=== 所有导入成功 ===")
except Exception as e:
    print(f"\n✗ 导入失败: {e}")
    import traceback
    traceback.print_exc()
