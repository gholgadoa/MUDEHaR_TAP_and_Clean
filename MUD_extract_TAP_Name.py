import pyvo
import pandas as pd
import numpy as np

# ==========================
# INPUT PARAMETERS
# ==========================

NAME_GOS = "Gaia_DR2_423577032022329600"

######################################



# TAP service URL
TAP_URL = "https://archive.cefca.es/catalogues/vo/tap/mudehar-dr1"

# Connect to the TAP service
service = pyvo.dal.TAPService(TAP_URL)


query = f"""
SELECT
    s.*,
    ob.exp_names,
    ob.exp_ts,
    ob.exp_jd
FROM mudehar.Sources AS s
JOIN mudehar.Pointing_block AS ob
    ON s.pb_id = ob.id
WHERE s.NAME_GOS = '{NAME_GOS}'
"""

# Execute the query
result = service.search(query)

# Convert to Astropy Table
table = result.to_table()

VECTOR_COLUMNS = [
    "mag660",
    "smag660",
    "mag861",
    "smag861",
    "exp_ts",
    "exp_jd",
]

# ==========================
# CONVERT TO PANDAS (safe)
# ==========================
df = table.to_pandas()

# ==========================
# FILTER
# ==========================
df = df[df["name_gos"] == NAME_GOS]

if len(df) == 0:
    raise ValueError(f"No rows found for NAME_GOS = {NAME_GOS}")

# Get RA/DEC
first_row = df.iloc[0]
RA = first_row["ra"]
DEC = first_row["dec"]

rows = []

# ==========================
# PARSER
# ==========================
def parse_vector(cell):
    """
    Handles:
    - numpy arrays (native from TAP)
    - lists
    - strings "(1.2, 3.4 ...)"
    """
    if cell is None:
        return []

    # FITS/TAP native array
    if isinstance(cell, (np.ndarray, list)):
        return list(cell)

    s = str(cell).strip()
    s = s.replace("(", "").replace(")", "")

    if "," in s:
        parts = s.split(",")
    else:
        parts = s.split()

    return [float(x) for x in parts if x.strip() != ""]

# ==========================
# EXPAND
# ==========================
for idx, row in df.iterrows():

    vectors = {}

    for col in VECTOR_COLUMNS:
        vec = parse_vector(row[col])

        # Replace sentinel values
        vec = [np.nan if x in (99.999, 9.999) else x for x in vec]

        vectors[col] = vec

    lengths = [len(vectors[c]) for c in VECTOR_COLUMNS]
    n = lengths[0]

    if not all(l == n for l in lengths):
        raise ValueError(f"Inconsistent vector lengths in row {idx}: {lengths}")

    for i in range(n):
        rows.append({
            "MAG660": vectors["mag660"][i],
            "SMAG660": vectors["smag660"][i],
            "MAG861": vectors["mag861"][i],
            "SMAG861": vectors["smag861"][i],
            "EXP_TS": vectors["exp_ts"][i],
            "EXP_JD": vectors["exp_jd"][i],
        })

out_df = pd.DataFrame(rows)

# ==========================
# CLEANING
# ==========================
out_df = out_df[~(
    out_df["MAG660"].isna() & out_df["MAG861"].isna()
)]

# ==========================
# OUTPUT
# ==========================
output_file = f"{NAME_GOS}_{RA}_{DEC}_TAP.csv"
out_df.to_csv(output_file, index=False)

print(f"Saved: {output_file}")
