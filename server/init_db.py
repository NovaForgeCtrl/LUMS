import os
import sqlite3

DB_PATH = os.environ.get(
    "LUMS_DB_PATH",
    "/var/lib/lums/lums.db"
)

os.makedirs(
    os.path.dirname(DB_PATH),
    exist_ok=True
)

connection = sqlite3.connect(DB_PATH)
cursor = connection.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hostname TEXT UNIQUE,
    ip TEXT,
    os TEXT,
    kernel TEXT,
    architecture TEXT,
    agent_version TEXT,
    last_seen TEXT NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS available_updates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    package TEXT NOT NULL,
    installed_version TEXT,
    available_version TEXT NOT NULL,
    FOREIGN KEY (client_id) REFERENCES clients(id),
    UNIQUE(client_id, package)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS installed_packages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    package TEXT NOT NULL,
    version TEXT NOT NULL,
    FOREIGN KEY (client_id) REFERENCES clients(id),
    UNIQUE(client_id, package)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS update_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    reboot_required INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (client_id) REFERENCES clients(id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS update_job_packages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    package TEXT NOT NULL,
    installed_version TEXT,
    target_version TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT,
    FOREIGN KEY (job_id) REFERENCES update_jobs(id),
    UNIQUE(job_id, package)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS update_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    job_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    package_count INTEGER NOT NULL,
    successful_count INTEGER NOT NULL,
    failed_count INTEGER NOT NULL,
    reboot_required INTEGER NOT NULL DEFAULT 0,
    started_at TEXT,
    finished_at TEXT,
    FOREIGN KEY (client_id) REFERENCES clients(id),
    FOREIGN KEY (job_id) REFERENCES update_jobs(id)
)
""")

connection.commit()
connection.close()

print(f"LUMS-Datenbank aktualisiert: {DB_PATH}")
