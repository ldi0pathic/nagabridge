# NagaBridge Requirements

## 1. Ziel des Systems

NagaBridge ist ein lokales System zur Integration und Steuerung von
Energiegeräten (z. B. Ecoflow Powerstream, Delta2, Delta2Max).

Ziel ist es:

* Gerätedaten lokal zu erfassen (ohne Cloud)
* diese Daten in Echtzeit verfügbar zu machen
* Steuerbefehle schnell und zuverlässig auszuführen
* verschiedene Systeme (MQTT, Web UI, weitere Adapter) zu integrieren

---

## 2. Kernanforderungen

### 2.1 Low Latency

* Neue Daten müssen ohne spürbare Verzögerung verarbeitet werden
* Ziel: Weitergabe von Daten innerhalb weniger Millisekunden
* Fokus auf Reaktionsgeschwindigkeit statt Vollständigkeit

---

### 2.2 State-First Modell

* Nur der aktuelle Zustand ist relevant
* Historische Daten sind für den Kernprozess nicht erforderlich
* Neue Zustände überschreiben alte vollständig

Beispiele:

* aktueller Hausverbrauch
* aktuelle Einspeisung
* aktueller Batteriestand

---

### 2.3 Lokaler Betrieb

* System läuft vollständig lokal (z. B. Raspberry Pi)
* keine Abhängigkeit von externen Cloud-Diensten
* Netzwerkzugriff optional, aber nicht erforderlich

---

### 2.4 Modulare Architektur

* System besteht aus unabhängigen Modulen (Adapter)
* Module kommunizieren ausschließlich über einen zentralen Bus
* neue Module können ohne Änderung bestehender Module hinzugefügt werden

Beispiele für Module:

* BLE Adapter (Ecoflow Geräte)
* MQTT Adapter (ioBroker Integration)
* Web UI (zukünftig)
* weitere Geräteadapter (z. B. Shelly)

---

### 2.5 Multi-Consumer Unterstützung

* mehrere Module können gleichzeitig Daten konsumieren
* alle Module können prinzipiell alle Topics abonnieren
* Module entscheiden selbst, welche Daten sie nutzen

---

### 2.6 Robustes Verhalten bei Fehlern

* bei Verbindungsabbrüchen (z. B. MQTT):

  * alte Daten werden verworfen
  * neue Daten werden verarbeitet, sobald verfügbar
* System darf nicht blockieren oder abstürzen

---

## 3. Datenanforderungen

### 3.1 State-Daten

* werden regelmäßig aktualisiert (ca. 1x pro Sekunde pro Gerät)
* enthalten nur aktuelle Werte
* müssen schnell weitergegeben werden

Beispiele:

* Leistung (Watt)
* PV Eingang
* Batteriestand

---

### 3.2 Commands

* dienen zur Steuerung von Geräten
* aktueller Command überschreibt vorherige Commands

Aktuelle Beispiele:

* set_power (Einspeisung ändern)
* set_min_battery (minimalen Akkustand setzen)

---

### 3.3 Events (optional)

* seltene Ereignisse (z. B. Fehler, Disconnect)
* nicht Teil des kritischen Steuerpfads
* können optional geloggt oder gespeichert werden

---

## 4. Performance-Anforderungen

* Verarbeitung von mindestens:

  * 1 Event pro Sekunde pro Gerät
* System muss stabil bleiben bei:

  * mehreren Geräten
  * mehreren Subscribern
* minimale CPU- und Speicherlast

---

## 5. Nicht-Funktionale Anforderungen

### 5.1 Einfachheit

* möglichst geringe Komplexität
* keine unnötigen Abstraktionen
* keine externen Abhängigkeiten für den Kern

---

### 5.2 Erweiterbarkeit

* neue Geräte und Adapter müssen leicht integrierbar sein
* bestehende Komponenten dürfen nicht angepasst werden müssen

---

### 5.3 Wartbarkeit

* klare Struktur
* nachvollziehbarer Datenfluss
* einfache Debugging-Möglichkeiten

---

## 6. Abgrenzung (Out of Scope)

Folgende Punkte sind aktuell nicht Teil des Systems:

* langfristige Datenspeicherung / Historie
* komplexe Event-Verarbeitung (z. B. Event Sourcing)
* garantierte Zustellung von Nachrichten
* Cloud-Integration als Pflichtbestandteil

---

## 7. Offene Punkte

* Bedarf an State-Persistenz bei Neustart
* Logging-Strategie
* Umgang mit kritischen Commands (falls Anforderungen steigen)
* Zugriffskontrolle für zukünftige APIs (Web UI)
