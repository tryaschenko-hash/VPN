param([switch]$Uninstall)

$dir = "$PSScriptRoot\xray-core"
$zip = "$dir\xray.zip"
$exe = "$dir\xray.exe"
$cfg = "$PSScriptRoot\xray-local-config.json"
$log = "$dir\xray.log"

if ($Uninstall) {
    $p = Get-Process -Name xray -ErrorAction SilentlyContinue
    if ($p) { $p.Kill(); Write-Host "xray остановлен" }
    Remove-Item -Recurse -Force $dir -ErrorAction SilentlyContinue
    Write-Host "xray-core удалён"
    return
}

if (!(Test-Path $exe)) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    Write-Host "Скачиваю xray-core..."
    $url = "https://github.com/XTLS/Xray-core/releases/latest/download/Xray-windows-64.zip"
    Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
    Expand-Archive -Path $zip -DestinationPath $dir -Force
    Remove-Item $zip
    Write-Host "Готово: $exe"
}

$p = Get-Process -Name xray -ErrorAction SilentlyContinue
if (!$p) {
    $ps = Start-Process -FilePath $exe -ArgumentList "run -c `"$cfg`"" -WindowStyle Hidden -PassThru
    Write-Host "xray запущен (PID $($ps.Id))"
} else {
    Write-Host "xray уже запущен (PID $($p.Id))"
}

Write-Host ""
Write-Host "=== НАСТРОЙКА ПРОКСИ ==="
Write-Host "SOCKS5: 127.0.0.1:1080"
Write-Host "HTTP:   127.0.0.1:1081"
Write-Host ""
Write-Host "В браузере установи прокси:"
Write-Host "  Chrome/Edge: Настройки → Система → Прокси → вручную"
Write-Host "  Или используй расширение (SwitchyOmega и т.п.)"
Write-Host ""
Write-Host "Для подписки в v2rayN/Nekoray/Clash Verge:"
Write-Host "  https://raw.githubusercontent.com/tryaschenko-hash/VPN/main/sub.txt"
