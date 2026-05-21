import json
import tempfile
import unittest
from pathlib import Path

from db_manager import HealthDatabase
from web_server import create_app


class WebServerTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_health_data.db"
        self.app = create_app(db_path=str(self.db_path))
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_index_route_returns_html(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("健康監測系統", response.get_data(as_text=True))
        self.assertIn("<canvas id=\"trend-chart\"></canvas>", response.get_data(as_text=True))

    def test_api_health_returns_ok_when_db_available(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["db"], "connected")
        self.assertIn("timestamp", data)

    def test_api_data_default_returns_empty_arrays(self):
        response = self.client.get("/api/data")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["heart_rate"], [])
        self.assertEqual(data["spo2"], [])
        self.assertEqual(data["time"], [])
        self.assertEqual(data["count"], 0)

    def test_api_data_invalid_seconds_returns_400(self):
        response = self.client.get("/api/data?seconds=0")
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("error", data)

    def test_api_latest_returns_no_data_on_empty_db(self):
        response = self.client.get("/api/latest")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "no_data")
        self.assertIsNone(data["heart_rate"])
        self.assertIsNone(data["spo2"])
        self.assertIsNone(data["timestamp"])

    def test_api_latest_status_warning_for_out_of_range_values(self):
        db = HealthDatabase(db_name=str(self.db_path))
        db.insert_record(55.0, 98.0)

        response = self.client.get("/api/latest")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "warning")
        self.assertEqual(data["heart_rate"], 55.0)
        self.assertEqual(data["spo2"], 98.0)

    def test_api_data_count_matches_array_length(self):
        db = HealthDatabase(db_name=str(self.db_path))
        db.insert_record(72.0, 97.0)
        db.insert_record(74.0, 96.5)

        response = self.client.get("/api/data?seconds=60")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["count"], len(data["heart_rate"]))
        self.assertEqual(len(data["heart_rate"]), len(data["spo2"]))
        self.assertEqual(len(data["heart_rate"]), len(data["time"]))


if __name__ == "__main__":
    unittest.main()
