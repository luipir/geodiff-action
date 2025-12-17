# GeoDiff Action

A GitHub Action for comparing geospatial files and detecting differences.

## Features

- Compare geospatial files (GeoJSON, Shapefile, GeoPackage, etc.)
- Output diff results in multiple formats (JSON, GeoJSON, summary)
- Detect added, removed, and modified features
- Generate job summaries with visual diff reports

## Usage

```yaml
- uses: your-username/geodiff-action@v1
  with:
    base_file: 'path/to/base.geojson'
    compare_file: 'path/to/compare.geojson'
    output_format: 'geojson'
```

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `base_file` | Path to the base geospatial file | Yes | - |
| `compare_file` | Path to the file to compare against base | Yes | - |
| `output_format` | Output format for the diff result (json, geojson, summary) | No | `geojson` |
| `summary` | Add Summary to Job | No | `true` |
| `token` | GitHub Token | No | `${{ github.token }}` |

## Outputs

| Output | Description |
|--------|-------------|
| `diff_result` | The diff result output |
| `has_changes` | Boolean indicating if changes were detected |

## Example Workflow

```yaml
name: Geo Diff Check

on:
  pull_request:
    paths:
      - '**.geojson'
      - '**.gpkg'

jobs:
  diff:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Get changed files
        id: changed
        uses: tj-actions/changed-files@v44
        with:
          files: |
            **.geojson
            **.gpkg

      - name: Run GeoDiff
        if: steps.changed.outputs.any_changed == 'true'
        uses: your-username/geodiff-action@v1
        with:
          base_file: ${{ steps.changed.outputs.all_changed_files }}
          compare_file: ${{ steps.changed.outputs.all_changed_files }}
          output_format: 'summary'
```

## Development

This action is built using Python and UV package manager.

### Prerequisites

- Python 3.10+
- UV package manager

### Local Development

```bash
# Install dependencies
uv sync

# Run linters
uv run ruff check src/
uv run black --check src/

# Run the action locally
uv run python src/main.py
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
