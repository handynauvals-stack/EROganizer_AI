# Mencatat ruang kosong disk C dan D setiap 3 detik ke .workdir\diskmon.csv sampai file .workdir\stop muncul.
# Dipakai untuk mencari tahu proses mana yang menghabiskan ruang C saat training/evaluasi.
$work = Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) '.workdir'
New-Item -ItemType Directory -Force -Path $work | Out-Null
Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $work 'stop')
$log = Join-Path $work 'diskmon.csv'
'waktu,C_bebas_GB,D_bebas_GB,pagefile_terpakai_MB,pagefile_ukuran_MB,python_ws_MB,python_private_MB' | Set-Content $log
while (-not (Test-Path (Join-Path $work 'stop'))) {
    $c = [math]::Round((Get-PSDrive C).Free / 1GB, 2)
    $d = [math]::Round((Get-PSDrive D).Free / 1GB, 2)
    $pf = Get-CimInstance Win32_PageFileUsage | Select-Object -First 1
    $py = Get-Process python -ErrorAction SilentlyContinue | Measure-Object WorkingSet64, PrivateMemorySize64 -Sum
    $ws = 0; $pm = 0
    if ($py) { $ws = [math]::Round(($py | Where-Object Property -eq 'WorkingSet64').Sum / 1MB); $pm = [math]::Round(($py | Where-Object Property -eq 'PrivateMemorySize64').Sum / 1MB) }
    ('{0},{1},{2},{3},{4},{5},{6}' -f (Get-Date -Format 'HH:mm:ss'), $c, $d, $pf.CurrentUsage, $pf.AllocatedBaseSize, $ws, $pm) | Add-Content $log
    Start-Sleep -Seconds 3
}
