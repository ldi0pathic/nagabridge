# ADR-010: Deployment – Verzeichnisse, Symlinks und konfigurierbarer Update-Trigger

## Status
Accepted

## Datum
2026-05-03

## Kontext

ADR-008 definierte ein Blue-Green Deployment für NagaBridge als
Gesamtsystem. ADR-009 führte danach eine Plugin-Architektur mit
unabhängig versionierten Adaptern ein und notierte explizit dass
ADR-008 angepasst werden muss.

Nach Abwägung (siehe ADR-009 Kontext) wurde entschieden:

* NagaBridge ist ein persönliches Projekt, kein Community-Framework
* Over-Engineering für hypothetische Community-Nutzung wird vermieden
* alle Adapter leben im selben Repo und werden gemeinsam released

ADR-010 ersetzt ADR-008 vollständig.

## Entscheidung

### 1. Ein Release für alles

Es gibt einen einzigen Release-Tag pro Version für das gesamte
NagaBridge-Repository. Alle Adapter und der Core werden gemeinsam
versioniert und deployed.

```
nagabridge-v1.0.0   ← ein Tag, alles drin
nagabridge-v1.0.1
nagabridge-v1.0.2
```

### 2. Verzeichnisstruktur auf dem Pi

```
/opt/nagabridge/
├── releases/
│   ├── v1.0.0/     ← Fallback-Version
│   └── v1.0.1/     ← aktive Version
├── current         ← Symlink auf aktive Version
├── rollback        ← Symlink auf Fallback-Version
└── nagabridge.toml ← Konfiguration (bleibt bei Updates erhalten)
```

NagaBridge läuft immer aus `current/` – unabhängig welche
Version dahintersteckt.

### 3. Konfigurierbarer Update-Trigger

Der Update-Trigger wird in `nagabridge.toml` konfiguriert:

```toml
[updates]
trigger = "hourly"               # hourly | daily | manual
check_only_if = "any_device_online"  # any_device_online | always
```

**trigger:**

* `hourly` – Pi prüft stündlich auf neuen GitHub Release-Tag
* `daily`  – Pi prüft täglich auf neuen GitHub Release-Tag
* `manual` – kein automatisches Update; Update wird ausgelöst durch
  Bus-Command `system/nagabridge/update`

**check_only_if:**

* `any_device_online` – Update nur wenn mindestens ein Gerät
  erreichbar ist (aussagekräftiger Health Check möglich)
* `always` – Update unabhängig vom Gerätezustand
  (Health Check prüft nur MQTT und Bus)

### 4. Update-Ablauf

```
Neuer GitHub Release-Tag erkannt (oder manueller Trigger)
         │
         ▼
pre_update_state speichern
(welche Geräte sind gerade online?)
         │
         ▼
Download → /opt/nagabridge/releases/<version>/
         │
         ▼
rollback → current  (alte Version sichern)
current  → <version> (neue Version aktivieren)
         │
         ▼
NagaBridge neu starten
         │
         ▼
Warte 60 Sekunden (siehe ADR-008 Amendment 2026-05-03)
         │
         ▼
Kontextabhängiger Health Check
    │                         │
    ✅ ok                     ❌ failed
    │                         │
Update erfolgreich        Rollback:
    │                     current → rollback
    ▼                         │
Alte Versionen prüfen:    NagaBridge neu starten
mehr als 2 vorhanden?         │
    │                     Bus publish:
    ▼                     system/nagabridge/update = "rollback"
älteste löschen
    │
Bus publish:
system/nagabridge/update = "ok"
```

### 5. Kontextabhängiger Health Check

Vor jedem Update wird der aktuelle Gerätezustand gespeichert:

```
pre_update_state = {
    "powerstream": "online" | "offline",
    "delta2max":   "online" | "offline",
    ...
}
```

Nach dem Update gilt:

```
Gerät war VOR Update online?
    │ ja → muss nach Update wieder online sein
    │      sonst: Rollback
    │
    └── nein → war bereits ausgeschaltet
               BLE-Fehler ist kein Rollback-Grund
               MQTT und Bus müssen trotzdem ok sein
```

Minimale Health Check Bedingungen – immer erfüllt sein:

* **MQTT Adapter:** verbunden mit Broker
* **Event Bus:** läuft und verarbeitet Events
* **Alle Adapter die vor dem Update online waren:**
  müssen nach dem Update wieder online sein

### 6. CI als Qualitätsgate

Ein Release-Tag wird nur erstellt wenn alle CI-Checks grün sind:

```
Code push
   │
   ▼
CI grün? (ruff, black, pytest, bandit)
   │ nein → kein Release möglich
   │ ja
   ▼
Release-Tag erstellen (manuell durch Entwickler)
   │
   ▼
Pi erkennt neuen Tag gemäß konfiguriertem Trigger
   │
   ▼
pre_update_state speichern → Update → Health Check → fertig
```

### 7. Versionsverwaltung auf Disk

* maximal 2 Versionen auf dem Pi
* älteste Version wird automatisch gelöscht sobald eine
  neuere stabil läuft
* `nagabridge.toml` liegt außerhalb der Releases und
  wird bei Updates nicht überschrieben

## Betrachtete Alternativen

### Alternative A: pip-basiertes Update

**Vorteile:**
* sauber für Community-Nutzung
* pip verwaltet Abhängigkeiten

**Nachteile:**
* Rollback umständlich
* zwei Versionen gleichzeitig nicht nativ möglich
* Over-Engineering für ein persönliches Projekt

**Verworfen:** Symlinks sind einfacher und robuster für diesen Scope.

### Alternative B: Unabhängige Releases pro Adapter

**Vorteile:**
* maximale Granularität
* nur geänderter Adapter muss neu starten

**Nachteile:**
* Verwaltungsaufwand für mehrere Release-Tags
* Kompatibilitätsmatrix zwischen Adaptern nötig
* unrealistisch für Solo-Entwickler

**Verworfen:** Ein gemeinsamer Release ist pragmatischer.

## Konsequenzen

**Positiv:**
* einfaches Rollback – Symlink umbiegen, fertig
* zwei Versionen immer auf Disk
* konfigurierbarer Trigger passt sich dem Nutzungsverhalten an
* `nagabridge.toml` überlebt Updates
* kein pip auf Produktion

**Negativ:**
* gemeinsamer Release bedeutet: MQTT-Adapter neu starten
  obwohl nur BLE geändert wurde
* Update verzögert sich wenn `check_only_if = any_device_online`
  und Geräte längere Zeit offline sind

## Offene Punkte

* maximale Wartezeit definieren wenn Geräte dauerhaft offline sind
* Benachrichtigung bei Rollback implementieren (z.B. MQTT publish)
* Mindest-Testabdeckung für CI festlegen
* GitHub API Token für Release-Abfrage konfigurieren
* Format für `nagabridge.toml` vollständig definieren

## Referenzen

* ADR-007: Health Check Pattern
* ADR-008: Blue-Green Deployment (Superseded)
* ADR-009: Plugin-Architektur (Amendment ausstehend)
* Blue-Green Deployment Pattern (Martin Fowler)
* GitHub Releases API
