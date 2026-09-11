# LUMS – Linux Update Management Server

LUMS (Linux Update Management Server) is a lightweight update management
solution for Linux environments.

It provides a central server for:

- registering Linux clients
- collecting system and package information
- detecting available updates
- displaying connected clients
- creating remote update jobs
- tracking update results
- recording update history
- detecting reboot requirements

The project is designed primarily for Linux homelabs, test environments
and small infrastructures.

---

## Features

### LUMS Server

- Flask-based web interface
- SQLite database
- Client inventory
- Available update tracking
- Installed package inventory
- Remote update jobs
- Per-package update status
- Update history
- Reboot-required information
- REST API

### LUMS Agent

The Linux client agent:

- reports system information
- reports installed packages
- detects available updates
- checks for pending update jobs
- installs selected package updates
- reports the result to the LUMS server
- detects whether a reboot is required
- supports systemd integration

---

## Project Structure

```text
LUMS/
├── agent/
│   ├── agent.py
│   ├── lums-agent.env.example
│   └── lums-agent.service
│
├── docs/
│
├── scripts/
│
├── server/
│   ├── app.py
│   ├── init_db.py
│   ├── static/
│   │   ├── app.js
│   │   ├── client.js
│   │   └── style.css
│   └── templates/
│       ├── client.html
│       └── index.html
│
├── .gitignore
├── LICENSE
└── README.md
