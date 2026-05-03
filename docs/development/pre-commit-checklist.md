# Pre-Commit Checklist (lokal)

Ziel: CI-Fehler früh lokal finden, bevor ein Commit/PR erstellt wird.

## 1) Python Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## 2) Pflicht-Checks vor jedem Commit

```bash
ruff check src/ tests/
black --target-version py312 --check src/ tests/
PYTHONPATH=src pytest -q tests/test_mock_pipeline.py tests/test_mqtt_adapter.py -k fake_client
```

Wenn Black Unterschiede findet:

```bash
black --target-version py312 src/ tests/
```

## 3) Optionaler MQTT-Integrationstest (nur wenn Broker erreichbar)

```bash
export MQTT_IT_BROKER=<HOST>
export MQTT_IT_PORT=1883
PYTHONPATH=src pytest -q tests/test_mqtt_adapter.py -k integration
```

## 4) Commit nur bei grün

- Kein `ruff` Fehler
- `black --check` grün
- relevante Tests grün
