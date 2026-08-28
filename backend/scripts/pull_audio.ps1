<#
.SYNOPSIS
    Pulls the dispatch audio corpus from the kiosk to the developer laptop.

.DESCRIPTION
    The other half of the ground-truth corpus (PROJECT_IDEAS.md #9 step 4).
    backup_db.sh protects the verified_* columns in public.dispatches; those
    columns are useless without the *.wav files they were transcribed from, and
    nothing regenerates audio. Measured on the kiosk 2026-08-27:

        backend/audio_files          718 MB   496 files
        frontend/public/recordings    19 MB    14 files

    RESUMABLE BY DESIGN. At ~768 MB this transfer can be interrupted -- a closed
    lid, a dropped link, a walk to the truck. Files already held at the matching
    byte size are skipped, so re-running continues where it stopped rather than
    starting over. Interrupted files land as .part and are re-pulled next run.

    THROUGHPUT DEPENDS ON THE LAPTOP'S UPLINK, not on Tailscale as such.
    Measured 2026-08-27: 10.6 MB in ~4 minutes, roughly 45 KB/s, with the
    laptop tethered to a phone hotspot on poor cell reception -- that would put
    this transfer near five hours. Measured 2026-08-28 on the same LAN as the
    kiosk: ~2,700 KB/s, about sixty times faster.

    The relay/direct state reported below is a useful SYMPTOM of this (a
    hotspot behind carrier NAT tends to relay, a shared LAN goes direct) but it
    is not the cause. Do not read "direct" as a promise of speed on a weak
    link. The honest rule is simpler: run this on the hall network, or on any
    real broadband connection, and avoid it on cell tethering.

        tailscale status | Select-String cfr-mapping

.EXAMPLE
    backend\scripts\pull_audio.ps1
    backend\scripts\pull_audio.ps1 -RequireSsid Badger
    backend\scripts\pull_audio.ps1 -DestRoot D:\cfr-audio
#>
[CmdletBinding()]
param(
    [string]$KioskHost = 'tcfire@100.95.146.94',
    [string]$DestRoot  = (Join-Path $env:USERPROFILE 'Nextcloud\Documents\Projects\Coding\CFR-EVO-Backups\audio'),
    # Label => remote path. Labels are explicit rather than derived from the
    # path leaf because BOTH source trees end in "recordings"
    # (backend/audio_files/recordings and frontend/public/recordings); keying on
    # the leaf silently merged them into one local folder.
    [hashtable]$RemoteDirs = [ordered]@{
        'backend_audio_files'  = '/home/tcfire/CFR-EVO-APP/backend/audio_files'
        'frontend_recordings'  = '/home/tcfire/CFR-EVO-APP/frontend/public/recordings'
    },
    # When set, refuses to run unless the active Wi-Fi SSID matches. Guards
    # against starting a ~768 MB pull on a metered phone hotspot.
    [string]$RequireSsid,
    [switch]$WhatIfOnly
)

$ErrorActionPreference = 'Stop'
function Log($m) { Write-Host ("{0} [pull_audio] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m) }
function Die($m) { Write-Host ("{0} [pull_audio] ERROR: {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m) -ForegroundColor Red; exit 1 }

if ($RequireSsid) {
    $ssid = (netsh wlan show interfaces |
             Select-String -Pattern '^\s*SSID\s*:\s*(.+)$' |
             ForEach-Object { $_.Matches[0].Groups[1].Value.Trim() } |
             Select-Object -First 1)
    if (-not $ssid) { Die "no active Wi-Fi SSID; expected '$RequireSsid'" }
    if ($ssid -ne $RequireSsid) { Die "connected to '$ssid', not '$RequireSsid' -- not starting" }
    Log "SSID check passed: $ssid"
}

# Report the Tailscale path rather than silently crawling over a relay.
try {
    $ts = (tailscale status 2>$null | Select-String 'cfr-mapping') -join ''
    if ($ts -match 'direct\s+(\S+)')   { Log "tailscale path: DIRECT ($($Matches[1]))" }
    elseif ($ts -match 'relay\s+"?(\w+)') { Log "tailscale path: RELAYED via '$($Matches[1])' -- expect this to be slow" }
} catch { Log "tailscale path: unknown (CLI not available)" }

if (-not (Test-Path $DestRoot)) {
    New-Item -ItemType Directory -Path $DestRoot -Force | Out-Null
    Log "created destination $DestRoot"
}
Log "source: $KioskHost"
Log "destination: $DestRoot"

$totalNew = 0; $totalSkip = 0; $totalBytes = 0L
$startedAt = Get-Date

foreach ($leaf in $RemoteDirs.Keys) {
    $remote  = $RemoteDirs[$leaf]
    $destDir = Join-Path $DestRoot $leaf
    if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }

    # One listing call: "<size> <relative path>" per file. Cheaper and far less
    # fragile than an ssh round trip per file across several hundred files.
    #
    # RECURSIVE, and %P (path relative to the search root) rather than %f
    # (basename). An earlier version used -maxdepth 1 with %f: every one of the
    # 508 files lives one level down in audio_files/recordings/, so it matched
    # nothing, logged "no files", and exited 0 -- reporting success while
    # skipping 718 MB. A silent gap presented as a clean run is the same defect
    # class as a fabricated value (CLAUDE.md 6.1), so an empty listing for a
    # directory that exists is now treated as suspicious, not as "done".
    $listing = ssh -o ConnectTimeout=15 $KioskHost "find '$remote' -type f -printf '%s %P\n' 2>/dev/null"
    if ($LASTEXITCODE -ne 0) { Die "could not list $remote" }
    if (-not $listing) {
        $exists = ssh -o ConnectTimeout=15 $KioskHost "test -d '$remote' && echo yes || echo no"
        if ($exists.Trim() -eq 'yes') { Die "$leaf : directory exists but listed zero files -- refusing to report success" }
        Log "$leaf : directory absent on kiosk, skipping"
        continue
    }

    $entries = @($listing -split "`n" | Where-Object { $_.Trim() })
    Log "$leaf : $($entries.Count) file(s) on kiosk"

    $i = 0
    foreach ($line in $entries) {
        $i++
        $parts = $line.Trim() -split ' ', 2
        if ($parts.Count -ne 2) { continue }
        $size = [int64]$parts[0]; $name = $parts[1]
        # $name may carry a subdirectory (e.g. "recordings/DISP-2026-C39B88.wav"),
        # so mirror the remote tree locally rather than flattening it.
        $dest = Join-Path $destDir ($name -replace '/', '\')
        $destParent = Split-Path $dest -Parent
        if (-not (Test-Path $destParent)) { New-Item -ItemType Directory -Path $destParent -Force | Out-Null }

        if ((Test-Path $dest) -and ((Get-Item $dest).Length -eq $size)) { $totalSkip++; continue }

        if ($WhatIfOnly) { Log "would pull $name ($([math]::Round($size/1MB,2)) MB)"; $totalNew++; continue }

        # .part then rename: an interrupted copy must not be left at a name the
        # size check would later accept as complete (CLAUDE.md 6.1).
        $part = "$dest.part"
        scp -q -o ConnectTimeout=15 "${KioskHost}:$remote/$name" $part
        if ($LASTEXITCODE -ne 0) { Remove-Item $part -EA SilentlyContinue; Die "transfer failed on $name" }

        $got = (Get-Item $part).Length
        if ($got -ne $size) { Remove-Item $part -Force; Die "size mismatch on $name (kiosk $size, got $got)" }

        Move-Item $part $dest -Force
        $totalNew++; $totalBytes += $size
        if ($totalNew -eq 1 -or $totalNew % 25 -eq 0) {
            $mb = [math]::Round($totalBytes/1MB, 1)
            $rate = if (((Get-Date) - $startedAt).TotalSeconds -gt 0) {
                [math]::Round($totalBytes/1KB/((Get-Date) - $startedAt).TotalSeconds, 0)
            } else { 0 }
            Log "$leaf : $i/$($entries.Count) -- $totalNew pulled, $mb MB, ~$rate KB/s"
        }
    }
}

$held = @(Get-ChildItem $DestRoot -Recurse -File)
$heldMb = [math]::Round((($held | Measure-Object Length -Sum).Sum)/1MB, 1)
Log ("done in {0:N0}s: {1} new, {2} already held" -f ((Get-Date) - $startedAt).TotalSeconds, $totalNew, $totalSkip)
Log "holding $($held.Count) file(s), $heldMb MB total at $DestRoot"
if ($totalNew -eq 0 -and $totalSkip -gt 0) { Log "corpus already complete" }
