var automationState = { appliances: {}, sensors: [] };
var lastGasStatus = null;
var notifiedDanger = false;

function fetchEvents() {
  fetch('/api/events')
    .then(res => res.json())
    .then(data => {
      renderTimeline(data.events || []);
    });
}

function fetchAutomationState() {
  fetch('/api/automation/state')
    .then(res => res.json())
    .then(data => {
      automationState = data;
      render();
    });
}

function render() {
  renderLiveSensors();
  renderAppliances();
  renderGasBanner();
}

function renderLiveSensors() {
  var container = document.getElementById('liveSensors');
  container.innerHTML = '';
  var q = document.getElementById('searchBox') ? document.getElementById('searchBox').value.toLowerCase() : '';
  automationState.sensors.forEach(function(s) {
    if (q && s.name.toLowerCase().indexOf(q) === -1 && s.id.toLowerCase().indexOf(q) === -1) return;
    var card = document.createElement('div');
    card.className = 'sensor-card';
    card.innerHTML = '<div class="sensor-header">' +
      '<div class="sensor-title">' +
        '<span class="room-icon">'+(s.name||'')+'</span>' +
        '<div class="sensor-label">' +
          '<div class="sensor-name">'+s.name+' Sensor</div>' +
          '<div class="sensor-subtitle">'+s.id+'</div>' +
        '</div>' +
      '</div>' +
      '<span class="badge '+(s.status==='Active' ? 'badge-active' : s.status==='Offline' ? 'badge-offline' : 'badge-low')+'">'+s.status+'</span>' +
      '</div>' +
      '<div class="sensor-reading">'+s.reading+'</div>';
    container.appendChild(card);
  });
}

function renderAppliances() {
  var container = document.getElementById('appliances');
  container.innerHTML = '';
  Object.keys(automationState.appliances).forEach(function(name) {
    var app = automationState.appliances[name];
    var card = document.createElement('div');
    card.className = 'quick-device-card';
    var mode = app.mode || 'auto';
    var stateText = app.state ? 'ON' : 'OFF';
    card.innerHTML = '<div style="display:flex;justify-content:space-between;align-items:center"><div><strong>'+name+'</strong><div style="font-size:12px;color:#666">Mode: '+mode+'</div></div><div style="text-align:right"><div style="font-weight:700">'+stateText+'</div><button onclick="toggleManual(\''+name+'\')">Toggle</button></div></div>';
    // manual toggle checkbox
    var manualBtn = document.createElement('div');
    manualBtn.style.marginTop = '8px';
    manualBtn.innerHTML = '<label><input type="checkbox" '+(app.mode==='manual'?'checked':'')+' onchange="setManual(\''+name+'\',this.checked)"> Manual</label>';
    card.appendChild(manualBtn);
    container.appendChild(card);
  });
}

function setManual(name, checked) {
  // set manual mode; keep current state as manual_state
  var current = automationState.appliances[name];
  var state = current ? current.state : false;
  fetch('/api/automation/set_manual', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({name: name, manual: checked, state: state})
  }).then(()=>fetchAutomationState());
}

function toggleManual(name) {
  fetch('/api/automation/toggle', {method: 'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({name: name})})
    .then(()=>fetchAutomationState());
}

// Poll periodically
fetchAutomationState();
setInterval(fetchAutomationState, 1500);
setInterval(fetchEvents, 1500);

// Request notification permission early
if (window.Notification && Notification.permission !== 'granted') {
  try { Notification.requestPermission(); } catch(e) {}
}

function renderTimeline(events) {
  var container = document.getElementById('eventTimeline');
  if (!container) return;
  container.innerHTML = '';
  // events list is newest-first
  events.forEach(function(ev) {
    var el = document.createElement('div');
    el.style.padding = '6px 4px';
    el.style.borderBottom = '1px solid #eee';
    el.innerText = ev.time + '  ' + ev.icon + '  ' + ev.message;
    container.appendChild(el);
  });
}

function renderGasBanner(){
  var banner = document.getElementById('gasBanner');
  if (!banner) return;
  var status = automationState.gas_status || 'Normal';
  var ppm = automationState.gas_ppm;
  if (status === 'Danger'){
    banner.style.display = 'block';
    banner.innerText = '⚠️ GAS LEAK DETECTED — Current Gas Level: ' + (ppm || 'N/A') + ' ppm — Alarm & Exhaust Fan activated';
    // send browser notification once per danger entry
    if (lastGasStatus !== 'Danger'){
      if (window.Notification && Notification.permission === 'granted' && !notifiedDanger){
        try{ new Notification('Gas Leak Detected', { body: 'Level: ' + (ppm || 'N/A') + ' ppm — Alarm & Exhaust Fan activated' }); notifiedDanger = true; }catch(e){}
      }
    }
  } else {
    banner.style.display = 'none';
    if (status !== 'Danger') notifiedDanger = false;
  }
  lastGasStatus = status;
}
