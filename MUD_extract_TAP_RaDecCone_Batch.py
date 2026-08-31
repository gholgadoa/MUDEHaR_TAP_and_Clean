"""
MUDEHaR DR1 - Batch Cone Search
================================

This script reads a list of RA/DEC coordinates from a TXT file and
performs an independent cone search for each coordinate using the
MUDEHaR DR1 TAP service.

A separate CSV file is generated for EACH pair of coordinates.

Input
-----
The TXT file must contain one RA/DEC pair per line, in decimal degrees:

    14.04715 55.94506
    14.12345 56.01234
    13.98765 55.87654

Lines beginning with '#' and empty lines are ignored.

Output
------
For each coordinate pair, one CSV file is created:

    MUDEHaR_RA_14.04715_DEC_55.94506.csv
    MUDEHaR_RA_14.12345_DEC_56.01234.csv
    ...

The output format is the same as in the single-target version.

Requirements
------------
    pip install pyvo pandas numpy
"""

# =============================================================================
# IMPORTS
# =============================================================================

import pyvo
import pandas as pd
import numpy as np


# =============================================================================
# CONFIGURATION
# =============================================================================

# Input TXT file containing the list of coordinates.
INPUT_FILE = "coordinates.txt"

# Cone-search radius in degrees.
#
# IMPORTANT:
# ADQL CIRCLE() expects the radius in degrees, not arcseconds.
#
# Example:
#     18 arcsec = 18 / 3600 = 0.005 degrees
#
RADIUS = 0.005

# MUDEHaR DR1 TAP service.
TAP_URL = "https://archive.cefca.es/catalogues/vo/tap/mudehar-dr1"


# =============================================================================
# VECTOR COLUMNS
# =============================================================================

# These catalogue columns contain several measurements stored together
# in a single cell.
#
# They will be expanded so that every measurement/exposure becomes
# a separate row in the output CSV.

VECTOR_COLUMNS = [
    "mag660",
    "smag660",
    "mag861",
    "smag861",
    "exp_ts",
    "exp_jd",
]


# =============================================================================
# READ COORDINATES FROM TXT
# =============================================================================

def read_coordinates(filename):
    """
    Read RA/DEC pairs from a TXT file.

    Expected format:

        RA DEC

    One coordinate pair per line.

    Empty lines and lines beginning with '#' are ignored.

    Parameters
    ----------
    filename : str
        Path to the input TXT file.

    Returns
    -------
    list of tuple
        List of (RA, DEC) coordinate pairs.
    """

    coordinates = []

    with open(filename, "r") as file:

        for line_number, line in enumerate(file, start=1):

            # Remove leading/trailing whitespace.
            line = line.strip()

            # Ignore empty lines and comments.
            if not line or line.startswith("#"):
                continue

            # Split the line into individual values.
            parts = line.split()

            # We need at least two values: RA and DEC.
            if len(parts) < 2:
                print(
                    f"WARNING: Invalid line {line_number}: {line}"
                )
                continue

            try:
                ra = float(parts[0])
                dec = float(parts[1])

            except ValueError:
                print(
                    f"WARNING: Could not parse line {line_number}: {line}"
                )
                continue

            coordinates.append((ra, dec))

    return coordinates


# =============================================================================
# PARSE VECTOR
# =============================================================================

def parse_vector(cell):
    """
    Convert a vector-like catalogue cell into a list of floats.

    The TAP service may return vector values in different formats,
    for example:

        (20.1, 20.2, 20.3)

    or:

        20.1 20.2 20.3

    or as a NumPy array/list.

    Parameters
    ----------
    cell : object
        Value stored in the catalogue cell.

    Returns
    -------
    list
        Parsed floating-point values.
    """

    # Missing values are represented by an empty list.
    if cell is None:
        return []

    # If the value is already an array or list, convert it
    # to a standard Python list.
    if isinstance(cell, (np.ndarray, list)):
        return list(cell)

    # Otherwise, treat it as a string.
    s = str(cell).strip()

    # Remove parentheses if present.
    s = s.replace("(", "").replace(")", "")

    # Handle comma-separated and whitespace-separated vectors.
    if "," in s:
        parts = s.split(",")
    else:
        parts = s.split()

    # Convert all values to floats.
    return [
        float(x)
        for x in parts
        if x.strip() != ""
    ]


# =============================================================================
# CONNECT TO TAP SERVICE
# =============================================================================

# Create the TAP service once.
#
# The same service object is reused for every coordinate pair.
service = pyvo.dal.TAPService(TAP_URL)


# =============================================================================
# READ INPUT COORDINATES
# =============================================================================

coordinates = read_coordinates(INPUT_FILE)

if len(coordinates) == 0:
    raise ValueError(
        f"No valid coordinates found in {INPUT_FILE}"
    )

print(f"Coordinates to process: {len(coordinates)}")
print()


# =============================================================================
# PROCESS EACH COORDINATE PAIR
# =============================================================================

for target_number, (RA, DEC) in enumerate(coordinates, start=1):

    print("=" * 70)
    print(
        f"[{target_number}/{len(coordinates)}] "
        f"RA = {RA}, DEC = {DEC}"
    )
    print("=" * 70)

    # -------------------------------------------------------------------------
    # ADQL QUERY
    # -------------------------------------------------------------------------

    # Perform a cone search around the current RA/DEC position.
    #
    # The query is identical to the single-target version.
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

    # -------------------------------------------------------------------------
    # EXECUTE QUERY
    # -------------------------------------------------------------------------

    result = service.search(query)

    # Convert the result into an Astropy Table.
    table = result.to_table()

    # Convert the Astropy Table to Pandas.
    df = table.to_pandas()

    # -------------------------------------------------------------------------
    # CHECK WHETHER SOURCES WERE FOUND
    # -------------------------------------------------------------------------

    if len(df) == 0:
        print("No sources found.")

        # No CSV is generated for this coordinate.
        # Continue with the next target.
        continue

    print(f"Sources found: {len(df)}")

    # List that will contain the expanded rows for THIS target only.
    rows = []


    # =========================================================================
    # EXPAND VECTOR COLUMNS
    # =========================================================================

    for idx, row in df.iterrows():

        vectors = {}

        # Parse all vector columns.
        for col in VECTOR_COLUMNS:

            vec = parse_vector(row[col])

            # -----------------------------------------------------------------
            # SENTINEL VALUE CLEANING
            # -----------------------------------------------------------------
            #
            # MUDEHaR uses special values to indicate invalid/missing
            # measurements.
            #
            # Convert them to NaN so that Pandas treats them as missing data.

            vec = [
                np.nan if x in (99.999, 9.999) else x
                for x in vec
            ]

            vectors[col] = vec


        # =====================================================================
        # CHECK VECTOR LENGTHS
        # =====================================================================

        # Every vector belonging to the same source should contain
        # the same number of measurements.

        lengths = [
            len(vectors[col])
            for col in VECTOR_COLUMNS
        ]

        # Number of measurements/exposures.
        n = lengths[0]

        # If the vector lengths do not agree, stop processing this source.
        if not all(length == n for length in lengths):

            raise ValueError(
                f"Inconsistent vector lengths at row {idx}: {lengths}"
            )


        # =====================================================================
        # CREATE ONE ROW PER EXPOSURE
        # =====================================================================

        for i in range(n):

            rows.append({

                # -------------------------------------------------------------
                # SOURCE INFORMATION
                # -------------------------------------------------------------

                "NAME_GOS": row["name_gos"],
                "RA": row["ra"],
                "DEC": row["dec"],

                # -------------------------------------------------------------
                # PHOTOMETRY
                # -------------------------------------------------------------

                "MAG660": vectors["mag660"][i],
                "SMAG660": vectors["smag660"][i],

                "MAG861": vectors["mag861"][i],
                "SMAG861": vectors["smag861"][i],

                # -------------------------------------------------------------
                # EXPOSURE INFORMATION
                # -------------------------------------------------------------

                "EXP_TS": vectors["exp_ts"][i],
                "EXP_JD": vectors["exp_jd"][i],
            })


    # =========================================================================
    # CREATE OUTPUT DATAFRAME
    # =========================================================================

    out_df = pd.DataFrame(rows)


    # =========================================================================
    # CLEANING
    # =========================================================================

    # Remove rows for which BOTH photometric bands are missing.
    #
    # A row is retained if at least one of MAG660 or MAG861
    # contains a valid measurement.

    out_df = out_df[
        ~(
            out_df["MAG660"].isna()
            & out_df["MAG861"].isna()
        )
    ]


    # =========================================================================
    # OUTPUT FILENAME
    # =========================================================================

    # Create one CSV filename for the current coordinate pair.
    #
    # Example:
    #
    #     RA = 14.04715
    #     DEC = 55.94506
    #
    # becomes:
    #
    #     MUDEHaR_RA_14.04715_DEC_55.94506.csv

    output_file = (
        f"MUDEHaR_RA_{RA}_DEC_{DEC}.csv"
    )


    # =========================================================================
    # SAVE CSV
    # =========================================================================

    out_df.to_csv(
        output_file,
        index=False
    )


    # -------------------------------------------------------------------------
    # REPORT
    # -------------------------------------------------------------------------

    print(
        f"Measurements saved: {len(out_df)}"
    )

    print(
        f"Saved: {output_file}"
    )

    print()


# =============================================================================
# END
# =============================================================================

print("=" * 70)
print("BATCH PROCESSING COMPLETE")
print("=" * 70)
