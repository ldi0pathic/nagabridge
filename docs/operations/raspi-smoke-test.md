# Raspberry Pi Smoke Test (MQTT-first, ohne BLE-Hardware)

Ziel: Verifizieren, dass NagaBridge vom EventBus auf MQTT publiziert.

## Voraussetzungen

- Raspberry Pi im gleichen Netz wie Mosquitto (Proxmox)
- Mosquitto läuft und akzeptiert Verbindungen vom Pi
- Python 3.11+

## 1) Installation auf dem Pi

```bash
git clone <repo-url>
cd nagabridge
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## 2) MQTT Erreichbarkeit testen

```bash
mosquitto_sub -h <MOSQUITTO_HOST> -t 'nagabridge/#' -v
```

In separater Shell:

```bash
mosquitto_pub -h <MOSQUITTO_HOST> -t 'nagabridge/health/ping' -m '{"ok":true}'
```

## 3) NagaBridge MQTT-Pipeline lokal testen

(noch ohne echte BLE-Hardware)

```bash
PYTHONPATH=src pytest -q tests/test_mqtt_adapter.py -k fake_client
```

Optional gegen echten Broker:

```bash
export MQTT_IT_BROKER=<MOSQUITTO_HOST>
export MQTT_IT_PORT=1883
PYTHONPATH=src pytest -q tests/test_mqtt_adapter.py -k integration
```

## 4) Erfolgsindikatoren

- `test_mqtt_adapter_forwards_bus_events_with_fake_client` ist grün
- Optional: Integrationstest gegen realen Broker ist grün
- Subscriber sieht Topic `nagabridge/ecoflow/powerstream/state`
