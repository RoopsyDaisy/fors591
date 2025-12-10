"""
Unit tests for Monte Carlo Phase 3: FVS keyword integration.

Tests the new mortality_multiplier, enable_calibration, and fvs_random_seed
parameters in FVSSimulationConfig and their keyword generation.
"""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from fvs_tools import keyword_builder
from fvs_tools.config import FVSSimulationConfig


class TestConfigValidation:
    """Test validation of new Monte Carlo parameters in FVSSimulationConfig."""

    def test_mortality_multiplier_valid_values(self):
        """Test that valid mortality_multiplier values are accepted."""
        valid_values = [0.1, 0.5, 0.8, 1.0, 1.2, 2.0, 5.0]
        for value in valid_values:
            config = FVSSimulationConfig(
                name="test",
                mortality_multiplier=value,
            )
            assert config.mortality_multiplier == value

    def test_mortality_multiplier_invalid_zero(self):
        """Test that mortality_multiplier=0 raises ValueError."""
        with pytest.raises(ValueError, match="mortality_multiplier must be in range"):
            FVSSimulationConfig(
                name="test",
                mortality_multiplier=0.0,
            )

    def test_mortality_multiplier_invalid_negative(self):
        """Test that negative mortality_multiplier raises ValueError."""
        with pytest.raises(ValueError, match="mortality_multiplier must be in range"):
            FVSSimulationConfig(
                name="test",
                mortality_multiplier=-0.5,
            )

    def test_mortality_multiplier_invalid_too_large(self):
        """Test that mortality_multiplier > 5.0 raises ValueError."""
        with pytest.raises(ValueError, match="mortality_multiplier must be in range"):
            FVSSimulationConfig(
                name="test",
                mortality_multiplier=5.1,
            )

    def test_mortality_multiplier_none_is_valid(self):
        """Test that mortality_multiplier=None is valid (not applied)."""
        config = FVSSimulationConfig(name="test", mortality_multiplier=None)
        assert config.mortality_multiplier is None

    def test_enable_calibration_default_true(self):
        """Test that enable_calibration defaults to True."""
        config = FVSSimulationConfig(name="test")
        assert config.enable_calibration is True

    def test_enable_calibration_false(self):
        """Test that enable_calibration can be set to False."""
        config = FVSSimulationConfig(name="test", enable_calibration=False)
        assert config.enable_calibration is False

    def test_fvs_random_seed_valid_values(self):
        """Test that valid fvs_random_seed values are accepted."""
        valid_values = [1, 42, 12345, 99999]
        for value in valid_values:
            config = FVSSimulationConfig(
                name="test",
                fvs_random_seed=value,
            )
            assert config.fvs_random_seed == value

    def test_fvs_random_seed_invalid_zero(self):
        """Test that fvs_random_seed=0 raises ValueError."""
        with pytest.raises(ValueError, match="fvs_random_seed must be in range"):
            FVSSimulationConfig(
                name="test",
                fvs_random_seed=0,
            )

    def test_fvs_random_seed_invalid_negative(self):
        """Test that negative fvs_random_seed raises ValueError."""
        with pytest.raises(ValueError, match="fvs_random_seed must be in range"):
            FVSSimulationConfig(
                name="test",
                fvs_random_seed=-1,
            )

    def test_fvs_random_seed_invalid_too_large(self):
        """Test that fvs_random_seed > 99999 raises ValueError."""
        with pytest.raises(ValueError, match="fvs_random_seed must be in range"):
            FVSSimulationConfig(
                name="test",
                fvs_random_seed=100000,
            )

    def test_fvs_random_seed_none_is_valid(self):
        """Test that fvs_random_seed=None is valid (not applied)."""
        config = FVSSimulationConfig(name="test", fvs_random_seed=None)
        assert config.fvs_random_seed is None


class TestKeywordGeneration:
    """Test keyword generation for Monte Carlo parameters."""

    @pytest.fixture
    def mock_stand(self):
        """Create a mock stand Series for testing."""
        return pd.Series(
            {
                "STAND_ID": "TEST_01",
                "INV_YEAR": 2023,
                "FOREST": 16,
                "PV_CODE": 250,
                "ASPECT": 2.4,
                "SLOPE": 30.1,
                "ELEVFT": 5400.0,
                "BASAL_AREA_FACTOR": 10.0,
                "NUM_PLOTS": 1,
                "DG_TRANS": 1,
                "DG_MEASURE": 5,
                "HTG_TRANS": 1,
                "HTG_MEASURE": 5,
                "MORT_MEASURE": 5,
                "AGE": 0.0,
                "SITE_SPECIES": 0,
                "SITE_INDEX": 0,
            }
        )

    def test_fixmort_keyword_present(self, mock_stand):
        """Test that FixMort keyword is generated when mortality_multiplier is set."""
        config = FVSSimulationConfig(
            name="test",
            mortality_multiplier=0.9,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            keyfile = Path(tmpdir) / "test.key"
            keyword_builder.build_keyword_file(
                stand=mock_stand,
                tree_filename="FVS_Data.db",
                config=config,
                filepath=keyfile,
                use_database=True,
            )

            content = keyfile.read_text()
            assert "FixMort" in content
            assert "0.90" in content  # Multiplier formatted to 2 decimal places
            assert "All" in content  # Apply to all species

    def test_fixmort_keyword_absent_when_none(self, mock_stand):
        """Test that FixMort keyword is NOT generated when mortality_multiplier is None."""
        config = FVSSimulationConfig(name="test", mortality_multiplier=None)

        with tempfile.TemporaryDirectory() as tmpdir:
            keyfile = Path(tmpdir) / "test.key"
            keyword_builder.build_keyword_file(
                stand=mock_stand,
                tree_filename="FVS_Data.db",
                config=config,
                filepath=keyfile,
                use_database=True,
            )

            content = keyfile.read_text()
            assert "FixMort" not in content

    def test_nocalib_keyword_present(self, mock_stand):
        """Test that NoCaLib keyword is generated when enable_calibration=False."""
        config = FVSSimulationConfig(
            name="test",
            enable_calibration=False,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            keyfile = Path(tmpdir) / "test.key"
            keyword_builder.build_keyword_file(
                stand=mock_stand,
                tree_filename="FVS_Data.db",
                config=config,
                filepath=keyfile,
                use_database=True,
            )

            content = keyfile.read_text()
            assert "NoCaLib" in content

    def test_nocalib_keyword_absent_when_true(self, mock_stand):
        """Test that NoCaLib keyword is NOT generated when enable_calibration=True."""
        config = FVSSimulationConfig(name="test", enable_calibration=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            keyfile = Path(tmpdir) / "test.key"
            keyword_builder.build_keyword_file(
                stand=mock_stand,
                tree_filename="FVS_Data.db",
                config=config,
                filepath=keyfile,
                use_database=True,
            )

            content = keyfile.read_text()
            assert "NoCaLib" not in content

    def test_rannseed_keyword_present(self, mock_stand):
        """Test that RanNSeed keyword is generated when fvs_random_seed is set."""
        config = FVSSimulationConfig(
            name="test",
            fvs_random_seed=12345,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            keyfile = Path(tmpdir) / "test.key"
            keyword_builder.build_keyword_file(
                stand=mock_stand,
                tree_filename="FVS_Data.db",
                config=config,
                filepath=keyfile,
                use_database=True,
            )

            content = keyfile.read_text()
            assert "RanNSeed" in content
            assert "12345" in content

    def test_rannseed_keyword_absent_when_none(self, mock_stand):
        """Test that RanNSeed keyword is NOT generated when fvs_random_seed is None."""
        config = FVSSimulationConfig(name="test", fvs_random_seed=None)

        with tempfile.TemporaryDirectory() as tmpdir:
            keyfile = Path(tmpdir) / "test.key"
            keyword_builder.build_keyword_file(
                stand=mock_stand,
                tree_filename="FVS_Data.db",
                config=config,
                filepath=keyfile,
                use_database=True,
            )

            content = keyfile.read_text()
            assert "RanNSeed" not in content

    def test_all_three_keywords_together(self, mock_stand):
        """Test that all three MC keywords can be generated together."""
        config = FVSSimulationConfig(
            name="test",
            mortality_multiplier=1.2,
            enable_calibration=False,
            fvs_random_seed=42,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            keyfile = Path(tmpdir) / "test.key"
            keyword_builder.build_keyword_file(
                stand=mock_stand,
                tree_filename="FVS_Data.db",
                config=config,
                filepath=keyfile,
                use_database=True,
            )

            content = keyfile.read_text()
            assert "RanNSeed" in content
            assert "42" in content
            assert "NoCaLib" in content
            assert "FixMort" in content
            assert "1.20" in content

    def test_keyword_order(self, mock_stand):
        """Test that keywords appear in correct order: RanNSeed, NoCaLib, FixMort."""
        config = FVSSimulationConfig(
            name="test",
            mortality_multiplier=1.0,
            enable_calibration=False,
            fvs_random_seed=99,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            keyfile = Path(tmpdir) / "test.key"
            keyword_builder.build_keyword_file(
                stand=mock_stand,
                tree_filename="FVS_Data.db",
                config=config,
                filepath=keyfile,
                use_database=True,
            )

            content = keyfile.read_text()
            rannseed_pos = content.find("RanNSeed")
            nocalib_pos = content.find("NoCaLib")
            fixmort_pos = content.find("FixMort")

            # All should be present
            assert rannseed_pos != -1
            assert nocalib_pos != -1
            assert fixmort_pos != -1

            # RanNSeed should come before NoCaLib and FixMort
            assert rannseed_pos < nocalib_pos
            assert rannseed_pos < fixmort_pos
            # NoCaLib should come before FixMort
            assert nocalib_pos < fixmort_pos

    def test_fixmort_format_precision(self, mock_stand):
        """Test that FixMort multiplier is formatted to exactly 2 decimal places."""
        test_cases = [
            (0.9, "0.90"),
            (1.0, "1.00"),
            (1.234, "1.23"),  # Should round/truncate
            (2.0, "2.00"),
        ]

        for multiplier, expected_str in test_cases:
            config = FVSSimulationConfig(
                name="test",
                mortality_multiplier=multiplier,
            )

            with tempfile.TemporaryDirectory() as tmpdir:
                keyfile = Path(tmpdir) / "test.key"
                keyword_builder.build_keyword_file(
                    stand=mock_stand,
                    tree_filename="FVS_Data.db",
                    config=config,
                    filepath=keyfile,
                    use_database=True,
                )

                content = keyfile.read_text()
                # Find the FixMort line
                for line in content.split("\n"):
                    if "FixMort" in line and "Title" not in line:
                        assert expected_str in line
                        break
