// script.js - Handles IoT Hub Simulator Client-Side Logic

var allSensors = [];
var sensorTypesMeta = {}; // name -> metadata from server
var currentDeviceId = null;

// ── Add Sensor ───────────────────────────────────────────────
function addSensor() {
  var type = document.getElementById("sensorType").value;

  fetch("/api/add_sensor", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: type })
  })
  .then(function(response) { return response.json(); })
  .then(function(data) {
    loadSensors();   // Refresh the sensor list.
  })
  .catch(function(err) {
    console.error("Error adding sensor:", err);
  });
}

// ── Remove Sensor ────────────────────────────────────────────
function removeSensor(id) {
  fetch("/api/remove_sensor", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id: id })
  })
  .then(function(response) { return response.json(); })
  .then(function(data) {
    loadSensors();
  })
  .catch(function(err) {
    console.error("Error removing sensor:", err);
  });
}

// ── Update Sensor ────────────────────────────────────────────
function updateSensor(id) {
  var inputEl = document.getElementById("reading_" + id);
  var selectEl = document.getElementById("status_" + id);
  
  var reading = inputEl.value.trim();
  var status  = selectEl.value;

  // Prepare payload: only include non-empty reading so server preserves old value
  var payload = { id: id, status: status };
  if (reading !== "") payload.reading = reading;

  fetch("/api/update_sensor", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  })
  .then(function(response) { return response.json(); })
  .then(function(data) {
    loadSensors();
  })
  .catch(function(err) {
    console.error("Error updating sensor:", err);
  });
}

// ── Device Management CRUD ──────────────────────────────────
function resetDeviceForm() {
  document.getElementById('deviceId').value = '';
  document.getElementById('deviceName').value = '';
  document.getElementById('deviceType').value = 'Temperature';
  document.getElementById('deviceLocation').value = '';
  document.getElementById('deviceStatus').value = 'Active';
  currentDeviceId = null;
}

function submitDeviceForm() {
  var payload = {
    device_name: document.getElementById('deviceName').value.trim(),
    device_type: document.getElementById('deviceType').value,
    location: document.getElementById('deviceLocation').value.trim(),
    status: document.getElementById('deviceStatus').value
  };

  if (!payload.device_name) {
    alert('Please enter a device name.');
    return;
  }

  var url = '/api/devices';
  var method = 'POST';
  if (currentDeviceId) {
    url = '/api/devices/' + currentDeviceId;
    method = 'PUT';
  }

  fetch(url, {
    method: method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  .then(function(response) { return response.json(); })
  .then(function() {
    resetDeviceForm();
    loadDeviceManagement();
    loadSensors();
  })
  .catch(function(err) {
    console.error('Error saving device:', err);
  });
}

function editDevice(device) {
  currentDeviceId = device.device_id;
  document.getElementById('deviceId').value = device.device_id;
  document.getElementById('deviceName').value = device.device_name || '';
  document.getElementById('deviceType').value = device.device_type || 'Temperature';
  document.getElementById('deviceLocation').value = device.location || '';
  document.getElementById('deviceStatus').value = device.status || 'Active';
  document.getElementById('deviceName').focus();
}

function deleteDevice(deviceId) {
  if (!confirm('Delete this device and its history?')) return;
  fetch('/api/devices/' + deviceId, { method: 'DELETE' })
    .then(function(response) { return response.json(); })
    .then(function() {
      loadDeviceManagement();
      loadSensors();
    })
    .catch(function(err) {
      console.error('Error deleting device:', err);
    });
}

function renderDeviceManagement(list) {
  var container = document.getElementById('deviceList');
  if (!container) return;
  if (!list || list.length === 0) {
    container.innerHTML = '<p class="empty-msg">No devices stored in PostgreSQL yet.</p>';
    return;
  }

  var html = '<table style="width:100%; border-collapse:collapse; font-size:13px;">' +
    '<thead><tr><th style="text-align:left; padding:6px 4px;">Name</th><th style="text-align:left; padding:6px 4px;">Type</th><th style="text-align:left; padding:6px 4px;">Location</th><th style="text-align:left; padding:6px 4px;">Status</th><th style="text-align:left; padding:6px 4px;">Actions</th></tr></thead><tbody>';

  list.forEach(function(device) {
    html += '<tr>' +
      '<td style="padding:6px 4px;">' + (device.device_name || '') + '</td>' +
      '<td style="padding:6px 4px;">' + (device.device_type || '') + '</td>' +
      '<td style="padding:6px 4px;">' + (device.location || '-') + '</td>' +
      '<td style="padding:6px 4px;">' + (device.status || 'Active') + '</td>' +
      '<td style="padding:6px 4px;"><button class="btn-update" style="padding:6px 10px; margin-right:6px;" onclick="editDevice(' + JSON.stringify(device) + ')">Edit</button>' +
      '<button class="btn-remove" style="padding:6px 10px;" onclick="deleteDevice(' + device.device_id + ')">Delete</button></td>' +
      '</tr>';
  });

  html += '</tbody></table>';
  container.innerHTML = html;
}

function loadDeviceManagement() {
  fetch('/api/devices')
    .then(function(response) { return response.json(); })
    .then(function(data) {
      renderDeviceManagement(data.devices || []);
    })
    .catch(function(err) {
      console.error('Error loading devices:', err);
    });
}

// ── Search Filtering ──────────────────────────────────────────
function filterSimulatorCards() {
  renderSensorCards();
}

// ── Render Sensor Control Cards ──────────────────────────────
function renderSensorCards() {
  var list = document.getElementById("sensorList");
  var emptyMsg = document.getElementById("emptyMsg");
  var query = document.getElementById("deviceSearch") ? document.getElementById("deviceSearch").value.toLowerCase() : "";
  
  list.innerHTML = "";

  var filtered = allSensors.filter(function(s) {
    if (!query) return true;
    return s.id.toLowerCase().indexOf(query) !== -1 || s.name.toLowerCase().indexOf(query) !== -1;
  });

  if (filtered.length === 0) {
    emptyMsg.style.display = "block";
    return;
  }

  emptyMsg.style.display = "none";

  // Build premium cards
  for (var i = 0; i < filtered.length; i++) {
    var s = filtered[i];

    // Placeholder and helper labels based on type
    var placeholder = "Enter numerical value";
    var icon = "🌡️";
    var iconClass = "temp-icon";
    var unitHelp = "";

    // Use metadata from registry when available for icon/unit/placeholder
    var meta = sensorTypesMeta[s.name] || {};
    icon = meta.icon || icon;
    unitHelp = meta.unit || "";
    // Choose placeholder based on unit presence
    if (unitHelp) placeholder = "e.g. " + meta.default_reading + " " + unitHelp;
    else placeholder = "Enter value";

    // Add some simple icon-class mapping for styling convenience
    var cls = (s.name || "").toLowerCase();
    iconClass = cls + "-icon";

    var badgeClass = "badge-active";
    if (s.status === "Offline") badgeClass = "badge-offline";
    if (s.status === "Low Battery") badgeClass = "badge-low";

    var card = document.createElement("div");
    card.className = "sensor-card";

    // Setup input value if exists in allSensors to prevent losing typing focus during load
    var existingInput = document.getElementById("reading_" + s.id);
    var savedTypedValue = existingInput ? existingInput.value : "";

    card.innerHTML =
      "<div class='sensor-header'>" +
        "<div style='display: flex; align-items: center; gap: 10px;'>" +
          "<span class='room-icon " + iconClass + "' style='width: 32px; height: 32px; font-size: 15px; border-radius: 8px;'>" + icon + "</span>" +
          "<span class='sensor-name'>" + s.name + " Sensor</span>" +
        "</div>" +
        "<span class='sensor-id'>" + s.id + "</span>" +
      "</div>" +

      "<div class='sensor-reading'>" + s.reading + "</div>" +

      "<div class='sensor-status'>" +
        "<span class='badge " + badgeClass + "'>" + s.status + "</span>" +
      "</div>" +

      "<div class='sensor-controls'>" +
        "<div style='display: flex; justify-content: space-between; align-items: center;'>" +
          "<label>Simulate Reading</label>" +
          "<span style='font-size: 10px; color: #8c8da7; font-weight: bold;'>" + unitHelp + "</span>" +
        "</div>" +
        "<input id='reading_" + s.id + "' type='text' placeholder='" + placeholder + "' value='" + savedTypedValue + "' />" +

        "<label>Device Status</label>" +
        "<select id='status_" + s.id + "'>" +
          "<option value='Active'" +      (s.status === "Active"      ? " selected" : "") + ">Active</option>" +
          "<option value='Offline'"  +    (s.status === "Offline"     ? " selected" : "") + ">Offline</option>" +
          "<option value='Low Battery'" + (s.status === "Low Battery" ? " selected" : "") + ">Low Battery</option>" +
        "</select>" +
      "</div>" +

      "<div class='sensor-buttons'>" +
        "<button class='btn-update' onclick='updateSensor(\"" + s.id + "\")'>Update</button>" +
        "<button class='btn-remove' onclick='removeSensor(\"" + s.id + "\")'>Remove</button>" +
      "</div>";

    list.appendChild(card);
  }
}

// ── Load Sensors telemetries from API ─────────────────────────
function loadSensors() {
  fetch("/api/sensors")
  .then(function(response) { return response.json(); })
  .then(function(data) {
    allSensors = data.sensors;
    renderSensorCards();
  })
  .catch(function(err) {
    console.error("Error loading sensors:", err);
  });
}

// ── Populate Sensor Type Dropdown ─────────────────────────────
function loadSensorTypes() {
  var selectEl = document.getElementById("sensorType");
  if (!selectEl) return; // Only run on simulator page

  fetch("/api/sensor_types")
  .then(function(res) { return res.json(); })
  .then(function(data) {
    selectEl.innerHTML = "";
    // store metadata map
    sensorTypesMeta = {};
    data.types.forEach(function(t) {
      sensorTypesMeta[t.name] = t;
      var option = document.createElement("option");
      option.value = t.name;
      option.textContent = t.name + " Sensor (" + (t.icon || "🔌") + ")";
      selectEl.appendChild(option);
    });

    // Build quick-add cards in right sidebar devices quick grid
    var quickGrid = document.querySelectorAll('.devices-quick-grid');
    quickGrid.forEach(function(grid) {
      grid.innerHTML = '';
      data.types.forEach(function(t) {
        var card = document.createElement('div');
        card.className = 'quick-device-card';
        card.onclick = function() { quickAdd(t.name); };
        card.innerHTML = "<div class='device-icon'>" + (t.icon || '🔌') + "</div>" +
                         "<span class='device-name'>+ " + t.name + "</span>";
        grid.appendChild(card);
      });
    });
  })
  .catch(function(err) {
    console.error("Error loading sensor types:", err);
  });
}

// Run immediately on page load
loadSensors();
loadSensorTypes();
loadDeviceManagement();
resetDeviceForm();
// Polling for simulator is turned off to prevent input focus resets, 
// but updates will refresh lists on edits.