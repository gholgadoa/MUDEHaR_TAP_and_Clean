import pandas as pd
import numpy as np

###################### INPUT

INPUT_CSV = "1689570.csv"
NAME_GOS = "Cyg_OB2-3_A"

###################### NO CHANGES AFTER THIS

VECTOR_COLUMNS = [
    "MAG660",
    "SMAG660",
    "MAG861",
    "SMAG861",
    "EXP_TS",
    "EXP_JD",
]

df = pd.read_csv(INPUT_CSV, skiprows=1)
df = df[df["NAME_GOS"] == NAME_GOS]
# Get RA and DEC from first valid row
first_row = df.iloc[0]
RA = first_row["RA"]
DEC = first_row["DEC"]

rows = []

def parse_vector(cell):
    if pd.isna(cell):
        return []
    return [float(x) for x in str(cell).split()]

for idx, row in df.iterrows():

    vectors = {}

    # Parse all vector columns
    for col in VECTOR_COLUMNS:
        vec = parse_vector(row[col])
        vec = [np.nan if x in (99.999, 9.999) else x for x in vec]
        vectors[col] = vec

    # Check internal consistency (within the same row)
    lengths = [len(vectors[col]) for col in VECTOR_COLUMNS]
    n = lengths[0]

    if not all(l == n for l in lengths):
        raise ValueError(
            f"Inconsistent vector lengths in row {idx}: {lengths}"
        )

    # Expand row
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
# CLEANING STEP (BEFORE SAVE)
# ==========================
out_df = out_df[~(
    out_df["MAG660"].isna() & out_df["MAG861"].isna()
)]

# ==========================
# OUTPUT FILENAME
# ==========================
output_file = f"{NAME_GOS}_{RA}_{DEC}.csv"

out_df.to_csv(output_file, index=False)

out_df.to_csv(f"{NAME_GOS}.csv", index=False)
