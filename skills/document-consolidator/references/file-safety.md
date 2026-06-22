# File Safety

This reference owns file mechanics. Read it before any candidate creation, replacement, backup, or source movement.

## Candidate Files

Create candidates beside the target:

```text
name.md -> name.candidate.md
name.txt -> name.candidate.txt
name -> name.candidate
```

If the candidate already exists, stop and ask. It may be from an unfinished prior run.

The candidate must be non-empty before replacement.

## Replacement

Never overwrite the target by writing content into it.

Required sequence:

1. Candidate already exists beside the target.
2. Candidate has been read back and validated.
3. User has confirmed replacement.
4. Move target to `_backup/<YYYY-MM-DD_HH-mm>/`.
5. Rename candidate to target name.
6. Read target back and verify.

If candidate rename fails after target backup, attempt to restore the target. Leave the candidate beside the target for diagnosis.

Do not keep a separate copy of the candidate after successful replacement.

## Backup

Backup folder is beside the working documents:

```text
_backup/<YYYY-MM-DD_HH-mm>/
```

The filesystem script creates it when needed. If the exact timestamp folder exists, the script may create a safe suffix and must report the actual path.

After a successful check, offer to delete only the backup created in the current run. Do not delete it without separate confirmation.

## Scripts

Use:

```text
scripts/document_fs_ops.ps1
scripts/document_fs_ops.sh
```

The scripts:

- accept only absolute paths;
- never use wildcard/glob expansion;
- operate only on explicitly listed files;
- return JSON;
- use filesystem move/rename for backup, replacement, and source movement;
- do not read or write document content except to check candidate size or path existence.

Operations:

```text
replace-with-candidate
move-sources
check-paths
restore-moved
```

For PowerShell lists, prefer JSON list parameters:

```text
-SourcePathsJson '["C:\abs\a.md","C:\abs\b.md"]'
-PathsJson '["C:\abs\a.md","C:\abs\missing.md"]'
```

Do not rely on comma-separated PowerShell arrays when invoking the script through `powershell.exe`.

The model must still ask for user confirmation before calling write/move operations.

## Link Repair Exception

After source movement, direct edit of the consolidated document is allowed only to update relative links inside the `Sources` or `Источники` section. No separate backup is required for this narrow technical link update.

After editing links, verify that every source link points to an existing file.
