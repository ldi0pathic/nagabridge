# ADR-013: delta2 und delta2max als separate Adapter

## Status
Accepted

## Datum
2026-05-26

## Kontext

Für die EcoFlow-Modelle **delta2** und **delta2max** werden Adapter im
Projekt bereitgestellt. Beide Geräte sind verwandt, aber unterscheiden
sich in Details, die für Verhalten, Telemetrie und Optimierung relevant
sein können.

Betroffene Adapter:

* `src/nagabridge/adapters/delta2/adapter.py`
* `src/nagabridge/adapters/delta2max/adapter.py`

## Entscheidung

**delta2** und **delta2max** werden als **zwei unabhängige Adapter**
implementiert und weiterentwickelt – auch wenn dadurch bewusst
Doppelcode entsteht.

Explizit ausgeschlossen:

* keine gemeinsame Basisklasse
* kein gemeinsames `delta2_common`-Modul
* keine geteilten Parser

## Begründung

Die **Modelloptimierung pro Gerät hat Vorrang vor DRY**.

Gerätespezifische Anpassungen sollen ohne Kopplung am jeweils anderen
Adapter möglich bleiben. Das reduziert Risiko bei Änderungen,
vereinfacht gezielte Fehlersuche pro Modell und verhindert
Kompromiss-Designs durch zu frühe Abstraktion.

## Betrachtete Alternativen

### Alternative A: Gemeinsame Basisklasse

**Vorteil:** weniger doppelter Code.

**Nachteil:** stärkere Kopplung, höheres Risiko für Seiteneffekte bei
modell-spezifischen Änderungen.

**Verworfen:** Optimierung und Änderbarkeit pro Gerät sind wichtiger.

### Alternative B: `delta2_common`-Modul für Shared Logic

**Vorteil:** zentrale Wiederverwendung.

**Nachteil:** implizite Abhängigkeiten zwischen zwei Geräten mit
potenziell unterschiedlicher Evolution.

**Verworfen:** verhindert klare Trennung der Modellverantwortung.

### Alternative C: Geteilte Parser mit Feature-Flags

**Vorteil:** ein Parser für mehrere Modelle.

**Nachteil:** steigende Komplexität, mehr Verzweigungen,
erschwerte Wartung und Debugbarkeit.

**Verworfen:** klare, eigenständige Parser pro Gerät sind robuster.

## Konsequenzen

**Positiv:**

* volle Unabhängigkeit der Adapter-Implementierungen
* schnelle modell-spezifische Optimierungen ohne Rücksicht auf Shared
  Komponenten
* klarere Fehleranalyse pro Gerät

**Negativ:**

* bewusster Doppelcode
* möglicher Mehraufwand bei parallelen Änderungen

## Referenzen

* `src/nagabridge/adapters/delta2/adapter.py`
* `src/nagabridge/adapters/delta2max/adapter.py`
