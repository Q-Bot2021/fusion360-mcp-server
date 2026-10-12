# Autodesk Fusion API Pointer Index

[Searchable pointer index](index.tsv) for Autodesk's desktop Fusion API.
Each TSV row contains only `symbol`, `kind`, and the official documentation `url`.
There are no descriptions, signatures, examples, or copied documentation bodies.

## Lookup for Agent Sessions

The [mechanical/drawing coverage inventory](../mechanical/README.md) tracks API
assignment review and development candidates separately from this pointer index.

1. Search `index.tsv` for the relevant class/member or action, rather than loading
   the entire index into context. Symbols are fully qualified and sorted.
2. Use `kind` to distinguish `method`, `property`, `event`, `object`, and
   `enumeration`. Start with the object pointer when you need its member overview.
3. Fetch the matching Autodesk URL, then follow its linked argument/return types
   as needed. Ingest the current function documentation on demand, not this entire
   archive. The link index alone does not establish a signature or valid workflow.
4. Check installed Fusion version, licensing, preview status and live behavior.
   A documented API member is not automatically an available MCP capability.
   Follow the unit/protocol/live gates in [developer rules](../../dev_rules.md).

From the repository root:

```text
rg -F "adsk.fusion.TemporaryBRepManager.createBox" docs/fusion-api/index.tsv
rg -F "adsk.fusion.ExtrudeFeatures." docs/fusion-api/index.tsv
rg -i "thread|joint|toolpath" docs/fusion-api/index.tsv
```

Use a TSV parser when selecting by kind/namespace programmatically; avoid parsing
tabular data with informal string splitting. Namespace prefixes cover `adsk.core`,
`adsk.fusion`, `adsk.cam`, `adsk.drawing`, `adsk.electron`, and `adsk.volume` in this
snapshot. The MCP currently uses selected operations, not all indexed namespaces.

## Snapshot and Provenance

- Indexed on **2026-10-09** from Autodesk's official
  [FusionAPI.chm](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/ExtraFiles/FusionAPI.chm).
- Archive SHA-256: `9CE7F06DC92F795CF29468D90810943C90579E06B7A3975FF021D93475DE2EA6`.
- Source: [Fusion API reference manual](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/ReferenceManual_UM.htm)
  and [API welcome page](https://help.autodesk.com/view/fusion360/ENU/?guid=GUID-A92A4B10-3781-4925-94C6-47DA85A4F65A).
- URLs come from official canonical links. Namespace identity comes from the
  reference metadata; descriptions/examples are discarded during generation.
- Snapshot covers the reference pages in that archive, not a promise that the
  archive matches every subsequent online change. Samples and user-manual topics
  are intentionally not indexed. Enumeration pages are pointers, not enum values.

| Pointer Kind | Count |
| --- | ---: |
| Methods | 4,928 |
| Properties | 12,445 |
| Events | 74 |
| Objects | 1,490 |
| Enumerations | 342 |
| Total | 19,279 |

## Refresh

The generator is [scripts/index_fusion_api.py](../../scripts/index_fusion_api.py).
It uses Python's standard HTML/CSV/URL parsers and does not contact Fusion or add
MCP registrations. Unit and index-contract checks live in
[tests/test_api_index.py](../../tests/test_api_index.py).

On Windows, download the official archive into a fresh temporary directory and
extract it with the built-in HTML Help decompiler. This extracts data; do not open
or execute the archive's sample code. Keep the archive and extracted page bodies
outside the repository:

```powershell
$work = Join-Path $env:TEMP ('fusion-api-index-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $work | Out-Null
$archive = Join-Path $work 'FusionAPI.chm'
Invoke-WebRequest -UseBasicParsing -ErrorAction Stop 'https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/ExtraFiles/FusionAPI.chm' -OutFile $archive
$extracted = Join-Path $work 'extracted'
Start-Process "$env:WINDIR\hh.exe" -ArgumentList @('-decompile', $extracted, $archive) -Wait
uv run --python 3.12 python scripts/index_fusion_api.py $extracted docs/fusion-api/index.tsv
Get-FileHash $archive -Algorithm SHA256
uv run --python 3.12 pytest tests/test_api_index.py tests/test_instructions_sync.py -v
```

On another platform, use an available CHM data extractor, then pass its extracted
directory to the same generator. No extractor dependency is bundled here.

Update the snapshot date, checksum and counts in this guide together with the TSV.
Review added/removed symbols, run focused tests and Ruff, and verify representative
official URLs. Never replace a failed/empty extraction with a partial claimed
complete index. Do not register the index as an MCP resource without the required
protocol and live acceptance; this change is repository documentation only.