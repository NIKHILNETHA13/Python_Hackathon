import unittest

from app import app


class DashboardAppTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_devices_endpoint_returns_json(self):
        response = self.client.get('/api/devices')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn('devices', payload)

    def test_history_endpoint_returns_json(self):
        response = self.client.get('/api/history')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn('datasets', payload)


if __name__ == '__main__':
    unittest.main()
