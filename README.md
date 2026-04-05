# BioSync FHIR

This is the BioSync FHIR app for CS 6440. It's a two-part application: a frontend dashboard built in Streamlit and an API backend built in FastAPI.

## How it Works

The app connects simulated wearable metrics with real-world genetic data to create an interactive patient-provider data flow.

1. **Frontend (Streamlit)**: Contains two separate interfaces. The **Patient View** lets patients track their health data and manage privacy toggles (deciding what they want their doctor to see). The **Provider View** acts as the doctor's dashboard, hiding or showing data strictly based on those patient toggles.
2. **Backend (FastAPI)**: Acts as the central data hub. 
   - It simulates realistic wearable data (steps, sleep, heart rate) on the fly.
   - It connects directly to the official NCBI ClinVar API to pull real-world pathogenic data for the **ADRB3** and **APOE** genes, and structures the data internally using HL7 FHIR standards.
   - It connects to a Supabase cloud database to securely save and load the patient's privacy consent toggles.

---

## How to Run Locally

You'll need two terminal windows open to run the frontend and backend side-by-side. Before starting, make sure your `.env` file in the main folder has your `SUPABASE_URL`, `SUPABASE_KEY`, and `NCBI_API_KEY`.

### 1. Start the Backend API (Terminal 1)
Open a terminal, navigate into the backend folder, install the packages, and boot up the server:
```bash
cd backend
pip3 install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 2. Start the Frontend Dashboard (Terminal 2)
Open a second terminal in the root project folder, install the Streamlit packages, and launch the dashboard:
```bash
pip3 install streamlit plotly pandas python-dotenv
streamlit run app.py
```
*(The dashboard will automatically pop up in your browser at `http://localhost:8501`)*
