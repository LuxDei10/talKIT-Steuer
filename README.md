# talKIT Steuermodul

Dieses Tool unterstützt das Finanzteam von talKIT e.V. bei der Vorbereitung der Steuerunterlagen auf Basis des Podio-Exports. Es berechnet alle relevanten Werte für die Elster-Formulare und gibt sie als strukturiertes PDF aus.

> Nur für das Finanzteam von talKIT e.V. – Zugang über Streamlit Viewer Authentication.

---

## Funktionsumfang

| Steuerart | Elster-Formular | Datumsbasis |
|---|---|---|
| USt-Voranmeldung (quartalsweise) | USt 1 A | Rechnungsdatum (Sollversteuerung, §16 Abs. 1 UStG) |
| USt-Jahreserklärung | USt 2 | Rechnungsdatum |
| Einnahmenüberschussrechnung | Anlage EÜR | Überweisungsdatum (Zufluss-Abfluss, §11 EStG) |
| Körperschaftsteuer | KSt 1 | EÜR-Ergebnis Sphäre D |
| Gewerbesteuer | GewSt 1 B | EÜR-Ergebnis Sphäre D |

Bei jedem Upload werden außerdem automatisch durchgeführt:
- Spalten-Matching mit manueller Korrekturoption
- MwSt-Konsistenzprüfung (Brutto gegen Netto-Felder)
- Zeitraumerkennung mit Vollständigkeitsprüfung

---

## Voraussetzungen

- Python 3.10 oder neuer
- Pakete aus `requirements.txt`

```bash
pip install -r requirements.txt
```

---

## Lokale Ausführung

```bash
streamlit run app.py
```

Der Browser öffnet sich automatisch auf `http://localhost:8501`.

---

## Deployment (Streamlit Community Cloud)

1. Repository auf GitHub als **public** anlegen
2. Alle Dateien pushen – **keine Excel-Dateien** (`.gitignore` schützt davor)
3. Auf [share.streamlit.io](https://share.streamlit.io) mit GitHub-Account einloggen
4. „New app" → Repository auswählen → `app.py` als Einstiegspunkt → Deploy
5. Unter **Settings → Sharing** die E-Mail-Adressen des Finanzteams eintragen

Die App aktualisiert sich automatisch bei jedem `git push`.

> ⚠️ Podio-Exportdateien dürfen **niemals** ins Repository gepusht werden. Die `.gitignore` schließt `.xlsx`-Dateien aus – trotzdem vor jedem Commit prüfen.

---

## Podio-Export vorbereiten

Export nach **Rechnungsdatum** filtern – das Modul übernimmt die interne Filterung nach Überweisungsdatum für die EÜR. Ein Jahresexport (alle GVs mit Rechnungsdatum im Steuerjahr) deckt alle Berechnungen ab.

Die Datei muss **genau ein Tabellenblatt** enthalten. Folgende Spalten werden benötigt:

| Spalte | Beschreibung |
|---|---|
| `Einmalige ID` | Eindeutige GV-Kennung, z.B. `TK003190` |
| `Buchung ext.` | Externe Buchungsnummer, z.B. `26.C1.A05 IT-Infrastruktur` |
| `Rechnungsdatum` | Datum der Rechnung (Basis USt-Voranmeldung) |
| `Überweisungsdatum` | Datum der Überweisung (Basis EÜR) |
| `Typ` | `Einnahme` oder `Ausgabe` |
| `Brutto-Betrag` | Gesamtbetrag inkl. MwSt |
| `Netto-Betrag 19% MwSt` | Nettobetrag des 19 %-Anteils |
| `Netto-Betrag 7% MwSt` | Nettobetrag des 7 %-Anteils |
| `Netto-Betrag anderer MwSt Satz` | Nettobetrag bei abweichendem Steuersatz |
| `Summe Netto` | Gesamtnettobetrag (wird in Podio automatisch berechnet) |

Optionale Spalten: `Titel`, `Konto`

Das Modul erkennt umbenannte Spalten automatisch per Ähnlichkeitssuche und bietet eine manuelle Korrekturoption an.

---

## Ablauf in der App

1. **Excel hochladen** – Podio-Export per Drag & Drop
2. **Spalten prüfen** – automatische Zuordnung wird angezeigt, bei Abweichungen manuell korrigieren
3. **MwSt-Check** – inkonsistente GVs werden mit `Einmaliger ID` gemeldet; Fehler in Podio korrigieren oder trotzdem fortfahren
4. **Steuerart wählen** – Voranmeldung (Quartal) oder Jahressteuererklärung
5. **Zeitraum wählen** – App macht Vorschlag basierend auf Buchungsdichte
6. **Vorauszahlungen eingeben** (nur Jahressteuer) – Werte aus den Elster-Bestätigungen der vier Quartale; positiv = Zahlung ans FA, negativ = Rückerstattung
7. **Berechnen** – Ergebnisse erscheinen direkt in der App
8. **PDF exportieren** – neben das Elster-Formular legen und Werte übertragen

---

## Dateistruktur

```
talkit-steuer/
├── app.py                  # Streamlit-Oberfläche
├── berechnung.py           # Berechnungslogik (Validierung, USt, EÜR, KSt, GewSt)
├── export.py               # PDF-Erzeugung (ReportLab)
├── requirements.txt        # Python-Abhängigkeiten
├── .gitignore              # Schützt Finanzdaten vor versehentlichem Push
├── README.md               # Diese Datei
└── PODIO_OPTIMIERUNG.md    # Verbesserungsvorschläge für das Podio-Buchungssystem
```

---

## Steuerrechtliche Grundlagen

### Sphärenzuordnung

Die Sphäre wird automatisch aus der externen Buchungsnummer extrahiert (zweites Segment nach dem ersten Punkt, z.B. `26.C1.A05` → Sphäre C):

| Sphäre | Inhalt | USt-pflichtig | KSt / GewSt |
|---|---|---|---|
| A – Ideeller Bereich | Mitgliedsbeiträge, Spenden, Verwaltung | Nein | Nein |
| C – Zweckbetrieb | Technologie-Events (Satzungszweck) | Ja | Nein |
| D – Wirtsch. Geschäftsbetrieb | Sponsoring, Merch, Getränke | Ja | Ja, wenn Freigrenze überschritten |

Bereich B (Vermögensverwaltung) wird nicht genutzt.

### Vorsteuerabzug

| Sphäre | Abzugsberechtigt | Grundlage |
|---|---|---|
| A | 0 % | §15 Abs. 2 UStG |
| C | 90 % | Vereinbarung mit dem Finanzamt Karlsruhe |
| D | 100 % | §15 Abs. 1 UStG |

### Freigrenze wirtschaftlicher Geschäftsbetrieb

| Steuerjahr | Freigrenze (Brutto-Einnahmen D) |
|---|---|
| bis 2025 | 45.000 € |
| ab 2026 | 50.000 € |

Bei Überschreitung gilt ein zusätzlicher Freibetrag von 5.000 € auf den Gewinn (§64 Abs. 3 AO). Erst darüber fallen KSt (15 % + 5,5 % SolZ) und GewSt an.

### Gewerbesteuer Karlsruhe

Hebesatz **450 %** (Stand 2026) · Steuermesszahl **3,5 %** (bundeseinheitlich)

---

## Konfiguration

Steuerrelevante Parameter stehen am Anfang von `berechnung.py` und müssen jährlich geprüft werden:

```python
GEWST_HEBESATZ       = 4.50   # 450 % – Hebesatz Karlsruhe, jährlich prüfen
VORSTEUER_ABSCHLAG_C = 0.90   # 90 % – laut Vereinbarung Finanzamt
```

Die Freigrenze ist jahresabhängig in `freigrenze(jahr)` hinterlegt und muss nur bei gesetzlichen Änderungen angepasst werden.

---

## Bekannte Einschränkungen

| Einschränkung | Ursache | Workaround |
|---|---|---|
| Negativbeträge (PayPal-Gebühren) | Podio hat keine eigene Buchungsnummer für Abzüge | Betrag negativ unter Einnahme-BN eintragen; Modul behandelt das korrekt |
| Andere Steuersätze nicht prüfbar | Steuersatz unbekannt, daher kein Soll-Brutto berechenbar | Modul listet betroffene GVs zur manuellen Prüfung auf |
| Vorauszahlungen manuell | Steuerzahlungen in Podio nicht maschinenlesbar getrennt | Werte aus Elster-Bestätigungen manuell eingeben |
| Gemischte Aufwendungen nicht aufteilbar | Buchungssystem unterstützt keine anteilige Sphärenzuordnung | GV vollständig einer Sphäre zuordnen; Pauschalvereinbarung mit FA gilt für C |

Weitere Verbesserungsvorschläge für das Podio-System: [`PODIO_OPTIMIERUNG.md`](PODIO_OPTIMIERUNG.md)

---

## Wartung & Übergabe

### Jährliche Checkliste

- [ ] `GEWST_HEBESATZ` in `berechnung.py` prüfen (Karlsruhe veröffentlicht Änderungen im Herbst)
- [ ] `freigrenze()` in `berechnung.py` prüfen (gesetzliche Änderungen)
- [ ] Streamlit Viewer Authentication: neue Finanzverantwortliche eintragen, ausgeschiedene entfernen
- [ ] Erste Voranmeldung des neuen Jahres gegen Kontoauszug gegenchecken

### Übergabe an neues Finanzteam

Das Modul erfordert keine Programmierkenntnisse für die Nutzung. Für Wartung und Anpassungen:
- GitHub-Zugang zum Repository
- Grundlegendes Python-Verständnis (Konstanten ändern, Variablen lesen)
- Streamlit-Account (Login via GitHub)

### Bei Änderungen am Podio-Buchungssystem

Das Format der Buchungsnummern (`XX.Sphäre.XXX Bezeichnung`) muss beibehalten werden – die Sphärenextraktion hängt davon ab. Neue Buchungsnummern innerhalb des bestehenden Schemas erfordern keine Code-Änderungen.

---

## Erstkalibrierung (vor dem ersten echten Einsatz)

Vor der ersten echten Einreichung sollte das Modul gegen bekannte Werte geprüft werden:

1. Einen abgeschlossenen Zeitraum exportieren für den eine Elster-Bestätigung vorliegt
2. Voranmeldung mit dem Modul berechnen
3. Ergebnis Zeile für Zeile mit der Elster-Bestätigung vergleichen
4. Abweichungen dokumentieren und ursächlich klären

---

## Lizenz

MIT License – Copyright (c) 2026 talKIT e.V.
