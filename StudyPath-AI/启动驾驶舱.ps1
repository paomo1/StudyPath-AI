# 启动/重启 StudyPath AI 学术驾驶舱
#  - 先 kill 占着 7860 端口的旧进程（如果有的话）
#  - 再启动新的 app_gradio.py
# 用法: PowerShell 里 .\启动驾驶舱.ps1
$ErrorActionPreference = "Stop"

Write-Host "🧹 检查并清理 7860 端口占用..." -ForegroundColor Gray
$conn = Get-NetTCPConnection -LocalPort 7860 -ErrorAction SilentlyContinue
if ($conn) {
    Stop-Process -Id $conn.OwningProcess -Force
    Write-Host "   已 kill PID $($conn.OwningProcess)" -ForegroundColor DarkYellow
    Start-Sleep -Milliseconds 500
}

Set-Location "F:\留学项目\StudyPath-AI\rag"
Write-Host "📂 当前目录: $(Get-Location)" -ForegroundColor Gray

$py = "C:\Users\13656\anaconda3\envs\ai-base\python.exe"
Write-Host "🚀 启动 Gradio 驾驶舱 (python=$py)..." -ForegroundColor Green
& $py app_gradio.py
