# JARVIS - Fix Ollama GPU Detection
# Run this in a FRESH Admin PowerShell window
# (Right-click PowerShell -> Run as Administrator)

Write-Host "=== JARVIS Ollama GPU Fix ===" -ForegroundColor Cyan

# Step 1: Kill ALL Ollama processes
Write-Host "`n[1/5] Killing all Ollama processes..." -ForegroundColor Yellow
Get-Process -Name "ollama*" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 3

# Step 2: Remove ALL Ollama/CUDA env vars from BOTH user and machine level
Write-Host "[2/5] Cleaning ALL Ollama environment variables..." -ForegroundColor Yellow
$varsToRemove = @("OLLAMA_NUM_GPU", "OLLAMA_LLM_LIBRARY", "OLLAMA_MAX_LOADED_MODELS", 
                   "OLLAMA_USE_CUDA", "OLLAMA_HOST", "CUDA_VISIBLE_DEVICES",
                   "OLLAMA_NOPRUNE", "OLLAMA_GPU_OVERHEAD", "OLLAMA_NO_CUDA")

foreach ($var in $varsToRemove) {
    # Remove from User level
    [System.Environment]::SetEnvironmentVariable($var, $null, "User")
    # Remove from Machine level (needs admin)
    try {
        [System.Environment]::SetEnvironmentVariable($var, $null, "Machine")
    } catch {
        Write-Host "  (Need admin to clear machine-level $var)" -ForegroundColor DarkGray
    }
    # Remove from current session
    Remove-Item "Env:\$var" -ErrorAction SilentlyContinue
}
Write-Host "  Cleaned all env vars" -ForegroundColor Green

# Step 3: Verify GPU is visible
Write-Host "[3/5] Checking GPU..." -ForegroundColor Yellow
$gpuInfo = nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader 2>&1
Write-Host "  GPU: $gpuInfo" -ForegroundColor Green

# Step 4: Start Ollama fresh
Write-Host "[4/5] Starting Ollama fresh..." -ForegroundColor Yellow
Start-Process "ollama" -ArgumentList "serve"
Start-Sleep -Seconds 5

# Step 5: Load model and check VRAM
Write-Host "[5/5] Loading model and checking GPU usage..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "http://localhost:11434/api/generate" -Method Post `
        -Body '{"model":"qwen3-fast","prompt":"say hi","stream":false}' `
        -ContentType "application/json" -TimeoutSec 120
    
    $evalMs = [math]::Round($response.eval_duration / 1000000)
    Write-Host "  Model responded in ${evalMs}ms" -ForegroundColor Green
    
    # Check VRAM usage
    $ps = Invoke-RestMethod -Uri "http://localhost:11434/api/ps" -Method Get
    $vram = $ps.models[0].size_vram
    $gpuMem = nvidia-smi --query-gpu=memory.used --format=csv,noheader 2>&1
    
    if ($vram -gt 0) {
        $vramGB = [math]::Round($vram / 1GB, 2)
        Write-Host "`n=== SUCCESS! Ollama is using GPU ===" -ForegroundColor Green
        Write-Host "  VRAM used by model: ${vramGB} GB" -ForegroundColor Green
        Write-Host "  GPU memory used: $gpuMem" -ForegroundColor Green
    } else {
        Write-Host "`n=== WARNING: Still running on CPU ===" -ForegroundColor Red
        Write-Host "  GPU memory used: $gpuMem" -ForegroundColor Yellow
        Write-Host "  Try: Restart your PC and run 'ollama serve' again" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  Error: $_" -ForegroundColor Red
}

Write-Host "`nDone! Press any key to close..." -ForegroundColor Cyan
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
