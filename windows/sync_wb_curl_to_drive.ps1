param(
    [string]$Source = "$env:USERPROFILE\Downloads\wb_curl.txt",
    [string]$Destination = "G:\Мой диск\WB_SERP_SYNC\wb_curl.txt",
    [int]$PollSeconds = 10,
    [switch]$Once
)

$ErrorActionPreference = "Stop"

function Sync-WbCurl {
    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) {
        return
    }

    $destinationDirectory = Split-Path -Parent $Destination
    if (-not (Test-Path -LiteralPath $destinationDirectory -PathType Container)) {
        return
    }

    $sourceHash = (Get-FileHash -LiteralPath $Source -Algorithm SHA256).Hash
    $destinationHash = if (Test-Path -LiteralPath $Destination -PathType Leaf) {
        (Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash
    } else {
        ""
    }

    if ($sourceHash -ne $destinationHash) {
        Copy-Item -LiteralPath $Source -Destination $Destination -Force
    }
}

do {
    try {
        Sync-WbCurl
    } catch {
        # Drive may still be mounting. The next poll retries without stopping the task.
    }
    if (-not $Once) {
        Start-Sleep -Seconds $PollSeconds
    }
} while (-not $Once)
