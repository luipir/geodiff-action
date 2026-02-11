# GeoDiff Action

> Compare GeoPackage and SQLite files in your CI/CD pipeline with detailed change detection

A GitHub Action for comparing GeoPackage and SQLite database files using [pygeodiff](https://github.com/MerginMaps/geodiff). Automatically detect insertions, updates, and deletions in your geospatial data during pull requests or CI workflows. Get structured JSON or human-readable summaries of all changes across tables, with full integration into GitHub Actions job summaries.

## Features

- Compare GeoPackage (.gpkg) and SQLite (.sqlite, .db) files
- Detect inserted, updated, and deleted records
- **Auto-compare with previous git commit** when only one file is provided
- Output diff results in JSON or summary format
- Generate job summaries with detailed change reports
- Uses the powerful [pygeodiff](https://pypi.org/project/pygeodiff/) library from Mergin Maps

## Usage

### Compare two files

```yaml
- uses: geobeyond/geodiff-action@v1
  with:
    base_file: 'path/to/base.gpkg'
    compare_file: 'path/to/compare.gpkg'
    output_format: 'json'
```

### Auto-compare with previous commit

When `compare_file` is not provided, the action automatically compares the current version of `base_file` with its version from the previous commit:

```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 2  # Need at least 2 commits for comparison

- uses: geobeyond/geodiff-action@v1
  with:
    base_file: 'data/spatial.gpkg'
    # compare_file omitted - will compare with previous commit
```

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `base_file` | Path to the GeoPackage/SQLite file | Yes | - |
| `compare_file` | Path to the file to compare against base. If not provided, compares with previous git commit. | No | - |
| `output_format` | Output format for the diff result (json, summary) | No | `json` |
| `summary` | Add Summary to Job | No | `true` |
| `token` | GitHub Token | No | `${{ github.token }}` |

## Outputs

| Output | Description |
|--------|-------------|
| `diff_result` | The diff result output |
| `has_changes` | Boolean indicating if changes were detected |

## Example Workflow

```yaml
name: GeoPackage Diff Check

on:
  pull_request:
    paths:
      - '**.gpkg'

jobs:
  diff:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Get base file from main branch
        run: |
          git show origin/main:data/spatial.gpkg > base.gpkg

      - name: Run GeoDiff
        id: geodiff
        uses: geobeyond/geodiff-action@v1
        with:
          base_file: 'base.gpkg'
          compare_file: 'data/spatial.gpkg'
          output_format: 'summary'

      - name: Check for changes
        if: steps.geodiff.outputs.has_changes == 'true'
        run: |
          echo "Changes detected in GeoPackage!"
          echo "${{ steps.geodiff.outputs.diff_result }}"
```

## Output Format

The JSON output follows the same format as the `geodiff diff --json` CLI from [pygeodiff](https://github.com/MerginMaps/geodiff). Each row change is a separate entry with per-column `old`/`new` values.

### JSON Output

```json
{
  "base_file": "base.gpkg",
  "compare_file": "compare.gpkg",
  "has_changes": true,
  "summary": {
    "total_changes": 6,
    "inserts": 2,
    "updates": 2,
    "deletes": 2
  },
  "changes": {
    "geodiff": [
      {
        "table": "cities",
        "type": "insert",
        "changes": [
          { "column": 0, "new": 6 },
          { "column": 1, "new": "R1AAAeYQAAABAQAAAB04Z0..." },
          { "column": 2, "new": "Bologna" },
          { "column": 3, "new": "University city in Emilia-Romagna" },
          { "column": 4, "new": 392203 },
          { "column": 5, "new": 54.0 }
        ]
      },
      {
        "table": "cities",
        "type": "delete",
        "changes": [
          { "column": 0, "old": 3 },
          { "column": 1, "old": "R1AAAeYQAAABAQAAAH4dOG..." },
          { "column": 2, "old": "Napoli" },
          { "column": 3, "old": "Major city in southern Italy" },
          { "column": 4, "old": 967068 },
          { "column": 5, "old": 17.0 }
        ]
      },
      {
        "table": "cities",
        "type": "update",
        "changes": [
          { "column": 0, "old": 1 },
          { "column": 3, "old": "Capital of Italy", "new": "Capital of Italy - Updated 2024" },
          { "column": 4, "old": 2870500, "new": 2873000 }
        ]
      }
    ]
  }
}
```

#### Change entry structure

Each entry in the `geodiff` array represents a single row change:

| Key | Description |
|-----|-------------|
| `table` | Name of the affected table |
| `type` | Operation: `insert`, `update`, or `delete` |
| `changes` | Array of per-column dicts with `column` index and `old`/`new` values |

Column-level rules by operation type:

| Operation | `old` | `new` | Notes |
|-----------|-------|-------|-------|
| `insert` | absent | present | All columns included |
| `delete` | present | absent | All columns included |
| `update` | present | present | Only modified columns + primary key; unchanged columns are omitted |

Binary values (e.g. geometry BLOBs) are serialized as **base64-encoded strings**.

### Summary Output

```
GeoDiff Summary: base.gpkg vs compare.gpkg
  Has Changes:   Yes
  Total Changes: 6
  Inserts:       2
  Updates:       2
  Deletes:       2

  Tables affected:
    - cities: 6 change(s)
```

## Using the Output in Downstream Steps

The `diff_result` output is a compact JSON string. You can parse it in subsequent workflow steps to filter changes, extract values, or decode geometries.

### Parse the JSON output

```yaml
- name: Run GeoDiff
  id: geodiff
  uses: geobeyond/geodiff-action@v1
  with:
    base_file: 'previous.gpkg'
    compare_file: 'current.gpkg'

- name: Process changes
  if: steps.geodiff.outputs.has_changes == 'true'
  run: |
    echo '${{ steps.geodiff.outputs.diff_result }}' | python3 -c "
    import json, sys
    result = json.load(sys.stdin)
    for entry in result['changes']['geodiff']:
        print(f\"{entry['type'].upper()} in {entry['table']}\")
        for col in entry['changes']:
            old = col.get('old', '')
            new = col.get('new', '')
            print(f\"  column {col['column']}: {old} -> {new}\")
    "
```

### Decode geometry columns

Geometry values are stored as GeoPackage binary (GP header + WKB) encoded in base64. To decode them downstream into usable coordinates:

```yaml
- name: Extract geometries from changes
  if: steps.geodiff.outputs.has_changes == 'true'
  run: |
    echo '${{ steps.geodiff.outputs.diff_result }}' | python3 -c "
    import json, sys, base64, struct

    def decode_gpkg_point(b64_value):
        \"\"\"Decode a base64 GeoPackage point geometry to (lon, lat).\"\"\"
        raw = base64.b64decode(b64_value)
        # GeoPackage binary header: 2 bytes magic ('GP') + 1 byte version
        # + 1 byte flags + 4 bytes SRS ID = 8 bytes
        # Followed by WKB: 1 byte order + 4 bytes type + 8 bytes X + 8 bytes Y
        header_size = 8
        wkb = raw[header_size:]
        byte_order = wkb[0]  # 1 = little-endian
        fmt = '<' if byte_order == 1 else '>'
        geom_type = struct.unpack(f'{fmt}I', wkb[1:5])[0]
        if geom_type != 1:  # 1 = Point
            return None
        x, y = struct.unpack(f'{fmt}dd', wkb[5:21])
        return (x, y)

    result = json.load(sys.stdin)
    for entry in result['changes']['geodiff']:
        # Find the geometry column (typically column index 1 in GeoPackage)
        for col in entry['changes']:
            val = col.get('new') or col.get('old')
            if isinstance(val, str) and val.startswith('R1'):  # GP magic in base64
                coords = decode_gpkg_point(val)
                if coords:
                    print(f\"{entry['type']} in {entry['table']}: lon={coords[0]:.4f}, lat={coords[1]:.4f}\")
    "
```

### Filter changes by type or table

```yaml
- name: Count inserts per table
  if: steps.geodiff.outputs.has_changes == 'true'
  run: |
    echo '${{ steps.geodiff.outputs.diff_result }}' | jq '
      .changes.geodiff
      | map(select(.type == "insert"))
      | group_by(.table)
      | map({table: .[0].table, count: length})
    '
```

## Supported File Formats

- GeoPackage (`.gpkg`)
- SQLite (`.sqlite`, `.db`)

## Development

This action is built using Python and UV package manager with [pygeodiff](https://github.com/MerginMaps/geodiff).

### Prerequisites

- Python 3.10+
- UV package manager

### Local Development

```bash
# Install dependencies
uv sync --group test

# Run linters
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/

# Run tests
uv run pytest -v

# Run tests with coverage
uv run pytest --cov=src --cov-report=term-missing
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Acknowledgements

- [pygeodiff](https://github.com/MerginMaps/geodiff) - The underlying library for geospatial diff operations
- [Mergin Maps](https://merginmaps.com/) - Creators of the geodiff library
