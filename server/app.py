from flask import Flask, request, jsonify, render_template, url_for, redirect
import os
import sqlite3
from datetime import datetime, timezone

from security import (
    configure_session,
    apply_security_headers,
    find_user,
    verify_password,
    password_needs_rehash,
    hash_password,
    login_user,
    logout_user,
    current_username,
    get_csrf_token,
    audit_log,
    current_user_id,
    login_required,
    csrf_required,
)


app = Flask(__name__)

# Security foundation
#
# Secret key is supplied externally and must never be stored in Git.
app.secret_key = os.environ.get("LUMS_SECRET_KEY")

if not app.secret_key:
    raise RuntimeError(
        "LUMS_SECRET_KEY is not configured. "
        "Refusing to start without a secure Flask secret."
    )

configure_session(app)

DB_PATH = "/var/lib/lums/lums.db"


@app.after_request
def security_headers(response):
    return apply_security_headers(response)


# ============================================================
# DATABASE HELPERS
# ============================================================

def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


# ============================================================
# CLIENT REPORT
# ============================================================

def save_client(data):

    connection = get_connection()
    cursor = connection.cursor()

    last_seen = datetime.now(timezone.utc).isoformat()

    cursor.execute("""
        INSERT INTO clients (
            hostname,
            ip,
            os,
            kernel,
            architecture,
            agent_version,
            last_seen
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)

        ON CONFLICT(hostname) DO UPDATE SET
            ip = excluded.ip,
            os = excluded.os,
            kernel = excluded.kernel,
            architecture = excluded.architecture,
            agent_version = excluded.agent_version,
            last_seen = excluded.last_seen
    """, (
        data.get("hostname"),
        data.get("ip"),
        data.get("os"),
        data.get("kernel"),
        data.get("architecture"),
        data.get("agent_version"),
        last_seen
    ))

    connection.commit()

    cursor.execute(
        "SELECT id FROM clients WHERE hostname = ?",
        (data.get("hostname"),)
    )

    row = cursor.fetchone()

    connection.close()

    if row:
        return row["id"]

    return None


def save_updates(client_id, updates):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "DELETE FROM available_updates WHERE client_id = ?",
        (client_id,)
    )

    for update in updates:

        package = update.get("package")
        installed_version = update.get("installed_version")
        available_version = update.get("available_version")

        if not package or not available_version:
            continue

        cursor.execute("""
            INSERT INTO available_updates (
                client_id,
                package,
                installed_version,
                available_version
            )
            VALUES (?, ?, ?, ?)
        """, (
            client_id,
            package,
            installed_version,
            available_version
        ))

    connection.commit()
    connection.close()


def save_packages(client_id, packages):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "DELETE FROM installed_packages WHERE client_id = ?",
        (client_id,)
    )

    for package, version in packages.items():

        if not package or not version:
            continue

        cursor.execute("""
            INSERT INTO installed_packages (
                client_id,
                package,
                version
            )
            VALUES (?, ?, ?)
        """, (
            client_id,
            package,
            version
        ))

    connection.commit()
    connection.close()


# ============================================================
# CLIENT STATUS
# ============================================================

def get_client_status(last_seen):

    last_seen_time = datetime.fromisoformat(last_seen)

    now = datetime.now(timezone.utc)

    difference = (now - last_seen_time).total_seconds()

    if difference <= 120:
        return "online"

    if difference <= 600:
        return "unknown"

    return "offline"


# ============================================================
# WEB PAGES
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template(
            "login.html",
            csrf_token=get_csrf_token(),
        )

    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""

    connection = get_connection()

    try:
        user = find_user(connection, username)

        # Deliberately use the same generic failure response for
        # unknown and disabled users to avoid account enumeration.
        if user is None or not user["enabled"]:
            audit_log(
                connection,
                actor_type="user",
                actor_id=username or None,
                action="login",
                target=None,
                result="failure",
                details="invalid credentials",
            )
            connection.commit()

            return render_template(
                "login.html",
                csrf_token=get_csrf_token(),
                error="Invalid username or password.",
                username=username,
            ), 401

        if not verify_password(user["password_hash"], password):
            audit_log(
                connection,
                actor_type="user",
                actor_id=user["id"],
                action="login",
                target=f"user:{user['id']}",
                result="failure",
                details="invalid credentials",
            )
            connection.commit()

            return render_template(
                "login.html",
                csrf_token=get_csrf_token(),
                error="Invalid username or password.",
                username=username,
            ), 401

        # Upgrade the password hash automatically if Argon2 parameters
        # have changed since the account was created.
        if password_needs_rehash(user["password_hash"]):
            new_hash = hash_password(password)

            connection.execute(
                """
                UPDATE users
                SET password_hash = ?
                WHERE id = ?
                """,
                (new_hash, user["id"]),
            )

        login_user(
            user_id=user["id"],
            username=user["username"],
        )

        audit_log(
            connection,
            actor_type="user",
            actor_id=user["id"],
            action="login",
            target=f"user:{user['id']}",
            result="success",
            details="interactive login",
        )

        connection.commit()

        return redirect(url_for("index"))

    finally:
        connection.close()


@app.route("/logout", methods=["POST"])
@login_required
@csrf_required
def logout():
    user_id = current_user_id()

    if user_id is not None:
        connection = get_connection()

        try:
            audit_log(
                connection,
                actor_type="user",
                actor_id=user_id,
                action="logout",
                target=f"user:{user_id}",
                result="success",
            )
            connection.commit()
        finally:
            connection.close()

    logout_user()

    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():

    return render_template("index.html")


@app.route("/client")
@login_required
def client_page():

    return render_template("client.html")


# ============================================================
# HEALTH
# ============================================================

@app.route("/api/health", methods=["GET"])
def health():

    return jsonify({
        "status": "ok",
        "service": "LUMS API"
    })


# ============================================================
# CLIENT REPORT
# ============================================================

@app.route("/api/report", methods=["POST"])
def report():

    data = request.get_json()

    if not data:

        return jsonify({
            "status": "error",
            "message": "No JSON data received"
        }), 400

    client_id = save_client(data)

    if client_id is not None:

        save_updates(
            client_id,
            data.get("updates", [])
        )

        save_packages(
            client_id,
            data.get("packages", {})
        )

    print(
        f"Client report: "
        f"{data.get('hostname')} "
        f"({data.get('ip')}) "
        f"Updates: {len(data.get('updates', []))} "
        f"Pakete: {len(data.get('packages', {}))}"
    )

    return jsonify({
        "status": "received"
    })


# ============================================================
# CLIENT LIST
# ============================================================

@app.route("/api/clients", methods=["GET"])
@login_required
def clients():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            c.id,
            c.hostname,
            c.ip,
            c.os,
            c.kernel,
            c.architecture,
            c.agent_version,
            c.last_seen,
            COUNT(DISTINCT p.id) AS package_count,
            COUNT(DISTINCT u.id) AS update_count
        FROM clients c
        LEFT JOIN installed_packages p
            ON p.client_id = c.id
        LEFT JOIN available_updates u
            ON u.client_id = c.id
        GROUP BY c.id
        ORDER BY c.hostname
    """)

    rows = cursor.fetchall()

    connection.close()

    result = []

    for row in rows:

        client_data = dict(row)

        client_data["status"] = get_client_status(
            client_data["last_seen"]
        )

        result.append(client_data)

    return jsonify(result)


# ============================================================
# CLIENT DETAILS
# ============================================================

@app.route("/api/clients/<int:client_id>", methods=["GET"])
@login_required
def client(client_id):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            hostname,
            ip,
            os,
            kernel,
            architecture,
            agent_version,
            last_seen
        FROM clients
        WHERE id = ?
    """, (client_id,))

    row = cursor.fetchone()

    if row is None:

        connection.close()

        return jsonify({
            "status": "error",
            "message": "Client not found"
        }), 404

    client_data = dict(row)

    cursor.execute("""
        SELECT COUNT(*)
        FROM installed_packages
        WHERE client_id = ?
    """, (client_id,))

    client_data["package_count"] = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM available_updates
        WHERE client_id = ?
    """, (client_id,))

    client_data["update_count"] = cursor.fetchone()[0]

    connection.close()

    client_data["status"] = get_client_status(
        client_data["last_seen"]
    )

    return jsonify(client_data)


# ============================================================
# AVAILABLE UPDATES
# ============================================================

@app.route("/api/clients/<int:client_id>/updates", methods=["GET"])
@login_required
def client_updates(client_id):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            package,
            installed_version,
            available_version
        FROM available_updates
        WHERE client_id = ?
        ORDER BY package
    """, (client_id,))

    rows = cursor.fetchall()

    connection.close()

    return jsonify([
        dict(row)
        for row in rows
    ])


# ============================================================
# INSTALLED PACKAGES
# ============================================================

@app.route("/api/clients/<int:client_id>/packages", methods=["GET"])
@login_required
def client_packages(client_id):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            package,
            version
        FROM installed_packages
        WHERE client_id = ?
        ORDER BY package
    """, (client_id,))

    rows = cursor.fetchall()

    connection.close()

    return jsonify([
        dict(row)
        for row in rows
    ])


# ============================================================
# CREATE UPDATE JOB
# ============================================================

@app.route(
    "/api/clients/<int:client_id>/update-jobs",
    methods=["POST"]
)
@login_required
@csrf_required
def create_update_job(client_id):

    data = request.get_json()

    if not data:

        return jsonify({
            "status": "error",
            "message": "No JSON data received"
        }), 400

    packages = data.get("packages")

    if not isinstance(packages, list):

        return jsonify({
            "status": "error",
            "message": "packages must be a list"
        }), 400

    packages = [
        package
        for package in packages
        if isinstance(package, str) and package.strip()
    ]

    packages = list(dict.fromkeys(packages))

    if not packages:

        return jsonify({
            "status": "error",
            "message": "No packages selected"
        }), 400

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            hostname
        FROM clients
        WHERE id = ?
    """, (client_id,))

    client_row = cursor.fetchone()

    if client_row is None:

        connection.close()

        return jsonify({
            "status": "error",
            "message": "Client not found"
        }), 404

    placeholders = ",".join("?" for _ in packages)

    cursor.execute(
        f"""
        SELECT
            package,
            installed_version,
            available_version
        FROM available_updates
        WHERE client_id = ?
        AND package IN ({placeholders})
        ORDER BY package
        """,
        [client_id] + packages
    )

    update_rows = cursor.fetchall()

    found_packages = {
        row["package"]
        for row in update_rows
    }

    invalid_packages = [
        package
        for package in packages
        if package not in found_packages
    ]

    if invalid_packages:

        connection.close()

        return jsonify({
            "status": "error",
            "message": "One or more packages are not available as updates",
            "invalid_packages": invalid_packages
        }), 400

    created_at = datetime.now(timezone.utc).isoformat()

    cursor.execute("""
        INSERT INTO update_jobs (
            client_id,
            status,
            created_at
        )
        VALUES (?, ?, ?)
    """, (
        client_id,
        "pending",
        created_at
    ))

    job_id = cursor.lastrowid

    for row in update_rows:

        cursor.execute("""
            INSERT INTO update_job_packages (
                job_id,
                package,
                installed_version,
                target_version,
                status
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            job_id,
            row["package"],
            row["installed_version"],
            row["available_version"],
            "pending"
        ))

    connection.commit()

    connection.close()

    print(
        f"Update job created: "
        f"Job #{job_id} "
        f"Client {client_row['hostname']} "
        f"Packages: {len(update_rows)}"
    )

    return jsonify({
        "status": "created",
        "job_id": job_id,
        "client_id": client_id,
        "hostname": client_row["hostname"],
        "package_count": len(update_rows),
        "packages": [
            {
                "package": row["package"],
                "installed_version": row["installed_version"],
                "target_version": row["available_version"]
            }
            for row in update_rows
        ]
    }), 201


# ============================================================
# LIST UPDATE JOBS FOR CLIENT
# ============================================================

@app.route(
    "/api/clients/<int:client_id>/update-jobs",
    methods=["GET"]
)
@login_required
def client_update_jobs(client_id):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "SELECT id FROM clients WHERE id = ?",
        (client_id,)
    )

    if cursor.fetchone() is None:

        connection.close()

        return jsonify({
            "status": "error",
            "message": "Client not found"
        }), 404

    cursor.execute("""
        SELECT
            j.id,
            j.client_id,
            j.status,
            j.created_at,
            j.started_at,
            j.finished_at,
            j.reboot_required,
            COUNT(p.id) AS package_count
        FROM update_jobs j
        LEFT JOIN update_job_packages p
            ON p.job_id = j.id
        WHERE j.client_id = ?
        GROUP BY j.id
        ORDER BY j.id DESC
    """, (client_id,))

    rows = cursor.fetchall()

    connection.close()

    return jsonify([
        dict(row)
        for row in rows
    ])


# ============================================================
# AGENT: CLAIM NEXT PENDING UPDATE JOB
# ============================================================

@app.route("/api/update-jobs/<int:job_id>/result", methods=["POST"])
def update_job_result(job_id):
    data = request.get_json(silent=True) or {}

    status = data.get("status")
    reboot_required = 1 if data.get("reboot_required") else 0
    packages = data.get("packages", [])

    if status not in ("success", "partial", "failed"):
        return jsonify({
            "error": "invalid status"
        }), 400

    conn = get_connection()

    job = conn.execute(
        """
        SELECT *
        FROM update_jobs
        WHERE id = ?
        """,
        (job_id,)
    ).fetchone()

    if job is None:
        conn.close()
        return jsonify({
            "error": "job not found"
        }), 404

    now = datetime.now(timezone.utc).isoformat()

    successful_count = 0
    failed_count = 0

    for package_result in packages:
        package = package_result.get("package")
        package_status = package_result.get("status")
        message = package_result.get("message")

        if not package:
            continue

        if package_status == "success":
            successful_count += 1
        else:
            failed_count += 1

        conn.execute(
            """
            UPDATE update_job_packages
            SET status = ?,
                message = ?
            WHERE job_id = ?
              AND package = ?
            """,
            (
                package_status,
                message,
                job_id,
                package
            )
        )

    conn.execute(
        """
        UPDATE update_jobs
        SET status = ?,
            finished_at = ?,
            reboot_required = ?
        WHERE id = ?
        """,
        (
            status,
            now,
            reboot_required,
            job_id
        )
    )

    conn.execute(
        """
        INSERT INTO update_history (
            client_id,
            job_id,
            status,
            package_count,
            successful_count,
            failed_count,
            reboot_required,
            started_at,
            finished_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job["client_id"],
            job_id,
            status,
            len(packages),
            successful_count,
            failed_count,
            reboot_required,
            job["started_at"],
            now
        )
    )

    conn.commit()
    conn.close()

    return jsonify({
        "status": "ok",
        "job_id": job_id,
        "job_status": status,
        "successful_count": successful_count,
        "failed_count": failed_count,
        "reboot_required": bool(reboot_required)
    })


@app.route(
    "/api/clients/<int:client_id>/update-jobs/pending",
    methods=["GET"]
)
def claim_pending_update_job(client_id):

    connection = get_connection()

    try:

        # BEGIN IMMEDIATE sorgt dafür, dass während der
        # Auswahl/Übernahme kein anderer Agent denselben
        # pending Job gleichzeitig übernehmen kann.
        connection.execute("BEGIN IMMEDIATE")

        cursor = connection.cursor()

        # ----------------------------------------------------
        # Client prüfen
        # ----------------------------------------------------

        cursor.execute("""
            SELECT
                id,
                hostname
            FROM clients
            WHERE id = ?
        """, (client_id,))

        client_row = cursor.fetchone()

        if client_row is None:

            connection.rollback()

            return jsonify({
                "status": "error",
                "message": "Client not found"
            }), 404

        # ----------------------------------------------------
        # Ältesten pending Job holen
        # ----------------------------------------------------

        cursor.execute("""
            SELECT
                id,
                client_id,
                created_at,
                reboot_required
            FROM update_jobs
            WHERE client_id = ?
            AND status = 'pending'
            ORDER BY id ASC
            LIMIT 1
        """, (client_id,))

        job_row = cursor.fetchone()

        if job_row is None:

            connection.commit()

            return jsonify({
                "status": "no_job"
            }), 204

        job_id = job_row["id"]

        started_at = datetime.now(timezone.utc).isoformat()

        # ----------------------------------------------------
        # Job übernehmen
        # ----------------------------------------------------

        cursor.execute("""
            UPDATE update_jobs
            SET
                status = 'running',
                started_at = ?
            WHERE id = ?
            AND status = 'pending'
        """, (
            started_at,
            job_id
        ))

        if cursor.rowcount != 1:

            connection.rollback()

            return jsonify({
                "status": "error",
                "message": "Job could not be claimed"
            }), 409

        # ----------------------------------------------------
        # Pakete laden
        # ----------------------------------------------------

        cursor.execute("""
            SELECT
                package,
                installed_version,
                target_version,
                status
            FROM update_job_packages
            WHERE job_id = ?
            ORDER BY package
        """, (job_id,))

        package_rows = cursor.fetchall()

        connection.commit()

        print(
            f"Update job claimed: "
            f"Job #{job_id} "
            f"Client {client_row['hostname']} "
            f"Packages: {len(package_rows)}"
        )

        return jsonify({
            "status": "claimed",
            "job_id": job_id,
            "client_id": client_id,
            "hostname": client_row["hostname"],
            "created_at": job_row["created_at"],
            "started_at": started_at,
            "reboot_required": job_row["reboot_required"],
            "package_count": len(package_rows),
            "packages": [
                dict(row)
                for row in package_rows
            ]
        })

    except Exception as error:

        connection.rollback()

        print(
            f"Error claiming update job "
            f"for client {client_id}: {error}"
        )

        return jsonify({
            "status": "error",
            "message": "Could not claim update job"
        }), 500

    finally:

        connection.close()


# ============================================================
# UPDATE JOB DETAILS
# ============================================================

@app.route(
    "/api/update-jobs/<int:job_id>",
    methods=["GET"]
)
@login_required
def update_job(job_id):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            j.id,
            j.client_id,
            c.hostname,
            c.ip,
            j.status,
            j.created_at,
            j.started_at,
            j.finished_at,
            j.reboot_required
        FROM update_jobs j
        JOIN clients c
            ON c.id = j.client_id
        WHERE j.id = ?
    """, (job_id,))

    job_row = cursor.fetchone()

    if job_row is None:

        connection.close()

        return jsonify({
            "status": "error",
            "message": "Update job not found"
        }), 404

    cursor.execute("""
        SELECT
            id,
            package,
            installed_version,
            target_version,
            status,
            message
        FROM update_job_packages
        WHERE job_id = ?
        ORDER BY package
    """, (job_id,))

    package_rows = cursor.fetchall()

    connection.close()

    job = dict(job_row)

    job["packages"] = [
        dict(row)
        for row in package_rows
    ]

    job["package_count"] = len(package_rows)

    job["successful_count"] = sum(
        1
        for row in package_rows
        if row["status"] == "success"
    )

    job["failed_count"] = sum(
        1
        for row in package_rows
        if row["status"] == "failed"
    )

    return jsonify(job)


# ============================================================
# UPDATE HISTORY
# ============================================================

@app.route(
    "/api/clients/<int:client_id>/update-history",
    methods=["GET"]
)
@login_required
def client_update_history(client_id):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            client_id,
            job_id,
            status,
            package_count,
            successful_count,
            failed_count,
            reboot_required,
            started_at,
            finished_at
        FROM update_history
        WHERE client_id = ?
        ORDER BY id DESC
    """, (client_id,))

    rows = cursor.fetchall()

    connection.close()

    return jsonify([
        dict(row)
        for row in rows
    ])


# ============================================================
# ALL UPDATE HISTORY
# ============================================================

@app.route(
    "/api/update-history",
    methods=["GET"]
)
@login_required
def update_history():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            h.id,
            h.client_id,
            c.hostname,
            c.ip,
            h.job_id,
            h.status,
            h.package_count,
            h.successful_count,
            h.failed_count,
            h.reboot_required,
            h.started_at,
            h.finished_at
        FROM update_history h
        JOIN clients c
            ON c.id = h.client_id
        ORDER BY h.id DESC
    """)

    rows = cursor.fetchall()

    connection.close()

    return jsonify([
        dict(row)
        for row in rows
    ])


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000
    )
