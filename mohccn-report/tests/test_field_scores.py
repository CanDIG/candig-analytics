"""
Tests for get_minimal_field_score() and get_fullsome_field_score(), including the row-level
partial-credit behaviour that fixed the "fullsome shows more complete donors than minimal" bug
(a single missing field on 1 of a donor's several sample rows should cost a small fraction of that
field's weight, not the whole field).
"""
import pandas as pd
import pytest


MINIMAL_FIELDS = [
    'gender', 'sex_at_birth', 'date_of_birth', 'date_resolution', 'date_of_diagnosis',
    'cancer_type_code', 'primary_site', 'basis_of_diagnosis', 'specimen_collection_date',
    'specimen_anatomic_location', 'specimen_tissue_source', 'tumour_normal_designation',
    'specimen_type', 'sample_type',
]


def _donor_with_n_samples(n_samples, missing_on_row=None, missing_field='specimen_anatomic_location'):
    """A single donor with n_samples rows, all fields present except optionally one field on one row."""
    rows = []
    for i in range(n_samples):
        row = {
            'program_id_id': 'PROG1', 'submitter_donor_id': 'D1',
            'gender': 'Man', 'sex_at_birth': 'Male', 'date_of_birth': '1970', 'date_resolution': 'Year',
            'date_of_diagnosis': '2020', 'cancer_type_code': 'C50', 'primary_site': 'Breast',
            'basis_of_diagnosis': 'Histology', 'specimen_collection_date': '2020-01-01',
            'specimen_anatomic_location': 'Left breast', 'specimen_tissue_source': 'Blood',
            'tumour_normal_designation': 'Tumour', 'specimen_type': 'Fresh', 'sample_type': 'Tumour~Total DNA',
        }
        if missing_on_row is not None and i == missing_on_row:
            row[missing_field] = None
        rows.append(row)
    return pd.DataFrame(rows)


def test_minimal_field_score_full_marks_when_all_present(rcr_module):
    df = _donor_with_n_samples(3)
    result = rcr_module.get_minimal_field_score(df)
    assert result.loc[0, 'minimal_required_fields_pct'] == 100.0
    assert result.loc[0, 'minimal_required_fields_total'] == 14 * 3


def test_minimal_field_score_gives_partial_credit_not_all_or_nothing(rcr_module):
    """
    A donor with 10 samples missing one field on only 1 of them should lose a small fraction of
    that field's weight (1/(14*10) of the total), NOT the whole field's worth (1/14) - this is the
    behaviour that was fixed after finding donors with a higher fullsome % than minimal % on the
    same data (see get_minimal_field_score's docstring).
    """
    df = _donor_with_n_samples(10, missing_on_row=0)
    result = rcr_module.get_minimal_field_score(df)
    pct = result.loc[0, 'minimal_required_fields_pct']
    # old (all-rows-required) scoring would have scored this 13/14 = 92.9%; row-level partial
    # credit should score it 139/140 = 99.3%
    assert pct == pytest.approx(99.3, abs=0.05)
    assert pct > 95.0, "a single isolated null on 1 of 10 rows should barely move the score"


def test_minimal_field_score_missing_on_every_row_still_costs_full_field(rcr_module):
    df = _donor_with_n_samples(4, missing_on_row=None)
    for i in range(4):
        df.loc[i, 'specimen_anatomic_location'] = None
    result = rcr_module.get_minimal_field_score(df)
    expected_pct = round(100 * 13 / 14, 1)
    assert result.loc[0, 'minimal_required_fields_pct'] == expected_pct


def test_fullsome_field_score_gives_valid_percentages(rcr_module, dfs, specimen_linked_treatment_ids):
    result = rcr_module.get_fullsome_field_score(dfs, specimen_linked_treatment_ids)
    non_null_pct = result['fullsome_required_fields_pct'].dropna()
    assert len(non_null_pct) > 0
    assert (non_null_pct >= 0).all() and (non_null_pct <= 100).all()
    # every donor should have at least the always-required donor-object fields counted
    assert (result['fullsome_required_fields_total'] >= 5).all()


def test_fullsome_field_score_known_incomplete_donor(rcr_module, dfs, specimen_linked_treatment_ids):
    """D3 (deceased, missing cause_of_death) should show up as fullsome-incomplete (pct < 100)."""
    result = rcr_module.get_fullsome_field_score(dfs, specimen_linked_treatment_ids)
    row = result.loc[result['submitter_donor_id'] == 'D3']
    assert not row.empty
    assert row.iloc[0]['fullsome_required_fields_pct'] < 100.0
