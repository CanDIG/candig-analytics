"""
Tests for get_donor_pct_distribution()'s half-open bucket boundaries. These buckets were
originally inclusive-inclusive (e.g. 51-60 and 61-70), which left fractional percentages like
60.6% uncounted in any bucket - fixed by switching to half-open (low, high] bounds. These tests
guard against that regression.
"""
import numpy as np
import pandas as pd
import pytest


def _dist_for_pcts(rcr_module, pcts):
    df = pd.DataFrame({'program_id': ['P1'] * len(pcts), 'pct': pcts})
    return rcr_module.get_donor_pct_distribution(df, 'pct', 'x', program_col='program_id')


@pytest.mark.parametrize("pct,expected_bucket", [
    (100.0, 'x_91_100_pct_complete'),
    (91.0, 'x_91_100_pct_complete'),
    (90.1, 'x_91_100_pct_complete'),
    (90.0, 'x_81_90_pct_complete'),
    (81.0, 'x_81_90_pct_complete'),
    (80.1, 'x_81_90_pct_complete'),
    (80.0, 'x_71_80_pct_complete'),
    (71.0, 'x_71_80_pct_complete'),
    (70.1, 'x_71_80_pct_complete'),
    (70.0, 'x_61_70_pct_complete'),
    (61.0, 'x_61_70_pct_complete'),
    (60.6, 'x_61_70_pct_complete'),  # the exact value that exposed the original gap bug
    (60.1, 'x_61_70_pct_complete'),
    (60.0, 'x_51_60_pct_complete'),
    (51.0, 'x_51_60_pct_complete'),
    (50.1, 'x_51_60_pct_complete'),
    (50.0, 'x_under_50_pct_complete'),
    (0.0, 'x_under_50_pct_complete'),
])
def test_bucket_boundaries(rcr_module, pct, expected_bucket):
    dist = _dist_for_pcts(rcr_module, [pct])
    bucket_cols = ['x_91_100_pct_complete', 'x_81_90_pct_complete', 'x_71_80_pct_complete',
                   'x_61_70_pct_complete', 'x_51_60_pct_complete', 'x_under_50_pct_complete']
    for col in bucket_cols:
        expected_count = 1 if col == expected_bucket else 0
        assert dist.loc[0, col] == expected_count, f"pct={pct} landed in the wrong bucket(s): {dist.iloc[0].to_dict()}"


def test_every_value_lands_in_exactly_one_bucket(rcr_module):
    """Exhaustive sweep from 0.0 to 100.0 in 0.1 increments - every value must land in exactly one
    bucket, with no gaps and no double-counting."""
    bucket_cols = ['x_91_100_pct_complete', 'x_81_90_pct_complete', 'x_71_80_pct_complete',
                   'x_61_70_pct_complete', 'x_51_60_pct_complete', 'x_under_50_pct_complete']
    pcts = [round(p, 1) for p in np.arange(0.0, 100.1, 0.1)]
    import run_completeness_reporting as rcr

    for pct in pcts:
        dist = _dist_for_pcts(rcr, [pct])
        total_bucketed = sum(dist.loc[0, col] for col in bucket_cols)
        assert total_bucketed == 1, f"pct={pct} landed in {total_bucketed} buckets, expected exactly 1"


def test_null_pct_excluded_from_all_buckets_and_average(rcr_module):
    df = pd.DataFrame({'program_id': ['P1', 'P1', 'P1'], 'pct': [100.0, None, 50.0]})
    dist = rcr_module.get_donor_pct_distribution(df, 'pct', 'x', program_col='program_id')
    bucket_cols = ['x_91_100_pct_complete', 'x_81_90_pct_complete', 'x_71_80_pct_complete',
                   'x_61_70_pct_complete', 'x_51_60_pct_complete', 'x_under_50_pct_complete']
    assert sum(dist.loc[0, col] for col in bucket_cols) == 2  # only the two non-null donors
    assert dist.loc[0, 'x_avg_pct_complete'] == 75.0  # average of 100 and 50, excluding the null
