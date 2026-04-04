# 小红书一键发布脚本
# 用法: .\publish_xiaohongshu.ps1 "C:\Users\Administrator\Desktop\文档.docx"

param(
    [Parameter(Mandatory=$true)]
    [string]$DocxPath
)

$ErrorActionPreference = "Stop"

Write-Host "========== 小红书自动发布 ==========" -ForegroundColor Cyan

# 1. 提取 Word 内容
Write-Host "[1/3] 提取 Word 内容..." -ForegroundColor Yellow

$extractScript = @"
from docx import Document
import json
import os

doc = Document(r'$DocxPath')

# 提取标题（第一段，限制20字）
raw_title = doc.paragraphs[0].text if doc.paragraphs else '无标题'
title = raw_title[:20] if len(raw_title) <= 20 else raw_title[:18] + '...'

# 提取正文
content_lines = []
for para in doc.paragraphs[1:]:
    text = para.text.strip()
    if text:
        content_lines.append(text)

content = '\n'.join(content_lines)

# 查找图片
import glob
image_dir = 'articles/images'
images = glob.glob(f'{image_dir}/*.jpg') + glob.glob(f'{image_dir}/*.png')
images = [os.path.abspath(img).replace('\\', '/') for img in images[:9]]  # 最多9张

result = {
    'title': title,
    'content': content[:2000],  # 限制长度
    'images': images
}

print(json.dumps(result, ensure_ascii=False))
"@

$result = & .venv\Scripts\python.exe -c $extractScript | ConvertFrom-Json

$title = $result.title
$content = $result.content
$images = $result.images -join " "

Write-Host "  标题: $title" -ForegroundColor Green
Write-Host "  正文长度: $($content.Length) 字" -ForegroundColor Green
Write-Host "  图片: $($result.images.Count) 张" -ForegroundColor Green

# 2. 检查登录
Write-Host "[2/3] 检查登录状态..." -ForegroundColor Yellow
$sauCheck = sau xiaohongshu check --account default 2>&1
if ($LASTEXITCODE -ne 0 -or $sauCheck -match "未登录|失效") {
    Write-Host "  需要登录，请扫码..." -ForegroundColor Red
    sau xiaohongshu login --account default
}

# 3. 发布
Write-Host "[3/3] 发布到小红书..." -ForegroundColor Yellow

# 构建命令
if ($result.images.Count -gt 0) {
    # 有图片：图文模式
    $imgArgs = $result.images -join " "
    sau xiaohongshu upload-note `
        --account default `
        --title "$title" `
        --note "$content" `
        --images $imgArgs
} else {
    # 无图片：纯文字
    sau xiaohongshu upload-note `
        --account default `
        --title "$title" `
        --note "$content"
}

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ 发布成功！" -ForegroundColor Green
} else {
    Write-Host "✗ 发布失败" -ForegroundColor Red
}

Write-Host "====================================" -ForegroundColor Cyan
