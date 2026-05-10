# PowerStream Integration – Getting Started (von Null)

Dieses Dokument hilft einem neuen Entwickler oder Coding-Agenten, sofort produktiv zu werden.

## 1. Projektüberblick

**nagabridge** ist ein cloud-freier IoT-Gateway für EcoFlow-Geräte.  
Der PowerStream-Adapter soll:
- Über BLE verbinden
- Daten entschlüsseln (Type1Crypto)
- Werte parsen
- Über den zentralen EventBus an MQTT/ioBroker weiterleiten

**Wichtigste Referenz:**
- Alter Prototyp: https://github.com/ldi0pathic/ecoflow-ble-mqtt.git

## 2. Technische Grundlagen (PowerStream)

- Verwendet **nur Type1Crypto** (AES-CBC mit Seriennummer)
- Type7Crypto wird **nicht** benötigt → muss entfernt werden
- Wichtige BLE-UUIDs:
  - Write: `00000002-0000-1000-8000-00805f9b34fb`
  - Notify: `00000003-0000-1000-8000-00805f9b34fb`
- Authentication: EcoFlow User-ID + MD5-Hash mit Seriennummer

## 3. Aktueller Stand der Dateien

- `src/nagabridge/adapters/powerstream/protocol.py` → teilweise portiert, aber noch Type7 vorhanden
- `parser.py` → nur Stub
- `adapter.py` → nur Dummy

## 4. Voraussetzungen

- Python 3.11+
- `bleak` (BLE Library)
- `pytest`, `ruff`, `mypy` (falls aktiviert)
- Für echte Tests: Raspberry Pi mit Bluetooth + PowerStream in Reichweite

## 5. Hilfreiche Befehle

```bash
# Neuen Branch anlegen
git checkout -b feature/powerstream-integration

# Nur PowerStream-Tests ausführen
pytest tests/adapters/powerstream/ -q

# Linting
ruff check src/nagabridge/adapters/powerstream/

# Formatierung
ruff format src/nagabridge/adapters/powerstream/
```

## 6. Weiterführende Dokumente

- `docs/development/powerstream_integration_plan.md` → detaillierter Plan
- `docs/development/powerstream_status.md` → aktueller Fortschritt
