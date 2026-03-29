# ADR-007: Health Check Pattern für alle Adapter

## Status
Accepted

## Datum
2026-03-29

## Kontext

NagaBridge besteht aus mehreren unabhängigen Modulen die über
den Event Bus kommunizieren. Bei automatischen Updates
(siehe ADR-008) muss das System zuverlässig erkennen ob ein
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

Jeder Adapter erbt von AdapterBase:
```python
class AdapterBase:

    @property
    def health(self) -> HealthStatus:
        pass

    async def publish_health(self, bus):
        status = self.health
        await bus.publish(
            f"system/health/{self.name}",
            {
                "status": status.value,
                "details": status.details,
                "timestamp": status.timestamp
            }
        )
```

### Health Check Intervall

* Adapter publishen ihren Status alle **30 Sekunden**
* Bei Statusänderung sofort publishen
* Health Monitor publisht Gesamtstatus bei jeder Änderung

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
* automatischer Rollback nach Update möglich (siehe ADR-008)
* Systemzustand jederzeit transparent
* ioBroker kann system/health/# abonnieren
* Web-UI kann Systemstatus visualisieren
* jeder Adapter ist unabhängig testbar

**Negativ:**
* jeder Adapter muss Health Check implementieren
* minimaler zusätzlicher Bus-Traffic

## Referenzen

* ADR-001: Event Bus als zentrales Kommunikationsmuster
* ADR-008: Blue-Green Deployment & Auto-Rollback
* Health Check Pattern (Microsoft Azure Architecture Patterns)
