# 启动/重启 StudyPath 学术驾驶舱（Gradio，http://127.0.0.1:7860）
#
# 做两件事：
#   1. kill 掉占着 7860 端口的旧进程（避免 Gradio 报 address already in use）
#   2. 启动 rag/app_gradio.py
#
# 用法（在本文件所在目录）：
#   PowerShell 里 .\启动驾驶舱.ps1
# 指定别的 Python 解释器：
#   $env:STUDYPATH_PY = "D:\miniconda3\envs\xxx\python.exe"; .\启动驾驶舱.ps1
#
# 路径全部基于本脚本位置推导，换机器 / 换目录都不用改代码。

$ErrorActionPreference = "Stop"

$Port = 7860

# ---- 1. 定位项目目录（脚本在 StudyPath-AI/scripts/，往上退一级就是项目根）----
$projectRoot = Split-Path -Parent $PSScriptRoot
$ragDir      = Join-Path $projectRoot "rag"
$entry       = Join-Path $ragDir "app_gradio.py"

if (-not (Test-Path $entry)) {
    Write-Host "❌ 找不到入口文件: $entry" -ForegroundColor Red
    Write-Host "   请把本脚本放在 StudyPath-AI/scripts/ 下运行。" -ForegroundColor Red
    exit 1
}

# ---- 2. 找 Python：能不能跑起来，看它有没有装 gradio ----
# 只看「PATH 里的 python」不够用：Anaconda 的 base 环境也提供 python 命令，
# 但 base 里通常没装项目依赖，直接跑就是 ModuleNotFoundError: No module named 'gradio'。
# 所以这里不看名字看能力 —— 逐个候选试 import gradio，第一个能成功的才用。
function Test-PythonHasGradio([string]$pyPath) {
    if (-not $pyPath -or -not (Test-Path $pyPath)) { return $false }
    $oldEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $pyPath -c "import gradio" 2>$null | Out-Null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    } finally {
        $ErrorActionPreference = $oldEap
    }
}

function Resolve-Python {
    $cands = @()
    if ($env:STUDYPATH_PY) { $cands += $env:STUDYPATH_PY }

    $onPath = Get-Command python -ErrorAction SilentlyContinue
    if ($onPath) { $cands += $onPath.Source }

    # 常见 conda 安装位置下的 AI 环境
    $condaRoots = @(
        (Join-Path $env:USERPROFILE "anaconda3"),
        (Join-Path $env:USERPROFILE "miniconda3"),
        "C:\ProgramData\anaconda3",
        "C:\ProgramData\miniconda3"
    )
    foreach ($root in $condaRoots) {
        foreach ($envName in @("ai-base", "ai-langchain")) {
            $cands += (Join-Path $root "envs\$envName\python.exe")
        }
    }

    foreach ($c in $cands) {
        if (Test-PythonHasGradio $c) { return $c }
    }
    return $null
}

$py = Resolve-Python
if (-not $py) {
    Write-Host "❌ 没找到装了 gradio 的 Python。" -ForegroundColor Red
    Write-Host "   多半是当前 python 落在 Anaconda 的 base 环境（没装项目依赖）。二选一：" -ForegroundColor Yellow
    Write-Host '   1) conda activate ai-base 之后再跑本脚本' -ForegroundColor Yellow
    Write-Host '   2) 或写死路径：$env:STUDYPATH_PY = "C:\Users\13656\anaconda3\envs\ai-base\python.exe"' -ForegroundColor Yellow
    exit 1
}

# ---- 3. 清理端口占用 ----
Write-Host "🧹 检查并清理 $Port 端口占用..." -ForegroundColor Gray
$conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($conn) {
    # 注意：$pid 是 PowerShell 的只读自动变量，不能拿来做循环变量，这里用 $procId
    foreach ($procId in ($conn.OwningProcess | Sort-Object -Unique)) {
        try {
            $procName = (Get-Process -Id $procId -ErrorAction Stop).ProcessName
            Stop-Process -Id $procId -Force
            Write-Host "   已 kill PID $procId ($procName)" -ForegroundColor DarkYellow
        } catch {
            Write-Host "   PID $procId 已退出或无权结束，跳过" -ForegroundColor DarkGray
        }
    }
    Start-Sleep -Milliseconds 500
} else {
    Write-Host "   端口空闲" -ForegroundColor DarkGray
}

# ---- 4. 启动 ----
Write-Host "📂 工作目录: $ragDir" -ForegroundColor Gray
Write-Host "🐍 Python  : $py"    -ForegroundColor Gray
Write-Host "🚀 启动 Gradio 驾驶舱 → http://127.0.0.1:$Port" -ForegroundColor Green

Set-Location $ragDir
& $py $entry
