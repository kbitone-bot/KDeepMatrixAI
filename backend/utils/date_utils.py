import pandas as pd
import numpy as np


def convert_mixed_dates(column_series: pd.Series) -> pd.Series:
    """
    Convert a pandas Series containing mixed date formats.
    Handles Excel serial numbers and string dates.
    """
    numeric_dates = pd.to_numeric(column_series, errors='coerce')
    converted_from_numeric = pd.to_datetime(numeric_dates, unit='D', origin='1899-12-30', errors='coerce')
    converted_from_string = pd.to_datetime(column_series, errors='coerce')
    result = converted_from_numeric.fillna(converted_from_string)
    return pd.to_datetime(result, errors='coerce')


def ensure_datetime(df, columns):
    """Ensure specified columns are datetime type."""
    for col in columns:
        if col in df.columns:
            df[col] = convert_mixed_dates(df[col])
    return df
