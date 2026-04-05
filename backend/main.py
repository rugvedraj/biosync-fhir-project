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
import random
from datetime import datetime, timedelta
from fastapi import FastAPI
from pydantic import BaseModel
from supabase import create_client, Client
from dotenv import load_dotenv

import pandas as pd
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

_MOCK_PATIENTS = [
    {"id": "P001", "name": "Jane Doe",     "age": 52, "last_updated": "2024-03-31"},
    {"id": "P002", "name": "John Smith",   "age": 45, "last_updated": "2024-03-30"},
    {"id": "P003", "name": "Maria Garcia", "age": 61, "last_updated": "2024-03-29"},
]

class ConsentPayload(BaseModel):
    steps: bool
    heart_rate: bool
    sleep: bool
    genomic: bool

@app.get("/patients")
def get_patients():
    return _MOCK_PATIENTS

@app.get("/patients/{patient_id}/wearable")
def get_wearable(patient_id: str):
    """
    Parses real Kaggle Fitbit datasets using pandas.
    Falls back to synthetic generation if CSVs aren't properly mounted in the data/ folder.
    """
    activity_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'dailyActivity_merged.csv')
    sleep_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'sleepDay_merged.csv')

    # Kaggle Real Data Parsing Pipeline
    if os.path.exists(activity_path) and os.path.exists(sleep_path):
        try:
            act_df = pd.read_csv(activity_path)
            slp_df = pd.read_csv(sleep_path)
            
            unique_ids = act_df["Id"].unique()
            # Deterministic hash to map our patient_ids (e.g. 'P001') to a real Kaggle user
            kaggle_id = unique_ids[sum(ord(c) for c in patient_id) % len(unique_ids)]
            
            p_act = act_df[act_df["Id"] == kaggle_id].copy()
            p_slp = slp_df[slp_df["Id"] == kaggle_id].copy()
            
            p_act["ActivityDate"] = pd.to_datetime(p_act["ActivityDate"]).dt.date
            p_slp["SleepDay"] = pd.to_datetime(p_slp["SleepDay"]).dt.date
            
            merged = pd.merge(p_act, p_slp, left_on="ActivityDate", right_on="SleepDay", how="left")
            merged = merged.sort_values(by="ActivityDate", ascending=False).head(30)
            
            results = []
            for _, row in merged.iterrows():
                # Kaggle total asleep is natively in minutes
                sleep_hrs = round(row["TotalMinutesAsleep"] / 60, 1) if pd.notna(row["TotalMinutesAsleep"]) else round(random.uniform(5.0, 8.5), 1)
                active_min = row["VeryActiveMinutes"] + row["FairlyActiveMinutes"] if pd.notna(row["VeryActiveMinutes"]) else random.randint(20, 80)
                
                # Simulating HR safely as heartrate_seconds_merged.csv is too heavy for single endpoint queries
                random.seed(f"{patient_id}_{row['ActivityDate']}")
                
                results.append({
                    "date": str(row["ActivityDate"]),
                    "steps": int(row["TotalSteps"]) if pd.notna(row["TotalSteps"]) else random.randint(3000, 10000),
                    "heart_rate_avg": random.randint(60, 88),
                    "sleep_hours": sleep_hrs,
                    "active_minutes": int(active_min)
                })
            
            if results:
                return results
                
        except Exception as e:
            print(f"Error parsing Kaggle datasets, falling back dynamically: {e}")

    # Synthetic fallback logic if data/ files are entirely missing
    random.seed(patient_id)
    dates = [datetime.today() - timedelta(days=i) for i in range(30)]
    dates.reverse()
    return [
        {
            "date": str(d.date()),
            "steps": random.randint(3500, 13000),
            "heart_rate_avg": random.randint(60, 88),
            "sleep_hours": round(random.uniform(4.5, 8.5), 1),
            "active_minutes": random.randint(15, 95),
        }
        for d in dates
    ]

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
