@echo off
chcp 65001
echo ==========================================
echo 晨间新闻自动化任务 - 安装程序
echo ==========================================
echo.

:: 检查管理员权限
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo 请以管理员身份运行此脚本！
    pause
    exit /b 1
)

echo [1/3] 安装依赖...
cd /d "D:\kimijiaoben\content-publisher"
.venv\Scripts\pip.exe install python-docx requests

echo.
echo [2/3] 创建工作目录...
if not exist "D:\kimijiaoben\content-publisher\morning_task" mkdir "D:\kimijiaoben\content-publisher\morning_task"

echo.
echo [3/3] 创建定时任务...
:: 删除旧任务
schtasks /delete /tn "MorningNews_Workflow" /f >nul 2>&1

:: 创建每天6:00执行的任务
schtasks /create ^
    /tn "MorningNews_Workflow" ^
    /tr "D:\kimijiaoben\content-publisher\.venv\Scripts\python.exe D:\kimijiaoben\content-publisher\morning_task\morning_workflow.py" ^
    /sc daily ^
    /st 06:00 ^
    /f

if %errorLevel% equ 0 (
    echo.
    echo ==========================================
    echo 安装成功！
    echo ==========================================
    echo 任务将在每天早上 6:00 自动执行：
    echo   1. 启动精灵学院代理
    echo   2. 搜索新闻并改写文章
    echo   3. 保存到桌面
    echo   4. 关闭代理
    echo   5. 定时 6:00 上传文章
    echo.
    echo 查看任务: schtasks /query /tn "MorningNews_Workflow"
    echo 删除任务: schtasks /delete /tn "MorningNews_Workflow" /f
    echo.
) else (
    echo 创建定时任务失败！
)

pause
