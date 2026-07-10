import sys
from pathlib import Path

import pytest

# Make both the tests/ directory (for synthetic_data / synthetic_data_builders) and the repo root
# (for run_completeness_reporting) importable regardless of where pytest is invoked from.
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

import run_completeness_reporting as rcr  # noqa: E402
from synthetic_data import DONORS  # noqa: E402
from synthetic_data_builders import build_all_dataframes  # noqa: E402


@pytest.fixture(scope="session")
def rcr_module():
    """The module under test, exposed as a fixture so test files don't each need their own import."""
    return rcr


@pytest.fixture(scope="session")
def dfs():
    """
    The same dict shape as rcr.load_all_category_dataframes(), built once from the synthetic
    22-donor DONORS master dict (tests/synthetic_data.py) instead of real sql_outputs/*.csv files.
    Each donor targets one or two specific completeness rules/edge cases - see the comment above
    each donor() call in synthetic_data.py for what it's testing and why.
    """
    return build_all_dataframes(DONORS)


@pytest.fixture(scope="session")
def specimen_linked_treatment_ids(dfs, rcr_module):
    return rcr_module.get_specimen_linked_treatment_ids(dfs['specimen'])


def _lookup(result_df, donor_id, col):
    """
    Look up a single donor's value in a get_*_completeness() result dataframe. Returns None if the
    donor is absent (meaning that donor has zero records of this type - the get_*_completeness()
    functions represent this via row-absence rather than an explicit False, so callers can
    distinguish "definitely incomplete" from "no applicable records" via `~col.eq(False)`).
    """
    row = result_df.loc[result_df['submitter_donor_id'] == donor_id]
    if row.empty:
        return None
    value = row.iloc[0][col]
    return None if pd_isna(value) else bool(value)


def pd_isna(value):
    import pandas as pd
    return pd.isna(value)


@pytest.fixture(scope="session")
def lookup():
    return _lookup
