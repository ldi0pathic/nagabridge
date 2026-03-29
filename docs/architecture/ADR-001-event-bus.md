# ADR-001: Event Bus als zentrales Kommunikationsmuster

## Status
Accepted

## Datum
2026-03-28

## Kontext

NagaBridge verbindet verschiedene Protokollwelten miteinander:
BLE-Geräte (Ecoflow Powerstream, Delta2Max, Delta2) sollen lokal
ohne Cloud-Abhängigkeit angesprochen und ihre Daten via MQTT an
einen ioBroker weitergeleitet werden.

Ein erster funktionierender Prototyp (ecoflow-ble-mqtt) hat gezeigt
dass die grundlegende BLE-Kommunikation mit Ecoflow-Geräten möglich
ist. Der Prototyp verwendete direkte Callbacks zwischen den
Komponenten:
```
BLEDeviceManager ──callbacks──► EcoFlowDevice
EcoFlowDevice    ──callbacks──► MQTTBridge  
MQTTBridge       ──callbacks──► BLEDeviceManager
```

Dies führte zu folgenden konkreten Problemen:

- **Tight Coupling:** Jede Komponente kennt die anderen direkt.
  Das Hinzufügen eines neuen Geräts (Delta2Max) erforderte
  Änderungen an mehreren Stellen gleichzeitig.
- **Schwer testbar:** Komponenten können nicht isoliert getestet
  werden ohne die anderen zu instanziieren.
- **Nicht erweiterbar:** Eine Web-UI, ein Logger oder ein
  Hausverbrauch-Modul müsste direkt in bestehende Komponenten
  eingebaut werden.

## Entscheidung

NagaBridge verwendet einen zentralen **Event Bus** als einzigen
Kommunikationskanal zwischen allen Modulen.
```
BLEDeviceManager ──publish──► [ Event Bus ] ◄──subscribe── MQTTBridge
MQTTBridge       ──publish──► [ Event Bus ] ◄──subscribe── BLEDeviceManager
WebUI            ──publish──► [ Event Bus ] ◄──subscribe── Logger
```

Jedes Modul kennt nur den Bus – nicht die anderen Module.
Die Kommunikation erfolgt über benannte Topics:
```
ecoflow/powerstream/state      # Gerätedaten eingehend
ecoflow/powerstream/set        # Steuerbefehle ausgehend  
mqtt/state                     # MQTT Verbindungsstatus
system/shutdown                # Graceful Shutdown
```

Der Event Bus wird als einfaches Python-Modul implementiert
(`asyncio`-basiert, kein externes Framework).

Der MQTT-Adapter ist ein normaler Bus-Subscriber der
Daten nach außen weiterleitet. Er ist nicht der Bus –
er nutzt den Bus.

WLAN-Ausfall betrifft nur den MQTT-Adapter.
Der interne Bus und alle anderen Adapter laufen weiter.

## Betrachtete Alternativen

### Alternative A: Direkte Callbacks (Status quo Prototyp)
**Vorteile:** Einfach, wenig Code, gut verständlich.  
**Nachteile:** Tight Coupling, schwer erweiterbar, Delta2Max-Problem
hat gezeigt dass neue Gerätevarianten schwierig einzubauen sind.  
**Verworfen:** Skaliert nicht für das geplante Modulkonzept.

### Alternative B: Externes Message Broker Framework (z.B. Redis Pub/Sub)
**Vorteile:** Battle-tested, viele Features, persistent.  
**Nachteile:** Externe Abhängigkeit, zusätzlicher Prozess,
Overhead für ein Embedded-System auf einem Raspberry Pi.  
**Verworfen:** Over-Engineering für den aktuellen Scope.

### Alternative C: Python `asyncio.Queue` pro Verbindung
**Vorteile:** Eingebaut in Python, keine Abhängigkeiten.  
**Nachteile:** Point-to-Point, kein Broadcasting,
jede neue Verbindung braucht eine neue Queue.  
**Verworfen:** Löst das Coupling-Problem nicht grundsätzlich.

## Konsequenzen

**Positiv:**
- Neue Module (Web-UI, Logger, CoAP-Adapter) können ohne
  Änderung bestehender Module hinzugefügt werden.
- Jedes Modul kann isoliert getestet werden.
- Der Delta2Max Type7 Buffer-Bug kann im BLE-Modul allein
  gefixt werden ohne andere Module zu berühren.
- Klare Systemgrenze: Was auf dem Bus landet ist die
  öffentliche API von NagaBridge.

**Negativ:**
- Etwas mehr initialer Boilerplate-Code.
- Debugging ist indirekter – man muss den Bus beobachten
  um den Datenfluss zu verstehen (Lösung: Bus-Logging).

## Referenzen

- Prototyp: https://github.com/ldi0pathic/ecoflow-ble-mqtt
- Muster: Publish-Subscribe Pattern (GoF)
- Muster: Mediator Pattern (GoF)
- Inspiration: CAN-Bus (Controller Area Network)
