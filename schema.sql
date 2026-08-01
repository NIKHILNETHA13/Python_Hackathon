-- IoT Hub Database Schema

-- Devices Table
CREATE TABLE IF NOT EXISTS devices (
    device_id INTEGER PRIMARY KEY AUTOINCREMENT, -- Use SERIAL PRIMARY KEY for PostgreSQL
    device_name TEXT NOT NULL,                  -- VARCHAR(100) for PostgreSQL
    device_type TEXT NOT NULL,                  -- VARCHAR(50) for PostgreSQL
    location TEXT,                              -- VARCHAR(100) for PostgreSQL
    status TEXT DEFAULT 'Active',               -- VARCHAR(20) for PostgreSQL
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sensor Readings Table
CREATE TABLE IF NOT EXISTS sensor_readings (
    reading_id INTEGER PRIMARY KEY AUTOINCREMENT, -- Use SERIAL PRIMARY KEY for PostgreSQL
    device_id INTEGER REFERENCES devices(device_id) ON DELETE CASCADE,
    sensor_value TEXT,                            -- VARCHAR(50) for PostgreSQL
    unit TEXT,                                    -- VARCHAR(20) for PostgreSQL
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    remarks TEXT                                  -- VARCHAR(100) for PostgreSQL
);
