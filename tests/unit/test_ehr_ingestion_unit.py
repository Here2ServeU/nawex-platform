import unittest

from healthcare.ehr_ingestion_service import app, ehr_records


class EHRIngestionUnitTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        ehr_records.clear()

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["service"], "ehr-ingestion")

    def test_ingest_valid_record(self):
        payload = {
            "patient_id": "patient-1",
            "resource_type": "Observation",
            "department": "icu",
        }
        response = self.client.post("/api/v1/ehr/ingest", json=payload)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["status"], "accepted")

    def test_ingest_invalid_resource_type(self):
        payload = {
            "patient_id": "patient-2",
            "resource_type": "BadFHIRResource",
        }
        response = self.client.post("/api/v1/ehr/ingest", json=payload)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["status"], "rejected")
        self.assertEqual(response.json["reason"], "invalid_resource_type")


if __name__ == "__main__":
    unittest.main()
