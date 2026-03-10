import unittest

from fintech.transaction_engine import app as tx_app


class SecurityHeaderTests(unittest.TestCase):
    def setUp(self):
        self.client = tx_app.test_client()

    def test_health_response_is_json(self):
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_json)


if __name__ == '__main__':
    unittest.main()
