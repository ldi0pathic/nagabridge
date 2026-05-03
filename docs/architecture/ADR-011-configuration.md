# ADR-011: Konfigurationsformat – nagabridge.toml

## Status
Accepted

## Datum
2026-05-03

## Kontext

NagaBridge besteht aus mehreren Adaptern die unterschiedliche
Parameter benötigen – BLE-Geräte brauchen MAC-Adressen und Namen,
der MQTT-Adapter braucht Host und Port, das System braucht einen
Log-Level.

Ohne ein definiertes Konfigurationsformat müssten diese Parameter
hardcodiert oder über Umgebungsvariablen übergeben werden.
Beides ist für ein dauerhaft laufendes System auf dem Pi unpraktisch.

Anforderungen:
* menschlich lesbar und editierbar
* ein zentraler Ort für alle Parameter
* überlebt Updates (liegt außerhalb der Release-Verzeichnisse,
  siehe ADR-010)
* erweiterbar für neue Adapter ohne Formatbruch

## Entscheidung

NagaBridge verwendet eine zentrale **`nagabridge.toml`** als
Konfigurationsdatei im TOML-Format.

### Speicherort

```
/opt/nagabridge/nagabridge.toml
```

Die Datei liegt außerhalb der Release-Verzeichnisse und wird
bei Updates nicht überschrieben (siehe ADR-010).

### Format

```toml
[system]
log_level = "INFO"          # DEBUG | INFO | WARNING | ERROR

[updates]
trigger = "hourly"          # hourly | daily | manual
check_only_if = "any_device_online"  # any_device_online | always

[mqtt]
host = "192.168.1.10"
port = 1883
# user = ""                 # optional
# password = ""             # optional

[[adapters.ble_device]]
name = "Powerstream"
mac  = "AA:BB:CC:DD:EE:FF"
type = "powerstream"

[[adapters.ble_device]]
name = "Delta2Max"
mac  = "AA:BB:CC:DD:EE:FE"
type = "delta2max"
```

### Sektionen

**[system]**
Systemweite Parameter.

* `log_level` – minimales Log-Level das ausgegeben wird.
  Gültige Werte: `DEBUG`, `INFO`, `WARNING`, `ERROR`.
  Standard: `INFO`.

**[updates]**
Konfiguration des Update-Triggers (siehe ADR-010).

* `trigger` – `hourly`, `daily` oder `manual`
* `check_only_if` – `any_device_online` oder `always`

**[mqtt]**
Verbindungsparameter für den MQTT-Adapter.

* `host` – IP oder Hostname des MQTT-Brokers (verpflichtend)
* `port` – Port des Brokers, Standard: `1883` (verpflichtend)
* `user` – Benutzername (optional)
* `password` – Passwort (optional)

**[[adapters.ble_device]]**
Liste aller BLE-Geräte. Jeder Eintrag definiert ein Gerät.

* `name` – lesbarer Name des Geräts, wird für Logging
  und Topics verwendet (z.B. `ecoflow/powerstream/state`)
* `mac` – MAC-Adresse des BLE-Geräts
* `type` – Gerätetyp, bestimmt welcher Protokoll-Handler
  geladen wird. Gültige Werte: `powerstream`, `delta2max`, `delta2`

### Geräte-Topics aus der Config

Der `name` eines BLE-Geräts wird normalisiert und als
Entity-Segment im Topic verwendet:

```
name = "Powerstream"  →  ecoflow/powerstream/state
name = "Delta2Max"    →  ecoflow/delta2max/state
```

Normalisierung: Lowercase, Leerzeichen → Underscore.

### Erweiterbarkeit

Neue Adapter können eigene Sektionen einführen ohne
bestehende Sektionen zu verändern:

```toml
[adapters.coap]           # zukünftiger CoAP-Adapter
host = "192.168.1.20"

[adapters.logserver]      # zukünftiger Log-Server-Adapter
host = "192.168.1.30"
port = 5000
```

## Betrachtete Alternativen

### Alternative A: YAML

**Vorteile:** weit verbreitet, gut lesbar.
**Nachteile:** Einrückungsfehler sind schwer zu debuggen,
externe Abhängigkeit (`pyyaml`).
**Verworfen:** TOML ist fehlerverzeihender und in der
Python Standardbibliothek enthalten (ab Python 3.11).

### Alternative B: .env / Umgebungsvariablen

**Vorteile:** einfach, keine Datei nötig.
**Nachteile:** Listen (mehrere BLE-Geräte) lassen sich
nicht sauber abbilden.
**Verworfen:** Nicht geeignet für mehrere Geräte.

### Alternative C: JSON

**Vorteile:** überall bekannt.
**Nachteile:** keine Kommentare möglich, weniger lesbar
für manuelle Bearbeitung.
**Verworfen:** Kommentare in der Config sind wichtig
für den Betreiber.

## Konsequenzen

**Positiv:**
* ein zentraler Ort für alle Parameter
* menschlich lesbar und editierbar
* keine externe Abhängigkeit (TOML in Python Stdlib)
* Kommentare möglich – wichtig für optionale Felder
* überlebt Updates

**Negativ:**
* TOML ist weniger bekannt als YAML oder JSON
* Validierung der Config muss im Code implementiert werden

## Offene Punkte

* Validierung der Config beim Start definieren
  (fehlende Pflichtfelder, ungültige Werte)
* Verhalten bei fehlerhafter Config festlegen
  (Abbruch oder Warnung + Defaults?)
* Beispiel-Config als `nagabridge.toml.example`
  ins Repo aufnehmen

## Referenzen

* ADR-010: Deployment – Verzeichnisse, Symlinks und
  konfigurierbarer Update-Trigger
* ADR-002: Topic-Struktur
* TOML Spezifikation: https://toml.io
* Python tomllib (Stdlib ab 3.11):
  https://docs.python.org/3/library/tomllib.html
