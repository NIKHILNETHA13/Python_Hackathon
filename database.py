import logging
import sqlite3

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None

from contextlib import contextmanager
from config import get_database_config

logger = logging.getLogger(__name__)


class DatabaseAdapter:
    def __init__(self, config):
        self.engine = config.get("engine", "sqlite")
        self.config = config

    def connect(self):
        if self.engine == "postgres":
            if psycopg is None:
                raise RuntimeError("psycopg package is not installed.")
            kwargs = self.config.get("kwargs", {})
            if "dsn" in kwargs:
                conn = psycopg.connect(kwargs["dsn"])
            else:
                conn = psycopg.connect(**kwargs)
            conn.autocommit = False
            return conn

        else:
            db_path = self.config.get("database", "iot_dashboard.db")
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            return conn

    @contextmanager
    def get_connection(self):
        conn = None
        try:
            conn = self.connect()
            yield conn
        except Exception as exc:
            logger.warning("Database connection unavailable: %s", exc)
            raise
        finally:
            if conn is not None:
                conn.close()


def _get_adapter():
    config = get_database_config()
    return DatabaseAdapter(config)


@contextmanager
def get_db_connection():
    adapter = _get_adapter()
    with adapter.get_connection() as conn:
        yield conn


def init_db():
    try:
        adapter = _get_adapter()
        with adapter.get_connection() as conn:
            cur = conn.cursor()
            if adapter.engine == "sqlite":
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS devices (
                        device_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        device_name TEXT NOT NULL,
                        device_type TEXT NOT NULL,
                        location TEXT,
                        status TEXT DEFAULT 'Active',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sensor_readings (
                        reading_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        device_id INTEGER REFERENCES devices(device_id) ON DELETE CASCADE,
                        sensor_value TEXT,
                        unit TEXT,
                        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        remarks TEXT
                    )
                    """
                )
            else:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS devices (
                        device_id SERIAL PRIMARY KEY,
                        device_name VARCHAR(100) NOT NULL,
                        device_type VARCHAR(50) NOT NULL,
                        location VARCHAR(100),
                        status VARCHAR(20) DEFAULT 'Active',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sensor_readings (
                        reading_id SERIAL PRIMARY KEY,
                        device_id INT REFERENCES devices(device_id) ON DELETE CASCADE,
                        sensor_value VARCHAR(50),
                        unit VARCHAR(20),
                        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        remarks VARCHAR(100)
                    )
                    """
                )
                try:
                    cur.execute("ALTER TABLE sensor_readings ADD COLUMN IF NOT EXISTS remarks VARCHAR(100);")
                except Exception:
                    pass
            conn.commit()

    except Exception as exc:
        logger.warning("Database initialization skipped: %s", exc)


def get_all_devices():
    try:
        adapter = _get_adapter()
        with adapter.get_connection() as conn:
            if adapter.engine == "sqlite":
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT d.device_id, d.device_name, d.device_type, d.location, d.status, d.created_at,
                           COALESCE(r.sensor_value, '0') AS latest_reading,
                           COALESCE(r.unit, '') AS unit,
                           COALESCE(r.recorded_at, d.created_at) AS last_seen
                    FROM devices d
                    LEFT JOIN (
                        SELECT r1.device_id, r1.sensor_value, r1.unit, r1.recorded_at
                        FROM sensor_readings r1
                        JOIN (
                            SELECT device_id, MAX(reading_id) as max_id
                            FROM sensor_readings
                            GROUP BY device_id
                        ) r2 ON r1.reading_id = r2.max_id
                    ) r ON d.device_id = r.device_id
                    ORDER BY d.device_id
                    """
                )
                rows = cur.fetchall()
                return [dict(row) for row in rows]
            else:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        """
                        SELECT d.device_id, d.device_name, d.device_type, d.location, d.status, d.created_at,
                               COALESCE(r.sensor_value, '0') AS latest_reading,
                               COALESCE(r.unit, '') AS unit,
                               COALESCE(r.recorded_at, d.created_at) AS last_seen
                        FROM devices d
                        LEFT JOIN LATERAL (
                            SELECT sensor_value, unit, recorded_at
                            FROM sensor_readings
                            WHERE device_id = d.device_id
                            ORDER BY recorded_at DESC, reading_id DESC
                            LIMIT 1
                        ) r ON TRUE
                        ORDER BY d.device_id
                        """
                    )
                    return [dict(row) for row in cur.fetchall()]
    except Exception as exc:
        logger.warning("Unable to fetch devices: %s", exc)
        return []


def create_device(device_name, device_type, location=None, status='Active'):
    try:
        adapter = _get_adapter()
        with adapter.get_connection() as conn:
            cur = conn.cursor()
            if adapter.engine == "sqlite":
                cur.execute(
                    """
                    INSERT INTO devices (device_name, device_type, location, status)
                    VALUES (?, ?, ?, ?)
                    """,
                    (device_name, device_type, location, status),
                )
                device_id = cur.lastrowid
            else:
                with conn.cursor(row_factory=dict_row) as pcur:
                    pcur.execute(
                        """
                        INSERT INTO devices (device_name, device_type, location, status)
                        VALUES (%s, %s, %s, %s)
                        RETURNING device_id
                        """,
                        (device_name, device_type, location, status),
                    )
                    device_id = pcur.fetchone()['device_id']
            conn.commit()
            return device_id
    except Exception as exc:
        logger.warning("Unable to create device: %s", exc)
        return None


def save_reading(device_id, sensor_value, unit='', remarks=''):
    if device_id is None:
        return False
    try:
        adapter = _get_adapter()
        with adapter.get_connection() as conn:
            cur = conn.cursor()
            ph = "?" if adapter.engine == "sqlite" else "%s"
            cur.execute(
                f"""
                INSERT INTO sensor_readings (device_id, sensor_value, unit, remarks)
                VALUES ({ph}, {ph}, {ph}, {ph})
                """,
                (device_id, str(sensor_value), unit, remarks),
            )
            conn.commit()
            return True
    except Exception as exc:
        logger.warning("Unable to save reading: %s", exc)
        return False


def update_device(device_id, device_name=None, device_type=None, location=None, status=None):
    if not any(v is not None for v in (device_name, device_type, location, status)):
        return False

    adapter = _get_adapter()
    ph = "?" if adapter.engine == "sqlite" else "%s"

    fields = []
    values = []
    if device_name is not None:
        fields.append(f'device_name = {ph}')
        values.append(device_name)
    if device_type is not None:
        fields.append(f'device_type = {ph}')
        values.append(device_type)
    if location is not None:
        fields.append(f'location = {ph}')
        values.append(location)
    if status is not None:
        fields.append(f'status = {ph}')
        values.append(status)

    values.append(device_id)
    try:
        with adapter.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"UPDATE devices SET {', '.join(fields)} WHERE device_id = {ph}",
                values,
            )
            conn.commit()
            return cur.rowcount > 0
    except Exception as exc:
        logger.warning("Unable to update device: %s", exc)
        return False


def delete_device(device_id):
    try:
        adapter = _get_adapter()
        ph = "?" if adapter.engine == "sqlite" else "%s"
        with adapter.get_connection() as conn:
            cur = conn.cursor()
            # Delete child readings first to prevent foreign key constraint violations
            cur.execute(f'DELETE FROM sensor_readings WHERE device_id = {ph}', (device_id,))
            cur.execute(f'DELETE FROM devices WHERE device_id = {ph}', (device_id,))
            conn.commit()
            return True
    except Exception as exc:
        logger.warning("Unable to delete device: %s", exc)
        return False


def reset_db():
    try:
        adapter = _get_adapter()
        with adapter.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('DELETE FROM sensor_readings;')
            cur.execute('DELETE FROM devices;')
            conn.commit()
            return True
    except Exception as exc:
        logger.warning("Unable to reset database: %s", exc)
        return False



def get_reading_history(device_id=None, limit=10):
    try:
        adapter = _get_adapter()
        ph = "?" if adapter.engine == "sqlite" else "%s"
        with adapter.get_connection() as conn:
            if adapter.engine == "sqlite":
                cur = conn.cursor()
                if device_id is None:
                    cur.execute(
                        """
                        SELECT r.reading_id, r.device_id, d.device_name, r.sensor_value, r.unit, r.recorded_at, r.remarks
                        FROM sensor_readings r
                        JOIN devices d ON d.device_id = r.device_id
                        ORDER BY r.recorded_at DESC, r.reading_id DESC
                        LIMIT ?
                        """,
                        (limit,),
                    )
                else:
                    cur.execute(
                        """
                        SELECT r.reading_id, r.device_id, d.device_name, r.sensor_value, r.unit, r.recorded_at, r.remarks
                        FROM sensor_readings r
                        JOIN devices d ON d.device_id = r.device_id
                        WHERE r.device_id = ?
                        ORDER BY r.recorded_at DESC, r.reading_id DESC
                        LIMIT ?
                        """,
                        (device_id, limit),
                    )
                return [dict(row) for row in cur.fetchall()]
            else:
                with conn.cursor(row_factory=dict_row) as cur:
                    if device_id is None:
                        cur.execute(
                            """
                            SELECT r.reading_id, r.device_id, d.device_name, r.sensor_value, r.unit, r.recorded_at, r.remarks
                            FROM sensor_readings r
                            JOIN devices d ON d.device_id = r.device_id
                            ORDER BY r.recorded_at DESC, r.reading_id DESC
                            LIMIT %s
                            """,
                            (limit,),
                        )
                    else:
                        cur.execute(
                            """
                            SELECT r.reading_id, r.device_id, d.device_name, r.sensor_value, r.unit, r.recorded_at, r.remarks
                            FROM sensor_readings r
                            JOIN devices d ON d.device_id = r.device_id
                            WHERE r.device_id = %s
                            ORDER BY r.recorded_at DESC, r.reading_id DESC
                            LIMIT %s
                            """,
                            (device_id, limit),
                        )
                    return [dict(row) for row in cur.fetchall()]
    except Exception as exc:
        logger.warning("Unable to fetch history: %s", exc)
        return []
