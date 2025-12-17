"""GeoDiff - Core logic for geospatial file comparison."""

import json
from pathlib import Path
from typing import Any


class GeoDiffError(Exception):
    """Custom exception for GeoDiff errors."""

    pass


def load_geojson(file_path: str) -> dict[str, Any]:
    """
    Load a GeoJSON file and return its contents as a dictionary.

    Args:
        file_path: Path to the GeoJSON file.

    Returns:
        Dictionary containing the GeoJSON data.

    Raises:
        GeoDiffError: If the file cannot be loaded or is invalid.
    """
    path = Path(file_path)

    if not path.exists():
        raise GeoDiffError(f"File not found: {file_path}")

    if not path.suffix.lower() == ".geojson":
        raise GeoDiffError(f"Unsupported file format: {path.suffix}. Only .geojson is supported.")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise GeoDiffError(f"Invalid JSON in file {file_path}: {e}")

    if not isinstance(data, dict):
        raise GeoDiffError(f"Invalid GeoJSON: root must be an object, got {type(data).__name__}")

    if "type" not in data:
        raise GeoDiffError("Invalid GeoJSON: missing 'type' field")

    return data


def get_feature_id(feature: dict[str, Any], index: int) -> str:
    """
    Get a unique identifier for a feature.

    Args:
        feature: A GeoJSON feature.
        index: The feature's index in the collection.

    Returns:
        A string identifier for the feature.
    """
    if "id" in feature:
        return str(feature["id"])

    properties = feature.get("properties", {})
    if properties:
        for key in ["id", "ID", "fid", "FID", "OBJECTID", "name", "NAME"]:
            if key in properties:
                return str(properties[key])

    return f"feature_{index}"


def compare_features(base_features: list[dict], compare_features: list[dict]) -> dict[str, Any]:
    """
    Compare two lists of GeoJSON features.

    Args:
        base_features: Features from the base file.
        compare_features: Features from the comparison file.

    Returns:
        Dictionary with added, removed, modified, and unchanged features.
    """
    base_map = {get_feature_id(f, i): f for i, f in enumerate(base_features)}
    compare_map = {get_feature_id(f, i): f for i, f in enumerate(compare_features)}

    base_ids = set(base_map.keys())
    compare_ids = set(compare_map.keys())

    added_ids = compare_ids - base_ids
    removed_ids = base_ids - compare_ids
    common_ids = base_ids & compare_ids

    added = [compare_map[fid] for fid in added_ids]
    removed = [base_map[fid] for fid in removed_ids]

    modified = []
    unchanged = []

    for fid in common_ids:
        base_feature = base_map[fid]
        compare_feature = compare_map[fid]

        if base_feature == compare_feature:
            unchanged.append(base_feature)
        else:
            modified.append({
                "id": fid,
                "base": base_feature,
                "compare": compare_feature,
            })

    return {
        "added": added,
        "removed": removed,
        "modified": modified,
        "unchanged": unchanged,
    }


def compute_diff(base_file: str, compare_file: str) -> dict[str, Any]:
    """
    Compute the difference between two GeoJSON files.

    Args:
        base_file: Path to the base GeoJSON file.
        compare_file: Path to the comparison GeoJSON file.

    Returns:
        Dictionary containing the diff results.

    Raises:
        GeoDiffError: If files cannot be loaded or compared.
    """
    base_data = load_geojson(base_file)
    compare_data = load_geojson(compare_file)

    base_type = base_data.get("type")
    compare_type = compare_data.get("type")

    if base_type != compare_type:
        raise GeoDiffError(f"Type mismatch: base is '{base_type}', compare is '{compare_type}'")

    if base_type == "FeatureCollection":
        base_features = base_data.get("features", [])
        compare_features_list = compare_data.get("features", [])
    elif base_type == "Feature":
        base_features = [base_data]
        compare_features_list = [compare_data]
    else:
        raise GeoDiffError(f"Unsupported GeoJSON type: {base_type}")

    comparison = compare_features(base_features, compare_features_list)

    has_changes = bool(comparison["added"] or comparison["removed"] or comparison["modified"])

    return {
        "base_file": base_file,
        "compare_file": compare_file,
        "type": base_type,
        "summary": {
            "added_count": len(comparison["added"]),
            "removed_count": len(comparison["removed"]),
            "modified_count": len(comparison["modified"]),
            "unchanged_count": len(comparison["unchanged"]),
            "total_base": len(base_features),
            "total_compare": len(compare_features_list),
        },
        "changes": comparison,
        "has_changes": has_changes,
    }


def format_output(diff_result: dict[str, Any], output_format: str = "geojson") -> str:
    """
    Format the diff result in the specified format.

    Args:
        diff_result: The diff result from compute_diff.
        output_format: Output format (json, geojson, summary).

    Returns:
        Formatted string output.
    """
    if output_format == "summary":
        summary = diff_result["summary"]
        lines = [
            f"GeoDiff Summary: {diff_result['base_file']} vs {diff_result['compare_file']}",
            f"  Added:     {summary['added_count']}",
            f"  Removed:   {summary['removed_count']}",
            f"  Modified:  {summary['modified_count']}",
            f"  Unchanged: {summary['unchanged_count']}",
            f"  Total (base):    {summary['total_base']}",
            f"  Total (compare): {summary['total_compare']}",
        ]
        return "\n".join(lines)

    elif output_format == "geojson":
        changes = diff_result["changes"]
        features = []

        for feature in changes["added"]:
            f = feature.copy()
            f.setdefault("properties", {})["_geodiff_status"] = "added"
            features.append(f)

        for feature in changes["removed"]:
            f = feature.copy()
            f.setdefault("properties", {})["_geodiff_status"] = "removed"
            features.append(f)

        for mod in changes["modified"]:
            f = mod["compare"].copy()
            f.setdefault("properties", {})["_geodiff_status"] = "modified"
            features.append(f)

        geojson_output = {
            "type": "FeatureCollection",
            "features": features,
            "properties": {
                "geodiff_summary": diff_result["summary"],
            },
        }
        return json.dumps(geojson_output, indent=2)

    else:  # json
        return json.dumps(diff_result, indent=2)
