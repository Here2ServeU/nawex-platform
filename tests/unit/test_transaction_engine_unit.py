import unittest

from fintech.transaction_engine import app, transactions


class TransactionEngineUnitTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        transactions.clear()

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["service"], "transaction-engine")

    def test_process_transaction_approves_low_risk(self):
        payload = {
            "account_id": "acct_1",
            "amount": 42.0,
            "fraud_score": 0.10,
        }
        response = self.client.post("/api/v1/transactions", json=payload)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["status"], "approved")

    def test_process_transaction_blocks_high_risk(self):
        payload = {
            "account_id": "acct_2",
            "amount": 4200.0,
            "fraud_score": 0.95,
        }
        response = self.client.post("/api/v1/transactions", json=payload)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["status"], "blocked")
        self.assertEqual(response.json["reason"], "fraud_score_exceeded")


if __name__ == "__main__":
    unittest.main()
