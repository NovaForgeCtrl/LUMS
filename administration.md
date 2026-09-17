# LUMS Administration Guide

## Linux Update Management Server

This document covers the daily operation and administration of an installed LUMS system.

---

# 1. Service Overview

The LUMS environment contains several services.

## Server

```text
lums.service
nginx.service
```

## Client

```text
lums-agent.service
lums-agent.timer
```

---

# 2. Check the LUMS Server

```bash
sudo systemctl status lums.service
```

A healthy service should show:

```text
Active: active (running)
```

Quick check:

```bash
sudo systemctl is-active lums.service
```

Expected:

```text
active
```

---

# 3. Restart LUMS

```bash
sudo systemctl restart lums.service
```

Then:

```bash
sudo systemctl status lums.service
```

Test:

```bash
curl -k https://127.0.0.1/api/health
```

---

# 4. Nginx

Check:

```bash
sudo systemctl status nginx
```

Configuration test:

```bash
sudo nginx -t
```

Reload after configuration changes:

```bash
sudo systemctl reload nginx
```

Restart only when necessary:

```bash
sudo systemctl restart nginx
```

---

# 5. Health Check

The LUMS health endpoint is:

```text
/api/health
```

Local:

```bash
curl -k https://127.0.0.1/api/health
```

Remote:

```bash
curl -k https://SERVER_IP/api/health
```

Expected:

```json
{
  "service": "LUMS API",
  "status": "ok"
}
```

---

# 6. Check Listening Ports

Run:

```bash
sudo ss -lntp
```

Important:

```text
127.0.0.1:5000
```

should be local only.

HTTPS:

```text
*:443
```

may be externally reachable depending on the firewall.

---

# 7. Firewall

Check:

```bash
sudo ufw status verbose
```

Typical rules:

```text
22/tcp
80/tcp
443/tcp
```

Port:

```text
5000/tcp
```

should not be exposed.

---

# 8. Manage Clients

A client normally has:

```text
ID
hostname
IP
operating system
kernel
architecture
agent version
last_seen
enabled state
available updates
```

Client information is populated by the agent report.

---

# 9. Client Authentication

Each client uses an individual token.

The token is sent as:

```http
Authorization: Bearer <TOKEN>
```

The server stores only the token hash.

Never place the token into:

* Git
* screenshots
* public documentation
* shell history where avoidable
* issue trackers
* chat messages

---

# 10. Disable a Client

If a client should temporarily stop communicating with LUMS, disable the client in the LUMS administration interface/database.

A disabled client should no longer be accepted by the client authentication layer.

---

# 11. Token Rotation

When rotating a token:

1. create a new token
2. update `/etc/default/lums-agent`
3. protect the configuration
4. test authentication
5. revoke the old token

Check configuration permissions:

```bash
sudo ls -l /etc/default/lums-agent
```

Expected:

```text
-rw------- root root
```

---

# 12. Update Jobs

An update job contains:

```text
Job ID
Client ID
Status
Creation time
Start time
Finish time
Reboot requirement
Packages
```

Typical lifecycle:

```text
pending
   ↓
running
   ↓
success
```

Possible final states can also include failure or partial completion depending on the execution result.

---

# 13. Inspect Update Jobs

Run on the server:

```bash
sudo -u lums sqlite3 /var/lib/lums/lums.db \
"SELECT id, client_id, status, created_at, started_at, finished_at, reboot_required FROM update_jobs ORDER BY id;"
```

---

# 14. Inspect Update Packages

```bash
sudo -u lums sqlite3 /var/lib/lums/lums.db \
"SELECT id, job_id, package, installed_version, target_version, status FROM update_job_packages ORDER BY id;"
```

This is useful when investigating a failed update.

---

# 15. Available Updates

```bash
sudo -u lums sqlite3 /var/lib/lums/lums.db \
"SELECT client_id, package, installed_version, available_version FROM available_updates ORDER BY client_id, package;"
```

Remember:

The server inventory represents the last report received from the client.

It is not a live query of APT.

---

# 16. Refresh Client Inventory

To force a client to report immediately:

```bash
sudo systemctl start lums-agent.service
```

The agent will:

```text
collect
   ↓
report
   ↓
check job
```

If an update job was executed, it also performs a second report.

---

# 17. Agent Timer

Check:

```bash
systemctl list-timers lums-agent.timer
```

Check status:

```bash
systemctl status lums-agent.timer
```

Start:

```bash
sudo systemctl start lums-agent.timer
```

Stop:

```bash
sudo systemctl stop lums-agent.timer
```

Enable at boot:

```bash
sudo systemctl enable lums-agent.timer
```

---

# 18. Agent Service

The agent is a `oneshot` service.

This means the service starts, performs its work and exits.

That is normal.

Check:

```bash
sudo systemctl status lums-agent.service
```

The timer is what schedules future executions.

---

# 19. Agent Logs

```bash
sudo journalctl -u lums-agent.service
```

Last 100 lines:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Live:

```bash
sudo journalctl \
    -u lums-agent.service \
    -f
```

---

# 20. LUMS Logs

```bash
sudo journalctl -u lums.service
```

Last 100 lines:

```bash
sudo journalctl \
    -u lums.service \
    -n 100 \
    --no-pager
```

Live:

```bash
sudo journalctl \
    -u lums.service \
    -f
```

---

# 21. Database

Database:

```text
/var/lib/lums/lums.db
```

Open:

```bash
sudo -u lums sqlite3 /var/lib/lums/lums.db
```

Show tables:

```sql
.tables
```

Integrity:

```sql
PRAGMA integrity_check;
```

Exit:

```sql
.quit
```

---

# 22. Database Backup

Create a timestamped copy:

```bash
sudo cp \
    /var/lib/lums/lums.db \
    "/var/lib/lums/lums.db.$(date +%Y%m%d-%H%M%S).backup"
```

For regular operation, backups should be copied to separate storage.

A backup on the same disk does not protect against disk failure.

---

# 23. What Should Be Backed Up?

At minimum:

```text
/var/lib/lums/lums.db
/etc/lums/lums.env
/etc/lums/tls/
```

The Git repository itself does not contain these secrets.

---

# 24. TLS Certificate Management

Certificate:

```text
/etc/lums/tls/lums.crt
```

Private key:

```text
/etc/lums/tls/lums.key
```

Configuration:

```text
/etc/lums/tls/lums-openssl.cnf
```

Check expiration:

```bash
openssl x509 \
    -in /etc/lums/tls/lums.crt \
    -noout \
    -dates
```

---

# 25. Server Secret

Configuration:

```text
/etc/lums/lums.env
```

Never print it into logs or documentation.

Check that it exists:

```bash
sudo grep -q '^LUMS_SECRET_KEY=' /etc/lums/lums.env \
    && echo "Secret vorhanden"
```

---

# 26. Update LUMS

Create a backup first.

Then:

```bash
cd /opt/lums-public
sudo git status
```

Pull:

```bash
sudo git pull
```

Deploy:

```bash
sudo rsync -a \
    --delete \
    --exclude='.git/' \
    /opt/lums-public/server/ \
    /opt/lums-api/
```

Permissions:

```bash
sudo chown -R lums:lums /opt/lums-api
```

Restart:

```bash
sudo systemctl restart lums.service
```

Test:

```bash
curl -k https://127.0.0.1/api/health
```

---

# 27. Update the Agent

On each client:

```bash
cd ~/lums-public
git pull
```

Copy:

```bash
sudo cp \
    agent/agent.py \
    /opt/lums-agent/agent.py
```

Check syntax:

```bash
sudo python3 -m py_compile /opt/lums-agent/agent.py
```

Copy service files if changed:

```bash
sudo cp \
    agent/lums-agent.service \
    /etc/systemd/system/lums-agent.service

sudo cp \
    agent/lums-agent.timer \
    /etc/systemd/system/lums-agent.timer
```

Reload:

```bash
sudo systemctl daemon-reload
```

---

# 28. Check Client Update Status

On the client:

```bash
apt list --upgradable 2>/dev/null
```

Count:

```bash
apt list --upgradable 2>/dev/null | tail -n +2 | wc -l
```

---

# 29. Reboot Detection

The agent checks:

```text
/var/run/reboot-required
```

If this exists, the agent reports that a reboot may be required.

LUMS does not silently reboot the machine.

---

# 30. APT Behaviour

The agent executes:

```bash
apt-get install --only-upgrade -y <package>
```

It does not automatically execute:

```bash
apt autoremove
```

It also does not automatically reboot the client.

---

# 31. Client Status

The current status calculation is based on `last_seen`.

Current thresholds:

```text
≤ 120 seconds
online

121–600 seconds
unknown

> 600 seconds
offline
```

Because the default timer runs every 15 minutes, a client may naturally become `unknown` or `offline` between reports.

This does not automatically indicate a broken client.

---

# 32. Security Maintenance

Regularly verify:

```bash
sudo systemctl status lums.service
sudo systemctl status nginx
sudo ufw status
```

Also verify:

```bash
sudo ss -lntp
```

Port 5000 should remain local.

---

# 33. Recommended Operational Routine

For a small installation:

### Daily

Check:

```text
LUMS web interface
client status
available updates
failed jobs
```

### Weekly

Check:

```text
LUMS logs
disk space
database integrity
backup status
```

### Before upgrades

Create a backup of:

```text
database
configuration
TLS material
```

---

# 34. Disk Space

Check:

```bash
df -h
```

Check LUMS directories:

```bash
sudo du -sh /var/lib/lums
sudo du -sh /opt/lums-api
```

---

# 35. Memory and CPU

Check:

```bash
free -h
```

CPU/load:

```bash
uptime
```

Processes:

```bash
top
```

---

# 36. Final Administration Checklist

```text
[ ] LUMS service active
[ ] Nginx active
[ ] HTTPS working
[ ] Firewall active
[ ] Port 5000 local only
[ ] Database backup available
[ ] Server secret protected
[ ] TLS key protected
[ ] Client tokens protected
[ ] Agents reporting
[ ] Timers active
[ ] Failed jobs reviewed
[ ] Update inventory current
[ ] Logs checked
```
