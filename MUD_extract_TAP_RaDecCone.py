"""
MUDEHaR DR1 - Cone Search and Photometry Extraction
====================================================

This script queries the MUDEHaR DR1 TAP service hosted by CEFCA,
performs a cone search around a given sky position, and expands
the vector columns containing measurements from individual exposures
into a row-per-exposure format.

The resulting data are saved as a CSV file.

Requirements
------------
Install the required Python packages with:

    pip install pyvo pandas numpy

References
----------
MUDEHaR DR1 TAP service:
https://archive.cefca.es/catalogues/vo/tap/mudehar-dr1

Notes
-----
- RA and DEC are given in decimal degrees.
- The search radius must also be given in degrees because the ADQL
  CIRCLE() function expects angular coordinates in degrees.
- Some MUDEHaR columns contain vector-like values, i.e. several
  measurements stored in a single table cell. These are expanded
  so that each exposure becomes a separate row.
"""

# =============================================================================
# IMPORTS
# =============================================================================

import pyvo
import pandas as pd
import numpy as np


# =============================================================================
# INPUT PARAMETERS
# =============================================================================

# Central coordinates of the cone search.
# Coordinates are given in decimal degrees (ICRS).
RA = 14.04715
DEC = 55.94506

# Search radius in decimal degrees.
#
# IMPORTANT:
# ADQL CIRCLE() expects the radius in degrees, NOT arcseconds.
#
# Example:
#     18 arcsec = 18 / 3600 = 0.005 degrees
#
RADIUS = 0.005

# If you prefer to specify the radius in arcseconds, convert it
# to degrees before constructing the ADQL query:
#
# RADIUS_ARCSEC = 18
# RADIUS = RADIUS_ARCSEC / 3600.0


# =============================================================================
# TAP SERVICE
# =============================================================================

# URL of the MUDEHaR DR1 TAP service provided by CEFCA.
#
# TAP (Table Access Protocol) is an IVOA standard that allows
# astronomical catalogues to be queried using ADQL.
TAP_URL = "https://archive.cefca.es/catalogues/vo/tap/mudehar-dr1"

# Create a PyVO TAPService object.
# This object is used to send the ADQL query to the remote archive.
service = pyvo.dal.TAPService(TAP_URL)


# =============================================================================
# ADQL QUERY - CONE SEARCH
# =============================================================================

# The query selects all columns from the Sources table and additionally
# retrieves exposure-related information from the Pointing_block table.
#
# The two tables are joined through:
#
#     s.pb_id = ob.id
#
# The CONTAINS(POINT(), CIRCLE()) condition performs the cone search:
#
#     POINT('', s.ra, s.dec)
#
# represents the position of each catalogue source, while
#
#     CIRCLE('', RA, DEC, RADIUS)
#
# defines the search region.
#
# CONTAINS(...) = 1 means that the source lies inside the circle.

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


# =============================================================================
# EXECUTE QUERY
# =============================================================================

# Send the ADQL query to the TAP service.
result = service.search(query)

# Convert the returned VO table into an Astropy Table.
table = result.to_table()


# =============================================================================
# VECTOR COLUMNS
# =============================================================================

# These columns contain vector-like values.
#
# In other words, a single catalogue row can contain several measurements,
# for example:
#
#     mag660 = [20.1, 20.2, 20.0, ...]
#
# Each element corresponds to an individual exposure/measurement.
#
# The script will later "expand" these vectors so that each measurement
# becomes a separate row in the output DataFrame.

VECTOR_COLUMNS = [
    "mag660",
    "smag660",
    "mag861",
    "smag861",
    "exp_ts",
    "exp_jd",
]


# =============================================================================
# CONVERT RESULT TO PANDAS
# =============================================================================

# Convert the Astropy Table returned by PyVO into a Pandas DataFrame.
# Pandas makes the subsequent cleaning and restructuring easier.
df = table.to_pandas()

# Stop the script if the cone search did not return any sources.
if len(df) == 0:
    raise ValueError("No sources found in cone search")


# This list will contain the final rows of the output table.
rows = []


# =============================================================================
# VECTOR PARSER
# =============================================================================

def parse_vector(cell):
    """
    Convert a vector-like catalogue cell into a Python list of floats.

    MUDEHaR vector columns may be returned in different representations,
    depending on how the TAP service encodes the data. This function
    handles the most common cases.

    Parameters
    ----------
    cell : object
        Value stored in a catalogue cell.

    Returns
    -------
    list
        List of floating-point values.

    Examples
    --------
    A value such as:

        "(20.1, 20.2, 20.3)"

    becomes:

        [20.1, 20.2, 20.3]

    Likewise, whitespace-separated values are also supported.
    """

    # Missing values are represented by an empty list.
    if cell is None:
        return []

    # If PyVO/Astropy already returned the value as an array or list,
    # convert it directly to a standard Python list.
    if isinstance(cell, (np.ndarray, list)):
        return list(cell)

    # Otherwise, treat the value as a string.
    s = str(cell).strip()

    # Remove parentheses that may surround the vector.
    s = s.replace("(", "").replace(")", "")

    # Some vectors are comma-separated, while others may be
    # whitespace-separated.
    if "," in s:
        parts = s.split(",")
    else:
        parts = s.split()

    # Convert all non-empty elements to floating-point numbers.
    return [float(x) for x in parts if x.strip() != ""]


# =============================================================================
# EXPAND VECTOR COLUMNS
# =============================================================================

# Iterate over every source returned by the cone search.
for idx, row in df.iterrows():

    # Dictionary containing the parsed vectors for the current source.
    vectors = {}

    # Parse every vector column.
    for col in VECTOR_COLUMNS:

        vec = parse_vector(row[col])

        # ---------------------------------------------------------------------
        # SENTINEL VALUE CLEANING
        # ---------------------------------------------------------------------
        #
        # The catalogue uses special numerical values to indicate invalid
        # or missing measurements.
        #
        # Here:
        #
        #     99.999
        #     9.999
        #
        # are converted to NaN so that Pandas/Numpy can treat them
        # as missing values.
        vec = [
            np.nan if x in (99.999, 9.999) else x
            for x in vec
        ]

        vectors[col] = vec

    # -------------------------------------------------------------------------
    # CHECK VECTOR LENGTHS
    # -------------------------------------------------------------------------
    #
    # All vector columns belonging to the same source should contain
    # the same number of measurements.
    #
    # For example:
    #
    #     mag660  -> 5 values
    #     smag660 -> 5 values
    #     mag861  -> 5 values
    #     smag861 -> 5 values
    #     exp_ts  -> 5 values
    #     exp_jd  -> 5 values
    #
    # If the lengths are inconsistent, something is wrong with the data
    # and we stop rather than silently producing an incorrect table.

    lengths = [len(vectors[c]) for c in VECTOR_COLUMNS]

    # Number of measurements/exposures for this source.
    n = lengths[0]

    if not all(length == n for length in lengths):
        raise ValueError(
            f"Inconsistent vector lengths at row {idx}: {lengths}"
        )

    # -------------------------------------------------------------------------
    # CREATE ONE OUTPUT ROW PER EXPOSURE
    # -------------------------------------------------------------------------

    for i in range(n):

        rows.append({
            # Source identification and sky position.
            "NAME_GOS": row["name_gos"],
            "RA": row["ra"],
            "DEC": row["dec"],

            # Photometry.
            "MAG660": vectors["mag660"][i],
            "SMAG660": vectors["smag660"][i],
            "MAG861": vectors["mag861"][i],

            # Photometric uncertainties.
            "SMAG861": vectors["smag861"][i],

            # Exposure information.
            "EXP_TS": vectors["exp_ts"][i],
            "EXP_JD": vectors["exp_jd"][i],
        })


# =============================================================================
# CREATE OUTPUT DATAFRAME
# =============================================================================

# Convert the list of dictionaries into a Pandas DataFrame.
#
# At this point, each row corresponds to one measurement/exposure
# of one source.
out_df = pd.DataFrame(rows)


# =============================================================================
# FINAL CLEANING
# =============================================================================

# Remove measurements for which BOTH photometric bands are missing.
#
# A row is removed only when:
#
#     MAG660 == NaN
#
# AND
#
#     MAG861 == NaN
#
# If at least one of the two measurements is available, the row is kept.

out_df = out_df[
    ~(
        out_df["MAG660"].isna()
        & out_df["MAG861"].isna()
    )
]


# =============================================================================
# SAVE OUTPUT
# =============================================================================

# Build the output filename from the coordinates used in the query.
#
# Example:
#
#     MUDEHaR_RA_14.04715_DEC_55.94506.csv
#
output_file = f"MUDEHaR_RA_{RA}_DEC_{DEC}.csv"

# Save the final DataFrame as a CSV file.
# index=False prevents Pandas from adding an unnecessary index column.
out_df.to_csv(output_file, index=False)


# =============================================================================
# SUMMARY
# =============================================================================

print(f"Sources found: {len(df)}")
print(f"Measurements saved: {len(out_df)}")
print(f"Saved: {output_file}")
