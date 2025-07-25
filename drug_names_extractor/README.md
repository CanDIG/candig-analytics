## Drug Names Comparison

Script that pulls out the drug names fields from all authorized programs in a deployment to compare fields.

### Prerequisites

- Authorized access to a CanDIG deployment in the network

### Runnng the script

1. Create a virtual environment and install requirements

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Login to your CanDIG deployment and grab a token by clicking the cog in the top right and clicking 'Get API Token' then clicking the token to copy it.

3. Run the script

```bash
python3 drug_extractor.py --url <YOUR CANDIG URL> --token <YOUR TOKEN>
```

Results will be saved to a file called `drug_names.csv`. The output is a table with four columns, `drug_name`, `drug_identifier`, `drug_reference_database` and `count`. The table is de-duplicated by the 3 drug columns and the count tells you how many time that combination occurs across all the programs in the system.

> [!NOTE]
> The script will only return results from programs that you have authorized access to, so it would be best to run it with a site curator or site admin token to get the full list of drug names ingested at the site.