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
from database import init_db, get_all_devices, create_device, save_reading, update_device, delete_device, get_reading_history, reset_db
import os

app = Flask(__name__)

# Initialize the database tables once on startup.
try:
    init_db()
except Exception as exc:
    print(f"[database] initialization warning: {exc}")

# ============================================================
# Create one IoTHub instance.
# This hub persists for the entire session (in-memory).
# ============================================================
hub = IoTHub("My IoT Hub")

# Global event log
event_log = EventLog()

# Start automation controller with event logging (deferred start)
automation = AutomationController(hub, event_log=event_log)


_automation_started = False

def _start_automation():
    """Start the automation loop once per process."""
    global _automation_started
    if _automation_started:
        return
    try:
        if not getattr(automation, '_running', False):
            automation.start()
            print(f"[automation] started in PID {os.getpid()}")
    except Exception:
        pass
    _automation_started = True

# Register start hook: prefer `before_first_request` but fall back to `before_request`
if hasattr(app, 'before_first_request'):
    app.before_first_request(_start_automation)
else:
    app.before_request(_start_automation)

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

def format_sensor_reading(sensor_type, raw_reading, unit=""):
    if raw_reading is None or str(raw_reading).strip() == "":
        raw_reading = "0"
    val = str(raw_reading).strip()

    if sensor_type == "Motion":
        if val in ("1", "true", "True", "Motion Detected", "Occupied"):
            return "Motion Detected"
        return "No Motion"
    elif sensor_type == "Temperature":
        clean = val.replace("°C", "").strip()
        return f"{clean} °C"
    elif sensor_type == "Humidity":
        clean = val.replace("%", "").strip()
        return f"{clean} %"
    elif sensor_type == "Pressure":
        clean = val.replace("hPa", "").strip()
        return f"{clean} hPa"
    elif sensor_type == "Light":
        clean = val.replace("lx", "").replace("lux", "").strip()
        return f"{clean} lx"
    elif sensor_type == "Gas":
        clean = val.replace("ppm", "").strip()
        return f"{clean} ppm"

    if unit and not val.endswith(unit):
        return f"{val} {unit}".strip()
    return val


def sync_hub_with_db():
    """Keep in-memory IoTHub in sync with database records."""
    devices = get_all_devices()
    existing = {d.get_id(): d for d in getattr(hub, '_IoTHub__devices', [])}
    for dev in devices:
        public_id = str(dev['device_name'])
        d_type = dev['device_type']
        reading = str(dev['latest_reading'])
        status = str(dev['status'])
        meta = SENSOR_REGISTRY.get(d_type)
        if public_id in existing:
            s = existing[public_id]
            s.set_reading(reading)
            s.set_status(status)
        elif meta and meta.get("class"):
            s_cls = meta["class"]
            try:
                sensor_obj = s_cls(public_id, reading=reading, device_status=status)
                hub.add_device(sensor_obj)
            except Exception:
                pass


@app.route("/api/add_sensor", methods=["POST"])
def add_sensor():
    """Add a new sensor to the IoTHub and persist it in database."""

    data = request.get_json() or {}
    sensor_type = data.get("type")

    meta = SENSOR_REGISTRY.get(sensor_type)
    if meta is None:
        return jsonify({"error": f"Sensor type {sensor_type} not supported"}), 400

    prefix, counter = get_sensor_id_params(sensor_type)
    id_counters[sensor_type] += 1
    new_id = prefix + str(id_counters[sensor_type])

    default_reading = meta.get("default_reading") if meta else None
    default_status = meta.get("default_status") if meta else None

    device_id = create_device(new_id, sensor_type, location="Living Room", status=str(default_status or "Active"))
    save_reading(device_id, str(default_reading or "0"), meta.get("unit", ""), "Provisioned for Living Room")

    sensor_class = meta.get("class")
    if default_reading is not None and default_status is not None:
        sensor = sensor_class(new_id, reading=str(default_reading), device_status=str(default_status))
    else:
        sensor = sensor_class(new_id)
    hub.add_device(sensor)
    sync_hub_with_db()

    return jsonify({
        "message": "Sensor added successfully",
        "id": new_id,
        "db_id": device_id
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
    return jsonify({"types": sorted(types, key=lambda x: x["name"])})


@app.route("/api/remove_sensor", methods=["POST"])
def remove_sensor():
    """Remove a sensor from the hub and delete its record."""

    data = request.get_json() or {}
    device_id = data.get("id")
    if device_id is None:
        return jsonify({"error": "Device id is required"}), 400

    removed_from_memory = hub.remove_device(device_id)

    db_device_id = None
    for device in get_all_devices():
        if str(device['device_id']) == str(device_id) or str(device['device_name']) == str(device_id):
            db_device_id = device['device_id']
            break

    deleted_from_db = False
    if db_device_id is not None:
        deleted_from_db = delete_device(db_device_id)

    sync_hub_with_db()

    if removed_from_memory or deleted_from_db:
        return jsonify({"message": "Sensor removed successfully"})

    return jsonify({"error": "Sensor not found"}), 404


@app.route("/api/update_sensor", methods=["POST"])
def update_sensor():
    """Update sensor reading and status, then store the reading in database."""

    data = request.get_json() or {}

    device_id = data.get("id")
    reading = data.get("reading")
    status = data.get("status")

    sensor = hub.get_device(device_id)

    db_device_id = None
    for device in get_all_devices():
        if str(device['device_name']) == str(device_id):
            db_device_id = device['device_id']
            break
    if db_device_id is None:
        db_device_id = create_device(str(device_id), str(device_id), location="Living Room", status="Active")

    if reading is not None and str(reading).strip() != "":
        save_reading(db_device_id, str(reading), "", "Updated from simulator")
    if status is not None and str(status).strip() != "":
        update_device(db_device_id, status=status)

    sync_hub_with_db()
    if sensor is None:
        sensor = hub.get_device(device_id)

    if sensor:
        old_reading = sensor.get_reading()
        old_status = sensor.get_status()
        if reading is not None and str(reading).strip() != "":
            sensor.set_reading(reading)
        if status is not None and str(status).strip() != "":
            sensor.set_status(status)

        try:
            if event_log:
                if sensor.get_reading() != old_reading:
                    icons = {"Temperature": "🌡️", "Humidity": "💧", "Pressure": "⏲️", "Motion": "🏃", "Light": "💡", "Gas": "💨"}
                    icon = icons.get(sensor.get_name(), "🔌")
                    event_log.add(icon, f"{sensor.get_name()} {sensor.get_id()} updated to {sensor.get_reading()}")
                if sensor.get_status() != old_status:
                    event_log.add("🔁", f"{sensor.get_name()} {sensor.get_id()} status changed to {sensor.get_status()}")
        except Exception:
            pass

    # Re-evaluate automation rules immediately so AC state updates instantly
    try:
        automation.evaluate()
    except Exception:
        pass

    return jsonify({"message": "Sensor updated successfully"})


@app.route("/api/sensors")
def get_sensors():
    """Return all sensors for Simulator and Dashboard with formatted readings and single-room context."""
    sync_hub_with_db()
    devices = get_all_devices()
    sensors = []
    for device in devices:
        formatted = format_sensor_reading(device['device_type'], device['latest_reading'], device['unit'])
        sensors.append({
            "id": str(device['device_name']),
            "db_id": int(device['device_id']),
            "name": device['device_type'],
            "reading": formatted,
            "raw_reading": str(device['latest_reading']),
            "status": device['status'],
            "location": device['location'] or "Living Room",
            "created_at": str(device['created_at'])
        })

    active_count = sum(1 for item in sensors if item['status'] == 'Active')
    summary = {
        "hub_name": "Living Room Smart Hub",
        "total": len(sensors),
        "active": active_count,
        "offline": len(sensors) - active_count,
        "low_battery": 0
    }

    return jsonify({
        "sensors": sensors,
        "summary": summary
    })



@app.route('/api/automation/state')
def api_automation_state():
    """Return current automation appliances state and sensors."""
    apps = automation.list_appliances()
    sensors = get_sensors().get_json()['sensors']
    gas_status = getattr(automation, 'gas_status', 'Normal')
    gas_ppm = getattr(automation, 'gas_ppm', None)
    return jsonify({"appliances": apps, "sensors": sensors, "gas_status": gas_status, "gas_ppm": gas_ppm})


@app.route('/api/events')
def api_events():
    try:
        return jsonify({"events": event_log.get_all()})
    except Exception:
        return jsonify({"events": []})


@app.route('/api/devices', methods=['GET'])
def api_devices():
    return jsonify({"devices": get_all_devices()})


@app.route('/api/history', methods=['GET'])
def api_history():
    history = get_reading_history(limit=12)
    labels = []
    values = []
    for entry in history:
        labels.append(str(entry['recorded_at']))
        values.append(float(entry['sensor_value']) if str(entry['sensor_value']).replace('.', '', 1).isdigit() else 0)
    return jsonify({"datasets": {"labels": labels, "values": values}})


@app.route('/api/devices', methods=['POST'])
def create_device_route():
    data = request.get_json() or {}
    device_name = data.get('device_name')
    device_type = data.get('device_type')
    location = data.get('location')
    status = data.get('status', 'Active')
    if not device_name or not device_type:
        return jsonify({'error': 'device_name and device_type are required'}), 400
    device_id = create_device(device_name, device_type, location=location, status=status)
    save_reading(device_id, '0', '', 'Created from CRUD form')
    return jsonify({'message': 'Device created', 'device_id': device_id})


@app.route('/api/devices/<int:device_id>', methods=['PUT'])
def update_device_route(device_id):
    data = request.get_json() or {}
    ok = update_device(
        device_id,
        device_name=data.get('device_name'),
        device_type=data.get('device_type'),
        location=data.get('location'),
        status=data.get('status')
    )
    if not ok:
        return jsonify({'error': 'Device not found'}), 404
    return jsonify({'message': 'Device updated'})


@app.route('/api/devices/<int:device_id>', methods=['DELETE'])
def delete_device_route(device_id):
    ok = delete_device(device_id)
    if not ok:
        return jsonify({'error': 'Device not found'}), 404
    return jsonify({'message': 'Device deleted'})


@app.route('/api/reset_db', methods=['POST'])
def api_reset_db():
    """Reset the database and clear all in-memory sensors."""
    reset_db()
    getattr(hub, '_IoTHub__devices', []).clear()
    id_counters.clear()
    id_prefix.clear()
    return jsonify({"message": "Page and database reset successfully"})



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
    # When running locally via `python app.py` keep previous behavior.
    automation.start()
    app.run(host='0.0.0.0', debug=True)