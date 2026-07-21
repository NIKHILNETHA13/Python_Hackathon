from app import app
c = app.test_client()
resp = c.get('/static/smarthome.js')
print('smarthome.js status', resp.status_code, 'length', len(resp.data) if resp.data else 0)
resp2 = c.get('/api/automation/state')
print('/api/automation/state status', resp2.status_code)
print(resp2.json)
