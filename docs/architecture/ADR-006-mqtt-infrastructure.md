# ADR-006: MQTT Infrastruktur – Mosquitto als eigenständiger LXC

## Status
Accepted

## Datum
2026-03-29

## Kontext

NagaBridge benötigt einen MQTT Broker als zentralen
Kommunikationspunkt zwischen:

* NagaBridge (Raspberry Pi)
* ioBroker (Proxmox LXC)
* Shelly-Geräten (zukünftig)
* weiteren Clients

Aktuell fungiert der **ioBroker MQTT Adapter** als Broker.
Das bedeutet: ioBroker ist ein Single Point of Failure.
Fällt ioBroker aus, verlieren alle MQTT-Clients ihre Verbindung –
inklusive NagaBridge und der Powerstream-Steuerung.

Die vorhandene Infrastruktur (Proxmox) ermöglicht es einen
eigenständigen Mosquitto-Broker als LXC Container zu betreiben.

## Entscheidung

**Mosquitto** wird als eigenständiger LXC Container auf Proxmox
betrieben und ersetzt den ioBroker MQTT Adapter als Broker.
```
Vorher:
NagaBridge ──MQTT──► ioBroker MQTT Adapter (Broker)
Shellys    ──MQTT──► ioBroker MQTT Adapter (Broker)

Nachher:
NagaBridge ──MQTT──► Mosquitto (Broker) ◄──── ioBroker (Client)
Shellys    ──MQTT──► Mosquitto (Broker)
```

ioBroker wird vom Broker zum Client – genau wie alle anderen.

## Betrachtete Alternativen

### Alternative A: ioBroker MQTT Adapter bleibt Broker

**Vorteile:**
* kein Setup-Aufwand
* funktioniert bereits

**Nachteile:**
* ioBroker ist Single Point of Failure
* fällt ioBroker aus, stoppt die Powerstream-Steuerung
* widerspricht dem Ziel der Cloud- und Abhängigkeitsfreiheit

**Verworfen:**
Single Point of Failure nicht akzeptabel für ein
Steuerungssystem.

### Alternative B: MQTT Broker auf dem Raspberry Pi

**Vorteile:**
* alles auf einer Hardware

**Nachteile:**
* Pi ist ressourcenbeschränkt
* Broker und NagaBridge teilen sich Hardware
* Pi-Ausfall würde Broker mitreißen

**Verworfen:**
Trennung von Broker und Client ist architektonisch sauberer.

## Konsequenzen

**Positiv:**
* ioBroker-Ausfall hat keinen Einfluss auf NagaBridge
* Mosquitto ist extrem leichtgewichtig (~10MB RAM)
* alle MQTT-Clients sind gleichwertige Teilnehmer
* Shellys können direkt zu Mosquitto migrieren ohne
  ioBroker-Abhängigkeit

**Negativ:**
* bestehende Shelly- und ioBroker-Konfiguration muss
  auf neuen Broker umgestellt werden
* ein weiterer LXC Container auf Proxmox

## Migrationspfad

1. Mosquitto LXC auf Proxmox aufsetzen
2. NagaBridge gegen Mosquitto konfigurieren
3. ioBroker MQTT Adapter auf Client-Modus umstellen
4. Shellys schrittweise auf Mosquitto migrieren
5. ioBroker MQTT Adapter (Server-Modus) deaktivieren

## Offene Punkte

* Mosquitto Authentifizierung konfigurieren
* TLS für MQTT prüfen (intern wahrscheinlich nicht nötig)
* ioBroker MQTT Bridge Adapter evaluieren für
  nahtlose Migration

## Referenzen

* Mosquitto: https://mosquitto.org
* ADR-001: Event Bus als zentrales Kommunikationsmuster
