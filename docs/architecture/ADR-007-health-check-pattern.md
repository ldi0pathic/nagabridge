# ADR-007: Health Check Pattern für alle Adapter

## Status
Accepted

## Datum
2026-03-29

## Kontext

NagaBridge besteht aus mehreren unabhängigen Modulen die über
den Event Bus kommunizieren. Bei automatischen Updates
(siehe ADR-010) muss das System zuverlässig erkennen ob ein
Update erfolgreich war oder ein Rollback notwendig ist.

Zusätzlich soll der Betriebszustand des Systems jederzeit
transparent sein – für Debugging, Monitoring und die
zukünftige Web-UI.

## Entscheidung

Jeder Adapter implementiert einen eigenen **Health Check**
und publisht seinen Status regelmäßig auf dem Bus:
```
system/health/<adapter_name>
```

Ein zentraler **Health Monitor** aggregiert alle Status-Meldungen
und publisht einen Gesamtstatus:
```
system/health/overall
```

### Health Status Werte
```
ok        – Adapter läuft normal
degraded  – Adapter läuft, aber mit Einschränkungen
            (z.B. BLE verbunden aber keine Daten seit 30s)
failed    – Adapter ausgefallen
            (z.B. keine BLE Verbindung)
```

### Adapter-spezifische Health Checks

Jeder Adapter definiert selbst was "gesund" bedeutet:

* **BLE Adapter Powerstream**
  ok: verbunden + authentifiziert + Daten in letzten 10s
  degraded: verbunden aber keine Daten
  failed: nicht verbunden

* **MQTT Adapter**
  ok: verbunden mit Broker
  failed: keine Verbindung zum Broker

* **BLE Adapter Delta2Max**
  ok: verbunden + authentifiziert + Daten in letzten 10s
  degraded: verbunden aber keine Daten
  failed: nicht verbunden

### Interface

Jeder Adapter erbt von `Adapter` (`core/adapter.py`) und implementiert
die abstrakte `health`-Property. Das Publizieren erfolgt über eine
private `_publish_health()`-Methode im jeweiligen Adapter:

```python
# core/health.py – HealthStatus.to_payload()
{
    "adapter":   "<adapter_name>",
    "state":     "ok" | "degraded" | "failed",
    "detail":    "<beschreibender Text>",
    "timestamp": <float, time.monotonic()>
}
```

Der zentrale Health Monitor (`main.py: _health_monitor`) publiziert
den aggregierten Gesamtstatus auf `system/health/overall`:

```python
{
    "state":     "ok" | "degraded" | "failed",
    "adapters":  {"<name>": "<state>", ...},
    "timestamp": <float, time.monotonic()>
}
```

### Health Check Intervall

* Adapter publishen ihren Status bei **jeder Statusänderung** sofort
* Health Monitor publiziert `system/health/overall` alle **30 Sekunden**

## Betrachtete Alternativen

### Alternative A: Zentraler Health Check

Ein Monitor prüft aktiv alle Adapter von außen.

**Nachteile:**
* Monitor muss alle Adapter kennen – Tight Coupling
* widerspricht dem Bus-Prinzip

**Verworfen:** Widerspricht ADR-001.

### Alternative B: Kein Health Check

**Nachteile:**
* kein automatischer Rollback möglich
* kein Monitoring
* Debugging schwierig

**Verworfen:** Nicht akzeptabel für automatisches Deployment.

## Konsequenzen

**Positiv:**
* automatischer Rollback nach Update möglich (siehe ADR-010)
* Systemzustand jederzeit transparent
* ioBroker kann system/health/# abonnieren
* Web-UI kann Systemstatus visualisieren
* jeder Adapter ist unabhängig testbar

**Negativ:**
* jeder Adapter muss Health Check implementieren
* minimaler zusätzlicher Bus-Traffic

## Referenzen

* ADR-001: Event Bus als zentrales Kommunikationsmuster
* ADR-010: Deployment – Verzeichnisse, Symlinks und konfigurierbarer Update-Trigger
* Health Check Pattern (Microsoft Azure Architecture Patterns)
