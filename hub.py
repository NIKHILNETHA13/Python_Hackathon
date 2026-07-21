# hub.py
# This file contains the IoTHub class.
# OOP Concepts demonstrated: Encapsulation, Polymorphism

# ============================================================
# IoTHub manages all sensors through a single list.
# It never checks the type of sensor.
# It only calls read() and status() — the abstract interface.
# This is pure POLYMORPHISM.
# ============================================================

class IoTHub:

    def __init__(self, hub_name):
        # ENCAPSULATION — hub data is private.
        self.__hub_name = hub_name
        self.__devices  = []   # One list holds ALL sensor types.

    def get_hub_name(self):
        return self.__hub_name

    # Add any SensorDevice subclass to the hub.
    def add_device(self, sensor):
        self.__devices.append(sensor)

    # Remove a sensor by its ID.
    def remove_device(self, device_id):
        for sensor in self.__devices:
            if sensor.get_id() == device_id:
                self.__devices.remove(sensor)
                return True
        return False

    # Find a sensor by its ID.
    def get_device(self, device_id):
        for sensor in self.__devices:
            if sensor.get_id() == device_id:
                return sensor
        return None

    # POLYMORPHISM — poll every sensor the same way.
    # No if/elif checks. No type checking. Just read() and status().
    def poll_devices(self):
        results = []
        for sensor in self.__devices:
            results.append({
                "id":      sensor.get_id(),
                "name":    sensor.get_name(),
                "reading": sensor.read(),     # Polymorphic call
                "status":  sensor.status()    # Polymorphic call
            })
        return results

    # Return summary statistics for the dashboard.
    def display_status(self):
        total   = len(self.__devices)
        active  = 0
        offline = 0

        for sensor in self.__devices:
            if sensor.status() == "Active":
                active += 1
            elif sensor.status() == "Offline":
                offline += 1

        return {
            "hub_name":    self.__hub_name,
            "total":       total,
            "active":      active,
            "offline":     offline,
            "low_battery": total - active - offline
        }