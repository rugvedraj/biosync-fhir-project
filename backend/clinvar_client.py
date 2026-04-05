import os
import httpx
from dotenv import load_dotenv

load_dotenv()

NCBI_API_KEY = os.getenv("NCBI_API_KEY")

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

async def fetch_clinvar_significance(hgvs: str) -> str:
    print(f"[API CALL] Querying ClinVar for: {hgvs}")
    async with httpx.AsyncClient() as client:
        try:
            search_resp = await client.get(ESEARCH_URL, params={
                "db": "clinvar",
                "term": f"{hgvs}[HGVS]",
                "retmode": "json",
                "api_key": NCBI_API_KEY,
            }, timeout=7.0)
            id_list = search_resp.json().get("esearchresult", {}).get("idlist", [])

            if not id_list:
                significance = "Uncertain significance"
                print(f"[NOT FOUND] Defaulting to: {significance}")
                return significance

            summary_resp = await client.get(ESUMMARY_URL, params={
                "db": "clinvar",
                "id": id_list[0],
                "retmode": "json",
                "api_key": NCBI_API_KEY,
            }, timeout=7.0)
        
            result = summary_resp.json().get("result", {})
            variant_data = result.get(id_list[0], {})

            significance = (
                variant_data
                .get("germline_classification", {})
                .get("description", "Uncertain significance")
            )
            print(f"[FOUND] {hgvs} → {significance}")
            return significance
        except Exception as e:
            print(f"[API ERROR] {e}")
            return "Uncertain significance"