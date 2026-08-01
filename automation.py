import threading
import time
from collections import OrderedDict
from datetime import datetime


# AutomationController reads sensor objects from an IoTHub instance
# and manages appliance states according to simple rules.

class AutomationController:
    def __init__(self, hub, poll_interval=1.0, event_log=None):
        self.hub = hub
        self.poll_interval = poll_interval
        self._running = False
        self._lock = threading.Lock()
        # appliances: name -> {state: bool, mode: 'auto'|'manual', manual_state: bool}
        self.appliances = OrderedDict()
        self._thread = None
        self.event_log = event_log
        # gas tracking
        self.gas_status = 'Normal'
        self.gas_ppm = None

        # Initialize appliances based on available sensors (lazy: hub may be empty)
        self._init_appliances()

    def _log(self, icon, message):
        try:
            if self.event_log:
                self.event_log.add(icon, message)
        except Exception:
            pass

    def _init_appliances(self):
        # Decide which appliances are meaningful based on sensors present in the registry
        # We inspect the hub's devices for sensor types.
        sensor_names = set([d.get_name() for d in self.hub.poll_devices()] )
        # However poll_devices returns dicts. To be conservative, allow creation of all appliances
        # but rules will only trigger if sensors exist.
        # Create appliances with default auto mode ON
        defaults = [
            ("AC", False),
            ("Fan", False),
            ("Lights", False),
            ("Exhaust Fan", False),
            ("Alarm", False)
        ]
        for name, state in defaults:
            self.appliances[name] = {"state": state, "mode": "auto", "manual_state": False}

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)

    def _run_loop(self):
        while self._running:
            try:
                self.evaluate()
            except Exception:
                pass
            time.sleep(self.poll_interval)

    def evaluate(self):
        # Read sensors directly from the hub's device list
        devices = self.hub._IoTHub__devices if hasattr(self.hub, '_IoTHub__devices') else []
        # Build a map by sensor name to list of device objects
        by_name = {}
        for d in devices:
            by_name.setdefault(d.get_name(), []).append(d)

        # Helper to parse numeric values from readings (e.g., '40 °C' -> 40.0)
        import re

        def parse_number(val):
            if val is None:
                return None
            match = re.search(r"[-+]?\d*\.?\d+", str(val))
            return float(match.group()) if match else None

        # Helper to read sensor from hub device objects
        def raw_value(sensor):
            try:
                return sensor.get_reading()
            except Exception:
                return None

        # Occupancy via Motion sensors
        motion_devices = by_name.get('Motion', [])
        motion_detected = False
        for m in motion_devices:
            rv = raw_value(m)
            if rv is None:
                continue
            rv_str = str(rv).strip().lower()
            if rv_str in ('1', 'true', 'motion detected', 'occupied', 'motion'):
                motion_detected = True
                break

        # Temperature
        temp_devices = by_name.get('Temperature', [])
        temp_val = None
        if temp_devices:
            temp_val = parse_number(raw_value(temp_devices[0]))

        # Light lux
        light_devices = by_name.get('Light', [])
        light_lux = None
        if light_devices:
            light_lux = parse_number(raw_value(light_devices[0]))

        # Gas ppm
        gas_devices = by_name.get('Gas', [])
        gas_ppm = None
        if gas_devices:
            gas_ppm = parse_number(raw_value(gas_devices[0]))

        # Determine gas tier
        prev_gas_status = self.gas_status
        self.gas_ppm = gas_ppm
        if gas_ppm is None or gas_ppm <= 300:
            self.gas_status = 'Normal'
        elif gas_ppm <= 600:
            self.gas_status = 'Warning'
        else:
            self.gas_status = 'Danger'

        # Evaluate rules and update appliances while respecting manual overrides
        with self._lock:
            # helper to update and log changes
            def apply_change(name, new_state):
                if name not in self.appliances:
                    return
                app = self.appliances[name]
                old = app['state']
                if app['mode'] == 'auto':
                    if old != new_state:
                        app['state'] = bool(new_state)
                        # log change
                        self._log('🔁', f"{name} set to {'ON' if new_state else 'OFF'} by automation")

            # AC: Temp > 30°C => ON (High priority cooling for room)
            ac_should_be_on = bool(temp_val is not None and temp_val > 30)
            apply_change('AC', ac_should_be_on)

            # Fan: 26°C <= Temp <= 30°C => ON (Moderate cooling when AC is not needed)
            fan_should_be_on = bool(temp_val is not None and 26 <= temp_val <= 30 and not ac_should_be_on)
            apply_change('Fan', fan_should_be_on)

            # Lights: Motion detected OR Light < 300 lx => ON
            lights_should_be_on = bool(motion_detected or (light_lux is not None and light_lux < 300))
            apply_change('Lights', lights_should_be_on)

            # Gas handling by tiers
            if self.gas_status == 'Danger' and prev_gas_status != 'Danger':
                self._log('💨', f"Gas level {gas_ppm} ppm")
                self._log('⚠️', "Gas leak detected")
                if 'Exhaust Fan' in self.appliances:
                    app = self.appliances['Exhaust Fan']
                    if app['mode'] == 'auto' and not app['state']:
                        app['state'] = True
                        self._log('🔄', 'Exhaust Fan started')
                if 'Alarm' in self.appliances:
                    app = self.appliances['Alarm']
                    if app['mode'] == 'auto' and not app['state']:
                        app['state'] = True
                        self._log('🔔', 'Alarm activated')
            else:
                apply_change('Exhaust Fan', bool(gas_ppm is not None and gas_ppm > 400))
                apply_change('Alarm', bool(gas_ppm is not None and gas_ppm > 1000))


    # API helpers
    def list_appliances(self):
        with self._lock:
            return {name: dict(info) for name, info in self.appliances.items()}

    def set_manual(self, name, manual_mode, manual_state=None):
        with self._lock:
            if name not in self.appliances:
                return False
            app = self.appliances[name]
            app['mode'] = 'manual' if manual_mode else 'auto'
            if manual_state is not None:
                app['manual_state'] = bool(manual_state)
                if app['mode'] == 'manual':
                    app['state'] = app['manual_state']
            return True

    def toggle_manual_state(self, name):
        with self._lock:
            if name not in self.appliances:
                return False
            app = self.appliances[name]
            app['manual_state'] = not app['manual_state']
            if app['mode'] == 'manual':
                app['state'] = app['manual_state']
            return True
