param(
    [string]$Source = "$env:USERPROFILE\Downloads\wb_curl.txt",
    [string]$Destination = "",
    [int]$PollSeconds = 10,
    [switch]$Once
)

$ErrorActionPreference = "Stop"

function Sync-WbCurl {
    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) {
        return
    }

    $targetDestination = $Destination
    if ([string]::IsNullOrWhiteSpace($targetDestination)) {
        $syncDirectory = Get-ChildItem -Path "G:\" -Directory -ErrorAction Stop |
            ForEach-Object { Join-Path $_.FullName "WB_SERP_SYNC" } |
            Where-Object { Test-Path -LiteralPath $_ -PathType Container } |
            Select-Object -First 1
        if (-not $syncDirectory) {
            return
        }
        $targetDestination = Join-Path $syncDirectory "wb_curl.txt"
    }

    $destinationDirectory = Split-Path -Parent $targetDestination
    if (-not (Test-Path -LiteralPath $destinationDirectory -PathType Container)) {
        return
    }

    $sourceHash = (Get-FileHash -LiteralPath $Source -Algorithm SHA256).Hash
    $destinationHash = if (Test-Path -LiteralPath $targetDestination -PathType Leaf) {
        (Get-FileHash -LiteralPath $targetDestination -Algorithm SHA256).Hash
    } else {
        ""
    }

    if ($sourceHash -ne $destinationHash) {
        Copy-Item -LiteralPath $Source -Destination $targetDestination -Force
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
