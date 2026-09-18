====== LUMS Administration Guide ======

===== Linux Update Management Server =====

This document covers the daily operation, maintenance and administration of an installed LUMS system.

It describes the LUMS server, Nginx reverse proxy, client agent, authentication, database, TLS configuration, updates and operational checks.

---

===== 1. Service Overview =====

A LUMS installation consists of a server component and one or more client agents.

==== Server ====

The LUMS server uses:

<code>
lums.service
nginx.service
</code>

The Flask application runs locally and is exposed through Nginx.

The application itself listens on:

<code>
127.0.0.1:5000
</code>

Nginx provides the external HTTP/HTTPS interface.

==== Client ====

Each managed client uses:

<code>
lums-agent.service
lums-agent.timer
</code>

The agent is implemented as a ''oneshot'' service.

The timer starts the agent periodically.

---

===== 2. Check the LUMS Server =====

Check the service:

<code bash>
sudo systemctl status lums.service
</code>

A healthy service should show:

<code>
Active: active (running)
</code>

Quick check:

<code bash>
sudo systemctl is-active lums.service
</code>

Expected:

<code>
active
</code>

---

===== 3. Restart LUMS =====

Restart the application:

<code bash>
sudo systemctl restart lums.service
</code>

Then verify:

<code bash>
sudo systemctl status lums.service
</code>

Test the API through the local HTTPS reverse proxy:

<code bash>
curl -k https://127.0.0.1/api/health
</code>

Expected response:

<code>
{
  "service": "LUMS API",
  "status": "ok"
}
</code>

---

===== 4. Nginx =====

Check Nginx:

<code bash>
sudo systemctl status nginx
</code>

Test the configuration:

<code bash>
sudo nginx -t
</code>

Reload after configuration changes:

<code bash>
sudo systemctl reload nginx
</code>

Restart only when necessary:

<code bash>
sudo systemctl restart nginx
</code>

Nginx terminates TLS and forwards requests to the local Flask application.

---

===== 5. HTTPS and Health Check =====

The LUMS health endpoint is:

<code>
/api/health
</code>

Local test:

<code bash>
curl -k https://127.0.0.1/api/health
</code>

Remote test:

<code bash>
curl -k https://SERVER_IP/api/health
</code>

Expected:

<code>
{
  "service": "LUMS API",
  "status": "ok"
}
</code>

The <code>-k</code> option is useful when testing with the self-signed LUMS certificate.

A trusted certificate can be used instead if the environment provides an appropriate internal or public CA.

---

===== 6. Check Listening Ports =====

Run:

<code bash>
sudo ss -lntp
</code>

The Flask application should listen locally:

<code>
127.0.0.1:5000
</code>

Port 5000 must not be exposed directly to the network.

Nginx provides the external interface:

<code>
*:80
*:443
</code>

HTTP is used for redirection to HTTPS.

HTTPS is the actual LUMS application interface.

---

===== 7. Firewall =====

Check:

<code bash>
sudo ufw status verbose
</code>

Typical externally required ports are:

<code>
22/tcp
80/tcp
443/tcp
</code>

Port 5000 should not be exposed.

The exact firewall configuration depends on the surrounding network and management requirements.

---

===== 8. Manage Clients =====

A LUMS client normally contains information such as:

<code>
ID
hostname
IP address
operating system
kernel
architecture
agent version
last_seen
enabled state
available updates
</code>

Client inventory is populated by the agent report.

The server therefore represents the most recently received client state.

It is not a live query of the client.

---

===== 9. Client Authentication =====

Each client uses an individual authentication token.

The token is transmitted using HTTP Bearer authentication:

<code>
Authorization: Bearer &lt;TOKEN&gt;
</code>

The server does not need to store the plaintext token.

The client token is stored as a SHA-256 hash.

The authentication layer verifies:

<code>
Bearer token
        |
        v
SHA-256 hash
        |
        v
client_token_hash
        |
        v
client enabled?
        |
        v
token not revoked?
</code>

Client authentication is separate from the administrator login.

The client-specific endpoint used by the agent to retrieve its own information is:

<code>
/api/client/me
</code>

Never place a real client token into:

* Git repositories
* screenshots
* public documentation
* issue trackers
* chat messages
* source code
* configuration examples

Only example placeholders should be documented.

---

===== 10. Disable a Client =====

A client can be disabled through the LUMS administration interface or database administration.

A disabled client is rejected by the client authentication layer.

This prevents the client from continuing normal authenticated communication with the server.

Disabling a client does not automatically remove its historical database information.

---

===== 11. Token Rotation =====

When rotating a client token:

* create a new token
* calculate/store the corresponding token hash on the server
* update the client configuration
* protect the configuration file
* test authentication
* revoke the old token

The client configuration is stored in:

<code>
/etc/default/lums-agent
</code>

Typical configuration:

<code>
LUMS_BASE=https://SERVER_IP
LUMS_CA_FILE=/path/to/lums.crt
LUMS_TOKEN=&lt;TOKEN&gt;
</code>

Never document the real value of <code>LUMS_TOKEN</code>.

Check permissions:

<code bash>
sudo ls -l /etc/default/lums-agent
</code>

The configuration should be readable only by root where possible:

<code>
-rw------- root root
</code>

---

===== 12. Update Jobs =====

An update job contains information such as:

<code>
Job ID
Client ID
Status
Creation time
Start time
Finish time
Reboot requirement
Packages
</code>

Typical lifecycle:

<code>
pending
   |
   v
running
   |
   v
success
</code>

Other final states can occur, for example when package execution fails.

The exact result should always be verified through the job information and agent logs.

---

===== 13. Inspect Update Jobs =====

On the LUMS server:

<code bash>
sudo -u lums sqlite3 /var/lib/lums/lums.db \
"SELECT id, client_id, status, created_at, started_at, finished_at, reboot_required FROM update_jobs ORDER BY id;"
</code>

This is useful when investigating:

* failed jobs
* jobs that remain pending
* clients that did not complete an update
* reboot requirements

---

===== 14. Inspect Update Packages =====

Run:

<code bash>
sudo -u lums sqlite3 /var/lib/lums/lums.db \
"SELECT id, job_id, package, installed_version, target_version, status FROM update_job_packages ORDER BY id;"
</code>

This can be used to determine which individual package caused or contributed to an update failure.

---

===== 15. Available Updates =====

Query the current inventory:

<code bash>
sudo -u lums sqlite3 /var/lib/lums/lums.db \
"SELECT client_id, package, installed_version, available_version FROM available_updates ORDER BY client_id, package;"
</code>

Important:

The <code>available_updates</code> table represents the last report received from the client.

It is not a live APT query.

The information becomes current when the client agent reports again.

---

===== 16. Refresh Client Inventory =====

To force an immediate client report:

<code bash>
sudo systemctl start lums-agent.service
</code>

The agent performs approximately:

<code>
collect
   |
   v
report
   |
   v
check pending job
   |
   v
execute job if required
   |
   v
report again
</code>

The service is a oneshot service and exits after completing its work.

This is normal behaviour.

---

===== 17. Agent Timer =====

List the timer:

<code bash>
systemctl list-timers lums-agent.timer
</code>

Check its status:

<code bash>
sudo systemctl status lums-agent.timer
</code>

Start:

<code bash>
sudo systemctl start lums-agent.timer
</code>

Stop:

<code bash>
sudo systemctl stop lums-agent.timer
</code>

Enable at boot:

<code bash>
sudo systemctl enable lums-agent.timer
</code>

The timer is responsible for starting the agent periodically.

---

===== 18. Agent Service =====

The agent uses a <code>oneshot</code> systemd service.

This means:

<code>
start
  |
  v
collect information
  |
  v
send report
  |
  v
check jobs
  |
  v
execute update if required
  |
  v
send result/report
  |
  v
exit
</code>

Therefore this is normal:

<code>
Active: inactive (dead)
</code>

after a successful execution.

The timer is what schedules the next execution.

---

===== 19. Agent Logs =====

View all logs:

<code bash>
sudo journalctl -u lums-agent.service
</code>

Last 100 lines:

<code bash>
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
</code>

Follow live:

<code bash>
sudo journalctl \
    -u lums-agent.service \
    -f
</code>

A successful manual execution should show the report being sent and the job check being completed.

---

===== 20. LUMS Server Logs =====

View server logs:

<code bash>
sudo journalctl -u lums.service
</code>

Last 100 lines:

<code bash>
sudo journalctl \
    -u lums.service \
    -n 100 \
    --no-pager
</code>

Follow live:

<code bash>
sudo journalctl \
    -u lums.service \
    -f
</code>

These logs are useful for:

* API errors
* authentication failures
* application startup problems
* database errors
* unexpected exceptions

---

===== 21. Database =====

The LUMS database is:

<code>
/var/lib/lums/lums.db
</code>

Open it:

<code bash>
sudo -u lums sqlite3 /var/lib/lums/lums.db
</code>

Show tables:

<code sql>
.tables
</code>

Check integrity:

<code sql>
PRAGMA integrity_check;
</code>

Expected:

<code>
ok
</code>

Exit:

<code sql>
.quit
</code>

The database should not be edited manually during normal operation unless the administrator understands the schema and has created a backup first.

---

===== 22. Database Backup =====

Create a timestamped backup:

<code bash>
sudo cp \
    /var/lib/lums/lums.db \
    "/var/lib/lums/lums.db.$(date +%Y%m%d-%H%M%S).backup"
</code>

For regular operation, backups should be copied to separate storage.

A backup stored on the same physical disk does not protect against:

* disk failure
* filesystem corruption
* accidental deletion
* complete system loss

---

===== 23. What Should Be Backed Up? =====

At minimum, protect:

<code>
/var/lib/lums/lums.db
/etc/lums.env
/etc/nginx/ssl/lums.crt
/etc/nginx/ssl/lums.key
</code>

The Git repository contains the application source code but must not contain:

* server secrets
* client tokens
* private TLS keys
* production database files

Configuration and secret material should therefore be backed up separately from Git.

---

===== 24. TLS Certificate Management =====

The current LUMS TLS files are managed by Nginx.

Certificate:

<code>
/etc/nginx/ssl/lums.crt
</code>

Private key:

<code>
/etc/nginx/ssl/lums.key
</code>

The certificate is used by Nginx for HTTPS.

Check certificate information:

<code bash>
sudo openssl x509 \
    -in /etc/nginx/ssl/lums.crt \
    -noout \
    -subject \
    -issuer \
    -dates
</code>

Check the SAN:

<code bash>
sudo openssl x509 \
    -in /etc/nginx/ssl/lums.crt \
    -noout \
    -ext subjectAltName
</code>

The LUMS client can use the certificate as its CA file when configured with:

<code>
LUMS_CA_FILE=/etc/nginx/ssl/lums.crt
</code>

The certificate must contain the correct Subject Alternative Name for the server address used by the client.

---

===== 25. Server Secret =====

The LUMS server secret is stored outside the Git repository:

<code>
/etc/lums.env
</code>

The systemd service loads this file using:

<code>
EnvironmentFile=/etc/lums.env
</code>

Never print the complete file into logs or documentation.

Check that the secret exists without displaying its value:

<code bash>
sudo grep -q '^LUMS_SECRET_KEY=' /etc/lums.env \
    && echo "Secret vorhanden"
</code>

Never use:

<code bash>
cat /etc/lums.env
</code>

for routine documentation or troubleshooting because this could expose the secret.

---

===== 26. Update LUMS Server =====

Before updating the server:

* verify that a database backup exists
* verify that configuration and TLS material are backed up
* check the current Git status
* review the changes before deploying

Check the repository:

<code bash>
cd /opt/lums-public
git status
</code>

Fetch current changes:

<code bash>
git fetch origin
</code>

Review incoming commits:

<code bash>
git log --oneline HEAD..origin/main
</code>

If the repository is clean and the update is intended:

<code bash>
git pull --ff-only origin main
</code>

Do not use a force pull or force push for normal administration.

Deploy the server application:

<code bash>
sudo rsync -a \
    --delete \
    --exclude='.git/' \
    /opt/lums-public/server/ \
    /opt/lums-api/
</code>

Restore correct ownership:

<code bash>
sudo chown -R lums:lums /opt/lums-api
</code>

Compile-check the deployed application:

<code bash>
sudo python3 -m py_compile \
    /opt/lums-api/app.py \
    /opt/lums-api/init_db.py
</code>

Restart LUMS:

<code bash>
sudo systemctl restart lums.service
</code>

Check:

<code bash>
sudo systemctl status lums.service
</code>

Finally test:

<code bash>
curl -k https://127.0.0.1/api/health
</code>

Important:

The Git deployment must not overwrite:

<code>
/var/lib/lums/lums.db
/etc/lums.env
/etc/nginx/ssl/
</code>

These are runtime configuration and data, not application source files.

---

===== 27. Update the Agent =====

The agent source is maintained in the Git repository.

On a client:

<code bash>
cd /path/to/LUMS
git pull --ff-only origin main
</code>

Check the source syntax before deploying:

<code bash>
python3 -m py_compile agent/agent.py
</code>

Copy the agent:

<code bash>
sudo cp \
    agent/agent.py \
    /opt/lums-agent/agent.py
</code>

Check the deployed agent:

<code bash>
sudo python3 -m py_compile \
    /opt/lums-agent/agent.py
</code>

Copy the service files if they changed:

<code bash>
sudo cp \
    agent/lums-agent.service \
    /etc/systemd/system/lums-agent.service
</code>

<code bash>
sudo cp \
    agent/lums-agent.timer \
    /etc/systemd/system/lums-agent.timer
</code>

Reload systemd:

<code bash>
sudo systemctl daemon-reload
</code>

Run the agent manually:

<code bash>
sudo systemctl start lums-agent.service
</code>

Then inspect:

<code bash>
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
</code>

---

===== 28. Check Client Update Status =====

On a Debian/Ubuntu client:

<code bash>
apt list --upgradable 2>/dev/null
</code>

Count available updates:

<code bash>
apt list --upgradable 2>/dev/null | tail -n +2 | wc -l
</code>

The result should correspond to the inventory reported by the agent after the next successful report.

---

===== 29. Reboot Detection =====

The agent checks:

<code>
/var/run/reboot-required
</code>

If this file exists, the agent reports that a reboot may be required.

LUMS does not silently reboot the client.

A reboot remains an explicit administrative action.

---

===== 30. APT Behaviour =====

When executing a package update, the agent uses:

<code bash>
apt-get install --only-upgrade -y &lt;package&gt;
</code>

The agent does not automatically execute:

<code bash>
apt autoremove
</code>

It also does not automatically reboot the client.

Only packages selected by the LUMS update job are processed.

---

===== 31. Client Status =====

Client status is based on the <code>last_seen</code> timestamp.

Current thresholds:

<code>
≤ 120 seconds
online

121–600 seconds
unknown

> 600 seconds
> offline
>
> </code>

Because the default agent timer runs periodically, a client can naturally transition to <code>unknown</code> or <code>offline</code> between reports.

This does not automatically mean that the client is broken.

When investigating a stale client, check:

<code bash>
sudo systemctl status lums-agent.timer
</code>

and:

<code bash>
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
</code>

---

===== 32. Security Maintenance =====

Regularly verify the main services:

<code bash>
sudo systemctl status lums.service
</code>

<code bash>
sudo systemctl status nginx
</code>

Check the firewall:

<code bash>
sudo ufw status verbose
</code>

Check listening ports:

<code bash>
sudo ss -lntp
</code>

The Flask port:

<code>
127.0.0.1:5000
</code>

must remain local.

HTTPS should be provided through Nginx.

---

===== 33. Recommended Operational Routine =====

==== Daily ====

Check:

* LUMS web interface
* client status
* available updates
* failed update jobs
* clients with stale <code>last_seen</code>

==== Weekly ====

Check:

* LUMS logs
* agent logs
* disk space
* database integrity
* backup status
* TLS certificate expiration
* firewall configuration

==== Before upgrades ====

Create or verify backups of:

<code>
database
server configuration
server secret
TLS certificate
TLS private key
</code>

---

===== 34. Disk Space =====

Check filesystem usage:

<code bash>
df -h
</code>

Check LUMS database storage:

<code bash>
sudo du -sh /var/lib/lums
</code>

Check deployed application:

<code bash>
sudo du -sh /opt/lums-api
</code>

Check repository:

<code bash>
du -sh /opt/lums-public
</code>

Insufficient disk space can cause problems with:

* SQLite
* system logs
* package updates
* application deployment
* backups

---

===== 35. Memory and CPU =====

Memory:

<code bash>
free -h
</code>

System load:

<code bash>
uptime
</code>

Processes:

<code bash>
top
</code>

For service-specific resource information:

<code bash>
systemctl status lums.service
</code>

---

===== 36. Quick Diagnostic Sequence =====

When LUMS appears to be unavailable, check the layers in this order:

<code>
1. LUMS service
       |
       v
2. Nginx
       |
       v
3. HTTPS
       |
       v
4. API health endpoint
       |
       v
5. Client authentication
       |
       v
6. Agent service
       |
       v
7. Agent timer
       |
       v
8. Database
</code>

Commands:

<code bash>
sudo systemctl is-active lums.service
</code>

<code bash>
sudo systemctl is-active nginx
</code>

<code bash>
curl -k https://127.0.0.1/api/health
</code>

<code bash>
sudo systemctl status lums-agent.timer
</code>

<code bash>
sudo journalctl -u lums.service -n 50 --no-pager
</code>

<code bash>
sudo journalctl -u lums-agent.service -n 50 --no-pager
</code>

---

===== 37. Final Administration Checklist =====

<code>
[ ] LUMS service active
[ ] Nginx active
[ ] HTTPS working
[ ] /api/health responds correctly
[ ] Firewall active
[ ] Port 5000 local only
[ ] Database backup available
[ ] Server secret protected
[ ] TLS certificate protected
[ ] TLS private key protected
[ ] Client tokens protected
[ ] Client authentication working
[ ] Agents reporting
[ ] Agent timers active
[ ] Failed jobs reviewed
[ ] Update inventory current
[ ] Logs checked
[ ] Database integrity verified
[ ] Disk space sufficient
[ ] TLS certificate expiration checked
</code>

---

===== 38. Important Security Rules =====

The following rules should always be followed:

* Never commit production secrets to Git.
* Never commit client tokens to Git.
* Never commit private TLS keys to Git.
* Never expose TCP/5000 externally.
* Use HTTPS for client/server communication.
* Keep the LUMS server secret outside the Git repository.
* Keep client tokens outside the Git repository.
* Back up the database before schema changes or upgrades.
* Test application syntax before deployment.
* Test the LUMS health endpoint after deployment.
* Review systemd and agent logs after updates.
* Do not use <code>git push --force</code> for normal LUMS administration.
* Do not modify the production database without a current backup.

---

===== 39. Current LUMS Runtime Layout =====

The important runtime paths are:

<code>
/opt/lums-public/
    Git repository

/opt/lums-api/
deployed LUMS server

/opt/lums-agent/
deployed client agent

/var/lib/lums/lums.db
LUMS SQLite database

/etc/lums.env
LUMS server secret

/etc/default/lums-agent
client agent configuration

/etc/nginx/ssl/lums.crt
LUMS TLS certificate

/etc/nginx/ssl/lums.key
LUMS TLS private key

/etc/systemd/system/lums.service
LUMS server systemd unit

/etc/systemd/system/lums-agent.service
LUMS agent systemd unit

/etc/systemd/system/lums-agent.timer
LUMS agent timer </code>

This layout separates:

<code>
Source Code
     |
     v
/opt/lums-public

Deployed Application
|
v
/opt/lums-api

Runtime Database
|
v
/var/lib/lums

Secrets / Configuration
|
+---- /etc/lums.env
|
+---- /etc/default/lums-agent

TLS
|
v
/ etc/nginx/ssl/ </code>

The runtime data and secrets are intentionally kept outside the Git repository.
