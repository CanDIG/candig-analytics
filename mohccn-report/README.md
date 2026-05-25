# MOHCCN report

Script that grabs data from the clinical database and CanDIG APIs in order to create a completeness report for all programs at a node

## How to run

1. `ssh` into the VM that is running your CanDIG node. The user should be able to access the `postgres-db` docker container
2. Clone this repo and cd into the mohccn-report directory
``` bash
git clone https://github.com/CanDIG/candig-analytics.git
cd mohccn-report
```
3. Create a virtual environment or conda environment and install requirements

```bash
conda create -n mohccn_report_env python=3.12
conda activate mohccn_report_env
pip install -r requirements.txt
```

4. Run the `run_completeness_reporting.py` script
```bash
python run_completeness_reporting.py --help
usage: run_completeness_reporting.py [-h] [--psql-user PSQL_USER] --token TOKEN --url URL --node NODE [--no-sql] [--dont-delete-sql-outputs]

options:
  -h, --help            show this help message and exit
  --psql-user PSQL_USER
                        Username of the postgres admin user, DEFAULT=admin
  --token TOKEN         site admin token for the candig deployment you are retrieving data from.
  --url URL             URL of the candig deployment you are retrieving data from
  --node NODE           name of the node running the report, e.g. UHN
  --no-sql              don't run the sql reports again, mainly used for debugging
  --dont-delete-sql-outputs
                        don't delete the sql outputs, mainly used for debugging
```

You will need to provide:
- `--token`: a site admin token from you candig node
- `--url`: the url of you candig deployment
- `--node`: name of your node

4. Share the output file `per_program_completeness_report.csv`

## MOHCCN Completeness Criteria

**Tier A complete cases:**

- Minimum clinical completeness with at least 1 DNA normal, 1 DNA tumour, 1 RNA tumour sample registration
- At least one VCF that contains samples from the DNA normal and DNA tumour
- An Expression matrix linked to the RNA tumour sample

**Tier B complete cases:**

- Won't contain any cases that already meet the Tier A criteria above
- Minimum clinical completeness with 1 DNA normal and 1 DNA tumour sample
- VCF that contains variants from the DNA normal and DNA tumour samples

**Tier A Fullsome complete:**

- all required and conditionally required fields with valid values with at least 1 DNA normal, 1 DNA tumour, 1 RNA tumour sample registration
- At least one VCF that contains samples from the DNA normal and DNA tumour
- An Expression matrix linked to the RNA tumour sample

**Tier B Fullsome complete:**

- all required and conditionally required fields with valid values with at least 1 DNA normal, 1 DNA tumour
- At least one VCF that contains samples from the DNA normal and DNA tumour

**Minimal clinical completeness**

The fields below need to have a valid value (including `Not available`) to be counted as complete:

- `donor`
  - `gender`
  - `sex_at_birth`
  - `date_of_birth`
  - `date_resolution`
- `primary diagnosis`
  - `date_of_diagnosis`
  - `cancer_type_code`
  - `primary_site`
  - `basis_of_diagnosis`
- `specimen`
  - `specimen_collection_date`
  - `specimen_anatomic_location`
- `sample registration`
  - `specimen_tissue_source`
  - `tumour_normal_designation`
  - `specimen_type`
  - `sample_type`

**DNA sample:**

A sample is counted as `DNA` if the `sample_registration.sample_type` is one of
- Total DNA
- Amplified DNA
- ctDNA
- Other DNA enrichments
- Whole cell - DNA

**RNA sample:**

A sample is counted as `RNA` if the `sample_registration.sample_type` is one of
- Total RNA
- Other RNA fractions
- polyA+ RNA
- rRNA-depleted RNA
- Whole cell - RNA

**Tumour/Normal**

A sample is counted as `Tumour` if `sample_registration.tumour_normal_designation` == `Tumour`.

A sample is counted as `Normal` if `sample_registration.tumour_normal_designation` == `Normal`.

## Outputs

All outputs are prefixed with a date-time stamp and the value provided to the `--node` argument.

### `YYYY-MM-DD_hhmm-NODE-per_program_completeness_report.csv`

Contains counts per program of completeness based on tier a, tier b and fullsome completeness

Columns:
* `node` - the node where the report was run
* `program_id` - the program id
* `donor_count` - total number of donors in the program
* `tier_a_min_cg_complete` - count of donors that meet minimal clinical and genomic data completeness for tier a criteria
* `tier_b_min_cg_complete` - count of donors that meet minimal clinical and genomic data completeness for tier b criteria, excluding donors counted in `tier_a_full_complete`
* `incomplete_min_donors` - count of donors that do not meet tier a or tier b minimal criteria
* `tier_a_full_cg_complete` - count of donors that meet fullsome clinical data completeness and tier_a genomic criteria
* `tier_b_full_cg_complete` - count of donors that meet fullsome clinical data completeness and tier_b genomic criteria
* `incomplete_full_donors` - count of donors that do not meet fullsome tier a or tier b criteria
* `tier_a_min_clinical_complete` - count of donors that meet tier a minimal clinical completeness
* `tier_b_min_clinical_complete` - count of donors that meet tier b minimal clinical completeness
* `tier_a_full_clinical_complete` - count of donors that meet tier a fullsome clinical completeness
* `tier_a_full_clinical_complete` - count of donors that meet tier b fullsome clinical completeness
* `tier_a_genomic_files_complete` - count of donors that meet tier a genomic completeness
* `tier_b_genomic_files_complete` - count of donors that meet tier b genomic completeness

## `YYYY-MM-DD_hhmm-NODE-per_program_failed_minimal_completeness.csv`

Contains a count of **samples** per program with a null value for each of the minimal clinical completeness criteria.

Columns:
* `program_id_id`
* `submitter_donor_id`
* `gender`
* `sex_at_birth`
* `date_of_birth`
* `date_resolution`
* `date_of_diagnosis`
* `cancer_type_code`
* `primary_site`
* `basis_of_diagnosis`
* `specimen_collection_date`
* `specimen_anatomic_location`
* `specimen_tissue_source`
* `submitter_sample_id`
* `tumour_normal_designation`
* `sample_type`
* `specimen_type`

> [!NOTE]
> Failed counts count the number of SAMPLES not DONORS, we generally expect a DONOR to have 2-3 samples. Since they are grouped in this way some of the metadata is repeated, e.g. the status of `gender` would be the same for all samples from the same donor

## `YYYY-MM-DD_hhmm-NODE-failed_minimal_completeness.csv`

Contains minimal completeness metadata for samples that have a null value in at least one of the minimal clinical completeness criteria (see list above)

This file can be used to figure out which field(s) are causing specific donors or samples to fail minimal completeness.

### `YYYY-MM-DD_hhmm-NODE-per_donor_full_completeness.csv`

Contains summary completeness including genomic and clinical data per donor

Columns:
* `program_id`
* `submitter_donor_id`
* `tier_a_full_clinical_complete` - whether donor has fullsome tier a clinical data completeness
* `tier_b_full_clinical_complete` - whether donor has fullsome tier a clinical data completeness
* `expression_file_count` - count of expression files linked to the sample
* `variant_sample_file_count` - count of variant files linked to the sample
* `read_file_count` - count of read files linked to the sample
* `tier_a_genomic_files_complete` - whether donor meets tier a genomic completeness
* `tier_b_genomic_files_complete` - whether donor meets tier b genomic completeness
* `tier_a_min_clinical_complete` - whether donor meets tier a clinical completeness
* `tier_b_min_clinical_complete` - whether donor meets tier b clinical completeness
* `tier_a_min_cg_complete` - whether donor meets minimal clinical and genomic data completeness for tier a criteria
* `tier_b_min_cg_complete` - whether donor meets minimal clinical and genomic data completeness for tier b criteria, excluding donors counted in `tier_a_min_cg_commplete`
* `tier_a_full_cg_complete` - whether the donor meets fullsome tier a clinical and genomic criteria
* `tier_b_full_cg_complete` - whether the donor meets fullsome tier b clinical and genomic criteria

### `YYYY-MM-DD_hhmm-NODE-per_sample_genomic_stats.csv`

Contains counts of genomic files linked to samples

Columns:
* `program_id`
* `submitter_sample_id`
* `expression_file_count` - count of expression files linked to the sample
* `variant_sample_file_count` - count of variant files linked to the sample
* `read_file_count` - count of read files linked to the sample

### `YYYY-MM-DD_hhmm-NODE-per_donor_clinical_completeness_full_breakdown.csv`

Full per donor breakdown of completeness in each category of object. May be useful for trying to understand where donors are not meeting fullsome clinical completeness.

### `YYYY-MM-DD_hhmm-NODE-complete_donor_samples.csv`

File containing a list of all minimally complete samples.