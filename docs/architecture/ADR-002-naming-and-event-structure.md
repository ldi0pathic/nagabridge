# ADR-002: Topic Naming und Event-Struktur für den Event Bus

## Status

Proposed

## Datum

2026-03-28

## Kontext

Mit der Einführung des zentralen Event Bus (ADR-001) wird dieser zur
zentralen Kommunikationsschnittstelle aller Module in NagaBridge.

Aktuell existieren erste Topic-Namen wie:

* ecoflow/powerstream/state
* ecoflow/powerstream/set
* mqtt/state
* system/shutdown

Diese sind funktional, aber es fehlen klare Regeln für:

* einheitliche Benennung
* Trennung von Zuständen, Events und Commands
* Struktur der Payloads

Ohne Konventionen besteht die Gefahr von:

* uneinheitlichen Topic-Strukturen
* schwer nachvollziehbaren Datenflüssen
* steigender Komplexität bei neuen Modulen

## Entscheidung (Vorschlag)

Es wird eine einheitliche Topic-Namenskonvention sowie eine
standardisierte Event-Struktur für alle Bus-Nachrichten definiert.

### 1. Topic-Struktur

Topics folgen dem Schema:

<domain>/<entity>/<type>

Beispiele:

* ecoflow/powerstream/state
* ecoflow/delta2max/state
* mqtt/connection/state
* system/lifecycle/shutdown

### 2. Event-Typen

Jedes Topic enthält einen klar definierten Typ:

* state
  Repräsentiert den aktuellen Zustand eines Systems (idempotent)

* event
  Ein einmaliges Ereignis (z. B. Fehler, Verbindung verloren)

* command
  Eine Anweisung an ein Modul

Beispiele:

* ecoflow/powerstream/state
* ecoflow/powerstream/event
* ecoflow/powerstream/command

### 3. Event-Payload-Struktur

Alle Nachrichten auf dem Event Bus verwenden eine einheitliche
Grundstruktur:

{
"timestamp": "<ISO8601>",
"source": "<modul.name>",
"type": "<state|event|command>",
"payload": { ... }
}

Optionale Erweiterung:
{
"version": 1
}

### 4. Namenskonventionen

* domain: System oder Integrationsbereich (ecoflow, mqtt, system)
* entity: konkretes Gerät oder Subsystem (powerstream, delta2max)
* type: state, event oder command

### 5. Erweiterbarkeit

Neue Module müssen:

* keine bestehenden Topics verändern
* sich an die definierte Struktur halten

## Betrachtete Alternativen

### Alternative A: Freie Topic-Namen ohne Konvention

**Vorteile:**

* maximale Flexibilität
* schneller Start

**Nachteile:**

* inkonsistente Struktur
* schwer wartbar
* hohe Fehleranfälligkeit

**Verworfen:**
Nicht skalierbar für wachsendes System

---

### Alternative B: Stark verschachtelte Topics

Beispiel:
ecoflow/device/powerstream/metrics/state

**Vorteile:**

* sehr granular
* hohe Ausdrucksstärke

**Nachteile:**

* unnötig komplex
* erschwert Debugging
* Overhead ohne klaren Mehrwert

**Verworfen:**
Zu komplex für aktuellen Scope

---

### Alternative C: Keine Payload-Standardisierung

**Vorteile:**

* maximale Freiheit für Module

**Nachteile:**

* inkonsistente Datenstrukturen
* erschwert Integration neuer Module
* hoher Debugging-Aufwand

**Verworfen:**
Führt langfristig zu Systeminstabilität

## Konsequenzen

**Positiv:**

* Einheitliche und verständliche Kommunikation
* Einfachere Integration neuer Module
* Bessere Debugbarkeit des Event Bus
* Klare Trennung von Zuständen, Events und Commands

**Negativ:**

* Initialer Mehraufwand bei Definition und Einhaltung
* Geringere Flexibilität für spontane Änderungen

## Offene Punkte

* Wildcard-Subscriptions (z. B. ecoflow/*) definieren
* Versionierung final festlegen (Topic vs Payload)
* Umgang mit großen Payloads klären
* Logging- und Debug-Strategie konkretisieren

## Referenzen

* Publish-Subscribe Pattern (GoF)
* Event-Driven Architecture
* MQTT Topic Best Practices
