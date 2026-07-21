# sensor.py
# This file contains the abstract base class and all sensor subclasses.
# OOP Concepts demonstrated: Abstraction, Inheritance, Encapsulation, Constructors, Polymorphism

from abc import ABC, abstractmethod


# ============================================================
# ABSTRACTION
# SensorDevice is an abstract class.
# It defines WHAT every sensor must do, but NOT HOW.
# You cannot create a SensorDevice() object directly.
# ============================================================
class SensorDevice(ABC):

    # CONSTRUCTOR
    # Every sensor must be initialized with these four values.
    def __init__(self, device_id, device_name, reading, device_status):

        # ENCAPSULATION
        # All attributes are private (double underscore prefix).
        # They cannot be accessed or changed directly from outside.
        self.__device_id     = device_id
        self.__device_name   = device_name
        self.__reading       = reading
        self.__device_status = device_status

    # ---------- Getters ----------
    # Controlled read access to private attributes.

    def get_id(self):
        return self.__device_id

    def get_name(self):
        return self.__device_name

    def get_reading(self):
        return self.__reading

    def get_status(self):
        return self.__device_status

    # ---------- Setters ----------
    # Controlled write access to private attributes.

    def set_reading(self, value):
        self.__reading = value

    def set_status(self, value):
        self.__device_status = value

    # ---------- Abstract Methods ----------
    # Every subclass MUST implement these two methods.
    # This is the contract that enables polymorphism.

    @abstractmethod
    def read(self):
        # Returns a formatted reading string (e.g. "30°C")
        pass

    @abstractmethod
    def status(self):
        # Returns the current status string (e.g. "Active")
        pass


# ============================================================
# INHERITANCE
# Each sensor inherits from SensorDevice.
# Each sensor fulfills the abstract contract by implementing
# read() and status() in its own way — this is POLYMORPHISM.
# ============================================================

class TemperatureSensor(SensorDevice):

    def __init__(self, device_id, reading="0", device_status="Active"):
        # Call the parent constructor to initialize shared attributes.
        super().__init__(device_id, "Temperature", reading, device_status)

    # POLYMORPHISM — read() behaves differently for each sensor type.
    def read(self):
        return self.get_reading() + "°C"

    def status(self):
        return self.get_status()


class HumiditySensor(SensorDevice):

    def __init__(self, device_id, reading="0", device_status="Active"):
        super().__init__(device_id, "Humidity", reading, device_status)

    def read(self):
        return self.get_reading() + "%"

    def status(self):
        return self.get_status()


class PressureSensor(SensorDevice):

    def __init__(self, device_id, reading="0", device_status="Active"):
        super().__init__(device_id, "Pressure", reading, device_status)

    def read(self):
        return self.get_reading() + " hPa"

    def status(self):
        return self.get_status()


class MotionSensor(SensorDevice):

    def __init__(self, device_id, reading="No Motion", device_status="Active"):
        super().__init__(device_id, "Motion", reading, device_status)

    def read(self):
        # Motion sensor returns a descriptive label instead of a number.
        value = self.get_reading()
        if value == "1":
            return "Motion Detected"
        return "No Motion"

    def status(self):
        return self.get_status()


class LightSensor(SensorDevice):
    def __init__(self, device_id, reading="0", device_status="Active"):
        super().__init__(device_id, "Light", reading, device_status)

    def read(self):
        # lux value
        return self.get_reading() + " lx"

    def status(self):
        return self.get_status()


class GasSensor(SensorDevice):
    def __init__(self, device_id, reading="0", device_status="Active"):
        super().__init__(device_id, "Gas", reading, device_status)

    def read(self):
        return self.get_reading() + " ppm"

    def status(self):
        return self.get_status()


# ============================================================
# Central Sensor Registry
# ============================================================
# A simple dictionary that holds metadata for every sensor type.
# To add a new sensor type: create a subclass of SensorDevice
# and then register it using `register_sensor(...)` below.
# This file is the single source-of-truth for sensor metadata.
# ============================================================

SENSOR_REGISTRY = {}


def register_sensor(name, sensor_class, *, unit="", icon="🔌", default_reading="0", default_status="Active", prefix=None):
    """Register a sensor class with metadata.

    name: Display name (e.g. "Temperature")
    sensor_class: The class object (subclass of SensorDevice)
    unit: Unit string appended to read() formatted output (for client hints)
    icon: Emoji or short icon string for UI
    default_reading: Default raw reading value for new devices
    default_status: Default device status
    prefix: ID prefix (e.g. 'T' for Temperature). If None a prefix will be derived.
    """
    if prefix is None:
        prefix = name[0].upper()

    SENSOR_REGISTRY[name] = {
        "class": sensor_class,
        "unit": unit,
        "icon": icon,
        "default_reading": default_reading,
        "default_status": default_status,
        "prefix": prefix
    }


# Helper: convenience decorator for lightweight registration
def register(name, **kwargs):
    def _decorator(cls):
        register_sensor(name, cls, **kwargs)
        return cls
    return _decorator


# Register existing sensors in the registry so other modules can
# read the available sensors and their metadata without hardcoding.
register_sensor("Temperature", TemperatureSensor, unit="°C", icon="🌡️", default_reading="0", default_status="Active", prefix="T")
register_sensor("Humidity", HumiditySensor, unit="%", icon="💧", default_reading="0", default_status="Active", prefix="H")
register_sensor("Pressure", PressureSensor, unit=" hPa", icon="⏲️", default_reading="1013", default_status="Active", prefix="P")
register_sensor("Motion", MotionSensor, unit="", icon="🏃", default_reading="0", default_status="Active", prefix="M")
register_sensor("Light", LightSensor, unit=" lx", icon="💡", default_reading="500", default_status="Active", prefix="L")
register_sensor("Gas", GasSensor, unit=" ppm", icon="💨", default_reading="100", default_status="Active", prefix="G")

