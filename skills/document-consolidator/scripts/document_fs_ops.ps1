param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("replace-with-candidate", "move-sources", "check-paths", "restore-moved")]
    [string]$Operation,

    [string]$TargetPath,
    [string]$CandidatePath,
    [string[]]$SourcePaths,
    [string]$SourcePathsJson,
    [string]$DestinationDir,
    [string[]]$Paths,
    [string]$PathsJson,
    [string]$PairsJson
)

$ErrorActionPreference = "Stop"

function Write-Result {
    param([hashtable]$Result)
    $Result | ConvertTo-Json -Depth 8 -Compress
}

function Test-AbsolutePath {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return $false }
    try {
        return [System.IO.Path]::IsPathFullyQualified($Path)
    } catch {
        return ([System.IO.Path]::IsPathRooted($Path) -and -not ($Path.StartsWith("\") -and -not $Path.StartsWith("\\")))
    }
}

function Assert-AbsolutePath {
    param([string]$Path, [string]$Name)
    if (-not (Test-AbsolutePath $Path)) {
        throw "$Name must be an absolute path: $Path"
    }
}

function Get-CandidatePathForTarget {
    param([string]$Path)
    $dir = Split-Path -Path $Path -Parent
    $leaf = Split-Path -Path $Path -Leaf
    $ext = [System.IO.Path]::GetExtension($leaf)
    if ([string]::IsNullOrEmpty($ext)) {
        $candidateLeaf = "$leaf.candidate"
    } else {
        $stem = [System.IO.Path]::GetFileNameWithoutExtension($leaf)
        $candidateLeaf = "$stem.candidate$ext"
    }
    return (Join-Path -Path $dir -ChildPath $candidateLeaf)
}

function New-BackupDir {
    param([string]$BaseDir)
    $root = Join-Path -Path $BaseDir -ChildPath "_backup"
    if (-not (Test-Path -LiteralPath $root)) {
        New-Item -ItemType Directory -Path $root | Out-Null
    }
    $stamp = Get-Date -Format "yyyy-MM-dd_HH-mm"
    $candidate = Join-Path -Path $root -ChildPath $stamp
    $i = 2
    while (Test-Path -LiteralPath $candidate) {
        $candidate = Join-Path -Path $root -ChildPath "$stamp-$i"
        $i++
    }
    New-Item -ItemType Directory -Path $candidate | Out-Null
    return $candidate
}

function Replace-WithCandidate {
    Assert-AbsolutePath $TargetPath "TargetPath"
    Assert-AbsolutePath $CandidatePath "CandidatePath"
    if (-not (Test-Path -LiteralPath $TargetPath -PathType Leaf)) { throw "TargetPath not found: $TargetPath" }
    if (-not (Test-Path -LiteralPath $CandidatePath -PathType Leaf)) { throw "CandidatePath not found: $CandidatePath" }

    $targetFull = [System.IO.Path]::GetFullPath($TargetPath)
    $candidateFull = [System.IO.Path]::GetFullPath($CandidatePath)
    $expected = [System.IO.Path]::GetFullPath((Get-CandidatePathForTarget $targetFull))
    if ($candidateFull -ne $expected) { throw "CandidatePath must be beside target and named as candidate: expected $expected" }

    $candidateItem = Get-Item -LiteralPath $candidateFull
    if ($candidateItem.Length -eq 0) { throw "CandidatePath is empty: $candidateFull" }

    $targetDir = Split-Path -Path $targetFull -Parent
    $targetLeaf = Split-Path -Path $targetFull -Leaf
    $backupDir = New-BackupDir $targetDir
    $backupTarget = Join-Path -Path $backupDir -ChildPath $targetLeaf
    $movedTarget = $false

    try {
        Move-Item -LiteralPath $targetFull -Destination $backupTarget
        $movedTarget = $true
        Move-Item -LiteralPath $candidateFull -Destination $targetFull
        Write-Result @{
            status = "success"
            operation = "replace-with-candidate"
            target = $targetFull
            candidate = $candidateFull
            backup_path = $backupTarget
            backup_dir = $backupDir
            moved = @(
                @{ from = $targetFull; to = $backupTarget },
                @{ from = $candidateFull; to = $targetFull }
            )
        }
    } catch {
        $restore = "not_needed"
        if ($movedTarget -and -not (Test-Path -LiteralPath $targetFull) -and (Test-Path -LiteralPath $backupTarget)) {
            try {
                Move-Item -LiteralPath $backupTarget -Destination $targetFull
                $restore = "restored_target"
            } catch {
                $restore = "restore_failed: $($_.Exception.Message)"
            }
        }
        Write-Result @{
            status = "error"
            operation = "replace-with-candidate"
            message = $_.Exception.Message
            target = $targetFull
            candidate = $candidateFull
            backup_path = $backupTarget
            restore = $restore
            next_valid_actions = @("inspect-paths", "fix-candidate", "retry-after-confirmation")
        }
        exit 1
    }
}

function Move-Sources {
    if (-not [string]::IsNullOrWhiteSpace($SourcePathsJson)) {
        $parsed = ConvertFrom-Json -InputObject $SourcePathsJson
        $SourcePaths = @()
        foreach ($item in $parsed) { $SourcePaths += [string]$item }
    }
    if (-not $SourcePaths -or $SourcePaths.Count -eq 0) { throw "SourcePaths is required" }
    if ($SourcePaths.Count -eq 1 -and $SourcePaths[0] -like "*,*") {
        $SourcePaths = @($SourcePaths[0].Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    }
    Assert-AbsolutePath $DestinationDir "DestinationDir"
    foreach ($path in $SourcePaths) {
        Assert-AbsolutePath $path "SourcePaths"
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Source not found: $path" }
    }
    if (-not (Test-Path -LiteralPath $DestinationDir)) {
        New-Item -ItemType Directory -Path $DestinationDir | Out-Null
    }
    $moved = @()
    try {
        foreach ($path in $SourcePaths) {
            $full = [System.IO.Path]::GetFullPath($path)
            $dest = Join-Path -Path $DestinationDir -ChildPath (Split-Path -Path $full -Leaf)
            if (Test-Path -LiteralPath $dest) { throw "Destination already exists: $dest" }
            Move-Item -LiteralPath $full -Destination $dest
            $moved += @{ from = $full; to = [System.IO.Path]::GetFullPath($dest) }
        }
        Write-Result @{
            status = "success"
            operation = "move-sources"
            destination_dir = [System.IO.Path]::GetFullPath($DestinationDir)
            moved = $moved
        }
    } catch {
        $rollback = @()
        $reversed = @($moved)
        [array]::Reverse($reversed)
        foreach ($item in $reversed) {
            try {
                if ((Test-Path -LiteralPath $item.to) -and -not (Test-Path -LiteralPath $item.from)) {
                    Move-Item -LiteralPath $item.to -Destination $item.from
                    $rollback += @{ from = $item.to; to = $item.from; status = "restored" }
                }
            } catch {
                $rollback += @{ from = $item.to; to = $item.from; status = "restore_failed"; message = $_.Exception.Message }
            }
        }
        Write-Result @{
            status = "error"
            operation = "move-sources"
            message = $_.Exception.Message
            moved_before_error = $moved
            rollback = $rollback
            next_valid_actions = @("inspect-paths", "manual-repair")
        }
        exit 1
    }
}

function Check-Paths {
    if (-not [string]::IsNullOrWhiteSpace($PathsJson)) {
        $parsed = ConvertFrom-Json -InputObject $PathsJson
        $Paths = @()
        foreach ($item in $parsed) { $Paths += [string]$item }
    }
    if (-not $Paths -or $Paths.Count -eq 0) { throw "Paths is required" }
    if ($Paths.Count -eq 1 -and $Paths[0] -like "*,*") {
        $Paths = @($Paths[0].Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    }
    $items = @()
    foreach ($path in $Paths) {
        Assert-AbsolutePath $path "Paths"
        $items += @{
            path = [System.IO.Path]::GetFullPath($path)
            exists = Test-Path -LiteralPath $path
            is_file = Test-Path -LiteralPath $path -PathType Leaf
            is_dir = Test-Path -LiteralPath $path -PathType Container
        }
    }
    Write-Result @{ status = "success"; operation = "check-paths"; items = $items }
}

function Restore-Moved {
    if ([string]::IsNullOrWhiteSpace($PairsJson)) { throw "PairsJson is required" }
    $pairs = $PairsJson | ConvertFrom-Json
    $restored = @()
    foreach ($pair in $pairs) {
        Assert-AbsolutePath $pair.from "pair.from"
        Assert-AbsolutePath $pair.to "pair.to"
        if (-not (Test-Path -LiteralPath $pair.from)) { throw "Restore source not found: $($pair.from)" }
        if (Test-Path -LiteralPath $pair.to) { throw "Restore destination already exists: $($pair.to)" }
        Move-Item -LiteralPath $pair.from -Destination $pair.to
        $restored += @{ from = $pair.from; to = $pair.to }
    }
    Write-Result @{ status = "success"; operation = "restore-moved"; restored = $restored }
}

try {
    switch ($Operation) {
        "replace-with-candidate" { Replace-WithCandidate }
        "move-sources" { Move-Sources }
        "check-paths" { Check-Paths }
        "restore-moved" { Restore-Moved }
    }
} catch {
    Write-Result @{
        status = "error"
        operation = $Operation
        message = $_.Exception.Message
        next_valid_actions = @("inspect-arguments", "retry-after-fix")
    }
    exit 1
}
