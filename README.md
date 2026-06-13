# MUDEHaR_TAP_and_Clean
Python scripts to online_TAP download MUDEHaR data -- Name or Coordinates -- and produce clean csv final tables in csv. Also accepts csv or fits downloaded from CEFCA_MUDEHaR repository.

# MUDEHaR Data Extraction Utilities

This repository provides a collection of Python scripts to simplify the retrieval and preparation of data from the **MUDEHaR** archive. The goal is to make MUDEHaR light curves easier to access and analyze by automatically downloading data through the TAP service or processing files previously downloaded from the archive website.

The scripts extract only the information typically required for time-series analysis, producing clean CSV files containing:

* `MAG660`
* `SMAG660`
* `MAG861`
* `SMAG861`
* `EXP_TS`
* `EXP_JD`

When applicable, additional source information such as `NAME_GOS`, `RA`, and `DEC` is also included.

These utilities are complementary to the official MUDEHaR archive, available at:

https://archive.cefca.es/catalogues/mudehar-dr1

## Included scripts

### `MUD_extract_TAP_Name.py`

Downloads data directly from the MUDEHaR TAP service using a valid `NAME_GOS` identifier.

The script:

* Connects to the online TAP service.
* Retrieves all matching MUDEHaR observations.
* Expands vector-valued columns into one row per exposure.
* Replaces invalid sentinel values (`99.999` and `9.999`) with `NaN`.
* Removes rows where both magnitudes are missing.
* Produces a clean CSV file ready for scientific analysis.

**Input:** A valid MUDEHaR `NAME_GOS`.

### `MUD_extract_TAP_RaDecCone.py`

Downloads data directly from the MUDEHaR TAP service using a cone search.

The script:

* Accepts a sky position (`RA`, `DEC`) and search radius.
* Queries all sources within the specified cone.
* Expands vector-valued columns into one row per exposure.
* Cleans invalid values.
* Produces a CSV containing all matching sources, including `NAME_GOS`, `RA`, and `DEC` columns.

**Input:** `RA`, `DEC`, and search radius.

### `MUD_extract_csv2csv.py`

Processes CSV files downloaded manually from the MUDEHaR archive website.

The script:

* Reads the original CSV file.
* Selects a user-specified `NAME_GOS`.
* Expands vector-valued fields into individual measurements.
* Cleans invalid values and removes unnecessary rows.
* Writes a simplified CSV ready for analysis.

**Input:** A MUDEHaR CSV file and a valid `NAME_GOS`.

### `MUD_extract_fits2csv.py`

Processes FITS tables downloaded manually from the MUDEHaR archive website.

The script performs the same operations as `MUD_extract_csv2csv.py`, but starting from a FITS file instead of a CSV file.

**Input:** A MUDEHaR FITS file and a valid `NAME_GOS`.

### Video tutorial

A short video tutorial demonstrating how to use the scripts included in this repository is also provided.

**Note:** the narration begins at **00:15**, so the first 15 seconds contain no audio.

