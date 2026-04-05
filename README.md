# BioSync FHIR

This is the BioSync FHIR app for CS 6440. It's a two-part application: a frontend dashboard built in Streamlit and an API backend built in FastAPI.

## How it Works

The app connects authentic, patient-level wearable metrics with real-world genetic data to create an interactive patient-provider data flow.

1. **Frontend (Streamlit)**: Contains two separate interfaces. The **Patient View** lets patients track their health data and manage privacy toggles (deciding what they want their doctor to see). The **Provider View** acts as the doctor's dashboard, hiding or showing data strictly based on those patient toggles.
2. **Backend (FastAPI)**: Acts as the central data hub. 
   - It reads and parses authentic Fitbit data directly from a static Kaggle dataset utilizing `pandas` dataframes.
   - It connects directly to the official NCBI ClinVar API to pull real-world pathogenic data for 4 distinct variants (**ADRB3**, **APOE**, **PCSK9**, and **TCF7L2**), structuring the data internally using strict HL7 FHIR standards.
   - It connects natively to a Supabase cloud database to securely save and load the patient's privacy consent toggles.

---

## Access the App

The backend API is officially deployed and accessible on Render. You can directly interact with the live FHIR endpoints by sending requests here:  
**Live Endpoint:** [https://biosync-fhir-project-backend.onrender.com](https://biosync-fhir-project-backend.onrender.com)

If you have deployed the frontend natively to Streamlit Cloud, the Streamlit app automatically proxies all patient requests directly to this Render address via its configured Secrets file.
