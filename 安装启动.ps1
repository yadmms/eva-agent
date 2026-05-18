# Eva Agent — Windows 一键启动
# 右键 → 使用 PowerShell 运行

$DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $DIR

Write-Host "╔══════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   伊娃 Eva Agent v0.11.3       ║" -ForegroundColor Cyan
Write-Host "║   千叶实验室 Qianye Lab        ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# 检查 Python
Write-Host "[1/3] 检查 Python..." -NoNewline
try { python --version | Out-Null; Write-Host " ✓" -ForegroundColor Green }
catch { Write-Host " ✗ 未安装 Python" -ForegroundColor Red; pause; exit }

# 安装依赖
Write-Host "[2/3] 安装组件..." -NoNewline
pip install -r requirements.txt --quiet 2>$null
Write-Host " ✓" -ForegroundColor Green

# 启动
Write-Host "[3/3] 启动服务..."
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = "python"
$psi.Arguments = "run.py"
$psi.UseShellExecute = $true
$psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Minimized
$p = [System.Diagnostics.Process]::Start($psi)

Start-Sleep 3
Start-Process "http://localhost:19198"

Write-Host "`n  Eva Agent 已启动，浏览器已打开" -ForegroundColor Green
Write-Host "  按任意键停止服务...`n"
pause

# 停止
$p.Kill()
