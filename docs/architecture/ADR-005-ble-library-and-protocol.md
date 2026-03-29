# ADR-005: BLE Bibliothek (bleak) und Protobuf als Protokoll-Constraint

## Status
Accepted

## Datum
2026-03-29

## Kontext

NagaBridge kommuniziert über Bluetooth Low Energy (BLE) mit
Ecoflow-Geräten. Dafür werden zwei Dinge benötigt:

1. Eine Python-Bibliothek für BLE-Kommunikation
2. Ein Protokoll zum Kodieren und Dekodieren der Nachrichten

Das Protokoll ist keine freie Entscheidung – Ecoflow-Geräte
kommunizieren über ein proprietäres Protokoll das auf
**Protocol Buffers (Protobuf)** basiert. Dies wurde durch
Community Reverse Engineering dokumentiert und im Prototyp
erfolgreich validiert.

## Entscheidung

### 1. BLE Bibliothek: bleak

NagaBridge verwendet **bleak** als BLE-Bibliothek.

### 2. Protokoll: Protobuf als Constraint

Protobuf ist **keine Architekturentscheidung** sondern eine
**Constraint** – die Ecoflow-Geräte sprechen Protobuf,
NagaBridge hat keine Wahl.

Die Protobuf-Definitionen (.proto Dateien) wurden durch
Community Reverse Engineering erarbeitet und sind im Prototyp
bereits implementiert.

## Evaluierung BLE Bibliotheken

| Bibliothek  | Async | Aktiv gepflegt | Pi Support | Bewertung     |
|-------------|-------|----------------|------------|---------------|
| bleak       | ✅    | ✅             | ✅         | Empfohlen     |
| PyBluez     | ❌    | ❌             | ⚠️          | Veraltet      |
| dbus-fast   | ✅    | ✅             | ✅         | Zu low-level  |

### Warum bleak:

* modernes async/await API – passt zu asyncio-basierter Architektur
* plattformübergreifend (Linux, Windows, macOS)
* nutzt BlueZ auf Linux/Raspberry Pi nativ
* aktiv gepflegt, große Community
* bereits im Prototyp erfolgreich validiert

### Warum nicht PyBluez:

* keine async-Unterstützung
* seit Jahren kaum noch gepflegt
* Installationsprobleme auf neueren Python-Versionen

### Warum nicht dbus-fast:

* direkter D-Bus Zugriff – maximale Kontrolle aber hohe Komplexität
* kein Mehrwert gegenüber bleak für diesen Anwendungsfall
* würde Wartbarkeit deutlich verschlechtern

## Konsequenzen

**Positiv:**
* bleak ist asyncio-nativ – kein Threading nötig
* Prototyp-Code kann direkt übernommen werden
* Community-Dokumentation für Ecoflow-Protokoll verfügbar

**Negativ:**
* Protobuf-Abhängigkeit macht NagaBridge auf Ecoflow-Geräte
  spezialisiert
* Protokolländerungen durch Ecoflow-Firmware-Updates könnten
  Anpassungen erfordern

## Offene Punkte

* Protobuf .proto Definitionen für Delta2 und Delta2Max
  vollständig dokumentieren
* Verhalten bei Firmware-Updates beobachten

## Referenzen

* bleak: https://github.com/hbldh/bleak
* Prototyp: https://github.com/ldi0pathic/ecoflow-ble-mqtt
* Community Reverse Engineering: https://github.com/rabits/ha-ef-ble
