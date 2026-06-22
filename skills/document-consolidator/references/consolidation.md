# Consolidation

Consolidation means creating one or more useful documents from several source documents without hiding source roles or conflicts.

## Before Drafting

Map:

- each source file;
- its role and owner of meaning;
- what should transfer;
- what should stay separate;
- what should be excluded;
- conflicts or uncertain claims;
- whether one output file is enough.

If one output file would mix incompatible roles, propose several output documents.

## Output File Naming

Suggest a final filename based on the topic and ask before writing. Do not create generic names like `merged.md`.

If source files come from different folders, ask where the output file and backup should be placed.

If the proposed final file already exists, stop and ask whether to replace it, choose another name, or cancel.

## Sources Section

Every consolidated document must include a short `Sources` or `Источники` section with relative links to the source files.

Use links immediately, even before source movement. If sources are later moved to `00_Source_Documents`, update only the source links in the consolidated document.

Do not edit the consolidated document's content under the excuse of link repair.

After link repair, check that each source link points to an existing file.

## Source Movement

Source movement is a separate step after the consolidated document is created and checked.

Default folder:

```text
00_Source_Documents
```

Move only files that actually contributed to the final document. Files analyzed but excluded must stay where they are and appear in the chat report as not moved.

Do not add banners or notes to source files. Do not create a README in `00_Source_Documents` by default.

If a same-name file already exists in `00_Source_Documents`, stop and ask. Do not auto-rename or overwrite.

## External Links

Do not repair links outside selected files by default. Report likely broken external references as risk.

For internal links among moved source documents, show the risk and ask before any repair.

## Partial Failure

If moving sources partially fails, attempt to move already moved files back. If rollback fails, stop and report exact current file locations and link risk.
