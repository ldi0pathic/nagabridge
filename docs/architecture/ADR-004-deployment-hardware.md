# ADR-004: Deployment auf Raspberry Pi als primäre Hardware

## Status
Accepted

## Datum
2026-03-29

## Kontext

NagaBridge benötigt eine Bluetooth-fähige Hardware um BLE-Geräte
(Ecoflow Powerstream, Delta2, Delta2Max) anzusprechen.

Die verfügbare Infrastruktur:

* Proxmox NUC (kein eingebautes Bluetooth)
* Raspberry Pi (Bluetooth eingebaut, Prototyp läuft bereits)

Eine RSSI-Messung hat ergeben:

* Powerstream direkt: -45 dBm
* NUC-Standort (durch eine Innenwand): -58 bis -66 dBm

Beide Werte liegen komfortabel über dem Grenzwert von -75 dBm
für stabile BLE-Verbindungen.

## Entscheidung

NagaBridge läuft auf dem **Raspberry Pi**.

Der Pi ist die primäre Laufzeitumgebung für alle
NagaBridge-Komponenten:

* BLE Adapter (Bluetooth eingebaut)
* Event Bus
* MQTT Adapter
* alle weiteren Module

Der Pi hat eine eigene Stromversorgung unabhängig von den
Ecoflow-Geräten.

## Betrachtete Alternativen

### Alternative A: Proxmox LXC mit USB Bluetooth Dongle

**Vorteile:**
* alles zentral auf Proxmox
* ein Wartungspunkt weniger
* kein separates Gerät im Netzwerk

**Nachteile:**
* USB Passthrough in LXC muss konfiguriert werden
* zusätzliche Hardware (Dongle) erforderlich
* noch nicht getestet

**Verworfen:**
Dongle aktuell nicht auffindbar. Pi funktioniert bereits.
Migration möglich sobald Dongle verfügbar und USB Passthrough
evaluiert wurde.

## Konsequenzen

**Positiv:**
* kein Setup-Aufwand – Prototyp läuft bereits
* Bluetooth eingebaut, keine externe Hardware nötig
* BLE-Signalstärke ausreichend getestet

**Negativ:**
* zusätzliches Gerät im Heimnetz
* zusätzlicher Wartungspunkt

## Offene Punkte

* Migration zu Proxmox LXC evaluieren sobald USB Dongle
  verfügbar
* USB Passthrough für Bluetooth in Proxmox LXC testen

## Referenzen

* RSSI-Messung mit nRF Connect App
* Prototyp: https://github.com/ldi0pathic/ecoflow-ble-mqtt
