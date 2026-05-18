# EcoFlow PowerStream

## Status

Der PowerStream-Adapter ist in der Architektur verdrahtet und nutzt:

- BLE über `BleConnection`
- EcoFlow Type1Crypto mit Seriennummer-basierter AES-CBC-Verschlüsselung
- lokalen Protobuf-Wire-Parser für Inverter-Heartbeat, PowerPack und HeaderMessage
- EventBus-Topics nach ADR-002

## Konfiguration

Beispiel:

```toml
[[adapters.ble_device]]
name = "Powerstream"
mac = "AA:BB:CC:DD:EE:FF"
type = "powerstream"
serial_number = "POWERSTREAM_SERIAL"
user_id = "ECOFLOW_USER_ID"
poll_interval_seconds = 10
reconnect_attempts = 3
reconnect_backoff_seconds = 1
write_with_response = false
```

### Felder

| Feld | Pflicht | Beschreibung |
|---|---:|---|
| `name` | ja | Anzeigename und Adaptername |
| `mac` | ja | BLE-MAC-Adresse des PowerStream |
| `type` | ja | Muss `powerstream` sein |
| `serial_number` | empfohlen | Seriennummer für Type1Crypto; ohne Seriennummer startet der Adapter nur im Legacy-/No-BLE-Modus |
| `user_id` | empfohlen | EcoFlow User-ID für den MD5-Auth-Handshake (`MD5(user_id + serial_number)`) |
| `poll_interval_seconds` | nein | Polling-Intervall; Default: 10 Sekunden |
| `reconnect_attempts` | nein | Verbindungsversuche pro Connect-Zyklus; Default: 3 |
| `reconnect_backoff_seconds` | nein | Initialer Backoff; Default: 1 Sekunde |
| `write_with_response` | nein | Ob BLE-Writes mit Response erfolgen; Default: `false` |

## Topics

Nach ADR-002 verwendet der Adapter schlanke Payloads und den Typ über den Topic-Namen.

| Topic | Richtung | Beschreibung |
|---|---|---|
| `ecoflow/powerstream/state` | Adapter → Bus | Aktueller Gerätezustand als flaches Dictionary |
| `ecoflow/powerstream/bat_state` | Adapter → Bus | Battery-State aus PowerPack/Type2-Payloads |
| `ecoflow/powerstream/command` | Bus → Adapter | Steuerbefehle |

Der MQTT-Adapter exportiert Bus-Topics mit dem Prefix `nagabridge`.
Damit entstehen auf dem Broker `nagabridge/ecoflow/powerstream/state`
und `nagabridge/ecoflow/powerstream/bat_state`. In ioBroker erscheinen
diese Pfade entsprechend als `mqtt.0.nagabridge.ecoflow.powerstream.state`
und `mqtt.0.nagabridge.ecoflow.powerstream.bat_state`.

Beispiel-State:

```json
{
  "message_type": "inverter_heartbeat",
  "pv1_input_watts": 320,
  "pv2_input_watts": 280,
  "pv_input_watts": 600,
  "bat_soc": 78,
  "inv_output_watts": 550
}
```

## Commands

### Status anfordern

```json
{
  "command": "get_status"
}
```

Alias: `refresh`

### Einspeiseleistung setzen

```json
{
  "command": "set_load_power",
  "watts": 600
}
```

Alias: `set_permanent_watts`

Der Adapter akzeptiert aktuell Werte von `0` bis `8000` Watt und encodiert den Wert little-endian im PowerStream-Command.

## Authentifizierung

PowerStream verwendet Type1Crypto. Die AES-Schlüssel werden aus der Seriennummer abgeleitet. Für den Auth-Handshake baut der Adapter zusätzlich einen 32 Byte langen Uppercase-ASCII-MD5-Wert aus:

```text
MD5(user_id + serial_number)
```

Wenn `user_id` fehlt, wird der Auth-Packet-Write übersprungen und im Log vermerkt. Für reale Geräte sollten `serial_number` und `user_id` gesetzt sein.

## Bekannte Einschränkungen

- Echte BLE-Captures sind noch als Fixtures nachzutragen.
- Manuelle Tests mit realem PowerStream-Gerät stehen noch aus.
- Parser-Felder basieren auf bekannten/community Protobuf-Feldern; unbekannte Payloads werden mit Hex-Dump geloggt.
