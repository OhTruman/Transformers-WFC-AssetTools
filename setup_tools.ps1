# Fetch third-party tools into AssetTools\bin (nothing is installed system-wide).
#   powershell -ExecutionPolicy Bypass -File AssetTools\setup_tools.ps1
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$bin  = Join-Path $root 'bin'
$dl   = Join-Path $root '_downloads'
New-Item -ItemType Directory -Force $bin, $dl | Out-Null

function Get-Zip($url, $zip, $referer) {
    $out = Join-Path $dl $zip
    if (-not (Test-Path $out)) {
        $h = @{ 'User-Agent' = 'Mozilla/5.0' }; if ($referer) { $h['Referer'] = $referer }
        Invoke-WebRequest -Uri $url -OutFile $out -Headers $h
    }
    return $out
}

# Python 3.12 (NuGet full package, includes pip) + libs
if (-not (Test-Path "$bin\py\python.exe")) {
    $z = Get-Zip 'https://www.nuget.org/api/v2/package/python/3.12.7' 'python.nupkg.zip'
    Expand-Archive $z "$dl\py" -Force; Move-Item "$dl\py\tools" "$bin\py"
}
& "$bin\py\python.exe" -m pip install -q numpy pillow lzallright

# UE Viewer (umodel) build 1590 - supports Transformers: War for Cybertron (-game=trans)
if (-not (Test-Path "$bin\umodel\umodel_64.exe")) {
    $z = Get-Zip 'https://www.gildor.org/down/47/umodel/umodel_win32.zip' 'umodel.zip' 'https://www.gildor.org/en/projects/umodel'
    Expand-Archive $z "$bin\umodel" -Force
}
# vgmstream (FSB4 / XMA2 -> WAV)
if (-not (Test-Path "$bin\vgmstream\vgmstream-cli.exe")) {
    $z = Get-Zip 'https://github.com/vgmstream/vgmstream/releases/latest/download/vgmstream-win64.zip' 'vgmstream.zip'
    Expand-Archive $z "$bin\vgmstream" -Force
}
# ffmpeg (Bink 1 video/audio decode)
if (-not (Test-Path "$bin\ffmpeg\ffmpeg.exe")) {
    $z = Get-Zip 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip' 'ffmpeg.zip'
    Expand-Archive $z "$dl\ff" -Force
    Move-Item (Get-ChildItem "$dl\ff\*\bin" | Select-Object -First 1).FullName "$bin\ffmpeg"
}
Write-Host 'Tools ready in' $bin
