# IoT Device Management Dashboard

This Flask application now uses PostgreSQL for persistent device and sensor-reading storage while keeping the original UI structure intact.

## Features
- Live sensor dashboard
- PostgreSQL-backed device persistence
- Historical sensor readings
- CRUD routes for device management
- Render-ready deployment configuration

## Local setup
1. Install dependencies: `pip install -r requirements.txt`
2. Create a PostgreSQL database named `iot_dashboard`.
3. Set environment variables:
   - `POSTGRES_HOST`
   - `POSTGRES_PORT`
   - `POSTGRES_DB`
   - `POSTGRES_USER`
   - `POSTGRES_PASSWORD`
   - or provide `DATABASE_URL` directly
4. Run the app with `python app.py`

## Render setup
1. Create a PostgreSQL service on Render.
2. Copy the internal database URL into the Render environment variable `DATABASE_URL`.
3. Deploy the app using the included `Procfile`.
