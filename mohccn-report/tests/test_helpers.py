"""
Unit tests for the small shared helper functions in run_completeness_reporting.py.
"""
import numpy as np
import pandas as pd
import pytest


@pytest.mark.parametrize("raw,expected", [
    ('t', True), ('f', False),
    ('T', True), ('F', False),
    ('true', True), ('false', False),
    ('True', True), ('False', False),
    ('TRUE', True), ('FALSE', False),
    ('1', True), ('0', False),
    (None, False), (np.nan, False),
    ('', False), ('garbage', False),
])
def test_parse_bool_flag(rcr_module, raw, expected):
    series = pd.Series([raw])
    result = rcr_module._parse_bool_flag(series)
    assert bool(result.iloc[0]) == expected


def test_record_pass_by_donor_true_false_and_absent(rcr_module):
    df = pd.DataFrame({
        'program_id_id': ['P1', 'P1', 'P1'],
        'submitter_donor_id': ['D1', 'D2', 'D2'],
    })
    total = pd.Series([2, 2, 2])
    complete = pd.Series([2, 2, 1])  # D1: 1 record, fully complete. D2: 2 records, one incomplete.
    result = rcr_module._record_pass_by_donor(df, total, complete, 'my_col')
    d1 = result.loc[result['submitter_donor_id'] == 'D1', 'my_col'].iloc[0]
    d2 = result.loc[result['submitter_donor_id'] == 'D2', 'my_col'].iloc[0]
    assert d1 == True
    assert d2 == False
    # D3 has no rows at all -> shouldn't appear in the result
    assert 'D3' not in set(result['submitter_donor_id'])


def test_treatment_base_pass_ongoing_exemption(rcr_module):
    df = pd.DataFrame({
        'program_id_id': ['P1', 'P1'],
        'submitter_treatment_id': ['T1', 'T2'],
        'treatment_type': ['Systemic therapy', 'Systemic therapy'],
        'is_primary_treatment': ['Yes', 'Yes'],
        'treatment_start_date': ['2020-01-01', '2020-01-01'],
        'treatment_end_date': [None, None],
        'treatment_intent': ['Curative', 'Curative'],
        'status_of_treatment': ['Treatment ongoing', 'Treatment completed'],
    })
    # exemption applies: ongoing treatment with no end_date should pass when NOT unconditional
    result_exempt = rcr_module._treatment_base_pass(df, require_end_date_unconditionally=False)
    t1_exempt = result_exempt.loc[result_exempt['submitter_treatment_id'] == 'T1', '_treatment_base_pass'].iloc[0]
    t2_exempt = result_exempt.loc[result_exempt['submitter_treatment_id'] == 'T2', '_treatment_base_pass'].iloc[0]
    assert t1_exempt == True  # ongoing, missing end_date -> exempt -> pass
    assert t2_exempt == False  # not ongoing, missing end_date -> fail

    # unconditional: end_date is required regardless of ongoing status (radiation/surgery rule)
    result_unconditional = rcr_module._treatment_base_pass(df, require_end_date_unconditionally=True)
    t1_unconditional = result_unconditional.loc[
        result_unconditional['submitter_treatment_id'] == 'T1', '_treatment_base_pass'].iloc[0]
    assert t1_unconditional == False  # ongoing no longer exempts end_date


def test_agg_field_score_by_donor_sums_across_rows(rcr_module):
    df = pd.DataFrame({
        'program_id_id': ['P1', 'P1', 'P1'],
        'submitter_donor_id': ['D1', 'D1', 'D2'],
    })
    total = pd.Series([5, 5, 5])
    complete = pd.Series([5, 4, 3])
    result = rcr_module._agg_field_score_by_donor(df, total, complete)
    d1 = result.loc[result['submitter_donor_id'] == 'D1']
    d2 = result.loc[result['submitter_donor_id'] == 'D2']
    assert d1.iloc[0]['_total'] == 10 and d1.iloc[0]['_complete'] == 9
    assert d2.iloc[0]['_total'] == 5 and d2.iloc[0]['_complete'] == 3
