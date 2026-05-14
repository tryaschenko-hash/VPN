param([switch]$Uninstall)

$dir = "$PSScriptRoot\xray-core"
$zip = "$dir\xray.zip"
$exe = "$dir\xray.exe"
$cfg = "$PSScriptRoot\xray-local-config.json"
$log = "$dir\xray.log"

if ($Uninstall) {
    $p = Get-Process -Name xray -ErrorAction SilentlyContinue
    if ($p) { $p.Kill(); Write-Host "xray stopped" }
    Remove-Item -Recurse -Force $dir -ErrorAction SilentlyContinue
    Write-Host "xray-core removed"
    return
}

if (!(Test-Path $exe)) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    Write-Host "Downloading xray-core..."
    $url = "https://github.com/XTLS/Xray-core/releases/latest/download/Xray-windows-64.zip"
    Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
    Expand-Archive -Path $zip -DestinationPath $dir -Force
    Remove-Item $zip
    Write-Host "Done: $exe"
}

$p = Get-Process -Name xray -ErrorAction SilentlyContinue
if (!$p) {
    $ps = Start-Process -FilePath $exe -ArgumentList "run -c `"$cfg`"" -WindowStyle Hidden -PassThru
    Write-Host "xray started (PID $($ps.Id))"
} else {
    Write-Host "xray already running (PID $($p.Id))"
}

Write-Host ""
Write-Host "=== PROXY SETTINGS ==="
Write-Host "SOCKS5: 127.0.0.1:1080"
Write-Host "HTTP:   127.0.0.1:1081"
Write-Host ""
Write-Host "Set proxy in browser settings, or use SwitchyOmega extension."
Write-Host ""
Write-Host "Subscription URL for v2rayN / Nekoray / Clash Verge:"
Write-Host "  https://raw.githubusercontent.com/tryaschenko-hash/VPN/main/sub.txt"
