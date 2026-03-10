import unittest

from healthcare.ehr_ingestion_service import app as ehr_app


class HealthcareIntegrationFlowTests(unittest.TestCase):
    def setUp(self):
        self.client = ehr_app.test_client()

    def test_ingest_and_query_patient_records(self):
        payload = {
            "patient_id": "patient-int-1",
            "resource_type": "Observation",
            "department": "emergency",
            "phi_flag": True,
        }

        ingest_res = self.client.post("/api/v1/ehr/ingest", json=payload)
        self.assertEqual(ingest_res.status_code, 201)

        read_res = self.client.get("/api/v1/ehr/patient/patient-int-1")
        self.assertEqual(read_res.status_code, 200)
        self.assertEqual(read_res.json["patient_id"], "patient-int-1")
        self.assertGreaterEqual(read_res.json["total"], 1)


if __name__ == "__main__":
    unittest.main()
