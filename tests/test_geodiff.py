"""Tests for src/geodiff.py"""

import json
import tempfile
from pathlib import Path

import pytest

import sys
sys.path.insert(0, "src")

from geodiff import (
    GeoDiffError,
    compare_features,
    compute_diff,
    format_output,
    get_feature_id,
    load_geojson,
)


# Fixtures

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_feature_collection():
    """Sample GeoJSON FeatureCollection."""
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": "point1",
                "geometry": {"type": "Point", "coordinates": [0, 0]},
                "properties": {"name": "Origin"},
            },
            {
                "type": "Feature",
                "id": "point2",
                "geometry": {"type": "Point", "coordinates": [1, 1]},
                "properties": {"name": "Point A"},
            },
        ],
    }


@pytest.fixture
def modified_feature_collection():
    """Modified version of sample_feature_collection."""
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": "point1",
                "geometry": {"type": "Point", "coordinates": [0, 0]},
                "properties": {"name": "Origin Modified"},  # Modified
            },
            {
                "type": "Feature",
                "id": "point3",  # Added (point2 removed)
                "geometry": {"type": "Point", "coordinates": [2, 2]},
                "properties": {"name": "Point B"},
            },
        ],
    }


def create_geojson_file(directory: Path, filename: str, data: dict) -> str:
    """Helper to create a GeoJSON file in a directory."""
    filepath = directory / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return str(filepath)


# Tests for load_geojson

class TestLoadGeojson:
    """Tests for the load_geojson function."""

    def test_load_valid_geojson(self, temp_dir, sample_feature_collection):
        """Test loading a valid GeoJSON file."""
        filepath = create_geojson_file(temp_dir, "test.geojson", sample_feature_collection)
        result = load_geojson(filepath)
        assert result == sample_feature_collection

    def test_load_nonexistent_file(self):
        """Test loading a file that doesn't exist."""
        with pytest.raises(GeoDiffError, match="File not found"):
            load_geojson("/nonexistent/path/file.geojson")

    def test_load_unsupported_format(self, temp_dir):
        """Test loading a file with unsupported extension."""
        filepath = temp_dir / "test.json"
        filepath.write_text("{}")
        with pytest.raises(GeoDiffError, match="Unsupported file format"):
            load_geojson(str(filepath))

    def test_load_invalid_json(self, temp_dir):
        """Test loading a file with invalid JSON."""
        filepath = temp_dir / "invalid.geojson"
        filepath.write_text("not valid json {")
        with pytest.raises(GeoDiffError, match="Invalid JSON"):
            load_geojson(str(filepath))

    def test_load_geojson_missing_type(self, temp_dir):
        """Test loading GeoJSON without type field."""
        filepath = create_geojson_file(temp_dir, "notype.geojson", {"features": []})
        with pytest.raises(GeoDiffError, match="missing 'type' field"):
            load_geojson(str(filepath))

    def test_load_geojson_array_root(self, temp_dir):
        """Test loading GeoJSON with array as root (invalid)."""
        filepath = temp_dir / "array.geojson"
        filepath.write_text("[]")
        with pytest.raises(GeoDiffError, match="root must be an object"):
            load_geojson(str(filepath))


# Tests for get_feature_id

class TestGetFeatureId:
    """Tests for the get_feature_id function."""

    def test_feature_with_id(self):
        """Test feature with explicit id."""
        feature = {"type": "Feature", "id": "my-id", "properties": {}}
        assert get_feature_id(feature, 0) == "my-id"

    def test_feature_with_numeric_id(self):
        """Test feature with numeric id."""
        feature = {"type": "Feature", "id": 123, "properties": {}}
        assert get_feature_id(feature, 0) == "123"

    def test_feature_with_property_id(self):
        """Test feature with id in properties."""
        feature = {"type": "Feature", "properties": {"id": "prop-id"}}
        assert get_feature_id(feature, 0) == "prop-id"

    def test_feature_with_fid(self):
        """Test feature with FID in properties."""
        feature = {"type": "Feature", "properties": {"FID": 456}}
        assert get_feature_id(feature, 0) == "456"

    def test_feature_with_name(self):
        """Test feature with name in properties."""
        feature = {"type": "Feature", "properties": {"name": "my-feature"}}
        assert get_feature_id(feature, 0) == "my-feature"

    def test_feature_without_id(self):
        """Test feature without any id field."""
        feature = {"type": "Feature", "properties": {"other": "value"}}
        assert get_feature_id(feature, 5) == "feature_5"

    def test_feature_empty_properties(self):
        """Test feature with empty properties."""
        feature = {"type": "Feature", "properties": {}}
        assert get_feature_id(feature, 3) == "feature_3"

    def test_feature_no_properties(self):
        """Test feature without properties key."""
        feature = {"type": "Feature"}
        assert get_feature_id(feature, 7) == "feature_7"


# Tests for compare_features

class TestCompareFeatures:
    """Tests for the compare_features function."""

    def test_identical_features(self):
        """Test comparing identical feature lists."""
        features = [
            {"type": "Feature", "id": "1", "geometry": {"type": "Point", "coordinates": [0, 0]}, "properties": {}},
        ]
        result = compare_features(features, features.copy())
        assert len(result["added"]) == 0
        assert len(result["removed"]) == 0
        assert len(result["modified"]) == 0
        assert len(result["unchanged"]) == 1

    def test_added_feature(self):
        """Test detecting an added feature."""
        base = []
        compare = [
            {"type": "Feature", "id": "1", "geometry": {"type": "Point", "coordinates": [0, 0]}, "properties": {}},
        ]
        result = compare_features(base, compare)
        assert len(result["added"]) == 1
        assert len(result["removed"]) == 0

    def test_removed_feature(self):
        """Test detecting a removed feature."""
        base = [
            {"type": "Feature", "id": "1", "geometry": {"type": "Point", "coordinates": [0, 0]}, "properties": {}},
        ]
        compare = []
        result = compare_features(base, compare)
        assert len(result["added"]) == 0
        assert len(result["removed"]) == 1

    def test_modified_feature(self):
        """Test detecting a modified feature."""
        base = [
            {"type": "Feature", "id": "1", "geometry": {"type": "Point", "coordinates": [0, 0]}, "properties": {"name": "old"}},
        ]
        compare = [
            {"type": "Feature", "id": "1", "geometry": {"type": "Point", "coordinates": [0, 0]}, "properties": {"name": "new"}},
        ]
        result = compare_features(base, compare)
        assert len(result["modified"]) == 1
        assert result["modified"][0]["id"] == "1"

    def test_complex_comparison(self):
        """Test a complex comparison with multiple changes."""
        base = [
            {"type": "Feature", "id": "1", "properties": {"v": "a"}},
            {"type": "Feature", "id": "2", "properties": {"v": "b"}},
            {"type": "Feature", "id": "3", "properties": {"v": "c"}},
        ]
        compare = [
            {"type": "Feature", "id": "1", "properties": {"v": "a"}},  # unchanged
            {"type": "Feature", "id": "2", "properties": {"v": "modified"}},  # modified
            {"type": "Feature", "id": "4", "properties": {"v": "d"}},  # added (3 removed)
        ]
        result = compare_features(base, compare)
        assert len(result["unchanged"]) == 1
        assert len(result["modified"]) == 1
        assert len(result["added"]) == 1
        assert len(result["removed"]) == 1


# Tests for compute_diff

class TestComputeDiff:
    """Tests for the compute_diff function."""

    def test_diff_identical_files(self, temp_dir, sample_feature_collection):
        """Test diff of identical files."""
        base_path = create_geojson_file(temp_dir, "base.geojson", sample_feature_collection)
        compare_path = create_geojson_file(temp_dir, "compare.geojson", sample_feature_collection)

        result = compute_diff(base_path, compare_path)

        assert result["has_changes"] is False
        assert result["summary"]["added_count"] == 0
        assert result["summary"]["removed_count"] == 0
        assert result["summary"]["modified_count"] == 0
        assert result["summary"]["unchanged_count"] == 2

    def test_diff_with_changes(self, temp_dir, sample_feature_collection, modified_feature_collection):
        """Test diff with actual changes."""
        base_path = create_geojson_file(temp_dir, "base.geojson", sample_feature_collection)
        compare_path = create_geojson_file(temp_dir, "compare.geojson", modified_feature_collection)

        result = compute_diff(base_path, compare_path)

        assert result["has_changes"] is True
        assert result["summary"]["added_count"] == 1  # point3
        assert result["summary"]["removed_count"] == 1  # point2
        assert result["summary"]["modified_count"] == 1  # point1

    def test_diff_type_mismatch(self, temp_dir):
        """Test diff with mismatched GeoJSON types."""
        base = {"type": "FeatureCollection", "features": []}
        compare = {"type": "Feature", "geometry": {"type": "Point", "coordinates": [0, 0]}, "properties": {}}

        base_path = create_geojson_file(temp_dir, "base.geojson", base)
        compare_path = create_geojson_file(temp_dir, "compare.geojson", compare)

        with pytest.raises(GeoDiffError, match="Type mismatch"):
            compute_diff(base_path, compare_path)

    def test_diff_single_features(self, temp_dir):
        """Test diff of single Feature (not FeatureCollection)."""
        base = {"type": "Feature", "id": "1", "geometry": {"type": "Point", "coordinates": [0, 0]}, "properties": {}}
        compare = {"type": "Feature", "id": "1", "geometry": {"type": "Point", "coordinates": [1, 1]}, "properties": {}}

        base_path = create_geojson_file(temp_dir, "base.geojson", base)
        compare_path = create_geojson_file(temp_dir, "compare.geojson", compare)

        result = compute_diff(base_path, compare_path)

        assert result["has_changes"] is True
        assert result["summary"]["modified_count"] == 1

    def test_diff_unsupported_type(self, temp_dir):
        """Test diff with unsupported GeoJSON type."""
        base = {"type": "Geometry", "coordinates": [0, 0]}
        compare = {"type": "Geometry", "coordinates": [0, 0]}

        base_path = create_geojson_file(temp_dir, "base.geojson", base)
        compare_path = create_geojson_file(temp_dir, "compare.geojson", compare)

        with pytest.raises(GeoDiffError, match="Unsupported GeoJSON type"):
            compute_diff(base_path, compare_path)


# Tests for format_output

class TestFormatOutput:
    """Tests for the format_output function."""

    @pytest.fixture
    def sample_diff_result(self):
        """Sample diff result for formatting tests."""
        return {
            "base_file": "base.geojson",
            "compare_file": "compare.geojson",
            "type": "FeatureCollection",
            "summary": {
                "added_count": 1,
                "removed_count": 1,
                "modified_count": 1,
                "unchanged_count": 1,
                "total_base": 3,
                "total_compare": 3,
            },
            "changes": {
                "added": [{"type": "Feature", "id": "new", "properties": {}}],
                "removed": [{"type": "Feature", "id": "old", "properties": {}}],
                "modified": [{"id": "mod", "base": {"properties": {"v": "a"}}, "compare": {"type": "Feature", "properties": {"v": "b"}}}],
                "unchanged": [{"type": "Feature", "id": "same", "properties": {}}],
            },
            "has_changes": True,
        }

    def test_format_summary(self, sample_diff_result):
        """Test summary output format."""
        output = format_output(sample_diff_result, "summary")

        assert "GeoDiff Summary" in output
        assert "Added:     1" in output
        assert "Removed:   1" in output
        assert "Modified:  1" in output
        assert "Unchanged: 1" in output

    def test_format_json(self, sample_diff_result):
        """Test JSON output format."""
        output = format_output(sample_diff_result, "json")

        parsed = json.loads(output)
        assert parsed["has_changes"] is True
        assert parsed["summary"]["added_count"] == 1

    def test_format_geojson(self, sample_diff_result):
        """Test GeoJSON output format."""
        output = format_output(sample_diff_result, "geojson")

        parsed = json.loads(output)
        assert parsed["type"] == "FeatureCollection"
        assert len(parsed["features"]) == 3  # added + removed + modified

        statuses = [f["properties"]["_geodiff_status"] for f in parsed["features"]]
        assert "added" in statuses
        assert "removed" in statuses
        assert "modified" in statuses

    def test_format_geojson_includes_summary(self, sample_diff_result):
        """Test that GeoJSON output includes summary in properties."""
        output = format_output(sample_diff_result, "geojson")

        parsed = json.loads(output)
        assert "geodiff_summary" in parsed["properties"]
        assert parsed["properties"]["geodiff_summary"]["added_count"] == 1

    def test_format_default_is_json(self, sample_diff_result):
        """Test that default format is JSON."""
        output = format_output(sample_diff_result, "unknown_format")
        parsed = json.loads(output)
        assert "has_changes" in parsed
