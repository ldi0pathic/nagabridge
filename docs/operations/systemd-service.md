# systemd Service für NagaBridge

Ziel: NagaBridge auf dem Raspberry Pi auch dann automatisch wieder
hochziehen, wenn Bluetooth beim Boot kurz nicht bereit ist oder per
`rfkill` blockiert war.

## Beispiel-Unit

```ini
[Unit]
Description=NagaBridge
After=bluetooth.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/opt/nagabridge
Environment=PYTHONUNBUFFERED=1
ExecStartPre=/usr/sbin/rfkill unblock bluetooth
ExecStartPre=/bin/sh -c '/usr/bin/hciconfig hci0 up || /usr/bin/btmgmt power on || true'
ExecStart=/opt/nagabridge/.venv/bin/python -m nagabridge --config /opt/nagabridge/nagabridge.toml
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## Warum diese Einstellungen

- `Restart=always` und `RestartSec=10` starten den Prozess nach
  unerwartetem Ende automatisch neu.
- `After=bluetooth.target network-online.target` wartet auf Bluetooth
  und Netzwerk, bevor NagaBridge hochfährt.
- `ExecStartPre=/usr/sbin/rfkill unblock bluetooth` entfernt eine
  mögliche Boot-Blockade durch `rfkill`.
- `hciconfig hci0 up` oder `btmgmt power on` bringt den Adapter vor dem
  eigentlichen Prozessstart wieder hoch.

## Aktivierung

```bash
sudo editor /etc/systemd/system/nagabridge.service
sudo systemctl daemon-reload
sudo systemctl enable --now nagabridge.service
sudo systemctl status nagabridge.service
```

In `/etc/systemd/system/nagabridge.service` kommt nur der Inhalt aus dem
INI-Block oben.
