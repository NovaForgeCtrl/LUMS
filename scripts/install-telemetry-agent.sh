#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
    echo "Run this installer with sudo." >&2
    exit 1
fi

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
config_file=/etc/default/lums-agent

if [ ! -r "$config_file" ]; then
    echo "Missing $config_file; configure the standard LUMS client first." >&2
    exit 1
fi

if ! grep -Eq '^LUMS_BASE=.+$' "$config_file" ||
    ! grep -Eq '^LUMS_TOKEN=.+$' "$config_file"; then
    echo "$config_file must define non-empty LUMS_BASE and LUMS_TOKEN values." >&2
    exit 1
fi

for file in agent/telemetry.py agent/lums-telemetry.service agent/lums-telemetry.timer; do
    if [ ! -f "$repo_root/$file" ]; then
        echo "Missing required repository file: $file" >&2
        exit 1
    fi
done

install -D -o root -g root -m 0755 \
    "$repo_root/agent/telemetry.py" \
    /usr/local/lib/lums-telemetry/telemetry.py
install -o root -g root -m 0644 \
    "$repo_root/agent/lums-telemetry.service" \
    /etc/systemd/system/lums-telemetry.service
install -o root -g root -m 0644 \
    "$repo_root/agent/lums-telemetry.timer" \
    /etc/systemd/system/lums-telemetry.timer

systemctl daemon-reload
systemctl enable --now lums-telemetry.timer

if ! systemctl start lums-telemetry.service; then
    echo "The telemetry service failed to start; recent logs follow:" >&2
    journalctl -u lums-telemetry.service -n 30 --no-pager >&2
    exit 1
fi

result=$(systemctl show --property=ExecMainStatus --value lums-telemetry.service)
if [ "$result" != "0" ]; then
    echo "The telemetry agent exited with status $result; recent logs follow:" >&2
    journalctl -u lums-telemetry.service -n 30 --no-pager >&2
    exit 1
fi

echo "LUMS telemetry agent installed and its timer is enabled."
systemctl status lums-telemetry.timer --no-pager --full
