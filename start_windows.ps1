# Eva Agent v0.11.3 — PowerShell 启动脚本
# 右键 → 使用 PowerShell 运行

$LogFile = "eva-startup.log"
"=== Eva Agent v0.11.3 ===" | Out-File $LogFile
"OS: Windows PowerShell" | Out-File $LogFile -Append

Write-Host "====================================" -ForegroundColor Cyan
Write-Host "  Eva Agent v0.11.3 - Qianye Lab" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check Python
Write-Host "[1/3] Checking Python..." -NoNewline
try { python --version | Out-Null; Write-Host " OK" -ForegroundColor Green }
catch { Write-Host " FAIL" -ForegroundColor Red; pause; exit }

# Step 2: Install deps
Write-Host "[2/3] Installing dependencies..."
pip install -r requirements.txt 2>&1 | Out-File $LogFile -Append
if ($LASTEXITCODE -ne 0) {
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple 2>&1 | Out-File $LogFile -Append
}
Write-Host "  OK" -ForegroundColor Green

# Step 3: Start server
Write-Host "[3/3] Starting server..."
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = "python"
$psi.Arguments = "run.py"
$psi.UseShellExecute = $true
$psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
$p = [System.Diagnostics.Process]::Start($psi)

Write-Host "  Waiting..."
Start-Sleep 3
Start-Process "http://localhost:19198"

Write-Host ""
Write-Host "  Eva Agent is running!" -ForegroundColor Green
Write-Host "  Browser opened at localhost:19198" -ForegroundColor Green
Write-Host "  Press any key to stop..."
Write-Host ""

pause
$p.Kill()
