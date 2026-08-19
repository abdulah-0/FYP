"""
Preprocess module for Algerian Forest Fires dataset & Edge Sensor Data.
Cleans raw data, handles anomalies, engineers rate-of-change and synthetic smoke/gas proxy features,
and assigns 4-tier fire risk labels: Safe (0), Warning (1), High Risk (2), Fire Detected (3).
"""

import os
from pathlib import Path
import numpy as np
import pandas as pd


RISK_TIERS = {
    0: "Safe",
    1: "Warning",
    2: "High Risk",
    3: "Fire Detected"
}

FEATURE_COLUMNS = [
    "Temperature",
    "RH",
    "Ws",
    "Rain",
    "Gas_ppm",
    "Smoke_ppm",
    "Delta_Temp",
    "Delta_RH"
]


def load_raw_algerian_dataset(csv_path: str) -> pd.DataFrame:
    """
    Reads the Algerian forest fire dataset CSV, skipping non-data header lines and stripping whitespace.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Dataset not found at {csv_path}")

    with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    clean_lines = []
    header_found = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Skip region separator headers like 'Sidi-Bel Abbes Region Dataset'
        if "Region Dataset" in stripped or "day,month,year" in stripped:
            if not header_found and "day,month,year" in stripped:
                clean_lines.append(stripped)
                header_found = True
            continue
        clean_lines.append(stripped)

    import io
    df = pd.read_csv(io.StringIO("\n".join(clean_lines)))
    
    # Strip whitespace from column names and string values
    df.columns = [c.strip() for c in df.columns]
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].astype(str).str.strip()

    # Drop non-numeric invalid rows
    df = df[pd.to_numeric(df["Temperature"], errors="coerce").notnull()].copy()

    # Convert columns to float/int
    numeric_cols = ["day", "month", "year", "Temperature", "RH", "Ws", "Rain", "FFMC", "DMC", "DC", "ISI", "BUI", "FWI"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna().reset_index(drop=True)
    return df


def engineer_sensor_features(df: pd.DataFrame, random_seed: int = 42) -> pd.DataFrame:
    """
    Synthesizes MQ-2 Gas and Smoke readings and calculates rate-of-change features (Delta_Temp, Delta_RH).
    
    Combustion physics proxy:
    - In Safe/Low fire conditions: Gas_ppm (ambient ~10-40 ppm), Smoke_ppm (~5-25 ppm).
    - In Fire/High risk conditions: Gas_ppm spikes (100-800+ ppm), Smoke_ppm spikes (80-600+ ppm).
    """
    np.random.seed(random_seed)
    df = df.copy()

    is_fire = df["Classes"].str.lower().str.contains("fire") & (~df["Classes"].str.lower().str.contains("not"))
    fwi = df["FWI"].values if "FWI" in df.columns else np.where(is_fire, 15.0, 1.0)
    temp = df["Temperature"].values
    rh = df["RH"].values

    # Base combustion index from FWI, temp, and rh
    combustion_factor = np.clip((fwi / 15.0) * (temp / 30.0) * (100.0 - rh) / 50.0, 0.1, 8.0)

    # Ambient vs fire gas/smoke proxy
    base_gas = np.where(is_fire, 250.0 * combustion_factor, 25.0 + 10.0 * (temp / 35.0))
    base_smoke = np.where(is_fire, 200.0 * combustion_factor, 15.0 + 8.0 * (100.0 - rh) / 60.0)

    noise_gas = np.random.normal(0, 15.0, size=len(df))
    noise_smoke = np.random.normal(0, 10.0, size=len(df))

    df["Gas_ppm"] = np.clip(np.round(base_gas + noise_gas, 2), 5.0, 1000.0)
    df["Smoke_ppm"] = np.clip(np.round(base_smoke + noise_smoke, 2), 2.0, 800.0)

    # Compute rate of change (Delta over consecutive samples)
    df["Delta_Temp"] = df["Temperature"].diff().fillna(0.0)
    df["Delta_RH"] = df["RH"].diff().fillna(0.0)

    # Assign 4-tier target label:
    # 0: Safe (not fire & low FWI & low gas)
    # 1: Warning (not fire but elevated temp > 30 or low RH < 50 or FWI > 5)
    # 2: High Risk (fire weather index high or gas > 150 or temp > 35)
    # 3: Fire Detected (fire flag true & high gas/smoke)
    labels = []
    for idx, row in df.iterrows():
        fire_flag = is_fire.iloc[idx]
        t = row["Temperature"]
        r = row["RH"]
        gas = row["Gas_ppm"]
        smoke = row["Smoke_ppm"]
        fwi_val = row.get("FWI", 0.0)

        if fire_flag and (gas > 200 or smoke > 150 or fwi_val > 10):
            labels.append(3)  # Fire Detected
        elif fire_flag or (gas > 120 or (t >= 35 and r <= 45)):
            labels.append(2)  # High Risk
        elif t >= 30 or r <= 55 or fwi_val > 3:
            labels.append(1)  # Warning
        else:
            labels.append(0)  # Safe

    df["Risk_Tier"] = labels
    return df


def prepare_and_save_dataset(raw_path: str, output_path: str) -> pd.DataFrame:
    """Preprocesses raw dataset and saves clean processed CSV."""
    df_raw = load_raw_algerian_dataset(raw_path)
    df_processed = engineer_sensor_features(df_raw)
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df_processed.to_csv(output_path, index=False)
    return df_processed


if __name__ == "__main__":
    raw_file = "data/raw/Algerian_forest_fires_dataset.csv"
    processed_file = "data/processed/forest_fire_processed.csv"
    print(f"Loading raw data from: {raw_file}")
    df = prepare_and_save_dataset(raw_file, processed_file)
    print(f"Processed dataset saved to: {processed_file} with shape {df.shape}")
    print("Risk tier distribution:")
    print(df["Risk_Tier"].value_counts().rename(index=RISK_TIERS))
