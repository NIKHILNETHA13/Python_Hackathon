from app import app, automation
c = app.test_client()
# Add required sensors
for t in ['Temperature','Motion','Light','Gas']:
    r = c.post('/api/add_sensor', json={'type': t})
    print('add', t, r.json)
# Get sensors
s = c.get('/api/sensors').json['sensors']
print('sensors after add:', s)
# Map ids
ids = {}
for device in s:
    ids.setdefault(device['name'], []).append(device['id'])
# Update readings: motion=1, temp=32, light=100, gas=500
if 'Motion' in ids:
    mid = ids['Motion'][0]
    c.post('/api/update_sensor', json={'id': mid, 'reading': '1', 'status': 'Active'})
if 'Temperature' in ids:
    tid = ids['Temperature'][0]
    c.post('/api/update_sensor', json={'id': tid, 'reading': '32', 'status': 'Active'})
if 'Light' in ids:
    lid = ids['Light'][0]
    c.post('/api/update_sensor', json={'id': lid, 'reading': '100', 'status': 'Active'})
if 'Gas' in ids:
    gid = ids['Gas'][0]
    c.post('/api/update_sensor', json={'id': gid, 'reading': '500', 'status': 'Active'})

import time
# Allow automation thread to run
time.sleep(2)
state = c.get('/api/automation/state').json
print('automation state:', state['appliances'])
