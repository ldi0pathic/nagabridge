# ADR-009: Plugin-Architektur mit unabhängig versionierten Adaptern

## Status
Accepted

## Datum
2026-03-29

## Kontext

NagaBridge besteht aus einem Core und mehreren Adaptern die
verschiedene Protokolle und Geräte anbinden. Mit wachsender
Anzahl von Adaptern (BLE Ecoflow, MQTT, Shelly, CoAP) entsteht
die Frage wie diese organisiert und deployed werden.

Anforderungen:

* neue Adapter sollen ohne Änderung bestehender Komponenten
  hinzugefügt werden können (bereits in ADR-001 definiert)
* Adapter sollen unabhängig voneinander installierbar sein
* ein Adapter-Update soll nicht das gesamte System neu starten
* die Community soll eigene Adapter entwickeln können

## Entscheidung

NagaBridge verwendet eine **Plugin-Architektur** im Monorepo.

Jeder Adapter ist ein eigenständiges Python-Package mit eigener
Versionsnummer – aber alle leben im selben GitHub Repository.

### Paketstruktur
```
nagabridge/                          ← GitHub Repo
├── core/
│   ├── pyproject.toml               ← nagabridge-core
│   └── src/nagabridge/core/
├── adapters/
│   ├── ble-ecoflow/
│   │   ├── pyproject.toml           ← nagabridge-ble-ecoflow
│   │   └── src/nagabridge/ble_ecoflow/
│   ├── mqtt/
│   │   ├── pyproject.toml           ← nagabridge-mqtt
│   │   └── src/nagabridge/mqtt/
│   └── ble-shelly/                  ← zukünftig, optional
│       ├── pyproject.toml           ← nagabridge-ble-shelly
│       └── src/nagabridge/ble_shelly/
└── .github/workflows/
```

### Versionierung

Jedes Package folgt **Semantic Versioning**:
```
MAJOR.MINOR.PATCH

PATCH  Bug fix, kein Interface-Bruch
MINOR  neue Features, rückwärtskompatibel
MAJOR  Interface-Bruch → alle abhängigen
       Adapter müssen geprüft werden
```

### Adapter Interface als formaler Vertrag

Der Core definiert ein Interface das alle Adapter
implementieren müssen:
```python
# nagabridge/core/adapter_interface.py

class AdapterInterface(ABC):
    """
    Formaler Vertrag zwischen Core und allen Adaptern.
    Major-Version-Änderung hier bedeutet: alle Adapter
    müssen aktualisiert werden.
    """

    @abstractmethod
    async def start(self, bus: EventBus) -> None: pass

    @abstractmethod
    async def stop(self) -> None: pass

    @property
    @abstractmethod
    def health(self) -> HealthStatus: pass

    @property
    @abstractmethod
    def name(self) -> str: pass

    @property
    @abstractmethod
    def version(self) -> str: pass
```

Solange ein Adapter dieses Interface implementiert ist er
kompatibel mit jedem Core der dieselbe Major-Version hat.

### Installation
```bash
# Minimales Setup:
pip install nagabridge-core
pip install nagabridge-ble-ecoflow
pip install nagabridge-mqtt

# Optional später:
pip install nagabridge-ble-shelly
pip install nagabridge-coap-shelly
```

### Adapter Discovery

Der Core lädt Adapter automatisch über Python Entry Points:
```toml
# In jedem Adapter pyproject.toml:
[project.entry-points."nagabridge.adapters"]
ble_ecoflow = "nagabridge.ble_ecoflow:BleEcoflowAdapter"
```

Der Core findet alle installierten Adapter automatisch:
```python
import importlib.metadata

adapters = [
    ep.load()
    for ep in importlib.metadata.entry_points(
        group="nagabridge.adapters"
    )
]
```

Kein hardcodierter Import – der Core weiß nicht welche
Adapter installiert sind. Er findet sie zur Laufzeit.

### CI pro Adapter

Jeder Adapter hat seinen eigenen CI-Job:
```yaml
# .github/workflows/ci.yml
jobs:
  core:
    ...
  ble-ecoflow:
    needs: core      ← Core muss zuerst grün sein
    ...
  mqtt:
    needs: core
    ...
```

### Releases pro Adapter

Jeder Adapter hat seinen eigenen Release Tag:
```
nagabridge-core-v1.0.0
nagabridge-ble-ecoflow-v1.2.0
nagabridge-mqtt-v1.0.3
```

## Betrachtete Alternativen

### Alternative A: Monorepo mit einem gemeinsamen Release

Alle Adapter haben dieselbe Versionsnummer.

**Vorteile:**
* einfacher
* Interface-Kompatibilität immer garantiert

**Nachteile:**
* MQTT-Adapter updaten obwohl nur BLE geändert wurde
* Community kann keine eigenen Adapter entwickeln
* unnötiger Neustart aller Komponenten

**Verworfen:**
Nicht erweiterbar für Community-Adapter.

### Alternative B: Separate Repositories pro Adapter

**Vorteile:**
* maximale Unabhängigkeit

**Nachteile:**
* hoher Verwaltungsaufwand
* schwieriger zu entwickeln wenn Änderungen
  mehrere Adapter betreffen
* für Solo-Entwickler unpraktisch

**Verworfen:**
Over-Engineering für aktuellen Entwicklungsstand.

## Konsequenzen

**Positiv:**
* neue Adapter ohne Änderung des Core installierbar
* Community kann eigene Adapter entwickeln
* nur geänderte Adapter müssen neu gestartet werden
* klare Trennung von Verantwortlichkeiten
* jeder Adapter unabhängig testbar und deploybar

**Negativ:**
* pyproject.toml pro Adapter erhöht initialen Aufwand
* Interface-Kompatibilität muss bei Major-Updates
  bewusst gemanagt werden
* Entry Points sind ein neues Python-Konzept
  das gelernt werden muss

## Auswirkungen auf andere ADRs

* **ADR-008** muss angepasst werden: Updates betreffen
  einzelne Adapter, nicht das gesamte System.
  Der Health Check muss pro Adapter durchgeführt werden.

## Offene Punkte

* PyPI Veröffentlichung der Pakete evaluieren
  (damit Community pip install nutzen kann)
* Kompatibilitätsmatrix dokumentieren
  (welche Adapter-Version benötigt welchen Core)
* Konfigurationsformat für aktivierte Adapter definieren

## Referenzen

* ADR-001: Event Bus
* ADR-007: Health Check Pattern
* ADR-008: Blue-Green Deployment
* Python Entry Points:
  https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/
* Semantic Versioning: https://semver.org

---

## Amendment 2026-05-03: Pragmatisches Monorepo statt Community-Plattform

### Problem

ADR-009 wurde mit dem Ziel entworfen dass die Community eigene
Adapter entwickeln und per PyPI installieren kann. Das führte zu
unnötiger Komplexität:

* Python Entry Points für Adapter Discovery
* unabhängige Versionierung pro Adapter
* PyPI Veröffentlichung als Ziel
* Kompatibilitätsmatrix zwischen Adaptern

NagaBridge ist ein persönliches Projekt. Diese Komplexität ist
nicht gerechtfertigt.

### Entscheidung

**Entry Points, PyPI und unabhängige Adapter-Versionierung
werden nicht umgesetzt.**

Stattdessen gilt:

* alle Adapter leben im Monorepo und werden gemeinsam versioniert
* ein Release-Tag gilt für das gesamte System (Core + alle Adapter)
* Adapter werden nicht als separate Python-Packages deployed
* der Core lädt Adapter direkt per Import – kein Discovery-Mechanismus

Das Plugin-Konzept bleibt erhalten als **Strukturprinzip**:

* Adapter implementieren weiterhin `AdapterInterface`
* neue Adapter können ohne Änderung bestehender Komponenten
  hinzugefügt werden
* jeder Adapter bleibt unabhängig testbar

Wer das Projekt nutzen möchte, kann es clonen oder forken.

### Konsequenz

* ADR-009 Abschnitte zu Entry Points, PyPI und Community-Releases
  gelten als überholt
* Deployment folgt ADR-010
* `AdapterInterface` als formaler Vertrag bleibt gültig
