# ContentPublisher Pro - Windows 安装指南

## 1. 前置要求
- Python 3.10+ (从 https://python.org 下载安装，记得勾选 "Add to PATH")
- Node.js (从 https://nodejs.org 下载安装)

## 2. 创建项目文件夹
在 PowerShell 中执行：

```powershell
mkdir C:\tools\content-publisher
cd C:\tools\content-publisher
mkdir platforms
mkdir articles
mkdir data
mkdir logs
```

## 3. 创建虚拟环境并安装依赖

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install playwright requests httpx beautifulsoup4 lxml pydantic sqlmodel python-frontmatter markdown PyYAML python-docx Pillow schedule APScheduler click rich
playwright install chromium
```

## 4. 创建以下文件

### requirements.txt
```
playwright>=1.40.0
requests>=2.31.0
httpx>=0.25.0
beautifulsoup4>=4.12.0
lxml>=5.0.0
pydantic>=2.5.0
sqlmodel>=0.0.14
python-frontmatter>=1.0.0
markdown>=3.5.0
PyYAML>=6.0.1
python-docx>=1.1.0
Pillow>=10.0.0
schedule>=1.2.0
APScheduler>=3.10.0
click>=8.1.0
rich>=13.7.0
```

然后把我发的代码文件保存到对应位置。

## 5. 初始化数据库
```powershell
python -c "from models import init_db; init_db()"
```

## 6. 运行
```powershell
# 登录知乎
python publisher.py login --platform zhihu

# 发布文章
python publisher.py publish articles\example.md
```
