# talKIT Steuermodul

Dieses Tool unterstützt das Finanzteam von talKIT e.V. bei der Vorbereitung der Steuerunterlagen auf Basis des Podio-Exports. Es berechnet alle relevanten Werte für die Elster-Formulare und gibt sie als strukturiertes PDF aus.

---

## Funktionsumfang

| Steuerart | Formular | Basis |
|---|---|---|
| USt-Voranmeldung (quartalsweise) | USt 1 A | Rechnungsdatum |
| USt-Jahreserklärung | USt 2 | Rechnungsdatum |
| Einnahmenüberschussrechnung | Anlage EÜR | Überweisungsdatum |
| Körperschaftsteuer | KSt 1 | EÜR-Ergebnis Sphäre D |
| Gewerbesteuer | GewSt 1 B | EÜR-Ergebnis Sphäre D |

Zusätzlich wird bei jedem Start eine **MwSt-Konsistenzprüfung** durchgeführt, die Eingabefehler im Podio-Export erkennt, bevor sie in die Berechnung einfließen.

---

## Voraussetzungen

- Python 3.10 oder neuer
- Die Pakete aus `requirements.txt`

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
2. Alle Dateien pushen – **keine Excel-Dateien** (sind in `.gitignore` ausgeschlossen)
3. Auf [share.streamlit.io](https://share.streamlit.io) mit GitHub einloggen
4. „New app" → Repository auswählen → `app.py` als Einstiegspunkt → Deploy
5. Unter **Settings → Sharing** die E-Mail-Adressen des Finanzteams als Viewer eintragen

Die App aktualisiert sich automatisch bei jedem `git push`.

> ⚠️ Die App-URL ist prinzipiell öffentlich erreichbar. Durch die Viewer-Authentication unter Streamlit Cloud Settings sind nur eingetragene E-Mail-Adressen zugelassen. Podio-Exportdateien dürfen **niemals** ins Repository gepusht werden.

---

## Benutzung

### Podio-Export vorbereiten

In Podio die Buchhaltungs-App als Excel exportieren. Die Datei muss **genau ein Tabellenblatt** enthalten und folgende Spalten aufweisen:

| Spalte | Beschreibung |
|---|---|
| `Einmalige ID` | Eindeutige GV-Kennung (z.B. `TK003190`) |
| `Buchung ext.` | Externe Buchungsnummer (z.B. `26.C1.A05 IT-Infrastruktur`) |
| `Rechnungsdatum` | Datum der Rechnung (Basis USt) |
| `Überweisungsdatum` | Datum der Überweisung (Basis EÜR) |
| `Typ` | `Einnahme` oder `Ausgabe` |
| `Brutto-Betrag` | Gesamtbetrag inkl. MwSt |
| `Netto-Betrag 19% MwSt` | Nettobetrag des 19%-Anteils |
| `Netto-Betrag 7% MwSt` | Nettobetrag des 7%-Anteils |
| `Netto-Betrag anderer MwSt Satz` | Nettobetrag bei abweichendem Steuersatz |
| `Summe Netto` | Gesamtnettobetrag (automatisch in Podio berechnet) |

Optionale Spalten: `Titel`, `Konto`

### Ablauf in der App

1. Excel-Datei hochladen
2. Automatische Validierung abwarten – Fehler werden mit der `Einmaligen ID` ausgewiesen
3. Steuerart wählen (Voranmeldung oder Jahressteuer)
4. Zeitraum wählen – die App macht Vorschläge basierend auf den Daten
5. Bei Jahressteuer: geleistete Vorauszahlungen eintragen
   - Positiver Wert = Zahlung ans Finanzamt
   - Negativer Wert = Rückzahlung vom Finanzamt
6. Berechnung starten
7. PDF exportieren und neben das Elster-Formular legen

---

## Dateistruktur

```
talkit-steuer/
├── app.py              # Streamlit-Oberfläche
├── berechnung.py       # Alle Berechnungsfunktionen
├── export.py           # PDF-Erzeugung
├── requirements.txt    # Python-Abhängigkeiten
├── .gitignore          # Schützt Finanzdaten vor versehentlichem Push
└── README.md           # Diese Datei
```

---

## Steuerrechtliche Grundlagen

### Sphärenzuordnung

Der Verein ist in drei steuerrelevante Bereiche aufgeteilt, die sich aus der externen Buchungsnummer ergeben (zweites Segment nach dem ersten Punkt):

| Sphäre | Kürzel | Inhalt | USt | KSt/GewSt |
|---|---|---|---|---|
| Ideeller Bereich | `A` | Mitgliedsbeiträge, Spenden, Verwaltung | nicht steuerbar | nein |
| Zweckbetrieb | `C` | Technologie-Events (Satzungszweck) | steuerpflichtig | nein |
| Wirtsch. Geschäftsbetrieb | `D` | Sponsoring, Merch, Getränke | steuerpflichtig | ja, wenn Freigrenze überschritten |

> Bereich B (Vermögensverwaltung) wird vom Verein nicht genutzt.

### Vorsteuerabzug

- Sphäre **A**: nicht vorsteuerabzugsberechtigt (§ 15 Abs. 2 UStG)
- Sphäre **C**: 90 % vorsteuerabzugsberechtigt (Vereinbarung mit dem Finanzamt)
- Sphäre **D**: 100 % vorsteuerabzugsberechtigt

### Freigrenze wirtschaftlicher Geschäftsbetrieb (§ 64 Abs. 3 AO)

| Steuerjahr | Freigrenze (Brutto-Einnahmen D) |
|---|---|
| bis 2025 | 45.000 € |
| ab 2026 | 50.000 € |

Wird die Freigrenze überschritten, gilt ein Freibetrag von 5.000 € auf den Gewinn. Erst darüber fallen KSt und GewSt an.

### Gewerbesteuer Karlsruhe

Hebesatz: **450 %** (Stand 2026) · Steuermesszahl: **3,5 %** (bundeseinheitlich)

---

## Konfiguration

Steuerrelevante Parameter sind am Anfang von `berechnung.py` als Konstanten hinterlegt und können dort jährlich aktualisiert werden:

```python
GEWST_HEBESATZ     = 4.50    # 450 % Karlsruhe
VORSTEUER_ABSCHLAG_C = 0.90  # 90 % laut Vereinbarung Finanzamt
```

Die Freigrenze ist jahresabhängig in der Funktion `freigrenze(jahr)` hinterlegt.

---

## Bekannte Einschränkungen

- **Negativbeträge (PayPal-Gebühren):** Korrekturbuchungen mit negativem Vorzeichen unter einer Einnahme-Buchungsnummer sind eine Übergangslösung und sollten in einer späteren Überarbeitung des Buchungssystems durch eine eigene Buchungsnummer ersetzt werden.
- **Andere Steuersätze:** GVs im Feld `Netto-Betrag anderer MwSt Satz` können vom MwSt-Check nicht automatisch verifiziert werden und werden zur manuellen Prüfung ausgegeben.
- **Abschreibungen:** Das Modul setzt voraus, dass alle Anschaffungen sofort als Aufwand verbucht werden (keine AfA-Tabelle).
- **Vorauszahlungen:** Die tatsächlich geleisteten USt-Vorauszahlungen müssen manuell eingegeben werden, da sie im Podio-Export nicht eindeutig als separate Felder vorliegen.

---

## Wartung & Übergabe

### Jährliche Aufgaben

- [ ] Hebesatz Karlsruhe prüfen und ggf. in `berechnung.py` aktualisieren
- [ ] Freigrenze prüfen (in `berechnung.py` → Funktion `freigrenze()`)
- [ ] Streamlit Viewer Authentication: E-Mail des neuen Finanzteams eintragen, altes Team entfernen

### Bei Änderungen am Podio-Buchungssystem

Neue oder geänderte Buchungsnummern haben keinen Einfluss auf die Berechnung, solange das Format `XX.Sphäre.XXX Bezeichnung` beibehalten wird. Die Sphärenzuordnung (A/C/D) wird dynamisch aus der Buchungsnummer extrahiert.

---

## Lizenz

Internes Tool des talKIT e.V. – nicht zur Weitergabe bestimmt.
