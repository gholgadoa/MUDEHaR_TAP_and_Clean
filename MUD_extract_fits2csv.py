import numpy as np
import pandas as pd
from astropy.io import fits

###################### INPUT


INPUT_FITS = "1689595.fits"
NAME_GOS = "Gaia_DR2_423577032022329600"

###################### NO CHANGES AFTER THIS


VECTOR_COLUMNS = [
    "MAG660",
    "SMAG660",
    "MAG861",
    "SMAG861",
    "EXP_TS",
    "EXP_JD",
]

# ==========================
# LOAD FITS
# ==========================
with fits.open(INPUT_FITS) as hdul:
    data = hdul[1].data

# Build DataFrame column by column (safe for vector fields)
df = pd.DataFrame({
    name: data[name] for name in data.names
})
# ==========================
# FILTER
# ==========================
df = df[df["NAME_GOS"] == NAME_GOS]

# Get RA/DEC from first valid row
first_row = df.iloc[0]
RA = first_row["RA"]
DEC = first_row["DEC"]

rows = []

# ==========================
# PARSER
# ==========================
def parse_vector(cell):
    """
    Handles:
    - numpy arrays (FITS native)
    - strings like "(1.2, 3.4, ...)"
    """
    if cell is None or (isinstance(cell, float) and np.isnan(cell)):
        return []

    # Case 1: FITS native array
    if isinstance(cell, np.ndarray) or isinstance(cell, list):
        return list(cell)

    # Case 2: string representation "(..., ..., ...)"
    s = str(cell).strip()

    # Remove parentheses if present
    s = s.replace("(", "").replace(")", "")

    # Split by whitespace or commas
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
            "MAG660": vectors["MAG660"][i],
            "SMAG660": vectors["SMAG660"][i],
            "MAG861": vectors["MAG861"][i],
            "SMAG861": vectors["SMAG861"][i],
            "EXP_TS": vectors["EXP_TS"][i],
            "EXP_JD": vectors["EXP_JD"][i],
        })

out_df = pd.DataFrame(rows)

# ==========================
# CLEANING
# ==========================
out_df = out_df[~(
    out_df["MAG660"].isna() & out_df["MAG861"].isna()
)]

# ==========================
# OUTPUT NAME
# ==========================
output_file = f"{NAME_GOS}_{RA}_{DEC}_fits.csv"

out_df.to_csv(output_file, index=False)
