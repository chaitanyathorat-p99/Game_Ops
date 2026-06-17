import pandas as pd
import numpy as np
import os

REQUIRED_COLUMNS = [
    'player_id', 'match_id', 'region', 'device', 'ping', 
    'score', 'kills', 'deaths', 'match_duration_seconds'
]

def load_and_clean_data(file_path: str) -> pd.DataFrame:
    """
    Loads raw player match CSV data, performs validation, cleans and normalizes,
    computes derived metrics, and returns a clean pandas DataFrame.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Input file not found at: {file_path}")

    # Read CSV
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        raise ValueError(f"Failed to read CSV file: {e}")

    initial_row_count = len(df)

    # 1. Validate required columns
    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns in CSV: {missing_cols}")

    # 2. Drop rows with nulls in critical identifiers (player_id, match_id)
    df = df.dropna(subset=['player_id', 'match_id'])

    # 3. Enforce data types and handle numeric conversions
    numeric_cols = ['ping', 'score', 'kills', 'deaths', 'match_duration_seconds']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # Drop rows where any numeric conversion resulted in NaN
    df = df.dropna(subset=numeric_cols)

    # 4. Enforce domain logic constraint (durations > 0, score/kills/deaths/ping >= 0)
    invalid_rows_mask = (
        (df['match_duration_seconds'] <= 0) |
        (df['ping'] < 0) |
        (df['score'] < 0) |
        (df['kills'] < 0) |
        (df['deaths'] < 0)
    )
    df = df[~invalid_rows_mask]

    # Convert numeric columns to appropriate integer/float types for consistency
    df['ping'] = df['ping'].astype(int)
    df['score'] = df['score'].astype(float)
    df['kills'] = df['kills'].astype(int)
    df['deaths'] = df['deaths'].astype(int)
    df['match_duration_seconds'] = df['match_duration_seconds'].astype(int)

    # 5. Deduplicate on (player_id, match_id)
    df = df.drop_duplicates(subset=['player_id', 'match_id'], keep='first')

    # 6. Normalize strings
    df['player_id'] = df['player_id'].astype(str).str.strip()
    df['match_id'] = df['match_id'].astype(str).str.strip()
    df['region'] = df['region'].astype(str).str.strip().str.title()
    df['device'] = df['device'].astype(str).str.strip().str.title()

    # 7. Compute derived columns
    df['score_per_second'] = df['score'] / df['match_duration_seconds']
    # kd_ratio uses deaths=1 if deaths is 0 to avoid division by zero
    df['kd_ratio'] = df['kills'] / np.maximum(df['deaths'], 1)

    final_row_count = len(df)
    dropped_count = initial_row_count - final_row_count

    print(f"Data Cleaning Pipeline: Loaded {initial_row_count} rows. Cleaned and retained {final_row_count} rows. Dropped {dropped_count} corrupt or duplicate rows.")

    return df.reset_index(drop=True)
