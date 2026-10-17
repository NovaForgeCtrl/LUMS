# LUMS Quick Start — English (UK)

This concise guide is for people who are new to LUMS or Linux. It is not a
complete translation of every technical manual. The detailed project
documentation is maintained in English. [Language index](../../README.md).

## What is LUMS?

LUMS centrally manages Linux computers. The server displays clients, installed
software, and available updates. An agent on each client carries out approved
actions with the computer's package manager: APT on Debian/Ubuntu and pacman
on Arch Linux. LUMS does not automatically install every update.

## If you only use LUMS

Open the web address provided by your administrator and sign in with your own
account. Available actions depend on your permissions. Do not share your
account or a client token. Choose a language in the upper-right corner of the
sign-in page; after signing in, LUMS can save the choice to your account.

## Installation and operation

A test run is not a production server. A secure production deployment needs,
among other things, HTTPS, a protected application secret, persistent database
storage, and verified backups. The server and Linux clients are set up
separately. Follow the [installation guide](../../../install.md) carefully.
Replace placeholders such as `LUMS-SERVER` and check every path before running
a command. If LUMS is already running, use the upgrade instructions in the
[administration guide](../../../administration.md), not the first-install
procedure.

During a normal upgrade, never delete the Docker volume `lums-data`; it
contains the database. Keep the existing secret and backup mounts and the
container security settings. Example commands are not universal—compare them
with your running container first.

## First checks when something goes wrong

On the server, these commands show the container state, recent application
logs, and Nginx status:

```bash
sudo docker ps -a --filter name=lums
sudo docker logs --tail 100 lums
sudo systemctl status nginx --no-pager
sudo nginx -t
```

`sudo` may ask for your Linux password. These checks do not change
configuration. Do not delete the database or Docker volume, run the container
as privileged, or disable security controls as a first step. Remove passwords,
tokens, keys, and personal information before sharing logs.

## Detailed documentation

* [Project overview](../../../README.md)
* [Installation and upgrades](../../../install.md)
* [Administration and backups](../../../administration.md)
* [Troubleshooting](../../../troubleshooting.md)
* [Security model](../../../security.md)
