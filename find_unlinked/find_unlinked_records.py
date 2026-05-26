# Reports data incomplete between tables.
#
# Kinda ugly (though functional) script overall - could be reworked if users express utility or interest.
# Takes .csv files as input because we are looking for pre-ingestion data absences.
# Not all test cases necessarily indicate an error.  For example, "Donors without a treatment" could be legitimate if the specimen was taken post-mortem.  This report simply intends to identify candidate cases for further investigation.
# 
# Requirements: See requirements.txt
#
# Input: Expects a directory of .csv files, named according to MOH the schema, with columns following the MoH metadata spec.
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

# base_data_path = "/media/veracrypt1/CanDIG/HMR/HMR_12DEC2025/pre_proc"
# base_data_path = "/media/veracrypt1/CanDIG/CHUM/CHUM_25aug2025/pre_proc"
# base_data_path = "/media/veracrypt1/CanDIG/MUHC/MUHC_25aug2025/pre_proc"
# base_data_path = "/media/veracrypt1/CanDIG/JGH/JGH_3feb2026/pre_proc"
# base_data_path = "/media/veracrypt1/CanDIG/MUHC/MUHC_27nov2025_MU16_MU36/pre_proc"
# base_data_path = "/media/veracrypt1/CanDIG/CHUQ/CHUQ_11dec2025/pre_proc"
# base_data_path = "/media/veracrypt1/CanDIG/CHUS/CHUS_5feb2026/pre_proc"
# base_data_path = "/media/veracrypt1/CanDIG/CHUM/CHUM_30jan2026/pre_proc"
# base_data_path = "/media/veracrypt1/CanDIG/MUHC/MUHC_11feb2026/pre_proc"
# base_data_path = "/media/veracrypt1/CanDIG/MUHC/MUHC_6mar2026_IQ33_only/pre_proc"
# base_data_path = "/media/veracrypt1/CanDIG/HMR/HMR_19mar2026/pre_proc"
# base_data_path = "/media/veracrypt1/CanDIG/CHUM/CHUM_19mar2026/pre_proc"
# base_data_path = "/media/veracrypt1/CanDIG/CHUQ/CHUQ_19mar2026/pre_proc"
# base_data_path = "/media/veracrypt1/CanDIG/MUHC/MUHC_19mar2026/pre_proc"
# base_data_path = "/media/veracrypt1/CanDIG/JGH/JGH_23mar2026/pre_proc"
# base_data_path = "/media/veracrypt1/CanDIG/JGH/JGH_24apr2026/orig"
# base_data_path = "/media/veracrypt1/CanDIG/CHUM/CHUM_23apr2026/pre_proc"
# base_data_path = "/media/veracrypt1/CanDIG/MUHC/MUHC_23apr2026/pre_proc"
base_data_path = "/media/veracrypt1/CanDIG/MUHC/MUHC_20may2026/orig"


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

    print(f"Absences report\n")
    print(f"Errors affecting minimal clinical completeness\n")

    ## MINIMALLY CLINICALLY INCOMPLETE
    # Check for the essential clinical fields.
    donor_empty = pandas.concat([donor_df[donor_df['gender'].isna()], donor_df[donor_df['sex_at_birth'].isna()], donor_df[donor_df['date_of_birth'].isna()], donor_df[donor_df['date_resolution'].isna()]], axis=0)
    pd_empty = pandas.concat([primary_diagnosis_df[primary_diagnosis_df['date_of_diagnosis'].isna()], primary_diagnosis_df[primary_diagnosis_df['cancer_type_code'].isna()], primary_diagnosis_df[primary_diagnosis_df['primary_site'].isna()], primary_diagnosis_df[primary_diagnosis_df['basis_of_diagnosis'].isna()]], axis=0)
    specimen_empty = pandas.concat([specimen_df[specimen_df['specimen_collection_date'].isna()], specimen_df[specimen_df['specimen_anatomic_location'].isna()]], axis=0)
    sample_empty = pandas.concat([sample_registration_df[sample_registration_df['specimen_tissue_source'].isna()], sample_registration_df[sample_registration_df['tumour_normal_designation'].isna()], sample_registration_df[sample_registration_df['specimen_type'].isna()], sample_registration_df[sample_registration_df['sample_type'].isna()], ], axis=0)

    count = pandas.concat([donor_empty[['program_id', 'submitter_donor_id']], pd_empty[['program_id', 'submitter_donor_id']], specimen_empty[['program_id', 'submitter_donor_id']], sample_empty[['program_id', 'submitter_donor_id']]], axis=0)
    # Drop duplicate lines.
    count.drop_duplicates(inplace=True)
    print("Donors failing minimal clinical completeness," + str(count.shape[0]))
    if not count.empty:
        print(count.loc[:, ['program_id', 'submitter_donor_id']].to_csv(index=False))
    else:
        print("None")    
    # Blank line
    print()

    ### DONORS
    # donors without primary_diagnosis.
    count = donor_df[~donor_df.submitter_donor_id.isin(primary_diagnosis_df.submitter_donor_id)]
    count.sort_values(['program_id', 'submitter_donor_id'], inplace=True)
    print("Donors without primary_diagnosis (minimally clinically incomplete)," + str(count.shape[0]))
    if not count.empty:
        print(count.loc[:, ['program_id', 'submitter_donor_id']].to_csv(index=False))
    else:
        print("None")    
    # Blank line
    print()

    # donors without specimen.
    count = donor_df[~donor_df.submitter_donor_id.isin(specimen_df.submitter_donor_id)]
    count.sort_values(['program_id', 'submitter_donor_id'], inplace=True)
    print("Donors without specimen (minimally clinically incomplete)," + str(count.shape[0]))
    if not count.empty:
        print(count.loc[:, ['program_id', 'submitter_donor_id']].to_csv(index=False))
    else:
        print("None")    
    # Blank line
    print()

    # donors without sample_registration.
    count = donor_df[~donor_df.submitter_donor_id.isin(sample_registration_df.submitter_donor_id)]
    count.sort_values(['program_id', 'submitter_donor_id'], inplace=True)
    print("Donors without sample_registration (minimally clinically incomplete)," + str(count.shape[0]))
    if not count.empty:
        print(count.loc[:, ['program_id', 'submitter_donor_id']].to_csv(index=False))
    else:
        print("None")    
    # Blank line
    print()
    
    # donors without both Normal and Tumour DNA sample_registrations.
    sr_all = set()
    sr_DN = set()
    sr_DT = set()
    for line in sample_registration_df.to_dict(orient="records"):
        sr_all.add(line["submitter_donor_id"])
        if line["tumour_normal_designation"] == "Normal" and line["sample_type"] == "Total DNA":
            sr_DN.add(line["submitter_donor_id"])
        elif line["tumour_normal_designation"] == "Tumour" and line["sample_type"] == "Total DNA":
            sr_DT.add(line["submitter_donor_id"])
    sr_missing = sr_all.difference(sr_DN.intersection(sr_DT))
    print(f"Donors without both Normal and Tumour DNA sample_registrations (minimally clinically incomplete),{len(sr_missing)}")
    if len(sr_missing) > 0:
        print("donor_id")
    else:
        print("None")
    for donor in sorted(sr_missing):
        print(donor)
    print()

    ### SPECIMENS
    # specimens without sample_registration
    count = specimen_df[~specimen_df.submitter_specimen_id.isin(sample_registration_df.submitter_specimen_id)]
    count.sort_values(['program_id', 'submitter_donor_id', 'submitter_specimen_id'], inplace=True)
    print("Specimens without sample_registration (minimally clinically incomplete)," + str(count.shape[0]))
    if not count.empty:
        print(count.loc[:, ['program_id', 'submitter_donor_id', 'submitter_specimen_id']].to_csv(index=False))
    else:
        print("None")
    # Blank line
    print()

    print(f"Warnings of unusual and potentially problematic cases\n")

    # donors without treatment.
    count = donor_df[~donor_df.submitter_donor_id.isin(treatment_df.submitter_donor_id)]
    count.sort_values(['program_id', 'submitter_donor_id'], inplace=True)
    print("Donors without treatment," + str(count.shape[0]))
    if not count.empty:
        print(count.loc[:, ['program_id', 'submitter_donor_id']].to_csv(index=False))
    else:
        print("None")    
    # Blank line
    print()

    # CM-3-10: One sample is registered 3 times (both tumour and normal)
    # donors without 2 specimens.
    specimen_counts = {}
    for value in specimen_df['submitter_donor_id']:
        specimen_counts[value] = specimen_counts.get(value, 0) + 1
    tally = 0
    for donor in specimen_counts:
        if specimen_counts[donor] != 2:
            tally = tally + 1
    print(f"Donors with more or less than 2 specimens,{tally}")
    if tally != 0:
        print("donor_id,specimen_count")
    else:
        print("None")    
    for donor in sorted(specimen_counts):
        if specimen_counts[donor] != 2:
            print(f'{donor},{specimen_counts[donor]}' )
    # Blank line
    print()

    # donors without 3 sample_registrations.
    sr_counts = {}
    for value in sample_registration_df['submitter_donor_id']:
        sr_counts[value] = sr_counts.get(value, 0) + 1
    tally = 0
    for donor in sr_counts:
        if sr_counts[donor] != 3:
            tally = tally + 1
    print(f"Donors with more or less than 3 sample_registrations,{tally}")
    if tally != 0:
        print("donor_id,sample_registration_count")
    else:
        print("None")    
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
        print("None")
    # Blank line
    print()

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
    # Omit treatment_types that needn't references to other tables.
    count.drop(count[count["treatment_type"] == "Bone marrow transplant"].index, inplace=True)
    count.drop(count[count["treatment_type"] == "No treatment"].index, inplace=True)
    count.drop(count[count["treatment_type"] == "Other"].index, inplace=True)
    count.drop(count[count["treatment_type"] == "Photodynamic therapy "].index, inplace=True)
    count.drop(count[count["treatment_type"] == "Stem cell transplant"].index, inplace=True)
    count.drop(count[count["treatment_type"] == "Targeted molecular therapy"].index, inplace=True)
    # Sort
    count.sort_values(['program_id', 'submitter_donor_id', 'submitter_primary_diagnosis_id', 'submitter_treatment_id'], inplace=True)
    print("Treatments without referenced details," + str(count.shape[0]) + ",(Treatments mentioned in the treatments table without a corresponding entry in the systemic_therapy or surgery or radiation table)")
    if not count.empty:
        print(count.loc[:, ['program_id', 'submitter_donor_id', 'submitter_primary_diagnosis_id', 'submitter_treatment_id', 'treatment_type']].to_csv(index=False))
    else:
        print("None")
    # Blank line
    print()

if __name__ == '__main__':
    main()
