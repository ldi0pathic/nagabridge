# ADR-003: State-First Bus ohne Backpressure für Low-Latency Steuerung

## Status

Accepted 

## Datum

2026-03-28

## Kontext

Das System verarbeitet hauptsächlich Zustandsdaten von Geräten
(Ecoflow Powerstream, Delta2, Delta2Max) zur Steuerung der Einspeisung.

Wichtige Anforderungen:

* immer der aktuellste Zustand ist relevant
* alte Zustände sind wertlos
* sehr schnelle Weitergabe von Daten zwischen Modulen
* geringe Eventrate (~1 Event pro Sekunde pro Gerät)
* mehrere zukünftige Consumer (MQTT, Web UI, Logger, weitere Adapter)

Ein klassisches Event-System mit Queues, Backpressure und
Persistenz würde unnötige Komplexität und Latenz einführen.

## Entscheidung

Der Bus folgt einem **State-First Ansatz ohne zentrale Queue und ohne
Backpressure-Mechanismen für State-Daten**.

### 1. Fire-and-Forget Verteilung

Events werden direkt an alle Subscriber verteilt:

Publisher → Bus → Subscriber

* keine zentrale Queue
* keine Blockierung durch langsame Module

### 2. State überschreibt sich

Für State-Topics gilt:

* nur der aktuellste Wert ist relevant
* neue Werte ersetzen alte vollständig
* keine Speicherung von Zwischenzuständen

Optional kann ein State Store geführt werden:
state_store[topic] = latest_value

### 3. Keine Backpressure für State

Der Bus:

* puffert keine State-Daten
* blockiert nicht bei langsamen Subscribern

Wenn ein Subscriber nicht mithalten kann:

* verliert er Zwischenwerte
* verarbeitet nur spätere Updates

Dieses Verhalten ist akzeptabel, da nur der aktuelle Zustand relevant ist.

### 4. Commands: Latest Wins

Commands werden nicht garantiert zugestellt.

Regel:

* ein neuer Command überschreibt ältere Commands
* nur der aktuellste Command ist relevant

Beispiel:

* set_power = 100
* set_power = 200 → nur dieser zählt

### 5. Events (optional)

Für seltene Ereignisse (z. B. Fehler):

* können separate Mechanismen verwendet werden
* dürfen optional gepuffert werden
* sind nicht Teil des kritischen Low-Latency-Pfads

### 6. Verantwortung der Subscriber

Subscriber sind verantwortlich für:

* eigene Entkopplung (z. B. interne Queues)
* Umgang mit langsamer Verarbeitung
* selektives Abonnieren relevanter Topics

Der Bus bleibt bewusst einfach.

### 7. Performance-Fokus

Der Bus ist optimiert für:

* minimale Latenz
* direkte Weitergabe von Daten
* geringe CPU- und Speicherlast

## Betrachtete Alternativen

### Alternative A: Queue-basierter Event Bus mit Backpressure

**Vorteile:**

* kontrollierter Datenfluss
* keine Eventverluste

**Nachteile:**

* höhere Latenz
* komplexe Implementierung
* unnötig für State-basierte Steuerung

**Verworfen:**
Widerspricht Low-Latency-Anforderung

---

### Alternative B: Persistente Event Streams

**Vorteile:**

* vollständige Historie
* Replay möglich

**Nachteile:**

* hoher Speicherbedarf
* komplexe Verarbeitung
* nicht notwendig für aktuellen Anwendungsfall

**Verworfen:**
Historie ist nicht erforderlich

---

### Alternative C: Blockierender Bus

**Vorteile:**

* deterministisches Verhalten

**Nachteile:**

* langsame Module blockieren das gesamte System
* schlechte Skalierbarkeit

**Verworfen:**
Gefährdet Systemstabilität

## Konsequenzen

**Positiv:**

* extrem geringe Latenz
* einfache Architektur
* gut geeignet für Echtzeitnahe Steuerung
* robust gegenüber kurzzeitigen Verzögerungen einzelner Module

**Negativ:**

* keine Garantie für Zustellung
* mögliche Verluste von Zwischenwerten
* Debugging erfordert Beobachtung des aktuellen Zustands

**Zur Command-Zustellung:** 
Verlorene Commands sind akzeptabel,da alle unterstützten Geräte 
(Ecoflow Powerstream, Delta2-Serie)
eine eigene Sicherheitslogik besitzen die einen stabilen
Grundzustand garantiert. NagaBridge optimiert – ersetzt aber
nicht die Gerätelogik.

## Offene Punkte

* optionaler State Store final definieren
* Debugging- und Logging-Strategie festlegen
* Umgang mit kritischen Commands bei zukünftigen Anforderungen prüfen

## Referenzen

* CAN Bus (State-basierte Kommunikation)
* Event-Driven Architecture (vereinfachte Form)
