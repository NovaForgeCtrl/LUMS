import sqlite3

DB_PATH = "/var/lib/lums/lums.db"

connection = sqlite3.connect(DB_PATH)
cursor = connection.cursor()


cursor.execute("""
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hostname TEXT NOT NULL UNIQUE,
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


connection.commit()
connection.close()

print(f"Datenbank aktualisiert: {DB_PATH}")
