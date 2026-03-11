@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo 正在准备推送到 GitHub...
echo 仓库地址: https://github.com/Caizhaohui/microbial-colony-counter.git
echo ==========================================
echo.

:: 1. 检查 git 是否存在
where git >nul 2>nul
if %errorlevel% neq 0 (
    echo 错误: 未找到 git 命令，请先安装 Git。
    pause
    exit /b 1
)

:: 2. 初始化或重置远程
echo [1/3] 配置远程仓库...
git remote remove origin 2>nul
git remote add origin https://github.com/Caizhaohui/microbial-colony-counter.git

:: 3. 确保所有更改已提交
echo [2/3] 提交本地更改...
git add -A
git commit -m "feat: update project files via auto-script" 2>nul

:: 4. 推送
echo [3/3] 正在推送 (如果弹出登录框，请登录 GitHub)...
echo.
git push -u origin main --force

if %errorlevel% neq 0 (
    echo.
    echo ==========================================
    echo 推送失败！
    echo 可能原因：
    echo 1. 网络连接 GitHub 失败
    echo 2. 没有权限 (请检查是否登录了正确的 GitHub 账号)
    echo ==========================================
) else (
    echo.
    echo ==========================================
    echo 推送成功！
    echo 请访问: https://github.com/Caizhaohui/microbial-colony-counter
    echo ==========================================
)

pause
