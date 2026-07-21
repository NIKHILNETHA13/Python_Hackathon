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

        # Helper to get first reading value raw (without unit)
        def raw_value(sensor):
            # sensor is SensorDevice
            try:
                val = sensor.get_reading()
                return val
            except Exception:
                return None

        # Occupancy via Motion sensors
        motion_devices = by_name.get('Motion', [])
        motion_detected = False
        for m in motion_devices:
            rv = raw_value(m)
            if rv is None:
                continue
            if str(rv) == '1' or str(rv).lower() in ('motion detected', 'true'):
                motion_detected = True
                break

        # Temperature
        temp_devices = by_name.get('Temperature', [])
        temp_val = None
        if temp_devices:
            try:
                temp_val = float(temp_devices[0].get_reading())
            except Exception:
                temp_val = None

        # Light lux
        light_devices = by_name.get('Light', [])
        light_lux = None
        if light_devices:
            try:
                light_lux = float(light_devices[0].get_reading())
            except Exception:
                light_lux = None

        # Gas ppm
        gas_devices = by_name.get('Gas', [])
        gas_ppm = None
        if gas_devices:
            try:
                gas_ppm = float(gas_devices[0].get_reading())
            except Exception:
                gas_ppm = None

        # Determine gas tier
        prev_gas_status = self.gas_status
        self.gas_ppm = gas_ppm
        if gas_ppm is None:
            self.gas_status = 'Normal'
        elif gas_ppm <= 300:
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

            # AC: Motion detected AND Temperature > 30 => ON
            apply_change('AC', bool(motion_detected and temp_val is not None and temp_val > 30))

            # Fan: Motion detected AND 26 <= Temp <= 30 => ON
            apply_change('Fan', bool(motion_detected and temp_val is not None and 26 <= temp_val <= 30))

            # Lights: Motion detected AND Light < 300 => ON
            apply_change('Lights', bool(motion_detected and light_lux is not None and light_lux < 300))

            # Gas handling by tiers
            # If Danger and we newly entered Danger, force Exhaust Fan and Alarm on (auto only) and log events
            if self.gas_status == 'Danger' and prev_gas_status != 'Danger':
                # log gas level and leak
                self._log('💨', f"Gas level {gas_ppm} ppm")
                self._log('⚠️', "Gas leak detected")
                # set Exhaust Fan and Alarm ON
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
                # In non-danger situations, update exhaust/alarm based on lower tiers
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
