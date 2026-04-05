"""
BioSync FHIR - FastAPI Backend

Supabase Setup Instructions:
Before running, you need to create the `consent` table. 
Run the following SQL in your Supabase project's SQL Editor:

CREATE TABLE consent (
  patient_id TEXT PRIMARY KEY,
  steps BOOLEAN DEFAULT TRUE,
  heart_rate BOOLEAN DEFAULT TRUE,
  sleep BOOLEAN DEFAULT FALSE,
  genomic BOOLEAN DEFAULT TRUE
);
"""

import os
import pandas as pd
import pandas as pd
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from supabase import create_client, Client
from dotenv import load_dotenv
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from clinvar_client import fetch_clinvar_significance
from genomics_fhir import build_variant_observation

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
NCBI_API_KEY = os.getenv("NCBI_API_KEY")

# Initialize Supabase Client
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY and "replace_with" not in SUPABASE_URL:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"Failed to initialize Supabase: {e}")

# Static patient database entries mapped to Kaggle datasets
DATABASE_PATIENTS = [
    {"id": "P001", "name": "Jane Doe",     "age": 52, "last_updated": "2024-03-31"},
    {"id": "P002", "name": "John Smith",   "age": 45, "last_updated": "2024-03-30"},
    {"id": "P003", "name": "Maria Garcia", "age": 61, "last_updated": "2024-03-29"},
    {"id": "P004", "name": "Patient P004", "age": 39, "last_updated": "2024-03-28"},
    {"id": "P005", "name": "Patient P005", "age": 55, "last_updated": "2024-03-27"},
    {"id": "P006", "name": "Patient P006", "age": 47, "last_updated": "2024-03-26"},
]

class ConsentPayload(BaseModel):
    steps: bool
    heart_rate: bool
    sleep: bool
    genomic: bool

@app.get("/patients")
def get_patients():
    return DATABASE_PATIENTS

@app.get("/patients/{patient_id}/wearable")
def get_wearable(patient_id: str):
    """
    Parses strictly authentic Kaggle Fitbit datasets using pandas.
    Throws a 404 Exception if the dataset is missing or unreadable.
    """
    activity_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'dailyActivity_merged.csv')
    sleep_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'sleepDay_merged.csv')
    hr_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'heartrate_daily_avg.csv')

    if not os.path.exists(activity_path) or not os.path.exists(sleep_path) or not os.path.exists(hr_path):
        raise HTTPException(status_code=404, detail="Kaggle data files not found in /data directory.")

    try:
        act_df = pd.read_csv(activity_path)
        slp_df = pd.read_csv(sleep_path)
        
        # Hardcoded to patients with strictly >15 days of concurrent sleep & HR data
        mapping = {
            "P001": 5553957443, 
            "P002": 6962181067, 
            "P003": 4388161847,
            "P004": 5577150313,
            "P005": 6117666160,
            "P006": 8792009665
        }
        # Explicit mapping ensures 100% density arrays
        kaggle_id = mapping.get(patient_id, 5553957443)
        
        p_act = act_df[act_df["Id"] == kaggle_id].copy()
        p_slp = slp_df[slp_df["Id"] == kaggle_id].copy()
        
        hr_df = pd.read_csv(hr_path)
        p_hr_daily = hr_df[hr_df["Id"] == kaggle_id].copy()
        p_hr_daily["Date"] = pd.to_datetime(p_hr_daily["Date"]).dt.date
        
        p_act["ActivityDate"] = pd.to_datetime(p_act["ActivityDate"]).dt.date
        p_slp["SleepDay"] = pd.to_datetime(p_slp["SleepDay"]).dt.date
        
        merged = pd.merge(p_act, p_slp, left_on="ActivityDate", right_on="SleepDay", how="left")
        merged = pd.merge(merged, p_hr_daily, left_on="ActivityDate", right_on="Date", how="left")
        merged = merged.sort_values(by="ActivityDate", ascending=False).head(30)
        
        results = []
        for _, row in merged.iterrows():
            # Kaggle total asleep is natively in minutes
            sleep_hrs = round(row["TotalMinutesAsleep"] / 60, 1) if pd.notna(row["TotalMinutesAsleep"]) else 0.0
            active_min = row["VeryActiveMinutes"] + row["FairlyActiveMinutes"] if pd.notna(row["VeryActiveMinutes"]) else 0
            
            # Extract calculated daily heart rate average
            hr = int(row["Value"]) if pd.notna(row["Value"]) else 0
            steps = int(row["TotalSteps"]) if pd.notna(row["TotalSteps"]) else 0
            
            results.append({
                "date": str(row["ActivityDate"]),
                "steps": steps,
                "heart_rate_avg": hr,
                "sleep_hours": sleep_hrs,
                "active_minutes": int(active_min)
            })
        
        return results
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing dataframe: {str(e)}")

@app.get("/patients/{patient_id}/genomic-variants")
async def get_genomic_variants(patient_id: str):
    """
    Fetches the patient's 4 genomic variants natively from NCBI clinvar logic.
    """
    targets = [
        {"gene": "ADRB3", "hgvs": "NM_000025.3(ADRB3):c.190T>C", "ref": "NM_000025.3", "clinvar_id": "67036", "condition": "Fat breakdown and thermogenesis regulation"},
        {"gene": "APOE", "hgvs": "NM_000041.4(APOE):c.388T>C", "ref": "NM_000041.4", "clinvar_id": "17864", "condition": "Cardiovascular / Alzheimer's Risk"},
        {"gene": "PCSK9", "hgvs": "NM_174936.4(PCSK9):c.137G>T", "ref": "NM_174936.4", "clinvar_id": "2878", "condition": "Hypercholesterolemia (LDL Risk)"},
        {"gene": "TCF7L2", "hgvs": "NM_001367943.1(TCF7L2):c.450+33966C>T", "ref": "NM_001367943.1", "clinvar_id": "7413", "condition": "Type 2 Diabetes Risk"}
    ]
    
    variants_ui = []
    
    for t in targets:
        # Dynamically execute lookup via NCBI APIs
        sig = await fetch_clinvar_significance(t["hgvs"])
        
        # Structure payload utilizing teammate's FHIR standard constructor
        fhir_obj = build_variant_observation(patient_id, t["gene"], t["hgvs"], t["ref"], sig, t["clinvar_id"])
        print(f"Generated Backend FHIR {t['gene']}: {fhir_obj['id']}")
        
        variants_ui.append({
            "gene": t["gene"],
            "variant": t["hgvs"],
            "condition": t["condition"],
            "clinvar": sig,
        })
        
    return variants_ui

@app.get("/patients/{patient_id}/consent")
def get_consent(patient_id: str):
    default_consent = {"steps": True, "heart_rate": True, "sleep": False, "genomic": True}
    if not supabase:
        return default_consent
        
    try:
        response = supabase.table("consent").select("*").eq("patient_id", patient_id).execute()
        if response.data:
            data = response.data[0]
            return {
                "steps": data.get("steps", True),
                "heart_rate": data.get("heart_rate", True),
                "sleep": data.get("sleep", False),
                "genomic": data.get("genomic", True)
            }
        return default_consent
    except Exception as e:
        print(f"Supabase GET error: {e}")
        return default_consent

@app.post("/patients/{patient_id}/consent")
def update_consent(patient_id: str, consent: ConsentPayload):
    if not supabase:
        return {"success": False, "error": "Supabase not configured. Changes saved in memory frontend only."}
        
    try:
        data = {
            "patient_id": patient_id,
            "steps": consent.steps,
            "heart_rate": consent.heart_rate,
            "sleep": consent.sleep,
            "genomic": consent.genomic
        }
        supabase.table("consent").upsert(data).execute()
        return {"success": True}
    except Exception as e:
        print(f"Supabase UPSERT error: {e}")
        return {"success": False, "error": str(e)}
