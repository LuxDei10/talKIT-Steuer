# -*- coding: utf-8 -*-
"""
export.py – talKIT Steuermodul
Erzeugt strukturierte PDF-Ausgaben für das Ausfüllen der Elster-Formulare.
"""

from datetime import date
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
import io

# ── DESIGN-TOKENS ─────────────────────────────────────────────────────────────

FARBE_DUNKEL    = colors.HexColor('#1A1A2E')   # Tiefes Nachtblau – Überschriften
FARBE_AKZENT    = colors.HexColor('#4A90D9')   # Klares Blau – Hervorhebungen
FARBE_HELL      = colors.HexColor('#F5F7FA')   # Helles Grau – Tabellenhintergrund
FARBE_WEISS     = colors.white
FARBE_LINIE     = colors.HexColor('#D0D7E3')   # Dezente Trennlinie
FARBE_WARNUNG   = colors.HexColor('#E8A020')   # Amber – Hinweise
FARBE_FEHLER    = colors.HexColor('#D64045')   # Rot – Fehler/Nullmeldung
FARBE_OK        = colors.HexColor('#2E7D52')   # Grün – positive Aussagen

SEITENBREITE = A4[0] - 30*mm  # Nutzbare Breite


def _erstelle_styles():
    styles = getSampleStyleSheet()

    titel = ParagraphStyle(
        'TalKITTitel',
        fontName='Helvetica-Bold',
        fontSize=18,
        textColor=FARBE_DUNKEL,
        spaceAfter=2*mm,
    )
    untertitel = ParagraphStyle(
        'TalKITUntertitel',
        fontName='Helvetica',
        fontSize=10,
        textColor=colors.HexColor('#666688'),
        spaceAfter=6*mm,
    )
    abschnitt = ParagraphStyle(
        'TalKITAbschnitt',
        fontName='Helvetica-Bold',
        fontSize=11,
        textColor=FARBE_AKZENT,
        spaceBefore=6*mm,
        spaceAfter=2*mm,
    )
    formular_label = ParagraphStyle(
        'TalKITFormularLabel',
        fontName='Helvetica',
        fontSize=8,
        textColor=colors.HexColor('#888888'),
        spaceAfter=0,
    )
    normal = ParagraphStyle(
        'TalKITNormal',
        fontName='Helvetica',
        fontSize=9,
        textColor=FARBE_DUNKEL,
        spaceAfter=2*mm,
    )
    hinweis = ParagraphStyle(
        'TalKITHinweis',
        fontName='Helvetica-Oblique',
        fontSize=8,
        textColor=colors.HexColor('#666666'),
        spaceAfter=2*mm,
    )
    return {
        'titel': titel,
        'untertitel': untertitel,
        'abschnitt': abschnitt,
        'formular_label': formular_label,
        'normal': normal,
        'hinweis': hinweis,
    }


def _zeilen_tabelle(zeilen: list[tuple], styles: dict) -> Table:
    """
    Erstellt eine zweispaltige Elster-Zeilentabelle.
    zeilen: [(bezeichnung, wert_str), ...]  oder  [(bezeichnung, wert_str, zeilen_nr), ...]
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
            Paragraph(f'<b>{wert}</b>', ParagraphStyle(
                'Wert', fontName='Helvetica-Bold', fontSize=9,
                textColor=FARBE_DUNKEL, alignment=TA_RIGHT
            ))
        ])

    col_breiten = [SEITENBREITE * 0.72, SEITENBREITE * 0.28]
    t = Table(data, colWidths=col_breiten)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), FARBE_HELL),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [FARBE_WEISS, FARBE_HELL]),
        ('GRID', (0, 0), (-1, -1), 0.3, FARBE_LINIE),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    return t


def _kopfzeile(elemente, zeitraum: str, formular: str, styles: dict):
    """Einheitliche Kopfzeile für jeden Abschnitt."""
    elemente.append(HRFlowable(
        width=SEITENBREITE, thickness=2, color=FARBE_AKZENT, spaceAfter=3*mm
    ))
    elemente.append(Paragraph(formular, styles['abschnitt']))
    elemente.append(Paragraph(
        f'Zeitraum: <b>{zeitraum}</b> &nbsp;|&nbsp; '
        f'Erstellt: {date.today().strftime("%d.%m.%Y")}',
        styles['hinweis']
    ))


def exportiere_voranmeldung(ergebnis: dict) -> bytes:
    """Erzeugt PDF für USt-Voranmeldung. Gibt Bytes zurück."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=15*mm, bottomMargin=15*mm
    )
    styles = _erstelle_styles()
    elemente = []

    # Kopf
    elemente.append(Paragraph('talKIT e.V.', styles['titel']))
    elemente.append(Paragraph(
        f'Steuermodul · Umsatzsteuer-Voranmeldung · {ergebnis["zeitraum"]}',
        styles['untertitel']
    ))

    _kopfzeile(elemente, ergebnis['zeitraum'], 'Formular USt 1 A', styles)

    zeilen = [
        ('Steuerpflichtige Umsätze 19 %', f'{ergebnis["zeile_13_netto_19"]:,.2f} €', 13),
        ('Steuerpflichtige Umsätze 7 %', f'{ergebnis["zeile_14_netto_7"]:,.2f} €', 14),
        ('Steuerfreie / nicht steuerbare Umsätze (0 %)', f'{ergebnis["zeile_15_netto_0"]:,.2f} €', 15),
        ('Umsätze zu anderen Steuersätzen', f'{ergebnis["zeile_16_netto_andere"]:,.2f} €', 16),
        ('Abziehbare Vorsteuerbeträge', f'{ergebnis["zeile_38_vorsteuer"]:,.2f} €', 38),
    ]
    elemente.append(_zeilen_tabelle(zeilen, styles))

    # Interne Zahllast
    elemente.append(Spacer(1, 4*mm))
    zahllast = ergebnis['zahllast_kontrolle']
    farbe = FARBE_FEHLER if zahllast > 0 else FARBE_OK
    elemente.append(Paragraph(
        f'<b>Interne Zahllast (Kontrolle):</b> '
        f'<font color="{farbe.hexval()}">{zahllast:,.2f} €</font><br/>'
        '<font size="8">Dieser Wert dient der internen Kontrolle. '
        'Positiv = Zahlung ans Finanzamt, Negativ = Erstattung.</font>',
        styles['normal']
    ))

    doc.build(elemente)
    return buffer.getvalue()


def exportiere_jahressteuer(
    eur: dict,
    ust: dict,
    kst_gewst: dict,
) -> bytes:
    """Erzeugt PDF für die Jahressteuererklärung (EÜR + USt + KSt/GewSt)."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=15*mm, bottomMargin=15*mm
    )
    styles = _erstelle_styles()
    elemente = []
    jahr = eur['jahr']

    # Kopf
    elemente.append(Paragraph('talKIT e.V.', styles['titel']))
    elemente.append(Paragraph(
        f'Steuermodul · Jahressteuererklärung · {jahr}',
        styles['untertitel']
    ))

    # ── EÜR ──
    _kopfzeile(elemente, str(jahr), 'Anlage EÜR – Einnahmenüberschussrechnung', styles)

    if eur.get('ohne_ueberweisung_ausgeschlossen', 0) > 0:
        elemente.append(Paragraph(
            f'ℹ️ {eur["ohne_ueberweisung_ausgeschlossen"]} GV(s) ohne Überweisungsdatum '
            f'wurden nicht berücksichtigt.',
            styles['hinweis']
        ))

    elemente.append(Paragraph('Betriebseinnahmen (Sphäre D)', styles['formular_label']))
    elemente.append(_zeilen_tabelle([
        ('Steuerpflichtige Betriebseinnahmen (Netto)', f'{eur["zeile_15_betriebseinnahmen_netto"]:,.2f} €', 15),
        ('Vereinnahmte Umsatzsteuer', f'{eur["zeile_17_vereinnahmte_ust"]:,.2f} €', 17),
        ('Steuerfreie / nicht steuerbare Einnahmen (A+C)', f'{eur["zeile_21_steuerfreie_einnahmen"]:,.2f} €', 21),
    ], styles))

    elemente.append(Spacer(1, 2*mm))
    elemente.append(Paragraph('Betriebsausgaben (Sphäre D)', styles['formular_label']))
    elemente.append(_zeilen_tabelle([
        ('Sonstige Betriebsausgaben (Netto)', f'{eur["zeile_46_betriebsausgaben_netto"]:,.2f} €', 46),
        ('Gezahlte Vorsteuerbeträge', f'{eur["zeile_48_vorsteuer"]:,.2f} €', 48),
    ], styles))

    elemente.append(Spacer(1, 2*mm))
    gewinn = eur['gewinn_verlust_d']
    farbe = FARBE_OK if gewinn >= 0 else FARBE_AKZENT
    elemente.append(Paragraph(
        f'<b>Gewinn / Verlust Sphäre D (Zeile 75):</b> '
        f'<font color="{farbe.hexval()}">{gewinn:,.2f} €</font>',
        styles['normal']
    ))

    # ── USt Jahreserklärung ──
    elemente.append(Spacer(1, 4*mm))
    _kopfzeile(elemente, str(jahr), 'Umsatzsteuer-Jahreserklärung (USt 2)', styles)

    zeilen_ust = [
        ('Netto-Umsatz 19 %', f'{ust["zeile_13_netto_19"]:,.2f} €', 13),
        ('Netto-Umsatz 7 %', f'{ust["zeile_14_netto_7"]:,.2f} €', 14),
        ('Umsätze 0 %', f'{ust["zeile_15_netto_0"]:,.2f} €', 15),
        ('Umsätze andere Steuersätze', f'{ust["zeile_16_netto_andere"]:,.2f} €', 16),
        ('Abziehbare Vorsteuer gesamt', f'{ust["zeile_38_vorsteuer"]:,.2f} €', 38),
    ]
    elemente.append(_zeilen_tabelle(zeilen_ust, styles))

    elemente.append(Spacer(1, 2*mm))
    # Quartalskontrolle
    elemente.append(Paragraph('Abgleich Vorauszahlungen', styles['formular_label']))
    vz_data = [['Quartal', 'Zahllast berechnet', 'Vorauszahlung geleistet', 'Differenz']]
    for q in [1, 2, 3, 4]:
        q_ergebnis = ust['quartalsergebnisse'].get(q)
        if q_ergebnis:
            zahllast = q_ergebnis['zahllast_kontrolle']
            vz = ust.get(f'vz_q{q}', 0.0)  # aus Vorauszahlungen-Dict
            diff = zahllast - vz
            vz_data.append([
                f'Q{q}',
                f'{zahllast:,.2f} €',
                f'{vz:,.2f} €',
                f'{diff:,.2f} €',
            ])
        else:
            vz_data.append([f'Q{q}', '–', '–', '–'])

    # Summenzeile
    vz_data.append([
        'Gesamt',
        f'{ust["zahllast_kontrolle"]:,.2f} €',
        f'{ust["summe_vorauszahlungen"]:,.2f} €',
        f'{ust["nachzahlung_erstattung"]:,.2f} €',
    ])

    col_b = [SEITENBREITE * 0.15, SEITENBREITE * 0.28,
             SEITENBREITE * 0.28, SEITENBREITE * 0.29]
    vz_tabelle = Table(vz_data, colWidths=col_b)
    vz_tabelle.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), FARBE_DUNKEL),
        ('TEXTCOLOR', (0, 0), (-1, 0), FARBE_WEISS),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [FARBE_WEISS, FARBE_HELL]),
        ('BACKGROUND', (0, -1), (-1, -1), FARBE_HELL),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.3, FARBE_LINIE),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elemente.append(vz_tabelle)

    nachz = ust['nachzahlung_erstattung']
    if nachz > 0:
        elemente.append(Paragraph(
            f'⚠️ Nachzahlung fällig: <b>{nachz:,.2f} €</b>', styles['normal']
        ))
    elif nachz < 0:
        elemente.append(Paragraph(
            f'✅ Erstattung zu erwarten: <b>{abs(nachz):,.2f} €</b>', styles['normal']
        ))

    # ── KSt + GewSt ──
    elemente.append(Spacer(1, 4*mm))
    _kopfzeile(
        elemente, str(jahr),
        'Körperschaftsteuer (KSt 1) & Gewerbesteuererklärung (GewSt 1 B)',
        styles
    )

    if not kst_gewst['steuerpflichtig']:
        elemente.append(Paragraph(
            f'✅ Nullmeldung: {kst_gewst["grund"]}',
            ParagraphStyle('Null', fontName='Helvetica', fontSize=9,
                           textColor=FARBE_OK, spaceAfter=2*mm)
        ))
    else:
        elemente.append(_zeilen_tabelle([
            ('Brutto-Einnahmen wirtsch. GB (D)', f'{kst_gewst["brutto_einnahmen_d"]:,.2f} €'),
            ('Gewinn wirtsch. GB (D)', f'{kst_gewst["gewinn_d"]:,.2f} €'),
            ('Freibetrag', f'{kst_gewst["freibetrag"]:,.2f} €'),
            ('Zu versteuernder Gewinn', f'{kst_gewst["zu_versteuernder_gewinn"]:,.2f} €'),
        ], styles))

        elemente.append(Spacer(1, 2*mm))
        elemente.append(Paragraph('Körperschaftsteuer', styles['formular_label']))
        elemente.append(_zeilen_tabelle([
            ('Körperschaftsteuer (15 %)', f'{kst_gewst["kst"]:,.2f} €'),
            ('Solidaritätszuschlag (5,5 % auf KSt)', f'{kst_gewst["solz"]:,.2f} €'),
            ('KSt gesamt', f'{kst_gewst["kst_gesamt"]:,.2f} €'),
        ], styles))

        elemente.append(Spacer(1, 2*mm))
        elemente.append(Paragraph('Gewerbesteuer', styles['formular_label']))
        elemente.append(_zeilen_tabelle([
            ('Gewerbeertrag (Steuermessbetrag × 3,5 %)', f'{kst_gewst["gewst_messbetrag"]:,.2f} €'),
            (f'Gewerbesteuer (Hebesatz {kst_gewst["gewst_hebesatz_prozent"]} %)', f'{kst_gewst["gewst"]:,.2f} €'),
        ], styles))

        elemente.append(Spacer(1, 2*mm))
        elemente.append(Paragraph(
            f'<b>Steuerbelastung gesamt: {kst_gewst["steuer_gesamt"]:,.2f} €</b>',
            styles['normal']
        ))

    doc.build(elemente)
    return buffer.getvalue()
