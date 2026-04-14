import unittest

from fintech.fraud_detector_service import app as fraud_app
from fintech.transaction_engine import app as transaction_app


class FintechIntegrationFlowTests(unittest.TestCase):
    def setUp(self):
        self.fraud_client = fraud_app.test_client()
        self.tx_client = transaction_app.test_client()

    def test_fraud_score_and_transaction_process(self):
        txn = {
            "transaction_id": "txn-100",
            "amount": 1500,
            "channel": "online",
            "country_code": "US",
            "merchant_category_code": "5732",
        }

        score_res = self.fraud_client.post("/score", json=txn)
        self.assertEqual(score_res.status_code, 200)
        self.assertIn("fraud_score", score_res.json)

        tx_res = self.tx_client.post(
            "/api/v1/transactions",
            json={
                "account_id": "acct-int-1",
                "amount": txn["amount"],
                "currency": "USD",
                "fraud_score": score_res.json["fraud_score"],
            },
        )
        self.assertEqual(tx_res.status_code, 201)
        self.assertIn(tx_res.json["status"], ["approved", "blocked"])


if __name__ == "__main__":
    unittest.main()
