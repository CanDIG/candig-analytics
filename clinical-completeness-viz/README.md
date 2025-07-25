## Clinical completeness visualisations

Files to generate reports for clinical completeness across sites in a CanDIG federated network.

### Prerequisites

- Authorized access to a CanDIG deployment in the network
- [Quarto](https://quarto.org/docs/get-started/) installed on your machine
- Virtual env with requirements installed
- [Jupyter](https://jupyter.org/install)


1. Create a virtual environment and install requirements

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. In a terminal, start the jupyter notebook browser interface with:

```bash
jupyter notebook
```

This should open a browser with the current directory shown. Double-click the `completeness_stats.ipynb` to open the notebook.

3. Grab a refresh token from your CanDIG deployment by using the cog button in the top right of the browser window and clicking it to copy

4. Run all cells in the notebook. Note that you will be prompted for your CanDIG deployment's domain as well as the token you copied from the browser

## Convert notebook to report output

Use quarto to convert the notebook into a report, multiple outputs are possible, I have found the doc easiest to share.

```bash
quarto render completeness_stats.ipynb --to docx
```

Note: this should work with the current CanDIG network of UHN, BCGSC and MOHQ, will need to be updated as new nodes join the network. There are probably smarter ways of writing the code so that it automatically works when new nodes are added, we should try to write better code in the future.
