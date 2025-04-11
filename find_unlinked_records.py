# Detects data incomplete between tables.
#
# Kinda ugly (though functional) script overall - could be reworked if users express utility or interest.
# Takes .csv files as input because we are looking for pre-ingestion data absences.
# Not all test cases necessarily indicate an error.  For example, "Donors without a treatment" could be legitimate if the specimen was taken post-mortem.  This report simply intends to identify candidate cases for further investigation.
# 
# Requirements: See requirements.txt
#
# Input: Expects a directory of .csv files with columns following the MoH metadata spec.
#
# Usage: Define the base_data_path directory where all the .csv files may be found.
# python find_unlinked_records.py > Cohort_date_absences_report.csv
#
# Output is a .csv that can be opened in Excel / LibreOffice.  The report is kinda ugly and rough, but functional.  Foreach test case, the report provides a count and then lists the specific cases.
#
# Known issues:
# Does not test for (nor handle) empty files or tables.
# No input .csv column or format validation is performed - assumes clean, organized inputs.
# Assumes .csv file names follow table names (ie. donor.csv, follow_up.csv) 

import os
import pandas

# base_data_path = "/media/veracrypt1/CanDIG/HMR/MOHQ_HMR_31MAR2025/orig" # Not yet working, since radiation.csv and surgery.csv are empty.
base_data_path = "/media/veracrypt1/CanDIG/CHUM/CHUM_27_mar_2025/pre_proc"
# base_data_path = "/media/veracrypt1/CanDIG/JGH/JGH_armita_16JAN2025/orig"

# Panda settings.
# Unlimited row output.
pandas.set_option('display.max_rows', None)
# Suppress SettingWithCopyWarning
pandas.options.mode.chained_assignment = None  # default='warn'

def open_and_read(schema):
    full_file = os.path.join(base_data_path, schema + ".csv")
    if os.path.isfile(full_file) and os.path.getsize(full_file) > 0:
        return pandas.read_csv(os.path.join(base_data_path, schema + ".csv"))
    else:
        return pandas.DataFrame()

def main():
    # Transform .csv to Pandas dataframes.
    donor_df = open_and_read("donor")
    follow_up_df = open_and_read("follow_up")
    primary_diagnosis_df = open_and_read("primary_diagnosis")
    radiation_df = open_and_read("radiation")
    sample_registration_df = open_and_read("sample_registration")
    specimen_df = open_and_read("specimen")
    surgery_df = open_and_read("surgery")
    systemic_therapy_df = open_and_read("systemic_therapy")
    treatment_df = open_and_read("treatment")

    ### DONORS
    # donors without primary_diagnosis.
    count = donor_df[~donor_df.submitter_donor_id.isin(primary_diagnosis_df.submitter_donor_id)]
    count.sort_values(['program_id', 'submitter_donor_id'], inplace=True)
    print("Donors without primary_diagnosis," + str(count.shape[0]))
    if not count.empty:
        print(count.loc[:, ['program_id', 'submitter_donor_id']].to_csv(index=False))
    else:
        print("None\n")    

    # donors without treatment.
    count = donor_df[~donor_df.submitter_donor_id.isin(treatment_df.submitter_donor_id)]
    count.sort_values(['program_id', 'submitter_donor_id'], inplace=True)
    print("Donors without treatment," + str(count.shape[0]))
    if not count.empty:
        print(count.loc[:, ['program_id', 'submitter_donor_id']].to_csv(index=False))
    else:
        print("None\n")    

    # donors without specimen.
    count = donor_df[~donor_df.submitter_donor_id.isin(specimen_df.submitter_donor_id)]
    count.sort_values(['program_id', 'submitter_donor_id'], inplace=True)
    print("Donors without specimen," + str(count.shape[0]))
    if not count.empty:
        print(count.loc[:, ['program_id', 'submitter_donor_id']].to_csv(index=False))
    else:
        print("None\n")    

    # CM-3-10: One sample is registered 3 times (both tumour and normal)
    # donors without 2 specimens.
    specimen_counts = {}
    for value in specimen_df['submitter_donor_id']:
        specimen_counts[value] = specimen_counts.get(value, 0) + 1
    tally = 0
    for donor in specimen_counts:
        if specimen_counts[donor] != 2:
            tally = tally + 1
    if tally != 0:
        print(f"Donors with more or less than 2 specimens,{tally}")
    print("donor_id,specimen_count")
    for donor in sorted(specimen_counts):
        if specimen_counts[donor] != 2:
            print(f'{donor},{specimen_counts[donor]}' )
    # Blank line
    print()

    # donors without sample_registration.
    count = donor_df[~donor_df.submitter_donor_id.isin(sample_registration_df.submitter_donor_id)]
    count.sort_values(['program_id', 'submitter_donor_id'], inplace=True)
    print("Donors without sample_registration," + str(count.shape[0]))
    if not count.empty:
        print(count.loc[:, ['program_id', 'submitter_donor_id']].to_csv(index=False))
    else:
        print("None\n")    
    
    # donors without 3 sample_registrations.
    sr_counts = {}
    for value in sample_registration_df['submitter_donor_id']:
        sr_counts[value] = sr_counts.get(value, 0) + 1
    tally = 0
    for donor in sr_counts:
        if sr_counts[donor] != 3:
            tally = tally + 1
    if tally != 0:
        print(f"Donors with more or less than 3 sample_registrations,{tally}")
    print("donor_id,sample_registration_count")
    for donor in sorted(sr_counts):
        if sr_counts[donor] != 3:
            print(f'{donor},{sr_counts[donor]}' )
    # Blank line
    print()

    # donors without follow_up
    count = donor_df[~donor_df.submitter_donor_id.isin(follow_up_df.submitter_donor_id)]
    count.sort_values(['program_id', 'submitter_donor_id'], inplace=True)
    print("Donors without follow_up," + str(count.shape[0]))
    if not count.empty:
        print(count.loc[:, ['program_id', 'submitter_donor_id']].to_csv(index=False))
    else:
        print("None\n")

    ### SPECIMENS
    # specimens without sample_registration
    count = specimen_df[~specimen_df.submitter_specimen_id.isin(sample_registration_df.submitter_specimen_id)]
    count.sort_values(['program_id', 'submitter_donor_id', 'submitter_specimen_id'], inplace=True)
    print("Specimens without sample_registration," + str(count.shape[0]))
    if not count.empty:
        print(count.loc[:, ['program_id', 'submitter_donor_id', 'submitter_specimen_id']].to_csv(index=False))
    else:
        print("None\n")

    # TREATMENTS
    # treatments without accompanying systemic_therapy, radiation or surgery tables.
    # Build df of all treatment detail table IDs.
    systemic_therapy_id = systemic_therapy_df[["submitter_treatment_id"]]
    radiation_id = radiation_df[["submitter_treatment_id"]]
    surgery_id = surgery_df[["submitter_treatment_id"]]
    combined_treatment_id_frames = [systemic_therapy_id, radiation_id, surgery_id]
    combined_treatment_id = pandas.concat(combined_treatment_id_frames)
    
    # Treatments without accompanying data in other tables.
    count = treatment_df[~treatment_df.submitter_treatment_id.isin(combined_treatment_id.submitter_treatment_id)]
    # Omit treatment_types that needn't reference other tables.
    count.drop(count[count["treatment_type"] == "Bone marrow transplant"].index, inplace=True)
    count.drop(count[count["treatment_type"] == "No treatment"].index, inplace=True)
    count.drop(count[count["treatment_type"] == "Other"].index, inplace=True)
    count.drop(count[count["treatment_type"] == "Photodynamic therapy "].index, inplace=True)
    count.drop(count[count["treatment_type"] == "Stem cell transplant"].index, inplace=True)
    count.drop(count[count["treatment_type"] == "Targeted molecular therapy"].index, inplace=True)
    # Sort
    count.sort_values(['program_id', 'submitter_donor_id', 'submitter_primary_diagnosis_id', 'submitter_treatment_id'], inplace=True)
    print("Treatments without referenced details," + str(count.shape[0]))
    if not count.empty:
        print(count.loc[:, ['program_id', 'submitter_donor_id', 'submitter_primary_diagnosis_id', 'submitter_treatment_id', 'treatment_type']].to_csv(index=False))
    else:
        print("None\n")

if __name__ == '__main__':
    main()
