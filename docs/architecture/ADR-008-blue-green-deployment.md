# ADR-008: Blue-Green Deployment mit automatischem Rollback

## Status
Accepted

## Datum
2026-03-29

## Kontext

NagaBridge steuert die Einspeisung der Powerstream in Echtzeit.
Ein fehlerhaftes Update das NagaBridge zum Absturz bringt würde
die Steuerung unterbrechen – die Powerstream fällt auf ihre
eigene interne Logik zurück (sicher, aber suboptimal).

Anforderungen an das Update-System:

* Updates sollen automatisch eingespielt werden
* fehlerhafte Updates sollen automatisch zurückgerollt werden
* mindestens zwei Versionen sollen auf dem Pi vorgehalten werden
* alte Versionen werden automatisch gelöscht wenn neuere
  stabil laufen

### Besonderheit: Geräte können ausgeschaltet sein

Die Powerstream schaltet sich bei leerem Akku und fehlender
Sonneneinstrahlung automatisch aus. Ein Health Check der
ausschließlich auf BLE-Verbindungen basiert würde in diesem
Zustand immer fehlschlagen – obwohl NagaBridge korrekt läuft.

Das Update-System muss zwischen zwei Zuständen unterscheiden:
```
"Gerät nicht erreichbar weil NagaBridge defekt"
            vs.
"Gerät nicht erreichbar weil es ausgeschaltet ist"
```

## Entscheidung

NagaBridge verwendet **Blue-Green Deployment** mit
kontextabhängigem Health Check und automatischem Rollback.

### Verzeichnisstruktur auf dem Pi
```
/opt/nagabridge/
├── releases/
│   ├── v1.0.0/     ← Fallback-Version
│   └── v1.0.1/     ← aktive Version
├── current         ← Symlink auf aktive Version
└── rollback        ← Symlink auf Fallback-Version
```

NagaBridge läuft immer aus `current/` – unabhängig welche
Version dahintersteckt.

### Kontextabhängiger Health Check

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

### Minimale Health Check Bedingungen nach Update

Unabhängig vom Gerätezustand müssen immer erfüllt sein:

* **MQTT Adapter:** verbunden mit Broker
* **Event Bus:** läuft und verarbeitet Events
* **Alle Adapter die vor dem Update online waren:**
  müssen nach dem Update wieder online sein

### Update-Ablauf
```
GitHub Release Tag (z.B. v1.0.2) erkannt
         │
         ▼
pre_update_state speichern
(welche Geräte sind gerade online?)
         │
         ▼
Download → /opt/nagabridge/releases/v1.0.2/
         │
         ▼
rollback → current  (alte Version sichern)
current  → v1.0.2   (neue Version aktivieren)
         │
         ▼
NagaBridge neu starten
         │
         ▼
Warte 60 Sekunden
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
    ▼                     system/update/status = "rollback"
älteste löschen
    │
Bus publish:
system/update/status = "ok"
```

### Update-Trigger

Der Pi prüft **stündlich** ob ein neuer GitHub Release Tag
verfügbar ist – jedoch nur wenn die Powerstream online ist:
```
Stündlicher Check:
    │
    ├── Powerstream online? nein → warte auf nächsten Check
    │
    └── ja → neuer Release verfügbar?
                 │ nein → nichts tun
                 └── ja → Update starten
```

Begründung: Ist die Powerstream online, läuft das System
aktiv. Ein Update in diesem Zustand ist sinnvoll weil der
anschließende Health Check aussagekräftig ist.

Ist die Powerstream offline (Akku leer, keine Sonne), ist
ein Update zwar technisch möglich – der Health Check wäre
jedoch weniger aussagekräftig da BLE-Verbindungen nicht
geprüft werden können.

### CI als Qualitätsgate

Ein Release Tag wird nur erstellt wenn:

* alle CI-Checks grün sind (ruff, black, pytest, bandit)
* Tests eine ausreichende Abdeckung haben
```
Code push
   │
   ▼
CI grün?
   │ nein → kein Release möglich
   │ ja
   ▼
Release Tag erstellen (manuell durch Entwickler)
   │
   ▼
Pi erkennt neuen Tag wenn Powerstream online
   │
   ▼
pre_update_state speichern → Update → Health Check → fertig
```

## Betrachtete Alternativen

### Alternative A: Festes nächtliches Update-Fenster

**Nachteile:**
* Powerstream nachts oft ausgeschaltet
* Health Check wäre nicht aussagekräftig
* BLE-Verbindung nicht prüfbar

**Verworfen:**
Geräte sind nachts oft offline – Health Check wäre wertlos.

### Alternative B: Vollautomatisch ohne Kontext

Pi zieht jeden Merge auf main automatisch ohne
Gerätezustand zu prüfen.

**Nachteile:**
* False Negatives wenn Geräte ausgeschaltet sind
* führt zu unnötigen Rollbacks

**Verworfen:** Zu unzuverlässig.

### Alternative C: Manuelles Update

**Nachteile:**
* kein automatisches Rollback
* Wartungsaufwand

**Verworfen:** Widerspricht dem Ziel der Wartungsarmut.

### Alternative D: Ansible / Chef / Puppet

**Nachteile:**
* Over-Engineering für einen Raspberry Pi

**Verworfen:** Over-Engineering.

## Konsequenzen

**Positiv:**
* fehlerhafte Updates werden automatisch zurückgerollt
* kontextabhängiger Health Check vermeidet False Negatives
* zwei Versionen immer verfügbar
* Speicherplatz wird automatisch verwaltet
* Update nur wenn System aktiv – aussagekräftiger Health Check

**Negativ:**
* Update-Script ist komplexer durch Kontextlogik
* Update kann sich verzögern wenn Powerstream längere Zeit
  offline ist

## Offene Punkte

* Maximale Wartezeit definieren wenn Powerstream dauerhaft
  offline ist
* Benachrichtigung bei Rollback implementieren
* Mindest-Testabdeckung für CI definieren
* GitHub API Token für Release-Abfrage konfigurieren

## Referenzen

* ADR-007: Health Check Pattern
* ADR-003: State-First Bus
* Blue-Green Deployment Pattern (Martin Fowler)
* GitHub Releases API
