"""
Per-category completeness tests, driven by the synthetic 22-donor dataset in synthetic_data.py.
Each donor was designed to exercise one specific business rule or edge case - see the comment
above each donor() call there for the intent. Expected values in this file are transcribed
directly from those comments.

Expected value convention: True/False mean "definitely complete/incomplete"; None means the donor
has zero records of that type, so it's expected to be ABSENT from the result dataframe (matching
the row-absence-means-NaN convention used throughout run_completeness_reporting.py, which lets
tier_a/b_full_clinical_complete's `~col.eq(False)` treat "no applicable records" as non-blocking).
"""
import pytest


def test_donor_obj_complete(rcr_module, dfs, lookup):
    cases = [
        ('D1', True),   # not deceased, all base fields present
        ('D2', True),   # deceased, cause_of_death + date_of_death both present
        ('D3', False),  # deceased, missing cause_of_death
    ]
    result = rcr_module.get_donors_completeness(dfs['donor'])
    for donor_id, expected in cases:
        assert lookup(result, donor_id, 'donor_obj_complete') == expected, donor_id


def test_pd_donor_complete(rcr_module, dfs, lookup):
    cases = [
        ('D1', True),   # full AJCC clinical staging, all T/N/M present
        ('D2', True),   # full AJCC pathological staging, all T/N/M present
        ('D4', False),  # clinical AJCC staging present but missing clinical_n_category
        ('D5', False),  # no staging system reported at all
    ]
    result = rcr_module.get_primary_diagnosis_completeness(dfs['primary_diagnosis'])
    for donor_id, expected in cases:
        assert lookup(result, donor_id, 'pd_donor_complete') == expected, donor_id


def test_specimen_donor_complete(rcr_module, dfs):
    cases = [
        ('D1', True),   # tumour specimen, all 7 histology fields present, matched samples all ok
        ('D2', True),   # normal specimen, no histology fields required
        ('D6', False),  # tumour specimen missing histology fields
        ('D21', False),  # specimen with no matched sample registration at all
        ('D22', False),  # specimen's matched sample is missing specimen_type
    ]
    result = rcr_module.get_specimens_completeness(dfs['specimen'], dfs['sample'])
    for donor_id, expected in cases:
        row = result.loc[result['submitter_donor_id'] == donor_id]
        assert not row.empty, f"{donor_id} unexpectedly absent from specimen completeness result"
        assert bool(row.iloc[0]['specimen_donor_complete']) == expected, donor_id


def test_sample_donor_complete(rcr_module, dfs, lookup):
    cases = [
        ('D1', True),  # 3 samples, all 4 registration fields present on each
        ('D22', False),  # sample missing specimen_type
    ]
    result = rcr_module.get_samples_completeness(dfs['sample'])
    for donor_id, expected in cases:
        assert lookup(result, donor_id, 'sample_donor_complete') == expected, donor_id


def test_donor_followups_complete(rcr_module, dfs, lookup):
    cases = [
        ('D7', True),   # relapse with all conditional fields present
        ('D8', False),  # relapse missing anatomic site, non-biochemical -> not exempt
        ('D9', True),   # Biochemical progression missing anatomic site -> exempt
        ('D1', True),   # stable status, no relapse/progression fields required
    ]
    result = rcr_module.get_followups_completeness(dfs['followup'])
    for donor_id, expected in cases:
        assert lookup(result, donor_id, 'donor_followups_complete') == expected, donor_id


def test_donor_comorbidities_complete(rcr_module, dfs, lookup):
    cases = [
        ('D1', True),    # both fields present
        ('D10', False),  # missing prior_malignancy
    ]
    result = rcr_module.get_comorbidity_completeness(dfs['comorbidity'])
    for donor_id, expected in cases:
        assert lookup(result, donor_id, 'donor_comorbidities_complete') == expected, donor_id


def test_treatment_donor_complete(rcr_module, dfs, lookup):
    cases = [
        ('D1', True),    # single complete Surgery treatment
        ('D11', True),   # two treatments, base fields complete on both
        ('D12', True),   # ongoing systemic therapy, base end_date exempt
        ('D20', False),  # base treatment_intent is missing -> base record itself is incomplete
    ]
    result = rcr_module.get_treatments_completeness(dfs['treatments'])
    for donor_id, expected in cases:
        assert lookup(result, donor_id, 'treatment_donor_complete') == expected, donor_id


def test_radiation_donor_complete(rcr_module, dfs, lookup):
    cases = [
        ('D11', False),  # radiation subtype missing anatomical_site_irradiated
        ('D18', False),  # radiation requires treatment_end_date UNCONDITIONALLY, even when ongoing
    ]
    result = rcr_module.get_radiations_completeness(dfs['radiation'], dfs['treatments'])
    for donor_id, expected in cases:
        assert lookup(result, donor_id, 'radiation_donor_complete') == expected, donor_id
    # D1 has no radiation records at all -> absent from the result, not False
    assert lookup(result, 'D1', 'radiation_donor_complete') is None


def test_surgery_donor_complete(rcr_module, dfs, specimen_linked_treatment_ids, lookup):
    cases = [
        ('D1', True),    # surgery_site/location present directly
        ('D11', True),   # surgery_site/location absent but exempt via linked specimen record
        ('D20', False),  # base treatment_intent missing -> surgery incomplete regardless of subtype fields
    ]
    result = rcr_module.get_surgeries_completeness(dfs['surgery'], specimen_linked_treatment_ids, dfs['treatments'])
    for donor_id, expected in cases:
        assert lookup(result, donor_id, 'surgery_donor_complete') == expected, donor_id


def test_sys_therapy_donor_complete(rcr_module, dfs, lookup):
    cases = [
        ('D12', True),   # ongoing, dose reported WITH units -> complete
        ('D13', False),  # not ongoing, missing end_date, dose reported WITHOUT units -> incomplete
        ('D19', True),   # ongoing at both base-treatment and sys-therapy level, no dose reported -> complete
    ]
    result = rcr_module.get_sys_therapy_completeness(dfs['sys_therapy'], dfs['treatments'])
    for donor_id, expected in cases:
        assert lookup(result, donor_id, 'sys_therapy_donor_complete') == expected, donor_id


def test_minimal_tier_boundaries(rcr_module, dfs):
    """D14/D15/D16 each have every clinical field minimally complete on every sample; they differ
    only in which samples are present, to test the Tier A / Tier B / neither boundary."""
    result = rcr_module.get_minimal_completeness(dfs['minimal'])
    tiers = result[['submitter_donor_id', 'tier_a_min_clinical_complete',
                    'tier_b_min_clinical_complete']].drop_duplicates()

    def tier_of(donor_id):
        row = tiers.loc[tiers['submitter_donor_id'] == donor_id]
        if row.empty:
            return 'absent'
        r = row.iloc[0]
        if r['tier_a_min_clinical_complete']:
            return 'A'
        if r['tier_b_min_clinical_complete']:
            return 'B'
        return 'neither'

    assert tier_of('D14') == 'A'        # normal DNA + tumour DNA + tumour RNA
    assert tier_of('D15') == 'B'        # normal DNA + tumour DNA, no tumour RNA
    assert tier_of('D16') == 'neither'  # tumour DNA only, no normal


def test_minimal_completeness_only_considers_passing_samples(rcr_module, dfs):
    """
    D17 has two samples: one tied to a primary diagnosis missing primary_site (fails minimal), one
    fully complete tumour-DNA-only sample (passes). Only the passing sample should count towards
    D17's tier - a single tumour-DNA sample is neither Tier A nor Tier B, even though the OTHER
    (failing) sample would have contributed a normal-DNA count if it were wrongly included.
    """
    result = rcr_module.get_minimal_completeness(dfs['minimal'])
    tiers = result[['submitter_donor_id', 'tier_a_min_clinical_complete',
                    'tier_b_min_clinical_complete']].drop_duplicates()
    row = tiers.loc[tiers['submitter_donor_id'] == 'D17']
    assert not row.empty, "D17 should still appear (it has one passing sample)"
    assert row.iloc[0]['tier_a_min_clinical_complete'] == False
    assert row.iloc[0]['tier_b_min_clinical_complete'] == False
