# EcoFlow Delta 2 Max

## Status

Der Delta2Max-Adapter läuft aktuell im **Prototype Mode**. Er akzeptiert bereits MQTT/Bus-Commands und publiziert einen minimalen State-Stand.

## Topics

| Topic | Richtung | Beschreibung |
|---|---|---|
| `ecoflow/delta2max/state` | Adapter → Bus | Aktueller Gerätezustand |
| `ecoflow/delta2max/command` | Bus/MQTT → Adapter | Eingehende Steuer-Commands |

MQTT-seitig werden die Topics standardmäßig mit Prefix `nagabridge/` gespiegelt, z. B. `nagabridge/ecoflow/delta2max/command`.

## Unterstützte Commands

Der Adapter wertet `payload.command` aus. Falls `command` fehlt, wird `payload.type` als Fallback verwendet.

| Command | Alias | Effekt |
|---|---|---|
| `get_status` | – | Publiziert den aktuellen State sofort erneut |
| `refresh` | – | Gleiches Verhalten wie `get_status` |

Nicht erkannte Commands werden ignoriert.

## Erwartete Payload-Felder

| Feld | Typ | Pflicht | Beschreibung |
|---|---|---:|---|
| `command` | `string` | nein* | Primäres Command-Feld |
| `type` | `string` | nein* | Fallback, wenn `command` fehlt |

\* Mindestens eines der Felder (`command` oder `type`) muss gesetzt sein, damit ein Command erkannt wird.

## Valid Ranges

- Für Delta2Max sind aktuell **keine numerischen Command-Parameter** implementiert.
- Valid ist nur der Wertebereich der Command-Strings: `get_status` oder `refresh`.

## Veröffentlichte State-Felder

| Feld | Typ | Bedeutung |
|---|---|---|
| `message_type` | `string` | Immer `delta2max_status` |
| `online` | `boolean` | `true` nach Start, `false` nach Stop |
| `mode` | `string` | Aktuell immer `prototype` |
| `heartbeat` | `integer` | Unix-Zeitstempel (sekündlich/periodisch je Poll-Intervall aktualisiert) |

## Intentional difference zu Delta2

- `message_type` ist absichtlich **`delta2max_status`** (Delta2 nutzt `delta2_status`). **(intentional difference)**
- Der Topic-Pfad ist absichtlich gerätespezifisch (`ecoflow/delta2max/...` statt `ecoflow/delta2/...`). **(intentional difference)**

## MQTT-Command-Beispiele

### Status abrufen (über `command`)

```json
{
  "command": "get_status"
}
```

### Status abrufen (über `type`-Fallback)

```json
{
  "type": "refresh"
}
```
