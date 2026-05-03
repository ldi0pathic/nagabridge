# ADR-012: Logging-Strategie

## Status
Accepted

## Datum
2026-05-03

## Kontext

NagaBridge läuft als dauerhafter Prozess auf einem Raspberry Pi.
ADR-003 stellte fest dass Debugging ohne Bus-Beobachtung schwierig
ist und eine Logging-Strategie definiert werden muss.

Anforderungen:
* mindestens eine Woche Log-Historie
* pro Adapter eine eigene Log-Datei für übersichtliches Debugging
* konfigurierbares Log-Level (siehe ADR-011)
* kein übermäßiger Speicherverbrauch auf der Pi SD-Karte
* zukünftig erweiterbar um einen Log-Server-Adapter

## Entscheidung

### 1. Log-Ausgabe

Jede Log-Zeile wird an zwei Ziele gleichzeitig geschrieben:

* **stdout** – systemd fängt es auf, lesbar via `journalctl -u nagabridge`
* **Datei** – pro Adapter eine eigene Datei unter `/var/log/nagabridge/`

### 2. Dateistruktur

```
/var/log/nagabridge/
├── nagabridge.log              ← Core, Bus, System (aktueller Tag)
├── nagabridge.2026-05-02.log
├── nagabridge.2026-05-01.log
├── ble-ecoflow.log             ← BLE Adapter (aktueller Tag)
├── ble-ecoflow.2026-05-02.log
├── mqtt.log                    ← MQTT Adapter (aktueller Tag)
├── mqtt.2026-05-02.log
└── ...
```

Jeder Adapter schreibt ausschließlich in seine eigene Datei.
Core, Bus und System schreiben in `nagabridge.log`.

### 3. Log-Rotation

* **Rotation:** täglich (zeitbasiert, nicht größenbasiert)
* **Aufbewahrung:** 7 Dateien pro Log (= eine Woche Historie)
* **Dateiname:** `<name>.YYYY-MM-DD.log`
* **Verwaltung:** logrotate auf dem Pi

Geschätzter Speicherbedarf bei INFO-Level:

```
~100 Bytes × 1 Event/s × 86400s = ~8MB pro Adapter pro Tag
2 Adapter + Core × 7 Tage       = ~170MB maximum
```

Bei WARNING/ERROR-Level deutlich weniger.

### 4. Log-Level

Das minimale Log-Level wird in `nagabridge.toml` konfiguriert
(siehe ADR-011):

```toml
[system]
log_level = "INFO"    # DEBUG | INFO | WARNING | ERROR
```

Das Level gilt systemweit für alle Adapter und den Core.

### 5. Log-Format

```
2026-05-03 14:23:01 [INFO ] [ble-ecoflow ] Verbindung zu Powerstream hergestellt
2026-05-03 14:23:02 [DEBUG] [bus         ] publish: ecoflow/powerstream/state
2026-05-03 14:23:02 [INFO ] [mqtt        ] State publiziert: ecoflow/powerstream/state
```

Format: `YYYY-MM-DD HH:MM:SS [LEVEL] [adapter] Nachricht`

* Timestamp: lokale Zeit
* Level: rechtsbündig auf 5 Zeichen (`DEBUG`, `INFO `, `WARN `, `ERROR`)
* Adapter-Name: linksbündig auf 12 Zeichen für lesbare Spalten

### 6. Was wird geloggt

**Core / Bus:**
* Start und Stop des Systems
* Adapter geladen / gestartet / gestoppt
* Bus-Aktivität auf DEBUG-Level

**Jeder Adapter:**
* Verbindungsaufbau und -verlust
* Health-Status-Änderungen
* empfangene und gesendete Commands auf DEBUG-Level
* Fehler und Warnungen immer unabhängig vom konfigurierten Level

**Nicht geloggt:**
* State-Daten im Normalbetrieb (zu viel Volumen)
* State-Daten sind auf DEBUG-Level optional

### 7. Erweiterbarkeit: Log-Server-Adapter

Ein zukünftiger Log-Server-Adapter ist ein normaler
Bus-Subscriber der Log-Events konsumiert und weiterleitet.
NagaBridge selbst muss dafür nicht verändert werden.

Log-Events werden auf dem Bus publiziert:

```
system/nagabridge/log
```

Payload:
```json
{
  "level": "ERROR",
  "adapter": "ble-ecoflow",
  "message": "Verbindung verloren"
}
```

Nur Ereignisse ab WARNING werden auf den Bus publiziert –
DEBUG und INFO erzeugen keinen Bus-Traffic.

## Betrachtete Alternativen

### Alternative A: Nur stdout / journalctl

**Vorteile:** kein eigener Code, journalctl ist mächtig.
**Nachteile:** keine pro-Adapter-Trennung, Log-Export
für externe Tools umständlich.
**Verworfen:** Pro-Adapter-Dateien sind für Debugging
deutlich übersichtlicher.

### Alternative B: Größenbasierte Rotation

**Vorteile:** garantierter maximaler Speicherverbrauch.
**Nachteile:** Dateinamen ohne Datum sind schwerer lesbar,
Wochengrenzen nicht klar erkennbar.
**Verworfen:** Datumsbasierte Rotation ist intuitiver.

### Alternative C: Zentrales Log-Framework (z.B. structlog)

**Vorteile:** strukturierte Logs, gut für Log-Server.
**Nachteile:** externe Abhängigkeit, Over-Engineering
für aktuellen Scope.
**Verworfen:** Python stdlib `logging` reicht vollständig.

## Konsequenzen

**Positiv:**
* eine Woche Historie pro Adapter
* übersichtliches Debugging durch getrennte Dateien
* kein eigener Rotation-Code – logrotate übernimmt
* Log-Server-Adapter später ohne Systemänderung möglich
* keine externe Abhängigkeit – Python stdlib `logging`

**Negativ:**
* logrotate muss auf dem Pi konfiguriert werden
* ~170MB maximaler Speicherbedarf bei INFO-Level

## Offene Punkte

* logrotate Konfiguration ins Repo aufnehmen
  (als `/etc/logrotate.d/nagabridge`)
* Log-Server-Adapter als zukünftiges Modul evaluieren
* Log-Level pro Adapter konfigurierbar machen
  falls sich der Bedarf zeigt

## Referenzen

* ADR-001: Event Bus
* ADR-003: State-First Bus
* ADR-011: Konfigurationsformat
* Python logging: https://docs.python.org/3/library/logging.html
* logrotate: https://linux.die.net/man/8/logrotate
