<#
.SYNOPSIS
    Pulls PostgreSQL backup archives from the CFR EVO kiosk to the developer laptop.

.DESCRIPTION
    backend/scripts/backup_db.sh writes dumps to /home/tcfire/cfr-backups on the kiosk
    -- the same SSD as the database they protect. That covers `docker compose down -v`,
    a bad migration, and accidental deletion. It does NOT cover hardware failure, which
    is the failure mode most likely to take the irreplaceable HITL corpus with it.

    This script is the off-kiosk half. It runs on the laptop and copies down any archive
    it does not already hold, verifying transferred size against the remote before
    accepting a file.

    Default destination is a SIBLING of the git repository, never inside it: the full
    dumps are tens of megabytes and must never be swept into a `git add .`. Because the
    default path sits under Nextcloud, syncing carries the archives off the laptop as
    well, giving a third copy at no cost.

    This is PROJECT_IDEAS.md #9 step 2, taken as an interim measure. It depends on the
    laptop being run periodically -- it is not a substitute for scheduled off-site
    storage, and the gap stays open until something runs unattended.

.PARAMETER Destination
    Local directory for archives. Created if absent.

.PARAMETER KeepFull
    Full dumps to retain locally. Critical dumps are never rotated here -- they are a
    few megabytes each and are the data that cannot be regenerated.

.EXAMPLE
    .\backend\scripts\pull_backups.ps1
.EXAMPLE
    .\backend\scripts\pull_backups.ps1 -Destination E:\cfr-backups -KeepFull 10
#>
[CmdletBinding()]
param(
    [string]$RemoteHost = 'tcfire@100.95.146.94',
    [string]$RemoteDir  = '/home/tcfire/cfr-backups',
    [string]$Destination = "$HOME\Nextcloud\Documents\Projects\Coding\CFR-EVO-Backups",
    [int]$KeepFull = 4,
    [int]$KeepModels = 3
)

$ErrorActionPreference = 'Stop'

function Write-Log($Message) {
    Write-Host ("{0} [pull_backups] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message)
}

Write-Log "source: ${RemoteHost}:${RemoteDir}"
Write-Log "destination: $Destination"

if (-not (Test-Path $Destination)) {
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    Write-Log "created destination directory"
}

# Ask the kiosk what it holds: "<bytes> <filename>" per archive.
$listing = & ssh $RemoteHost "ls -1 $RemoteDir/*.sql.gz $RemoteDir/*.tar.gz $RemoteDir/*.sha256 2>/dev/null | while read f; do echo \`"`$(stat -c%s `"`$f`") `$(basename `"`$f`")\`"; done"
if ($LASTEXITCODE -ne 0) {
    throw "could not reach $RemoteHost -- is the kiosk up and Tailscale connected?"
}
if ([string]::IsNullOrWhiteSpace($listing)) {
    throw "no archives found in ${RemoteDir} -- has backup_db.sh run yet?"
}

$remote = @()
foreach ($line in ($listing -split "`n")) {
    $t = $line.Trim()
    if ($t -match '^(\d+)\s+(.+\.(?:sql\.gz|tar\.gz|sha256))$') {
        $remote += [pscustomobject]@{ Size = [int64]$Matches[1]; Name = $Matches[2] }
    }
}
Write-Log "kiosk holds $($remote.Count) archive(s)"

# Do not download what rotation deletes on the way out. The kiosk retains full dumps 7
# deep while this copy keeps only -KeepFull, so pulling everything and rotating afterwards
# re-downloaded the same three archives on every single run -- roughly 36 MB per
# invocation, indefinitely, with nothing to show for it. Choose the newest N up front.
# Critical dumps are never filtered: keeping every one is the entire point of this copy.
$wantedFull   = @($remote | Where-Object { $_.Name -like 'cfr-full-*.sql.gz'   } | Sort-Object Name -Descending | Select-Object -First $KeepFull)
$wantedModels = @($remote | Where-Object { $_.Name -like 'cfr-model-*.tar.gz'  } | Sort-Object Name -Descending | Select-Object -First $KeepModels)
$wantedOther  = @($remote | Where-Object {
    $_.Name -notlike 'cfr-full-*.sql.gz' -and $_.Name -notlike 'cfr-model-*.tar.gz' -and $_.Name -notlike '*.sha256'
})
# A checksum is only worth carrying if the archive it describes is being carried too.
$keptNames  = @(($wantedFull + $wantedModels + $wantedOther) | ForEach-Object { $_.Name })
$wantedSums = @($remote | Where-Object {
    $_.Name -like '*.sha256' -and $keptNames -contains ($_.Name -replace '\.sha256$', '')
})

$wanted = @($wantedFull + $wantedModels + $wantedOther + $wantedSums)
$beyondRetention = $remote.Count - $wanted.Count
if ($beyondRetention -gt 0) {
    Write-Log "$beyondRetention archive(s) left on the kiosk -- older than local retention"
}
$remote = $wanted

$pulled = 0; $skipped = 0
foreach ($r in $remote) {
    $localPath = Join-Path $Destination $r.Name

    # Size match is the completeness check. A partially transferred archive that is
    # kept and later trusted is the same defect class as a truncated dump: a file
    # that looks like a backup and is not (CLAUDE.md 6.1).
    if ((Test-Path $localPath) -and ((Get-Item $localPath).Length -eq $r.Size)) {
        $skipped++
        continue
    }

    $tmp = "$localPath.part"
    & scp -q "${RemoteHost}:$($RemoteDir)/$($r.Name)" $tmp
    if ($LASTEXITCODE -ne 0) {
        Remove-Item $tmp -Force -ErrorAction SilentlyContinue
        throw "scp failed for $($r.Name)"
    }

    $got = (Get-Item $tmp).Length
    if ($got -ne $r.Size) {
        Remove-Item $tmp -Force -ErrorAction SilentlyContinue
        throw "size mismatch on $($r.Name): expected $($r.Size) bytes, got $got"
    }

    Move-Item -Force $tmp $localPath
    $pulled++
    Write-Log ("pulled {0} ({1:N1} MB)" -f $r.Name, ($r.Size / 1MB))
}

Write-Log "$pulled new, $skipped already held"

# Rotate local full dumps only. Critical archives are tiny and irreplaceable; keeping
# every one of them costs almost nothing and is the entire point of this copy.
$full = Get-ChildItem $Destination -Filter 'cfr-full-*.sql.gz' | Sort-Object Name -Descending
if ($full.Count -gt $KeepFull) {
    $drop = $full | Select-Object -Skip $KeepFull
    $drop | Remove-Item -Force
    Write-Log "rotated $($drop.Count) old full dump(s), keeping $KeepFull"
}

# Rotate fine-tuned model archives. Retrainable, but only while the audio and the
# verified_* corpus both survive -- and the 2026-07-17 model was lost precisely because
# backend/models/ is git-ignored and nothing copied it anywhere. Keep a few generations so
# a bad fine-tune can be rolled back to a known-good one.
$models = Get-ChildItem $Destination -Filter 'cfr-model-*.tar.gz' | Sort-Object Name -Descending
if ($models.Count -gt $KeepModels) {
    $drop = $models | Select-Object -Skip $KeepModels
    $drop | ForEach-Object {
        Remove-Item $_.FullName -Force
        Remove-Item "$($_.FullName).sha256" -Force -ErrorAction SilentlyContinue
    }
    Write-Log "rotated $($drop.Count) old model archive(s), keeping $KeepModels"
}

$crit = @(Get-ChildItem $Destination -Filter 'cfr-critical-*.sql.gz')
$total = (Get-ChildItem "$Destination\*" -Include '*.sql.gz', '*.tar.gz' | Measure-Object Length -Sum).Sum

if ($crit.Count -eq 0) {
    Write-Warning "no critical archives held locally -- the irreplaceable data is NOT backed up here"
} else {
    Write-Log ("newest critical archive: {0}" -f ($crit | Sort-Object Name -Descending)[0].Name)
}
$archives = @(Get-ChildItem "$Destination\*" -Include '*.sql.gz', '*.tar.gz')
Write-Log ("holding {0} archive(s), {1:N1} MB total" -f $archives.Count, ($total / 1MB))
$modelsHeld = @(Get-ChildItem $Destination -Filter 'cfr-model-*.tar.gz')
if ($modelsHeld.Count -eq 0) {
    Write-Warning "no fine-tuned model archive held locally -- backend/models/ is git-ignored and exists only on the kiosk"
} else {
    Write-Log ("newest model archive: {0}" -f ($modelsHeld | Sort-Object Name -Descending)[0].Name)
}
