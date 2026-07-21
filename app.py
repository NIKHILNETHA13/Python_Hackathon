# app.py
# This file connects the OOP backend to the web interface using Flask.
# Flask routes receive HTTP requests and return JSON or HTML responses.

from flask import Flask, render_template, request, jsonify
import inspect
import sensor as sensor_module
from sensor import SensorDevice, SENSOR_REGISTRY
from hub import IoTHub
from automation import AutomationController
from events import EventLog

app = Flask(__name__)

# ============================================================
# Create one IoTHub instance.
# This hub persists for the entire session (in-memory).
# ============================================================
hub = IoTHub("My IoT Hub")

# Global event log
event_log = EventLog()

# Start automation controller with event logging
automation = AutomationController(hub, event_log=event_log)
automation.start()

# Counters and prefixes generated dynamically
id_counters = {}
id_prefix = {}

def get_sensor_id_params(sensor_type):
    if sensor_type not in id_counters:
        # Use registry to determine default prefix, fall back to first letter
        if sensor_type in SENSOR_REGISTRY:
            id_prefix[sensor_type] = SENSOR_REGISTRY[sensor_type].get("prefix", sensor_type[0].upper())
            # start counters by group to avoid collisions; base on number of existing types
            id_counters[sensor_type] = (len(id_counters) + 1) * 100
        else:
            prefix = sensor_type[0].upper()
            used_prefixes = list(id_prefix.values())
            if prefix in used_prefixes:
                for char in sensor_type[1:]:
                    if char.upper() not in used_prefixes:
                        prefix = char.upper()
                        break
                else:
                    prefix = prefix + str(len(used_prefixes))
            id_prefix[sensor_type] = prefix
            id_counters[sensor_type] = (len(id_counters) + 1) * 100

    return id_prefix[sensor_type], id_counters[sensor_type]


# ============================================================
# Page Routes
# ============================================================

@app.route("/")
def simulator():
    """Render the Sensor Simulator page."""
    return render_template("simulator.html")


@app.route("/dashboard")
def dashboard():
    """Render the IoT Hub Dashboard page."""
    return render_template("dashboard.html")


@app.route('/smarthome')
def smarthome():
    """Smart Home Dashboard page."""
    return render_template('smarthome.html')


# ============================================================
# API Routes
# ============================================================

@app.route("/api/add_sensor", methods=["POST"])
def add_sensor():
    """Add a new sensor to the IoTHub."""

    data = request.get_json()
    sensor_type = data.get("type")

    # Use central registry to find sensor class/metadata
    meta = SENSOR_REGISTRY.get(sensor_type)
    if meta is None:
        return jsonify({"error": f"Sensor type {sensor_type} not supported"}), 400
    sensor_class = meta.get("class")

    # Retrieve or generate ID settings dynamically
    prefix, counter = get_sensor_id_params(sensor_type)
    id_counters[sensor_type] += 1
    new_id = prefix + str(id_counters[sensor_type])

    # Instantiate sensor dynamically using default reading/status from registry when available
    default_reading = meta.get("default_reading") if meta else None
    default_status = meta.get("default_status") if meta else None

    if default_reading is not None and default_status is not None:
        sensor = sensor_class(new_id, reading=str(default_reading), device_status=str(default_status))
    else:
        sensor = sensor_class(new_id)
    hub.add_device(sensor)

    return jsonify({
        "message": "Sensor added successfully",
        "id": new_id
    })


@app.route("/api/sensor_types")
def get_sensor_types():
    """List all supported sensor types dynamically from the sensor module subclasses."""
    types = []
    for name, meta in SENSOR_REGISTRY.items():
        types.append({
            "name": name,
            "unit": meta.get("unit", ""),
            "icon": meta.get("icon", "🔌"),
            "default_reading": meta.get("default_reading"),
            "default_status": meta.get("default_status"),
            "prefix": meta.get("prefix")
        })
    # Return a list of metadata objects
    return jsonify({"types": sorted(types, key=lambda x: x["name"])})



@app.route("/api/remove_sensor", methods=["POST"])
def remove_sensor():
    """Remove a sensor from the hub."""

    data = request.get_json()
    device_id = data.get("id")

    removed = hub.remove_device(device_id)

    if removed:
        return jsonify({"message": "Sensor removed successfully"})

    return jsonify({"error": "Sensor not found"}), 404


@app.route("/api/update_sensor", methods=["POST"])
def update_sensor():
    """Update sensor reading and status."""

    data = request.get_json()

    device_id = data.get("id")
    reading = data.get("reading")
    status = data.get("status")

    sensor = hub.get_device(device_id)

    if sensor is None:
        return jsonify({"error": "Sensor not found"}), 404

    # Encapsulation: only update provided non-empty fields
    old_reading = sensor.get_reading()
    old_status = sensor.get_status()

    if reading is not None and str(reading).strip() != "":
        sensor.set_reading(reading)
    if status is not None and str(status).strip() != "":
        sensor.set_status(status)

    # Log changes
    try:
        if event_log:
            if sensor.get_reading() != old_reading:
                # icon by sensor name
                icons = {"Temperature": "🌡️", "Humidity": "💧", "Pressure": "⏲️", "Motion": "🏃", "Light": "💡", "Gas": "💨"}
                icon = icons.get(sensor.get_name(), "🔌")
                event_log.add(icon, f"{sensor.get_name()} {sensor.get_id()} reading updated to {sensor.get_reading()}")
            if sensor.get_status() != old_status:
                event_log.add("🔁", f"{sensor.get_name()} {sensor.get_id()} status changed to {sensor.get_status()}")
    except Exception:
        pass

    return jsonify({"message": "Sensor updated successfully"})


@app.route("/api/sensors")
def get_sensors():
    """Return all sensors for Simulator and Dashboard."""

    sensors = hub.poll_devices()
    summary = hub.display_status()

    return jsonify({
        "sensors": sensors,
        "summary": summary
    })


@app.route('/api/automation/state')
def api_automation_state():
    """Return current automation appliances state and sensors."""
    apps = automation.list_appliances()
    sensors = hub.poll_devices()
    # include gas status from automation controller if available
    gas_status = getattr(automation, 'gas_status', 'Normal')
    gas_ppm = getattr(automation, 'gas_ppm', None)
    return jsonify({"appliances": apps, "sensors": sensors, "gas_status": gas_status, "gas_ppm": gas_ppm})


@app.route('/api/events')
def api_events():
    try:
        return jsonify({"events": event_log.get_all()})
    except Exception:
        return jsonify({"events": []})


@app.route('/api/automation/set_manual', methods=['POST'])
def api_automation_set_manual():
    data = request.get_json()
    name = data.get('name')
    manual = data.get('manual')
    manual_state = data.get('state')
    if name is None or manual is None:
        return jsonify({'error': 'missing parameters'}), 400
    ok = automation.set_manual(name, bool(manual), bool(manual_state) if manual_state is not None else None)
    if not ok:
        return jsonify({'error': 'appliance not found'}), 404
    return jsonify({'message': 'ok'})


@app.route('/api/automation/toggle', methods=['POST'])
def api_automation_toggle():
    data = request.get_json()
    name = data.get('name')
    if name is None:
        return jsonify({'error': 'missing name'}), 400
    ok = automation.toggle_manual_state(name)
    if not ok:
        return jsonify({'error': 'appliance not found'}), 404
    return jsonify({'message': 'ok'})


if __name__ == "__main__":
    app.run(debug=True)