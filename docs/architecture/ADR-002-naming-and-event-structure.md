# ADR-002: Topic-Struktur und schlanke Payloads für den State Bus

## Status

Proposed

## Datum

2026-03-28

## Kontext

Mit ADR-001 wurde ein zentraler Bus als Kommunikationsmittel zwischen
allen Modulen eingeführt.

Das System ist auf lokale, latenzarme Verarbeitung ausgelegt:

* Steuerung der Einspeisung in nahezu Echtzeit
* Fokus auf aktuelle Zustände (State), nicht auf Historie
* geringe Eventrate (ca. 1 Update pro Sekunde pro Gerät)
* Betrieb auf ressourcenbeschränkter Hardware (Raspberry Pi)

Eine klassische Event-Struktur mit umfangreicher Metadaten-Hülle
(timestamp, source, type, payload) würde zusätzlichen Overhead erzeugen
und die Reaktionszeit verschlechtern.

## Entscheidung

Der Bus verwendet eine **einfache Topic-Struktur** und
**minimale Payloads ohne verpflichtende Metadaten**.

### 1. Topic-Struktur

Topics folgen dem Schema:

<domain>/<entity>/<type>

Beispiele:

* ecoflow/powerstream/state
* ecoflow/delta2max/state
* ecoflow/powerstream/command
* system/shutdown
* mqtt/connection/state

### 2. Event-Typen über Topic definiert

Der Typ wird ausschließlich über das Topic bestimmt:

* state
  aktueller Zustand eines Geräts oder Systems
  (wird überschrieben, keine Historie)

* command
  Anweisung an ein Modul
  (latest wins)

* event
  seltene Ereignisse (z. B. Fehler, Disconnect)

### 3. Payload-Design

Payloads enthalten nur die notwendigen Nutzdaten.

Beispiel (state):
{
"power": 120,
"battery": 80,
"pv_input": 300
}

Beispiel (command):
{
"set_power": 200
}

Es gibt **keine verpflichtenden Felder** wie:

* timestamp
* source
* type

Diese können bei Bedarf optional ergänzt werden.

### 4. State-Semantik

State-Daten sind:

* vollständig überschreibbar
* nicht historisch relevant
* immer als aktueller Snapshot zu verstehen

Ein neuer State ersetzt den vorherigen vollständig.

### 5. Erweiterbarkeit

Neue Module:

* können neue Topics hinzufügen
* müssen bestehende Topics nicht verändern

Subscriber entscheiden selbst:

* welche Topics sie konsumieren
* wie sie die Daten interpretieren

## Betrachtete Alternativen

### Alternative A: Vollständige Event-Hülle (timestamp, source, type, payload)

**Vorteile:**

* hohe Flexibilität
* klare Struktur

**Nachteile:**

* zusätzlicher Overhead
* höhere Latenz
* unnötig komplex für State-basierte Steuerung

**Verworfen:**
Nicht passend für Low-Latency-Anforderung

---

### Alternative B: Freie Topic- und Payload-Struktur

**Vorteile:**

* maximale Flexibilität

**Nachteile:**

* inkonsistente Datenstrukturen
* erschwert Integration neuer Module

**Verworfen:**
Nicht wartbar bei wachsendem System

## Konsequenzen

**Positiv:**

* minimale Latenz
* geringer Overhead
* einfache Implementierung
* gut geeignet für Echtzeitnahe Steuerung

**Negativ:**

* weniger Standardisierung
* optionale Metadaten müssen bei Bedarf individuell ergänzt werden

## Offene Punkte

* optionale Zeitstempel bei Bedarf definieren
* Namenskonventionen für Payload-Felder weiter vereinheitlichen
* Umgang mit komplexeren Commands bei zukünftigen Erweiterungen

## Referenzen

* Publish-Subscribe Pattern
* CAN Bus Prinzipien (State statt Historie)
