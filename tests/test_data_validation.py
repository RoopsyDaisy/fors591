"""
Tests for stand/tree data validation functions.
"""

import pandas as pd

from fvs_tools.data_loader import (
    get_carbon_plot_ids,
    print_validation_report,
    validate_stands,
)


class TestGetCarbonPlotIds:
    """Tests for get_carbon_plot_ids function."""

    def test_filters_carbon_prefix(self):
        """Only returns plots with CARB_ prefix."""
        stands = pd.DataFrame(
            {
                "STAND_ID": ["CARB_1", "CARB_2", "LEF_3", "OTHER_4"],
                "PlotID": [1, 2, 3, 4],
            }
        )
        result = get_carbon_plot_ids(stands)
        assert result == [1, 2]

    def test_returns_sorted_list(self):
        """Returns plot IDs in sorted order."""
        stands = pd.DataFrame(
            {
                "STAND_ID": ["CARB_99", "CARB_2", "CARB_50"],
                "PlotID": [99, 2, 50],
            }
        )
        result = get_carbon_plot_ids(stands)
        assert result == [2, 50, 99]

    def test_empty_if_no_carbon_plots(self):
        """Returns empty list if no carbon plots."""
        stands = pd.DataFrame(
            {
                "STAND_ID": ["LEF_1", "LEF_2"],
                "PlotID": [1, 2],
            }
        )
        result = get_carbon_plot_ids(stands)
        assert result == []

    def test_unique_plot_ids(self):
        """Returns unique plot IDs even if duplicates exist."""
        stands = pd.DataFrame(
            {
                "STAND_ID": ["CARB_1", "CARB_1_v2"],
                "PlotID": [1, 1],
            }
        )
        result = get_carbon_plot_ids(stands)
        assert result == [1]


class TestValidateStands:
    """Tests for validate_stands function."""

    def test_excludes_stands_with_no_trees(self):
        """Stands with zero trees are excluded."""
        stands = pd.DataFrame(
            {
                "STAND_ID": ["A", "B", "C"],
                "PlotID": [1, 2, 3],
            }
        )
        trees = pd.DataFrame(
            {
                "STAND_ID": ["A", "A", "C"],
                "TREE_ID": [1, 2, 3],
            }
        )

        valid_stands, valid_trees, report = validate_stands(stands, trees)

        assert len(valid_stands) == 2
        assert "B" not in valid_stands["STAND_ID"].values
        assert report["total_stands"] == 3
        assert report["valid_stands"] == 2
        assert len(report["excluded_stands"]) == 1
        assert report["excluded_stands"][0]["stand_id"] == "B"

    def test_min_trees_parameter(self):
        """Respects min_trees threshold."""
        stands = pd.DataFrame(
            {
                "STAND_ID": ["A", "B", "C"],
                "PlotID": [1, 2, 3],
            }
        )
        trees = pd.DataFrame(
            {
                "STAND_ID": ["A", "A", "A", "B", "B", "C"],
                "TREE_ID": [1, 2, 3, 4, 5, 6],
            }
        )

        # Default min_trees=1: all valid
        _, _, report = validate_stands(stands, trees, min_trees=1)
        assert report["valid_stands"] == 3

        # min_trees=3: only A is valid
        valid_stands, _, report = validate_stands(stands, trees, min_trees=3)
        assert report["valid_stands"] == 1
        assert valid_stands["STAND_ID"].iloc[0] == "A"

    def test_all_stands_valid(self):
        """When all stands have trees, all are valid."""
        stands = pd.DataFrame(
            {
                "STAND_ID": ["A", "B"],
                "PlotID": [1, 2],
            }
        )
        trees = pd.DataFrame(
            {
                "STAND_ID": ["A", "B"],
                "TREE_ID": [1, 2],
            }
        )

        valid_stands, valid_trees, report = validate_stands(stands, trees)

        assert len(valid_stands) == 2
        assert len(valid_trees) == 2
        assert report["excluded_stands"] == []

    def test_all_stands_invalid(self):
        """When no stands have trees, all are excluded."""
        stands = pd.DataFrame(
            {
                "STAND_ID": ["A", "B"],
                "PlotID": [1, 2],
            }
        )
        trees = pd.DataFrame(
            {
                "STAND_ID": [],
                "TREE_ID": [],
            }
        )

        valid_stands, valid_trees, report = validate_stands(stands, trees)

        assert len(valid_stands) == 0
        assert len(valid_trees) == 0
        assert len(report["excluded_stands"]) == 2

    def test_report_includes_tree_counts(self):
        """Report includes tree counts per stand."""
        stands = pd.DataFrame(
            {
                "STAND_ID": ["A", "B"],
                "PlotID": [1, 2],
            }
        )
        trees = pd.DataFrame(
            {
                "STAND_ID": ["A", "A", "A", "B"],
                "TREE_ID": [1, 2, 3, 4],
            }
        )

        _, _, report = validate_stands(stands, trees)

        assert report["tree_counts"]["A"] == 3
        assert report["tree_counts"]["B"] == 1

    def test_trees_filtered_correctly(self):
        """Valid trees correspond to valid stands only."""
        stands = pd.DataFrame(
            {
                "STAND_ID": ["A", "B"],
                "PlotID": [1, 2],
            }
        )
        trees = pd.DataFrame(
            {
                "STAND_ID": ["A", "A"],
                "TREE_ID": [1, 2],
            }
        )

        _, valid_trees, _ = validate_stands(stands, trees)

        # Only A's trees should be in valid_trees
        assert len(valid_trees) == 2
        assert all(valid_trees["STAND_ID"] == "A")


class TestPrintValidationReport:
    """Tests for print_validation_report function."""

    def test_prints_without_error(self, capsys):
        """Function prints report without error."""
        report = {
            "total_stands": 10,
            "valid_stands": 8,
            "excluded_stands": [
                {"stand_id": "A", "plot_id": 1, "reason": "no trees"},
                {"stand_id": "B", "plot_id": 2, "reason": "no trees"},
            ],
            "tree_counts": {"C": 5, "D": 3},
        }

        print_validation_report(report)

        captured = capsys.readouterr()
        assert "Total stands:    10" in captured.out
        assert "Valid stands:    8" in captured.out
        assert "Excluded stands: 2" in captured.out
        assert "A (plot 1)" in captured.out

    def test_no_excluded_stands(self, capsys):
        """Handles case with no excluded stands."""
        report = {
            "total_stands": 5,
            "valid_stands": 5,
            "excluded_stands": [],
            "tree_counts": {},
        }

        print_validation_report(report)

        captured = capsys.readouterr()
        assert "Excluded stands: 0" in captured.out
        assert "no trees" not in captured.out


class TestIntegrationWithRealData:
    """Integration tests with actual Lubrecht data."""

    def test_carbon_plots_excludes_lef(self):
        """Carbon plots don't include LEF_ stands."""
        from fvs_tools import load_stands

        stands = load_stands()
        carbon_plots = get_carbon_plot_ids(stands)

        # Get stand IDs for carbon plots
        carbon_stands = stands[stands["PlotID"].isin(carbon_plots)]
        stand_ids = carbon_stands["STAND_ID"].tolist()

        # None should start with LEF_
        lef_stands = [s for s in stand_ids if s.startswith("LEF_")]
        assert lef_stands == [], f"Found LEF stands: {lef_stands}"

    def test_validation_excludes_empty_carbon_plots(self):
        """Validation excludes CARB_157 and CARB_289 (known empty)."""
        from fvs_tools import load_stands, load_trees, filter_by_plot_ids

        stands = load_stands()
        trees = load_trees()

        carbon_plots = get_carbon_plot_ids(stands)
        carbon_stands, carbon_trees = filter_by_plot_ids(stands, trees, carbon_plots)

        _, _, report = validate_stands(carbon_stands, carbon_trees)

        excluded_ids = [e["stand_id"] for e in report["excluded_stands"]]
        assert "CARB_157" in excluded_ids
        assert "CARB_289" in excluded_ids
        assert len(excluded_ids) == 2  # Only these two

    def test_full_validation_pipeline(self):
        """Full pipeline produces usable data."""
        from fvs_tools import load_stands, load_trees, filter_by_plot_ids

        stands = load_stands()
        trees = load_trees()

        # Step 1: Get carbon plots
        carbon_plots = get_carbon_plot_ids(stands)
        assert len(carbon_plots) == 270

        # Step 2: Filter
        carbon_stands, carbon_trees = filter_by_plot_ids(stands, trees, carbon_plots)
        assert len(carbon_stands) == 270

        # Step 3: Validate
        valid_stands, valid_trees, report = validate_stands(carbon_stands, carbon_trees)
        assert len(valid_stands) == 268
        assert report["valid_stands"] == 268
        assert len(report["excluded_stands"]) == 2
