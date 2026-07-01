# -*- coding: utf-8 -*-
"""
export.py – talKIT Steuermodul
Erzeugt strukturierte PDF-Ausgaben für das Ausfüllen der Elster-Formulare.
"""

from datetime import date
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image
)
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
import io

# ── DESIGN-TOKENS ─────────────────────────────────────────────────────────────

FARBE_DUNKEL  = colors.HexColor('#1A1A2E')
FARBE_AKZENT  = colors.HexColor('#4A90D9')
FARBE_HELL    = colors.HexColor('#F5F7FA')
FARBE_WEISS   = colors.white
FARBE_LINIE   = colors.HexColor('#D0D7E3')
FARBE_WARNUNG = colors.HexColor('#E8A020')
FARBE_FEHLER  = colors.HexColor('#D64045')
FARBE_OK      = colors.HexColor('#2E7D52')

SEITENBREITE  = A4[0] - 30*mm   # nutzbare Breite bei je 15 mm Rand

# Padding-Konstanten – zentral definiert für konsistenten Abstand
PAD_ZELLE_V = 5    # vertikales Padding in Tabellenzellen (pt)
PAD_ZELLE_H = 6    # horizontales Padding in Tabellenzellen (pt)


def _logo_element() -> Image | None:
    """Gibt ein ReportLab-Image-Objekt für das talKIT-Logo zurück, oder None."""
    for pfad in ['talKITlogogruen.png', 'assets/talKITlogogruen.png']:
        p = Path(pfad)
        if p.exists():
            # Originalgröße: 1722 × 510 px → auf 40 mm Höhe skalieren
            hoehe = 10 * mm
            breite = hoehe * (1722 / 510)
            return Image(str(p), width=breite, height=hoehe)
    return None


def _erstelle_styles() -> dict:
    styles = getSampleStyleSheet()

    return {
        'verein': ParagraphStyle(
            'TKVerein',
            fontName='Helvetica',
            fontSize=9,
            textColor=colors.HexColor('#666688'),
            spaceAfter=1 * mm,
        ),
        'titel': ParagraphStyle(
            'TKTitel',
            fontName='Helvetica-Bold',
            fontSize=16,
            textColor=FARBE_DUNKEL,
            spaceAfter=1 * mm,
        ),
        'untertitel': ParagraphStyle(
            'TKUntertitel',
            fontName='Helvetica',
            fontSize=9,
            textColor=colors.HexColor('#666688'),
            spaceAfter=5 * mm,
        ),
        'abschnitt': ParagraphStyle(
            'TKAbschnitt',
            fontName='Helvetica-Bold',
            fontSize=11,
            textColor=FARBE_AKZENT,
            spaceBefore=7 * mm,
            spaceAfter=2 * mm,
        ),
        'label': ParagraphStyle(
            'TKLabel',
            fontName='Helvetica-Oblique',
            fontSize=8,
            textColor=colors.HexColor('#888888'),
            spaceBefore=4 * mm,
            spaceAfter=1 * mm,
        ),
        'normal': ParagraphStyle(
            'TKNormal',
            fontName='Helvetica',
            fontSize=9,
            textColor=FARBE_DUNKEL,
            spaceAfter=3 * mm,
            leading=13,
        ),
        'hinweis': ParagraphStyle(
            'TKHinweis',
            fontName='Helvetica-Oblique',
            fontSize=8,
            textColor=colors.HexColor('#666666'),
            spaceAfter=3 * mm,
            leading=12,
        ),
        'wert': ParagraphStyle(
            'TKWert',
            fontName='Helvetica-Bold',
            fontSize=9,
            textColor=FARBE_DUNKEL,
            alignment=TA_RIGHT,
        ),
    }


def _pdf_header(elemente: list, zeitraum: str, dokument: str, styles: dict):
    """
    Einheitlicher Seitenkopf: Logo (falls vorhanden) + Titel + Metazeile.
    Wird einmal pro PDF-Dokument aufgerufen.
    """
    logo = _logo_element()
    if logo:
        elemente.append(logo)
        elemente.append(Spacer(1, 3 * mm))
    else:
        elemente.append(Paragraph('talKIT e.V.', styles['verein']))

    elemente.append(Paragraph(dokument, styles['titel']))
    elemente.append(Paragraph(
        f'Zeitraum: <b>{zeitraum}</b> &nbsp;·&nbsp; '
        f'Erstellt am: {date.today().strftime("%d.%m.%Y")}',
        styles['untertitel']
    ))
    elemente.append(HRFlowable(
        width=SEITENBREITE, thickness=1.5, color=FARBE_AKZENT,
        spaceAfter=4 * mm
    ))


def _abschnitt_trenner(elemente: list, titel: str, styles: dict):
    """Abschnittsüberschrift mit leichter Trennlinie davor."""
    elemente.append(HRFlowable(
        width=SEITENBREITE, thickness=0.5, color=FARBE_LINIE,
        spaceBefore=5 * mm, spaceAfter=0
    ))
    elemente.append(Paragraph(titel, styles['abschnitt']))


def _zeilen_tabelle(zeilen: list[tuple], styles: dict) -> Table:
    """
    Zweispaltige Elster-Zeilentabelle.
    zeilen: (bezeichnung, wert_str)  oder  (bezeichnung, wert_str, zeilen_nr)
    """
    data = []
    for zeile in zeilen:
        if len(zeile) == 3:
            bezeichnung, wert, nr = zeile
            label = f'Zeile {nr} – {bezeichnung}'
        else:
            bezeichnung, wert = zeile
            label = bezeichnung

        data.append([
            Paragraph(label, styles['normal']),
            Paragraph(f'<b>{wert}</b>', styles['wert']),
        ])

    col_b = [SEITENBREITE * 0.72, SEITENBREITE * 0.28]
    t = Table(data, colWidths=col_b)
    t.setStyle(TableStyle([
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [FARBE_WEISS, FARBE_HELL]),
        ('GRID', (0, 0), (-1, -1), 0.3, FARBE_LINIE),
        ('LEFTPADDING',   (0, 0), (-1, -1), PAD_ZELLE_H),
        ('RIGHTPADDING',  (0, 0), (-1, -1), PAD_ZELLE_H),
        ('TOPPADDING',    (0, 0), (-1, -1), PAD_ZELLE_V),
        ('BOTTOMPADDING', (0, 0), (-1, -1), PAD_ZELLE_V),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    return t


# ── EXPORT: VORANMELDUNG ──────────────────────────────────────────────────────

def exportiere_voranmeldung(ergebnis: dict) -> bytes:
    """Erzeugt PDF für die USt-Voranmeldung eines Quartals."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=15*mm, bottomMargin=15*mm
    )
    styles = _erstelle_styles()
    e = []

    _pdf_header(
        e,
        zeitraum=ergebnis['zeitraum'],
        dokument=f'Umsatzsteuer-Voranmeldung {ergebnis["zeitraum"]}',
        styles=styles
    )

    e.append(Paragraph('Formular USt 1 A', styles['label']))
    e.append(_zeilen_tabelle([
        ('Steuerpflichtige Umsätze 19 %',
         f'{ergebnis["zeile_13_netto_19"]:,.2f} €', 13),
        ('Steuerpflichtige Umsätze 7 %',
         f'{ergebnis["zeile_14_netto_7"]:,.2f} €', 14),
        ('Steuerfreie / nicht steuerbare Umsätze',
         f'{ergebnis["zeile_15_netto_0"]:,.2f} €', 15),
        ('Umsätze zu anderen Steuersätzen',
         f'{ergebnis["zeile_16_netto_andere"]:,.2f} €', 16),
        ('Abziehbare Vorsteuerbeträge',
         f'{ergebnis["zeile_38_vorsteuer"]:,.2f} €', 38),
    ], styles))

    e.append(Spacer(1, 5 * mm))

    zahllast = ergebnis['zahllast_kontrolle']
    farbe = FARBE_FEHLER if zahllast > 0 else FARBE_OK
    richtung = 'Zahlung ans Finanzamt' if zahllast > 0 else 'Erstattung vom Finanzamt'
    e.append(Paragraph(
        f'<b>Interne Zahllast (Kontrolle):</b> '
        f'<font color="{farbe.hexval()}">{zahllast:,.2f} €</font> – {richtung}',
        styles['normal']
    ))
    e.append(Paragraph(
        'Dieser Wert dient der internen Plausibilitätskontrolle. '
        'Maßgeblich für Elster sind ausschließlich die Zeilen 13–38.',
        styles['hinweis']
    ))

    doc.build(e)
    return buffer.getvalue()


# ── EXPORT: JAHRESSTEUER ──────────────────────────────────────────────────────

def exportiere_jahressteuer(eur: dict, ust: dict, kst_gewst: dict) -> bytes:
    """Erzeugt PDF für die vollständige Jahressteuererklärung."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=15*mm, bottomMargin=15*mm
    )
    styles = _erstelle_styles()
    e = []
    jahr = eur['jahr']

    _pdf_header(
        e,
        zeitraum=str(jahr),
        dokument=f'Jahressteuererklärung {jahr}',
        styles=styles
    )

    # ── EÜR ──────────────────────────────────────────────────────────────────
    _abschnitt_trenner(e, 'Anlage EÜR – Einnahmenüberschussrechnung', styles)

    if eur.get('ohne_ueberweisung_ausgeschlossen', 0) > 0:
        e.append(Paragraph(
            f'Hinweis: {eur["ohne_ueberweisung_ausgeschlossen"]} GV(s) ohne '
            f'Überweisungsdatum wurden nicht berücksichtigt.',
            styles['hinweis']
        ))

    e.append(Paragraph('Betriebseinnahmen – wirtschaftlicher Geschäftsbetrieb (D)',
                       styles['label']))
    e.append(_zeilen_tabelle([
        ('Steuerpflichtige Betriebseinnahmen (Netto)',
         f'{eur["zeile_15_betriebseinnahmen_netto"]:,.2f} €', 15),
        ('Vereinnahmte Umsatzsteuer',
         f'{eur["zeile_17_vereinnahmte_ust"]:,.2f} €', 17),
        ('Steuerfreie / nicht steuerbare Einnahmen (Sphären A+C)',
         f'{eur["zeile_21_steuerfreie_einnahmen"]:,.2f} €', 21),
    ], styles))

    e.append(Spacer(1, 3 * mm))
    e.append(Paragraph('Betriebsausgaben – wirtschaftlicher Geschäftsbetrieb (D)',
                       styles['label']))
    e.append(_zeilen_tabelle([
        ('Sonstige Betriebsausgaben (Netto)',
         f'{eur["zeile_46_betriebsausgaben_netto"]:,.2f} €', 46),
        ('Gezahlte Vorsteuerbeträge',
         f'{eur["zeile_48_vorsteuer"]:,.2f} €', 48),
    ], styles))

    e.append(Spacer(1, 4 * mm))
    gewinn = eur['gewinn_verlust_d']
    farbe_g = FARBE_OK if gewinn >= 0 else FARBE_FEHLER
    e.append(Paragraph(
        f'<b>Gewinn / Verlust Sphäre D (Zeile 75):</b> '
        f'<font color="{farbe_g.hexval()}">{gewinn:,.2f} €</font>',
        styles['normal']
    ))

    # ── USt Jahreserklärung ───────────────────────────────────────────────────
    _abschnitt_trenner(e, 'Umsatzsteuer-Jahreserklärung (USt 2)', styles)

    e.append(Paragraph('Jahressummen – Basis Rechnungsdatum', styles['label']))
    e.append(_zeilen_tabelle([
        ('Netto-Umsatz 19 %',
         f'{ust["zeile_13_netto_19"]:,.2f} €', 13),
        ('Netto-Umsatz 7 %',
         f'{ust["zeile_14_netto_7"]:,.2f} €', 14),
        ('Umsätze 0 %',
         f'{ust["zeile_15_netto_0"]:,.2f} €', 15),
        ('Umsätze andere Steuersätze',
         f'{ust["zeile_16_netto_andere"]:,.2f} €', 16),
        ('Abziehbare Vorsteuer gesamt',
         f'{ust["zeile_38_vorsteuer"]:,.2f} €', 38),
    ], styles))

    # Quartalskontrolltabelle
    e.append(Spacer(1, 4 * mm))
    e.append(Paragraph('Abgleich Vorauszahlungen', styles['label']))

    header = [['Quartal', 'Daten', 'Zahllast\nberechnet',
               'Vorauszahlung\ngeleistet', 'Differenz']]
    q_rows = []
    for q in [1, 2, 3, 4]:
        q_erg = ust['quartalsergebnisse'].get(q)
        vz = ust.get(f'vz_q{q}', 0.0)
        if q_erg:
            zahllast = q_erg['zahllast_kontrolle']
            q_rows.append([
                f'Q{q}', '✓',
                f'{zahllast:,.2f} €',
                f'{vz:,.2f} €',
                f'{zahllast - vz:,.2f} €',
            ])
        else:
            q_rows.append([f'Q{q}', '–', '0,00 €', f'{vz:,.2f} €',
                           f'{0.0 - vz:,.2f} €'])

    nachz = ust['nachzahlung_erstattung']
    summen_zeile = [
        'Gesamt', '',
        f'{ust["zahllast_kontrolle"]:,.2f} €',
        f'{ust["summe_vorauszahlungen"]:,.2f} €',
        f'{nachz:,.2f} €',
    ]

    col_b = [
        SEITENBREITE * 0.12, SEITENBREITE * 0.08,
        SEITENBREITE * 0.25, SEITENBREITE * 0.28,
        SEITENBREITE * 0.27
    ]
    q_tabelle = Table(header + q_rows + [summen_zeile], colWidths=col_b)
    q_tabelle.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0),  FARBE_DUNKEL),
        ('TEXTCOLOR',     (0, 0), (-1, 0),  FARBE_WEISS),
        ('FONTNAME',      (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, -1), 8),
        ('ROWBACKGROUNDS',(0, 1), (-1, -2), [FARBE_WEISS, FARBE_HELL]),
        ('BACKGROUND',    (0, -1),(-1, -1), FARBE_HELL),
        ('FONTNAME',      (0, -1),(-1, -1), 'Helvetica-Bold'),
        ('GRID',          (0, 0), (-1, -1), 0.3, FARBE_LINIE),
        ('ALIGN',         (1, 0), (-1, -1), 'RIGHT'),
        ('ALIGN',         (0, 0), (0, -1),  'CENTER'),
        ('LEFTPADDING',   (0, 0), (-1, -1), PAD_ZELLE_H),
        ('RIGHTPADDING',  (0, 0), (-1, -1), PAD_ZELLE_H),
        ('TOPPADDING',    (0, 0), (-1, -1), PAD_ZELLE_V),
        ('BOTTOMPADDING', (0, 0), (-1, -1), PAD_ZELLE_V),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    e.append(q_tabelle)

    e.append(Spacer(1, 3 * mm))
    if nachz > 0:
        e.append(Paragraph(
            f'<b>Nachzahlung fällig: {nachz:,.2f} €</b>',
            styles['normal']
        ))
    elif nachz < 0:
        e.append(Paragraph(
            f'<b>Erstattung zu erwarten: {abs(nachz):,.2f} €</b>',
            styles['normal']
        ))
    else:
        e.append(Paragraph(
            'Vorauszahlungen und Jahresschuld sind ausgeglichen.',
            styles['normal']
        ))

    # ── KSt + GewSt ──────────────────────────────────────────────────────────
    _abschnitt_trenner(
        e,
        'Körperschaftsteuer (KSt 1) & Gewerbesteuererklärung (GewSt 1 B)',
        styles
    )
    e.append(Paragraph(
        'Sphäre D – wirtschaftlicher Geschäftsbetrieb', styles['label']
    ))

    if not kst_gewst['steuerpflichtig']:
        e.append(Paragraph(
            f'Nullmeldung: {kst_gewst["grund"]}',
            styles['normal']
        ))
    else:
        e.append(_zeilen_tabelle([
            ('Brutto-Einnahmen wirtsch. Geschäftsbetrieb (D)',
             f'{kst_gewst["brutto_einnahmen_d"]:,.2f} €'),
            ('Gewinn Sphäre D',
             f'{kst_gewst["gewinn_d"]:,.2f} €'),
            ('Freibetrag',
             f'{kst_gewst["freibetrag"]:,.2f} €'),
            ('Zu versteuernder Gewinn',
             f'{kst_gewst["zu_versteuernder_gewinn"]:,.2f} €'),
        ], styles))

        e.append(Spacer(1, 3 * mm))
        e.append(Paragraph('Körperschaftsteuer', styles['label']))
        e.append(_zeilen_tabelle([
            ('Körperschaftsteuer (15 %)',   f'{kst_gewst["kst"]:,.2f} €'),
            ('Solidaritätszuschlag (5,5 %)', f'{kst_gewst["solz"]:,.2f} €'),
            ('KSt gesamt',                  f'{kst_gewst["kst_gesamt"]:,.2f} €'),
        ], styles))

        e.append(Spacer(1, 3 * mm))
        e.append(Paragraph('Gewerbesteuer', styles['label']))
        e.append(_zeilen_tabelle([
            ('Steuermessbetrag (Gewinn × 3,5 %)',
             f'{kst_gewst["gewst_messbetrag"]:,.2f} €'),
            (f'Gewerbesteuer (Hebesatz {kst_gewst["gewst_hebesatz_prozent"]} %)',
             f'{kst_gewst["gewst"]:,.2f} €'),
        ], styles))

        e.append(Spacer(1, 4 * mm))
        e.append(Paragraph(
            f'<b>Steuerbelastung gesamt: {kst_gewst["steuer_gesamt"]:,.2f} €</b>',
            styles['normal']
        ))

    doc.build(e)
    return buffer.getvalue()
