# -*- coding: utf-8 -*-
"""
berechnung.py – talKIT Steuermodul
Alle Berechnungsfunktionen: Validierung, Voranmeldung, EÜR, USt-Jahres, KSt/GewSt
"""

import pandas as pd
import numpy as np

# ── KONFIGURATION ─────────────────────────────────────────────────────────────

# Gewerbesteuer-Hebesatz Karlsruhe (Stand 2026)
GEWST_HEBESATZ = 4.50          # 450% als Dezimalzahl
GEWST_MESSZAHL = 0.035         # 3,5% bundeseinheitlich

# Körperschaftsteuer
KST_SATZ = 0.15                # 15%
SOLZ_SATZ = 0.055              # 5,5% auf KSt

# Freigrenze wirtschaftlicher Geschäftsbetrieb (§ 64 Abs. 3 AO)
# Ab Steuerjahr 2026: 50.000 €, davor: 45.000 €
def freigrenze(jahr: int) -> float:
    return 50_000.0 if jahr >= 2026 else 45_000.0

# Freibetrag nach Überschreiten der Freigrenze
FREIBETRAG_D = 5_000.0

# Zweckbetrieb (C): Anteil vorsteuerabzugsberechtigt laut Vereinbarung Finanzamt
VORSTEUER_ABSCHLAG_C = 0.90    # 90%

# Pflichtfelder im Podio-Export
PFLICHT_SPALTEN = [
    'Einmalige ID',
    'Buchung ext.',
    'Rechnungsdatum',
    'Überweisungsdatum',
    'Typ',
    'Brutto-Betrag',
    'Netto-Betrag 19% MwSt',
    'Netto-Betrag 7% MwSt',
    'Netto-Betrag anderer MwSt Satz',
    'Summe Netto',
]
OPTIONALE_SPALTEN = ['Titel', 'Konto']


# ── 1. VALIDIERUNG ────────────────────────────────────────────────────────────

def pruefe_spalten(df: pd.DataFrame) -> list[str]:
    """Gibt Liste fehlender Pflicht-Spalten zurück. Leer = alles OK."""
    return [s for s in PFLICHT_SPALTEN if s not in df.columns]


def pruefe_mwst_konsistenz(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Prüft ob 19%- und 7%-Netto-Felder mit dem Brutto-Betrag übereinstimmen.
    Formel: Brutto_erwartet = Netto_19 * 1.19 + Netto_7 * 1.07 + Netto_andere

    Gibt zurück:
        fehler_df   – GVs mit echter Abweichung (ohne GVs mit anderem Steuersatz)
        andere_df   – GVs mit 'anderem Steuersatz' (manuell zu prüfen)
    """
    df = df.copy()

    # Fehlende Betragsfelder mit 0 auffüllen (nur für Prüfzwecke)
    for col in ['Netto-Betrag 19% MwSt', 'Netto-Betrag 7% MwSt',
                'Netto-Betrag anderer MwSt Satz', 'Brutto-Betrag']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Erwarteter Brutto (Beträge können negativ sein – Vorzeichen beibehalten)
    df['_brutto_erwartet'] = (
        df['Netto-Betrag 19% MwSt'] * 1.19 +
        df['Netto-Betrag 7% MwSt'] * 1.07 +
        df['Netto-Betrag anderer MwSt Satz'] * 1.0
    ).round(2)

    df['_differenz'] = (df['_brutto_erwartet'] - df['Brutto-Betrag']).abs().round(2)

    # GVs mit anderem Steuersatz separat – diese können legitim abweichen
    hat_anderen = df['Netto-Betrag anderer MwSt Satz'].abs() > 0
    andere_df = df[hat_anderen].copy()
    pruefbar_df = df[~hat_anderen].copy()

    # Fehler: Abweichung > 0,02 € (Rundungstoleranz)
    ausgabe_spalten = ['Einmalige ID', 'Titel', 'Brutto-Betrag',
                       'Netto-Betrag 19% MwSt', 'Netto-Betrag 7% MwSt',
                       '_brutto_erwartet', '_differenz']
    ausgabe_spalten = [s for s in ausgabe_spalten if s in pruefbar_df.columns]

    fehler_df = pruefbar_df[pruefbar_df['_differenz'] > 0.02][ausgabe_spalten].copy()
    fehler_df = fehler_df.rename(columns={
        '_brutto_erwartet': 'Brutto erwartet',
        '_differenz': 'Abweichung (€)'
    })

    andere_ausgabe = ['Einmalige ID', 'Titel', 'Brutto-Betrag',
                      'Netto-Betrag anderer MwSt Satz']
    andere_ausgabe = [s for s in andere_ausgabe if s in andere_df.columns]
    andere_df = andere_df[andere_ausgabe].copy()

    return fehler_df, andere_df


def erkenne_zeitraeume(df: pd.DataFrame) -> pd.DataFrame:
    """
    Erkennt alle Quartale und Jahre in den Daten (basierend auf Rechnungsdatum).
    Gibt DataFrame zurück: Jahr, Quartal, Anzahl Buchungen, vollständig (bool)
    """
    df = df.copy()
    df['Rechnungsdatum'] = pd.to_datetime(df['Rechnungsdatum'], errors='coerce')
    df = df[df['Rechnungsdatum'].notna()]
    df['_jahr'] = df['Rechnungsdatum'].dt.year
    df['_quartal'] = df['Rechnungsdatum'].dt.quarter

    quartal_counts = (
        df.groupby(['_jahr', '_quartal'])
        .size()
        .reset_index(name='Buchungen')
        .rename(columns={'_jahr': 'Jahr', '_quartal': 'Quartal'})
        .sort_values(['Jahr', 'Quartal'])
    )

    # Prüfe welche Jahre alle 4 Quartale haben
    quartale_pro_jahr = quartal_counts.groupby('Jahr')['Quartal'].nunique()
    quartal_counts['Jahr vollständig'] = quartal_counts['Jahr'].map(
        lambda j: quartale_pro_jahr.get(j, 0) == 4
    )

    return quartal_counts


# ── 2. DATENVORBEREITUNG ──────────────────────────────────────────────────────

def _parse_datum(series: pd.Series) -> pd.Series:
    """
    Robuste Datumsverarbeitung für Podio-Exporte.

    Podio kann Daten je nach Browser/Exporteinstellung unterschiedlich
    formatieren. Diese Funktion versucht mehrere Formate und gibt NaT
    zurück wo kein Format passt.

    Besonderheit: Amerikanisches Format (MM/DD/YYYY) wird nur als letzten
    Fallback versucht und nur wenn kein deutsches Format passt.
    Damit wird verhindert dass "01.02.2026" (1. Februar) als
    "2. Januar" interpretiert wird.
    """
    # Erster Versuch: pd.to_datetime ohne Format – erkennt ISO und Excel-Zahlen
    result = pd.to_datetime(series, errors='coerce', dayfirst=True)

    # Für verbleibende NaT: explizite Formate in sicherer Reihenfolge
    # Deutsches Format zuerst – verhindert amerikanische Fehlinterpretation
    formate_sicher = [
        '%d.%m.%Y',   # 28.01.2026
        '%d.%m.%y',   # 28.01.26
        '%d/%m/%Y',   # 28/01/2026
        '%Y-%m-%d',   # 2026-01-28 (ISO)
    ]
    # Amerikanisches Format nur als letzter Ausweg – potenziell mehrdeutig
    formate_mehrdeutig = ['%m/%d/%Y']

    for fmt_liste in [formate_sicher, formate_mehrdeutig]:
        mask_nat = result.isna()
        if not mask_nat.any():
            break
        for fmt in fmt_liste:
            noch_nat = result.isna()
            if not noch_nat.any():
                break
            versuch = pd.to_datetime(
                series[noch_nat], format=fmt, errors='coerce'
            )
            result[noch_nat] = versuch

    return result


def bereite_daten_vor(df: pd.DataFrame) -> pd.DataFrame:
    """
    Bereitet den Podio-Export für Berechnungen vor:
    - Extrahiert steuerrelevante Spalten
    - Konvertiert Datentypen
    - Filtert GVs ohne externe Buchungsnummer (z.B. Steuerzahlungen)
    - Extrahiert Sphäre (A/C/D) aus Buchungsnummer
    - Behält Vorzeichen bei (negative Beträge = Korrekturbuchungen)
    """
    spalten = PFLICHT_SPALTEN + [s for s in OPTIONALE_SPALTEN if s in df.columns]
    df = df[spalten].copy()

    # Datumsfelder – robuste Verarbeitung mehrerer Formate
    for datumsspalte in ['Rechnungsdatum', 'Überweisungsdatum']:
        df[datumsspalte] = _parse_datum(df[datumsspalte])

    # Betragsfelder numerisch
    betragsspalten = [
        'Brutto-Betrag', 'Netto-Betrag 19% MwSt',
        'Netto-Betrag 7% MwSt', 'Netto-Betrag anderer MwSt Satz', 'Summe Netto'
    ]
    for col in betragsspalten:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Nur GVs mit externer Buchungsnummer (ohne: Steuerzahlungen etc.)
    df = df[df['Buchung ext.'].notna()].copy()

    # Sphäre extrahieren: zweites Segment nach erstem Punkt
    # Beispiel: "26.C1.A05 IT-Infrastruktur" → "C"
    def extrahiere_sphare(text):
        try:
            teile = str(text).split('.')
            if len(teile) >= 2:
                return teile[1][0].upper()  # erster Buchstabe des zweiten Segments
        except Exception:
            pass
        return None

    df['Sphäre'] = df['Buchung ext.'].apply(extrahiere_sphare)

    # Vorzeichen: Ausgaben negativ, Einnahmen positiv
    df['Multiplikator'] = df['Typ'].map({'Einnahme': 1, 'Ausgabe': -1})

    unbekannt = df['Multiplikator'].isna().sum()
    if unbekannt > 0:
        df = df[df['Multiplikator'].notna()].copy()

    for col in betragsspalten:
        df[col] = df[col] * df['Multiplikator']

    return df, unbekannt


# ── 3. UMSATZSTEUER-VORANMELDUNG ──────────────────────────────────────────────

def berechne_voranmeldung(df: pd.DataFrame, quartal: int, jahr: int) -> dict | None:
    """
    Berechnet die Werte für die USt-Voranmeldung (Formular USt 1 A) eines Quartals.

    Basis: Rechnungsdatum (Sollversteuerung)
    Vorsteuer: nur aus Sphären C (90%) und D (100%), nicht A (§15 Abs. 2 UStG)

    Gibt dict mit Elster-Zeilennummern zurück oder None wenn keine Buchungen.
    """
    df = df.copy()

    # Filter: Quartal + Jahr nach Rechnungsdatum
    mask = (
        (df['Rechnungsdatum'].dt.year == jahr) &
        (df['Rechnungsdatum'].dt.quarter == quartal)
    )
    df_q = df[mask].copy()

    if df_q.empty:
        return None

    einnahmen = df_q[df_q['Typ'] == 'Einnahme'].copy()
    ausgaben = df_q[df_q['Typ'] == 'Ausgabe'].copy()

    # === Umsätze (Einnahmenseite) ===

    # 0%-Umsätze: Brutto == Netto (keine MwSt enthalten)
    einnahmen_0 = einnahmen[
        einnahmen['Brutto-Betrag'].round(2) == einnahmen['Summe Netto'].round(2)
    ]
    einnahmen_besteuert = einnahmen.drop(einnahmen_0.index)

    netto_19 = einnahmen_besteuert['Netto-Betrag 19% MwSt'].sum()
    netto_7 = einnahmen_besteuert['Netto-Betrag 7% MwSt'].sum()
    netto_andere = einnahmen_besteuert['Netto-Betrag anderer MwSt Satz'].sum()
    netto_0 = einnahmen_0['Summe Netto'].sum()

    # === Vorsteuer (Ausgabenseite) ===
    # Nur C und D – A ist nicht vorsteuerabzugsberechtigt (§15 Abs. 2 UStG)

    def berechne_vorsteuer(df_bereich: pd.DataFrame, abschlag: float = 1.0) -> float:
        """Vorsteuer = Brutto - Summe Netto, mit optionalem Abschlag."""
        df_b = df_bereich[df_bereich['Sphäre'].isin(['C', 'D'])].copy()
        brutto = df_b['Brutto-Betrag'].sum()
        netto = df_b['Summe Netto'].sum()
        steuer = abs(brutto) - abs(netto)  # beide negativ nach Vorzeichenumwandlung
        return steuer * abschlag

    ausgaben_c = ausgaben[ausgaben['Sphäre'] == 'C']
    ausgaben_d = ausgaben[ausgaben['Sphäre'] == 'D']

    vorsteuer_c = berechne_vorsteuer(ausgaben_c, abschlag=VORSTEUER_ABSCHLAG_C)
    vorsteuer_d = berechne_vorsteuer(ausgaben_d, abschlag=1.0)
    vorsteuer_gesamt = vorsteuer_c + vorsteuer_d

    # === Interne Zahllast (Kontrollrechnung) ===
    brutto_einnahmen = einnahmen_besteuert['Brutto-Betrag'].sum()
    netto_einnahmen = einnahmen_besteuert['Summe Netto'].sum()
    eingenommene_ust = brutto_einnahmen - netto_einnahmen
    zahllast = eingenommene_ust - vorsteuer_gesamt

    return {
        'zeitraum': f'Q{quartal} {jahr}',
        'zeile_13_netto_19': round(netto_19, 2),
        'zeile_14_netto_7': round(netto_7, 2),
        'zeile_15_netto_0': round(netto_0, 2),
        'zeile_16_netto_andere': round(netto_andere, 2),
        'zeile_38_vorsteuer': round(vorsteuer_gesamt, 2),
        'zahllast_kontrolle': round(zahllast, 2),
    }


# ── 4. EÜR ───────────────────────────────────────────────────────────────────

def berechne_eur(df: pd.DataFrame, jahr: int) -> dict | None:
    """
    Einnahmenüberschussrechnung (Anlage EÜR) für ein Kalenderjahr.

    Basis: Überweisungsdatum (Ist-Versteuerung / Zufluss-Abfluss-Prinzip)
    Nur GVs mit vorhandenem Überweisungsdatum werden berücksichtigt.

    Gibt dict mit EÜR-Werten aufgeteilt nach Sphären zurück.
    """
    df = df.copy()

    # Nur GVs mit Überweisungsdatum im Zieljahr
    mask = (
        df['Überweisungsdatum'].notna() &
        (df['Überweisungsdatum'].dt.year == jahr)
    )
    df_jahr = df[mask].copy()

    if df_jahr.empty:
        return None

    # Anzahl ausgeschlossener GVs (kein Überweisungsdatum)
    gesamt_im_rechnungsjahr = df[df['Rechnungsdatum'].dt.year == jahr].shape[0]
    ohne_ueberweisung = gesamt_im_rechnungsjahr - df_jahr.shape[0]

    einnahmen = df_jahr[df_jahr['Typ'] == 'Einnahme']
    ausgaben = df_jahr[df_jahr['Typ'] == 'Ausgabe']

    # === Betriebseinnahmen Sphäre D (steuerpflichtig) ===
    ein_d = einnahmen[einnahmen['Sphäre'] == 'D']
    netto_ein_d = ein_d['Summe Netto'].sum()
    ust_ein_d = (ein_d['Brutto-Betrag'] - ein_d['Summe Netto']).sum()

    # === Sonstige Einnahmen (A + C – nicht steuerbar / steuerfrei) ===
    ein_ac = einnahmen[einnahmen['Sphäre'].isin(['A', 'C'])]
    netto_ein_ac = ein_ac['Summe Netto'].sum()

    # === Betriebsausgaben Sphäre D ===
    aus_d = ausgaben[ausgaben['Sphäre'] == 'D']
    netto_aus_d = abs(aus_d['Summe Netto'].sum())
    vorsteuer_d = abs((aus_d['Brutto-Betrag'] - aus_d['Summe Netto']).sum())

    # === Ausgaben A + C (nicht steuerrelevant für EÜR, aber zur Vollständigkeit) ===
    aus_ac = ausgaben[ausgaben['Sphäre'].isin(['A', 'C'])]
    netto_aus_ac = abs(aus_ac['Summe Netto'].sum())

    # === Gewinn / Verlust Sphäre D ===
    gewinn_d = netto_ein_d - netto_aus_d

    return {
        'jahr': jahr,
        'ohne_ueberweisung_ausgeschlossen': ohne_ueberweisung,
        # Einnahmen
        'zeile_15_betriebseinnahmen_netto': round(netto_ein_d, 2),
        'zeile_17_vereinnahmte_ust': round(ust_ein_d, 2),
        'zeile_21_steuerfreie_einnahmen': round(netto_ein_ac, 2),
        # Ausgaben
        'zeile_46_betriebsausgaben_netto': round(netto_aus_d, 2),
        'zeile_48_vorsteuer': round(vorsteuer_d, 2),
        # Zusatz (intern)
        'ausgaben_ac_intern': round(netto_aus_ac, 2),
        # Ergebnis
        'gewinn_verlust_d': round(gewinn_d, 2),
        # Summen
        'summe_betriebseinnahmen': round(netto_ein_d + ust_ein_d, 2),
        'summe_betriebsausgaben': round(netto_aus_d + vorsteuer_d, 2),
    }


# ── 5. UST-JAHRESERKLÄRUNG ────────────────────────────────────────────────────

def berechne_ust_jahres(
    df: pd.DataFrame,
    jahr: int,
    vorauszahlungen: dict[int, float]
) -> dict | None:
    """
    Umsatzsteuer-Jahreserklärung für ein Kalenderjahr.

    vorauszahlungen: {1: float, 2: float, 3: float, 4: float}
        Positive Werte = Zahlung ans Finanzamt
        Negative Werte = Rückzahlung vom Finanzamt

    Gibt Jahreswerte und Saldierung gegen Vorauszahlungen zurück.
    """
    # Alle vier Quartale berechnen
    quartale = {}
    for q in [1, 2, 3, 4]:
        ergebnis = berechne_voranmeldung(df, quartal=q, jahr=jahr)
        quartale[q] = ergebnis

    verfuegbare_quartale = [q for q, e in quartale.items() if e is not None]
    if not verfuegbare_quartale:
        return None

    # Jahressummen aggregieren
    felder = [
        'zeile_13_netto_19', 'zeile_14_netto_7', 'zeile_15_netto_0',
        'zeile_16_netto_andere', 'zeile_38_vorsteuer', 'zahllast_kontrolle'
    ]

    jahreswerte = {}
    for feld in felder:
        jahreswerte[feld] = sum(
            quartale[q][feld] for q in verfuegbare_quartale
        )

    # Vorauszahlungen saldieren
    summe_vorauszahlungen = sum(vorauszahlungen.values())
    nachzahlung = round(jahreswerte['zahllast_kontrolle'] - summe_vorauszahlungen, 2)

    return {
        'jahr': jahr,
        'verfuegbare_quartale': verfuegbare_quartale,
        'quartalsergebnisse': quartale,
        **{k: round(v, 2) for k, v in jahreswerte.items()},
        'summe_vorauszahlungen': round(summe_vorauszahlungen, 2),
        'nachzahlung_erstattung': nachzahlung,  # positiv = Nachzahlung, negativ = Erstattung
    }


# ── 6. KÖRPERSCHAFT- & GEWERBESTEUER ─────────────────────────────────────────

def berechne_kst_gewst(eur_ergebnis: dict, jahr: int) -> dict:
    """
    Körperschaft- und Gewerbesteuerberechnung basierend auf EÜR-Ergebnis.

    Logik:
    1. Brutto-Einnahmen D über Freigrenze? → sonst Nullmeldung
    2. Gewinn D über Freibetrag (5.000 €)? → sonst Nullmeldung
    3. KSt = (Gewinn - 5.000) * 15% + SolZ
    4. GewSt = (Gewinn - 5.000) * 3,5% * Hebesatz
    """
    grenze = freigrenze(jahr)
    gewinn = eur_ergebnis['gewinn_verlust_d']
    brutto_einnahmen_d = eur_ergebnis['summe_betriebseinnahmen']

    # Stufe 1: Freigrenze
    if brutto_einnahmen_d <= grenze:
        return {
            'jahr': jahr,
            'steuerpflichtig': False,
            'grund': f'Brutto-Einnahmen D ({brutto_einnahmen_d:,.2f} €) '
                     f'unter Freigrenze ({grenze:,.0f} €) – Nullmeldung',
            'kst': 0.0,
            'solz': 0.0,
            'gewst': 0.0,
        }

    # Stufe 2: Freibetrag auf den Gewinn
    zu_versteuern = gewinn - FREIBETRAG_D

    if zu_versteuern <= 0:
        return {
            'jahr': jahr,
            'steuerpflichtig': False,
            'grund': f'Freigrenze überschritten, aber Gewinn D ({gewinn:,.2f} €) '
                     f'nach Freibetrag (5.000 €) nicht positiv – Nullmeldung',
            'kst': 0.0,
            'solz': 0.0,
            'gewst': 0.0,
        }

    # Stufe 3: Steuerberechnung
    kst = round(zu_versteuern * KST_SATZ, 2)
    solz = round(kst * SOLZ_SATZ, 2)
    gewst = round(zu_versteuern * GEWST_MESSZAHL * GEWST_HEBESATZ, 2)

    return {
        'jahr': jahr,
        'steuerpflichtig': True,
        'brutto_einnahmen_d': round(brutto_einnahmen_d, 2),
        'gewinn_d': round(gewinn, 2),
        'freibetrag': FREIBETRAG_D,
        'zu_versteuernder_gewinn': round(zu_versteuern, 2),
        'kst': kst,
        'solz': solz,
        'kst_gesamt': round(kst + solz, 2),
        'gewst_messbetrag': round(zu_versteuern * GEWST_MESSZAHL, 2),
        'gewst_hebesatz_prozent': int(GEWST_HEBESATZ * 100),
        'gewst': gewst,
        'steuer_gesamt': round(kst + solz + gewst, 2),
    }
