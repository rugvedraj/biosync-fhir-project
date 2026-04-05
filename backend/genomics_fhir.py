import os

# Mapping clinical significace to LOINC code
CLINSIG_TO_LOINC = {
    "Pathogenic":              ("LA6668-3",  "Pathogenic"),
    "Likely pathogenic":       ("LA26332-9", "Likely pathogenic"),
    "Uncertain significance":  ("LA26333-7", "Uncertain significance"),
    "Likely benign":           ("LA26334-5", "Likely benign"),
    "Benign/Likely benign":    ("LA26334-5", "Likely benign"),
    "Benign":                  ("LA6675-8",  "Benign"),
    "risk factor":             ("LA26333-7", "Uncertain significance"), # Both map to uncertain because LOINC only has 5 tiers
    "association":             ("LA26333-7", "Uncertain significance"),
}


def build_variant_observation(
    patient_id: str,
    gene_name: str,
    hgvs: str,
    ref_seq: str,
    clinvar_significance: str,
    clinvar_id: str = None,
) -> dict:

    loinc_code, loinc_display = CLINSIG_TO_LOINC.get(
        clinvar_significance,
        ("LA26333-7", "Uncertain significance")
    )

    observation = {
        "resourceType": "Observation",
        "id": f"variant-{gene_name.lower()}-{patient_id}",
        "meta": {
            "profile": [
                "http://hl7.org/fhir/uv/genomics-reporting/StructureDefinition/variant"
            ]
        },
        "status": "final",
        "category": [{
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                "code": "laboratory",
                "display": "Laboratory"
            }]
        }],
        "code": {
            "coding": [{
                "system": "http://loinc.org",
                "code": "69548-6",
                "display": "Genetic variant assessment"
            }]
        },
        "subject": {
            "reference": f"Patient/{patient_id}"
        },
        "component": [
            {
                "code": {"coding": [{"system": "http://loinc.org", "code": "48018-6", "display": "Gene studied [ID]"}]},
                "valueCodeableConcept": {
                    "coding": [{"system": "http://www.genenames.org", "display": gene_name}],
                    "text": gene_name
                }
            },
            {
                "code": {"coding": [{"system": "http://loinc.org", "code": "81252-9", "display": "Discrete genetic variant"}]},
                "valueCodeableConcept": {
                    "coding": [{"system": "http://varnomen.hgvs.org", "code": hgvs, "display": hgvs}]
                }
            },
            {
                "code": {"coding": [{"system": "http://loinc.org", "code": "48013-7", "display": "Genomic reference sequence [ID]"}]},
                "valueCodeableConcept": {
                    "coding": [{"system": "http://www.ncbi.nlm.nih.gov/nuccore", "code": ref_seq}]
                }
            },
            {
                "code": {"coding": [{"system": "http://loinc.org", "code": "53037-8", "display": "Genetic variation clinical significance [Imp]"}]},
                "valueCodeableConcept": {
                    "coding": [{"system": "http://loinc.org", "code": loinc_code, "display": loinc_display}]
                }
            },
        ]
    }

    if clinvar_id:
        observation["note"] = [{
            "text": f"ClinVar Variation ID: {clinvar_id}. Significance retrieved dynamically at runtime."
        }]

    return observation