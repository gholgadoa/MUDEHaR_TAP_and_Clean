import pyvo
import pandas as pd
import numpy as np

# ==========================
# INPUT PARAMETERS
# ==========================
RA = 14.04715          # degrees
DEC = 55.94506         # degrees
RADIUS = 0.005      # degrees (IMPORTANT: TAP uses degrees, not arcsec)

# Optional: if you want arcsec input instead, convert:
# RADIUS = radius_arcsec / 3600.0

######################################

# TAP service URL
TAP_URL = "https://archive.cefca.es/catalogues/vo/tap/mudehar-dr1"

service = pyvo.dal.TAPService(TAP_URL)

# ==========================
# ADQL QUERY (CONE SEARCH)
# ==========================
query = f"""
SELECT
    s.*,
    ob.exp_names,
    ob.exp_ts,
    ob.exp_jd
FROM mudehar.Sources s
JOIN mudehar.Pointing_block ob
    ON s.pb_id = ob.id
WHERE CONTAINS(
    POINT('', s.ra, s.dec),
    CIRCLE('', {RA}, {DEC}, {RADIUS})
) = 1
"""

# ==========================
# EXECUTE
# ==========================
result = service.search(query)
table = result.to_table()

# ==========================
# CONFIG
# ==========================
VECTOR_COLUMNS = [
    "mag660",
    "smag660",
    "mag861",
    "smag861",
    "exp_ts",
    "exp_jd",
]

# ==========================
# TO PANDAS
# ==========================
df = table.to_pandas()

if len(df) == 0:
    raise ValueError("No sources found in cone search")

rows = []

# ==========================
# PARSER
# ==========================
def parse_vector(cell):
    if cell is None:
        return []

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
# EXPAND ALL ROWS
# ==========================
for idx, row in df.iterrows():

    vectors = {}

    for col in VECTOR_COLUMNS:
        vec = parse_vector(row[col])

        # sentinel cleaning
        vec = [np.nan if x in (99.999, 9.999) else x for x in vec]

        vectors[col] = vec

    lengths = [len(vectors[c]) for c in VECTOR_COLUMNS]
    n = lengths[0]

    if not all(l == n for l in lengths):
        raise ValueError(f"Inconsistent vector lengths at row {idx}: {lengths}")

    for i in range(n):
        rows.append({
            "NAME_GOS": row["name_gos"],
            "RA": row["ra"],
            "DEC": row["dec"],

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
# OUTPUT NAME (RA DEC ONLY)
# ==========================
output_file = f"MUDEHaR_RA_{RA}_DEC_{DEC}.csv"

out_df.to_csv(output_file, index=False)

print(f"Saved: {output_file}")
