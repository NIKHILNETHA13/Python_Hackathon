import os
import tempfile
import unittest

from config import BASE_DIR
import database


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        os.environ["SQLITE_DB_PATH"] = self.temp_db.name
        os.environ["DB_ENGINE"] = "sqlite"
        database.init_db()

    def tearDown(self):
        if os.path.exists(self.temp_db.name):
            try:
                os.remove(self.temp_db.name)
            except OSError:
                pass

    def test_init_db_creates_tables(self):
        devices = database.get_all_devices()
        self.assertIsInstance(devices, list)
        self.assertEqual(len(devices), 0)

    def test_device_crud_operations(self):
        device_id = database.create_device("TEMP-101", "Temperature", location="Living Room", status="Active")
        self.assertIsNotNone(device_id)

        devices = database.get_all_devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["device_name"], "TEMP-101")
        self.assertEqual(devices[0]["device_type"], "Temperature")

        saved = database.save_reading(device_id, "24.5", "°C", "Normal temp")
        self.assertTrue(saved)

        history = database.get_reading_history(device_id=device_id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["sensor_value"], "24.5")

        updated = database.update_device(device_id, status="Inactive")
        self.assertTrue(updated)

        devices_after_update = database.get_all_devices()
        self.assertEqual(devices_after_update[0]["status"], "Inactive")

        deleted = database.delete_device(device_id)
        self.assertTrue(deleted)
        self.assertEqual(len(database.get_all_devices()), 0)


if __name__ == "__main__":
    unittest.main()
