# CI Failure Playbook

Kurzanleitung für häufige Fehler in diesem Repo.

## Ruff: `F401 imported but unused`

**Symptom:**

```
F401 ... imported but unused
```

**Fix:**

- Unbenutzten Import entfernen.
- Danach lokal prüfen:

```bash
ruff check src/ tests/
```

---

## Black: `would reformat ...`

**Symptom:**

```
would reformat <file>
```

**Fix:**

```bash
black --target-version py312 <file>
black --target-version py312 --check src/ tests/
```

Hinweis: Zielversion ist `py312`, damit lokale/CI-Umgebungen konsistent sind.

---

## Pytest: optionale Integrationstests werden übersprungen

**Symptom:**

MQTT-Integrationstest ist `skipped`.

**Grund:**

`MQTT_IT_BROKER` ist nicht gesetzt oder Broker ist nicht erreichbar.

**Fix:**

```bash
export MQTT_IT_BROKER=<HOST>
export MQTT_IT_PORT=1883
PYTHONPATH=src pytest -q tests/test_mqtt_adapter.py -k integration
```
