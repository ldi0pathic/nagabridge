# NagaBridge

NagaBridge verbindet lokale Energiegeraete ueber einen internen EventBus
mit MQTT. Der aktuelle Schwerpunkt liegt auf EcoFlow PowerStream per BLE
und der Weitergabe der Zustandsdaten an Mosquitto, ioBroker oder andere
MQTT-Subscriber im Heimnetz.

## Aktueller Stand

- PowerStream ist der am weitesten ausgebaute Adapter.
- MQTT exportiert interne Bus-Topics standardmaessig unter
  `nagabridge/ecoflow/...`.
- Delta2 und Delta2Max sind aktuell nur Adapter-Stubs und melden
  bewusst `online = false`, bis die echte Type7/BLE-Implementierung
  produktiv vorhanden ist.

## Architektur in kurz

- `src/nagabridge/core/`: EventBus, BLE-Abstraktion, Health, Logging,
  Konfigurationsmodell
- `src/nagabridge/adapters/powerstream/`: PowerStream BLE-Adapter
- `src/nagabridge/adapters/mqtt/`: MQTT-Bridge fuer Bus-Topics
- `tests/`: Unit- und Integrationsnahe Tests
- `docs/`: ADRs, Betriebsdoku und Geraetehinweise

Der PowerStream publiziert intern auf:

- `ecoflow/powerstream/state`
- `ecoflow/powerstream/bat_state`
- `ecoflow/powerstream/command`

Der MQTT-Adapter mappt diese Topics standardmaessig auf:

- `nagabridge/ecoflow/powerstream/state`
- `nagabridge/ecoflow/powerstream/bat_state`
- `nagabridge/ecoflow/powerstream/command` (Inbound-Command Richtung Adapter)

Optional kann der MQTT-Topic-Vertrag versioniert werden. Dann lautet das Schema:

- `nagabridge/v<version>/<domain>/<entity>/<type>`
- Beispiel: `nagabridge/v1/ecoflow/powerstream/state`

Beispiel fuer einen Command via MQTT:

- Topic: `nagabridge/ecoflow/powerstream/command`
- Payload: `{"command":"get_status"}`
- Payload: `{"command":"set_load_power","watts":250}`

In ioBroker erscheinen sie entsprechend als:

- `mqtt.0.nagabridge.ecoflow.powerstream.state`
- `mqtt.0.nagabridge.ecoflow.powerstream.bat_state`

## Quickstart

### Voraussetzungen

- Python 3.11+
- fuer lokale Entwicklung: Python 3.12 empfohlen
- fuer PowerStream-Betrieb: BLE faehige Linux-/Raspberry-Pi-Umgebung

### Installation

```bash
git clone <repo-url>
cd nagabridge
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Linux/macOS:

```bash
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

### Konfiguration

Beispiel:

```toml
[system]
log_level = "INFO"

[[adapters.ble_device]]
name = "Powerstream"
mac = "AA:BB:CC:DD:EE:FF"
type = "powerstream"
serial_number = "POWERSTREAM_SERIAL"
user_id = "ECOFLOW_USER_ID"
poll_interval_seconds = 10
reconnect_attempts = 3
reconnect_backoff_seconds = 1
write_with_response = false

[mqtt]
host = "192.168.1.10"
port = 1883
```

### Starten

Konfiguration pruefen:

```bash
python -m nagabridge.main --config ./nagabridge.toml --check-config
```

Bridge starten:

```bash
python -m nagabridge.main --config ./nagabridge.toml
```

## Lokale Checks

Im Repo liegt ein lokaler Check-Runner, der Ruff, Mypy und Pytest in der
gleiche Richtung wie die CI ausfuehrt.

Automatisch fixen und dann pruefen:

```powershell
.\check-local.ps1
```

Nur CI-aehnlich pruefen, ohne automatische Aenderungen:

```powershell
.\check-local.ps1 -CheckOnly
```

Falls `.venv` fehlt oder kaputt ist:

```powershell
Remove-Item .venv -Recurse -Force
.\check-local.ps1 -Setup
```

## Betrieb auf Raspberry Pi

Fuer einen MQTT-nahen Smoke-Test ohne echte BLE-Hardware:

- [raspi-smoke-test.md](docs/operations/raspi-smoke-test.md)

Fuer einen robusten `systemd`-Service mit `rfkill`-/Bluetooth-Workaround:

- [systemd-service.md](docs/operations/systemd-service.md)

## Weiterfuehrende Doku

- [PowerStream](docs/devices/powerstream.md)
- [Architektur-ADRs](docs/architecture/README.md)
- [Pre-commit Checklist](docs/development/pre-commit-checklist.md)
- [CI Failure Playbook](docs/development/ci-failure-playbook.md)

## Bekannte Grenzen

- Delta2 und Delta2Max sind noch nicht produktiv implementiert.
- Reale BLE-Geraetetests sind noch duenn im Vergleich zu den Unit-Tests.
- Einige Betriebsdokumente sind noch Raspberry-Pi-zentriert und nicht
  als vollstaendige allgemeine Deployment-Anleitung ausgearbeitet.
