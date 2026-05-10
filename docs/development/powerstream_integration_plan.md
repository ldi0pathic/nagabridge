# PowerStream Integration Plan

**Ziel:** Einen robusten, wartbaren und gut getesteten PowerStream-Adapter in nagabridge einbauen.

**Referenz-Dokumente:**
- `powerstream_getting_started.md`
- Alter Prototyp: https://github.com/ldi0pathic/ecoflow-ble-mqtt.git

**Wichtige Regeln:**
- Nach **jedem Schritt** die Datei `powerstream_status.md` aktualisieren.
- Nach **jedem größeren Schritt** Unit Tests schreiben und ausführen (`pytest ...`).
- Type7Crypto muss komplett entfernt werden.

---

## Schritt 0: Vorbereitung

- [ ] Dieses Dokument und `powerstream_getting_started.md` gelesen
- [ ] Branch anlegen: `git checkout -b feature/powerstream-integration`
- [ ] Payload-Fixtures aus dem alten Prototyp in `tests/fixtures/powerstream/` ablegen
- [ ] `powerstream_status.md` anlegen (Vorlage aus Getting Started verwenden)
- [ ] Abhängigkeiten in `pyproject.toml` prüfen (`bleak`)

**Nach Schritt 0:** `powerstream_status.md` aktualisieren.

---

## Schritt 1: Protokoll bereinigen & stabilisieren

- [ ] `src/nagabridge/adapters/powerstream/protocol.py`:
  - Type7Crypto komplett entfernen
  - Type1Crypto verbessern (Typing, Docstrings, Logging)
  - CRC8 prüfen und mit altem Prototyp abgleichen
  - UUIDs und häufige Command-IDs als Konstanten definieren
- [ ] `__init__.py` im Adapter-Ordner aktualisieren

**Unit Tests nach Schritt 1:**
- [ ] `tests/adapters/powerstream/test_protocol.py`

**Nach Schritt 1:** Status-Datei aktualisieren.

---

## Schritt 2: Parser vollständig implementieren

- [ ] `src/nagabridge/adapters/powerstream/parser.py` neu schreiben
  - Klare `parse(payload: bytes) -> dict` Funktion
  - Alle wichtigen Werte aus dem alten Prototyp (snake_case)
  - Unbekannte Payloads mit Hex-Dump loggen

**Unit Tests nach Schritt 2:**
- [ ] `tests/adapters/powerstream/test_parser.py`

**Nach Schritt 2:** Status-Datei aktualisieren.

---

## Schritt 3: BLE-Abstraktion (wiederverwendbar)

- [ ] Ordner `src/nagabridge/core/ble/` anlegen
  - `connection.py`, `client.py`, `exceptions.py`
  - Zentrale `BleConnection` Klasse mit Reconnect, Backoff und Notifications

**Unit Tests nach Schritt 3:**
- [ ] `tests/core/ble/test_connection.py`

**Nach Schritt 3:** Status-Datei aktualisieren.

---

## Schritt 4: Adapter Kern implementieren

- [ ] `src/nagabridge/adapters/powerstream/adapter.py` vollständig neu schreiben
  - Config-Handling, Type1Crypto, Parser
  - BLE-Connection nutzen
  - Authentication-Flow, Polling, Notification-Handler
  - EventBus Integration + Command-Methoden
  - Robustes Error-Handling & State-Management

**Unit Tests nach Schritt 4:**
- [ ] `tests/adapters/powerstream/test_adapter.py`

**Nach Schritt 4:** Status-Datei aktualisieren.

---

## Schritt 5: Konfiguration & Integration

- [ ] Config-Schema in `core/config.py` erweitern
- [ ] Adapter in der Haupt-Adapter-Factory registrieren
- [ ] Beispiel-Konfigurationsdatei aktualisieren

**Unit Tests nach Schritt 5:**
- [ ] Config-Validierung + Command-Tests

**Nach Schritt 5:** Status-Datei aktualisieren.

---

## Schritt 6: Dokumentation & Final Polish

- [ ] `docs/devices/powerstream.md` erstellen
- [ ] Linting, Typing und Code-Qualität prüfen
- [ ] Manuelle Tests mit echtem Gerät

**Nach Schritt 6:** Status-Datei final aktualisieren.

---

**Definition of Done**
- Type7Crypto entfernt
- Alle Tests grün
- `powerstream_status.md` ist aktuell
- Stabiler Connect, Reconnect und regelmäßige Updates
- Wichtige Commands (z. B. Einspeiseleistung setzen) funktionieren
