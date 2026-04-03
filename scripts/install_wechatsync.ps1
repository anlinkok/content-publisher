# Wechatsync 一键安装脚本
# 保存为 install_wechatsync.ps1，右键"使用 PowerShell 运行"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Wechatsync 一键安装脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查 Node.js
Write-Host "[1/5] 检查 Node.js..." -ForegroundColor Yellow
$nodeVersion = node --version 2>$null
if ($?) {
    Write-Host "    ✓ Node.js 已安装: $nodeVersion" -ForegroundColor Green
} else {
    Write-Host "    ✗ Node.js 未安装" -ForegroundColor Red
    Write-Host "    正在下载安装 Node.js LTS..." -ForegroundColor Yellow
    
    # 下载 Node.js 安装包
    $nodeUrl = "https://nodejs.org/dist/v20.11.1/node-v20.11.1-x64.msi"
    $nodeInstaller = "$env:TEMP\node-installer.msi"
    
    try {
        Invoke-WebRequest -Uri $nodeUrl -OutFile $nodeInstaller -UseBasicParsing
        Write-Host "    下载完成，开始安装..." -ForegroundColor Yellow
        Start-Process msiexec.exe -ArgumentList "/i", $nodeInstaller, "/quiet", "/norestart" -Wait
        Write-Host "    ✓ Node.js 安装完成" -ForegroundColor Green
        
        # 刷新环境变量
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    } catch {
        Write-Host "    ✗ 安装失败，请手动下载: https://nodejs.org/" -ForegroundColor Red
        pause
        exit
    }
}

# 安装 Wechatsync CLI
Write-Host ""
Write-Host "[2/5] 安装 Wechatsync CLI..." -ForegroundColor Yellow
try {
    npm install -g @wechatsync/cli 2>&1 | Out-Null
    Write-Host "    ✓ Wechatsync CLI 安装完成" -ForegroundColor Green
} catch {
    Write-Host "    ✗ 安装失败" -ForegroundColor Red
    Write-Host "    错误: $_" -ForegroundColor Red
    pause
    exit
}

# 验证安装
Write-Host ""
Write-Host "[3/5] 验证安装..." -ForegroundColor Yellow
$wechatsyncVersion = wechatsync --version 2>$null
if ($?) {
    Write-Host "    ✓ Wechatsync 版本: $wechatsyncVersion" -ForegroundColor Green
} else {
    Write-Host "    ✗ 验证失败" -ForegroundColor Red
    pause
    exit
}

# 设置环境变量
Write-Host ""
Write-Host "[4/5] 设置 MCP Token..." -ForegroundColor Yellow
$token = Read-Host "请输入你的 MCP Token（在 Chrome 扩展中设置）"
if ($token) {
    [Environment]::SetEnvironmentVariable("WECHATSYNC_TOKEN", $token, "User")
    $env:WECHATSYNC_TOKEN = $token
    Write-Host "    ✓ Token 已设置" -ForegroundColor Green
} else {
    Write-Host "    ⚠ 未设置 Token，稍后请手动设置" -ForegroundColor Yellow
}

# 检查平台登录状态
Write-Host ""
Write-Host "[5/5] 检查平台登录状态..." -ForegroundColor Yellow
try {
    $platforms = wechatsync platforms --auth 2>&1
    Write-Host "    平台状态:" -ForegroundColor Cyan
    $platforms | ForEach-Object { Write-Host "      $_" }
} catch {
    Write-Host "    ⚠ 无法获取平台状态，请确保:" -ForegroundColor Yellow
    Write-Host "      1. 已安装 Chrome 扩展" -ForegroundColor Yellow
    Write-Host "      2. 已在 Chrome 扩展中启用 MCP" -ForegroundColor Yellow
    Write-Host "      3. 已在 Chrome 中登录各平台" -ForegroundColor Yellow
}

# 使用说明
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "安装完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "使用命令:" -ForegroundColor Cyan
Write-Host "  wechatsync platforms           # 查看支持的平台" -ForegroundColor White
Write-Host "  wechatsync platforms --auth    # 查看登录状态" -ForegroundColor White
Write-Host "  wechatsync sync 文章.md -p zhihu,toutiao,baijiahao" -ForegroundColor White
Write-Host ""
Write-Host "支持的平台 ID:" -ForegroundColor Cyan
Write-Host "  zhihu, toutiao, baijiahao, juejin, csdn, jianshu, weibo, bilibili..." -ForegroundColor White
Write-Host ""

pause
