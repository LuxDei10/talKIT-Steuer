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
    HRFlowable, Image, KeepTogether
)
from reportlab.lib.enums import TA_RIGHT
from reportlab.pdfgen import canvas as rl_canvas
import io

# ── DESIGN-TOKENS ─────────────────────────────────────────────────────────────

FARBE_DUNKEL  = colors.HexColor('#1A1A2E')
FARBE_AKZENT  = colors.HexColor('#4A90D9')
FARBE_HELL    = colors.HexColor('#F5F7FA')
FARBE_WEISS   = colors.white
FARBE_LINIE   = colors.HexColor('#D0D7E3')
FARBE_FEHLER  = colors.HexColor('#D64045')
FARBE_OK      = colors.HexColor('#2E7D52')

SEITENBREITE  = A4[0] - 30 * mm   # nutzbare Breite bei je 15 mm Rand
PAD_V         = 5                  # vertikales Zellen-Padding (pt)
PAD_H         = 6                  # horizontales Zellen-Padding (pt)


# ── SEITENNUMMERN ─────────────────────────────────────────────────────────────

class _SeitenNummernCanvas(rl_canvas.Canvas):
    """Canvas-Subklasse: zeichnet 'Seite X von Y' nach dem Build."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seiten = []

    def showPage(self):
        self._seiten.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        gesamt = len(self._seiten)
        for zustand in self._seiten:
            self.__dict__.update(zustand)
            self._zeichne_fusszeile(gesamt)
            super().showPage()
        super().save()

    def _zeichne_fusszeile(self, gesamt: int):
        seite = self._seiten.index(dict(self.__dict__)) + 1 if dict(self.__dict__) in self._seiten else self._pageNumber
        # Aktuelle Seitennummer aus dem Zustand lesen
        seite = self._pageNumber
        self.saveState()
        self.setFont('Helvetica', 7)
        self.setFillColor(colors.HexColor('#999999'))
        text = f'Seite {seite} von {gesamt}'
        self.drawRightString(A4[0] - 15 * mm, 8 * mm, text)
        self.drawString(15 * mm, 8 * mm, 'talKIT e.V. · Steuermodul')
        self.restoreState()


class _SeitenNummernCanvasV2(rl_canvas.Canvas):
    """Zuverlässige Zwei-Pass-Variante für 'Seite X von Y'."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_footer(num_pages)
            rl_canvas.Canvas.showPage(self)
        rl_canvas.Canvas.save(self)

    def _draw_footer(self, total: int):
        page = self._saved_page_states.index(dict(self.__dict__)) + 1
        self.saveState()
        self.setFont('Helvetica', 7)
        self.setFillColor(colors.HexColor('#999999'))
        self.drawRightString(A4[0] - 15 * mm, 8 * mm, f'Seite {page} von {total}')
        self.drawString(15 * mm, 8 * mm, 'talKIT e.V. · Steuermodul')
        self.restoreState()


# ── LOGO ──────────────────────────────────────────────────────────────────────

def _logo_element() -> Image | None:
    """
    Sucht das talKIT-Logo relativ zur export.py-Datei.
    Unterstützt Dateinamen mit und ohne Leerzeichen.
    """
    basis = Path(__file__).parent
    kandidaten = [
        basis / 'talKITlogogruen.png',
        basis / 'talKIT logo gruen.png',
        basis / 'assets' / 'talKITlogogruen.png',
        basis / 'assets' / 'talKIT logo gruen.png',
    ]
    for p in kandidaten:
        if p.exists():
            hoehe = 11 * mm
            breite = hoehe * (1722 / 510)
            return Image(str(p), width=breite, height=hoehe)
    return None


# ── STYLES ────────────────────────────────────────────────────────────────────

def _erstelle_styles() -> dict:
    return {
        'verein': ParagraphStyle(
            'TKVerein', fontName='Helvetica', fontSize=9,
            textColor=colors.HexColor('#666688'), spaceAfter=0,
        ),
        'titel': ParagraphStyle(
            'TKTitel', fontName='Helvetica-Bold', fontSize=16,
            textColor=FARBE_DUNKEL, spaceBefore=3 * mm, spaceAfter=2 * mm,
        ),
        'meta': ParagraphStyle(
            'TKMeta', fontName='Helvetica', fontSize=9,
            textColor=colors.HexColor('#666688'), spaceAfter=4 * mm,
        ),
        'abschnitt': ParagraphStyle(
            'TKAbschnitt', fontName='Helvetica-Bold', fontSize=11,
            textColor=FARBE_AKZENT, spaceBefore=2 * mm, spaceAfter=2 * mm,
        ),
        'label': ParagraphStyle(
            'TKLabel', fontName='Helvetica-Oblique', fontSize=8,
            textColor=colors.HexColor('#888888'),
            spaceBefore=3 * mm, spaceAfter=1 * mm,
        ),
        'normal': ParagraphStyle(
            'TKNormal', fontName='Helvetica', fontSize=9,
            textColor=FARBE_DUNKEL, spaceAfter=3 * mm, leading=13,
        ),
        'hinweis': ParagraphStyle(
            'TKHinweis', fontName='Helvetica-Oblique', fontSize=8,
            textColor=colors.HexColor('#666666'), spaceAfter=3 * mm, leading=12,
        ),
        'wert': ParagraphStyle(
            'TKWert', fontName='Helvetica-Bold', fontSize=9,
            textColor=FARBE_DUNKEL, alignment=TA_RIGHT,
        ),
    }


# ── BAUSTEINE ─────────────────────────────────────────────────────────────────

def _pdf_header(zeitraum: str, dokument: str, styles: dict) -> list:
    """
    Gibt eine Liste von Flowables für den Seitenkopf zurück.
    Wird in KeepTogether gewickelt damit Logo+Titel nie getrennt werden.
    """
    elemente = []
    logo = _logo_element()
    if logo:
        elemente.append(logo)
    else:
        elemente.append(Paragraph('talKIT e.V.', styles['verein']))

    elemente.append(Paragraph(dokument, styles['titel']))
    elemente.append(Paragraph(
        f'Zeitraum: <b>{zeitraum}</b> &nbsp;·&nbsp; '
        f'Erstellt am: {date.today().strftime("%d.%m.%Y")}',
        styles['meta']
    ))
    elemente.append(HRFlowable(
        width=SEITENBREITE, thickness=1.5, color=FARBE_AKZENT,
        spaceBefore=0, spaceAfter=5 * mm
    ))
    return [KeepTogether(elemente)]


def _abschnitt(titel: str, inhalt: list, styles: dict) -> KeepTogether:
    """
    Wickelt Abschnittsüberschrift + Inhalt in KeepTogether.
    Verhindert dass der Titel allein am Seitenende steht.
    """
    elemente = [
        HRFlowable(
            width=SEITENBREITE, thickness=0.5, color=FARBE_LINIE,
            spaceBefore=6 * mm, spaceAfter=0
        ),
        Paragraph(titel, styles['abschnitt']),
    ] + inhalt
    return KeepTogether(elemente)


def _zeilen_tabelle(zeilen: list[tuple], styles: dict) -> Table:
    """
    Zweispaltige Elster-Zeilentabelle.
    zeilen: (bezeichnung, wert_str) oder (bezeichnung, wert_str, zeilen_nr)
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

    t = Table(data, colWidths=[SEITENBREITE * 0.72, SEITENBREITE * 0.28])
    t.setStyle(TableStyle([
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [FARBE_WEISS, FARBE_HELL]),
        ('GRID',          (0, 0), (-1, -1), 0.3, FARBE_LINIE),
        ('LEFTPADDING',   (0, 0), (-1, -1), PAD_H),
        ('RIGHTPADDING',  (0, 0), (-1, -1), PAD_H),
        ('TOPPADDING',    (0, 0), (-1, -1), PAD_V),
        ('BOTTOMPADDING', (0, 0), (-1, -1), PAD_V),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    return t


# ── EXPORT: VORANMELDUNG ──────────────────────────────────────────────────────

def exportiere_voranmeldung(ergebnis: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=15*mm, bottomMargin=18*mm  # etwas mehr unten für Fußzeile
    )
    styles = _erstelle_styles()
    e = []

    e += _pdf_header(
        zeitraum=ergebnis['zeitraum'],
        dokument=f'Umsatzsteuer-Voranmeldung {ergebnis["zeitraum"]}',
        styles=styles
    )

    # Hauptinhalt als KeepTogether-Block
    inhalt = [
        Paragraph('Formular USt 1 A', styles['label']),
        _zeilen_tabelle([
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
        ], styles),
        Spacer(1, 5 * mm),
    ]

    zahllast = ergebnis['zahllast_kontrolle']
    farbe = FARBE_FEHLER if zahllast > 0 else FARBE_OK
    richtung = 'Zahlung ans Finanzamt' if zahllast > 0 else 'Erstattung vom Finanzamt'
    inhalt += [
        Paragraph(
            f'<b>Interne Zahllast (Kontrolle):</b> '
            f'<font color="{farbe.hexval()}">{zahllast:,.2f} €</font> – {richtung}',
            styles['normal']
        ),
        Paragraph(
            'Dieser Wert dient der internen Plausibilitätskontrolle. '
            'Maßgeblich für Elster sind ausschließlich die Zeilen 13–38.',
            styles['hinweis']
        ),
    ]
    e.append(KeepTogether(inhalt))

    doc.build(e, canvasmaker=_SeitenNummernCanvasV2)
    return buffer.getvalue()


# ── EXPORT: JAHRESSTEUER ──────────────────────────────────────────────────────

def exportiere_jahressteuer(eur: dict, ust: dict, kst_gewst: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=15*mm, bottomMargin=18*mm
    )
    styles = _erstelle_styles()
    e = []
    jahr = eur['jahr']

    e += _pdf_header(
        zeitraum=str(jahr),
        dokument=f'Jahressteuererklärung {jahr}',
        styles=styles
    )

    # ── EÜR ──────────────────────────────────────────────────────────────────
    eur_inhalt = []

    if eur.get('ohne_ueberweisung_ausgeschlossen', 0) > 0:
        eur_inhalt.append(Paragraph(
            f'Hinweis: {eur["ohne_ueberweisung_ausgeschlossen"]} GV(s) ohne '
            f'Überweisungsdatum wurden nicht berücksichtigt.',
            styles['hinweis']
        ))

    eur_inhalt += [
        Paragraph('Betriebseinnahmen – wirtschaftlicher Geschäftsbetrieb (D)',
                  styles['label']),
        _zeilen_tabelle([
            ('Steuerpflichtige Betriebseinnahmen (Netto)',
             f'{eur["zeile_15_betriebseinnahmen_netto"]:,.2f} €', 15),
            ('Vereinnahmte Umsatzsteuer',
             f'{eur["zeile_17_vereinnahmte_ust"]:,.2f} €', 17),
            ('Steuerfreie / nicht steuerbare Einnahmen (Sphären A+C)',
             f'{eur["zeile_21_steuerfreie_einnahmen"]:,.2f} €', 21),
        ], styles),
        Spacer(1, 3 * mm),
        Paragraph('Betriebsausgaben – wirtschaftlicher Geschäftsbetrieb (D)',
                  styles['label']),
        _zeilen_tabelle([
            ('Sonstige Betriebsausgaben (Netto)',
             f'{eur["zeile_46_betriebsausgaben_netto"]:,.2f} €', 46),
            ('Gezahlte Vorsteuerbeträge',
             f'{eur["zeile_48_vorsteuer"]:,.2f} €', 48),
        ], styles),
        Spacer(1, 4 * mm),
    ]

    gewinn = eur['gewinn_verlust_d']
    farbe_g = FARBE_OK if gewinn >= 0 else FARBE_FEHLER
    eur_inhalt.append(Paragraph(
        f'<b>Gewinn / Verlust Sphäre D (Zeile 75):</b> '
        f'<font color="{farbe_g.hexval()}">{gewinn:,.2f} €</font>',
        styles['normal']
    ))

    e.append(_abschnitt('Anlage EÜR – Einnahmenüberschussrechnung', eur_inhalt, styles))

    # ── USt Jahreserklärung ───────────────────────────────────────────────────
    ust_inhalt = [
        Paragraph('Jahressummen – Basis Rechnungsdatum', styles['label']),
        _zeilen_tabelle([
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
        ], styles),
    ]
    e.append(_abschnitt('Umsatzsteuer-Jahreserklärung (USt 2)', ust_inhalt, styles))

    # Quartalskontrolle – eigener KeepTogether-Block
    header_q = [['Quartal', 'Daten', 'Zahllast\nberechnet',
                 'Vorauszahlung\ngeleistet', 'Differenz']]
    q_rows = []
    for q in [1, 2, 3, 4]:
        q_erg = ust['quartalsergebnisse'].get(q)
        vz = ust.get(f'vz_q{q}', 0.0)
        if q_erg:
            zahllast = q_erg['zahllast_kontrolle']
            q_rows.append([f'Q{q}', '✓',
                           f'{zahllast:,.2f} €', f'{vz:,.2f} €',
                           f'{zahllast - vz:,.2f} €'])
        else:
            q_rows.append([f'Q{q}', '–', '0,00 €', f'{vz:,.2f} €',
                           f'{0.0 - vz:,.2f} €'])

    nachz = ust['nachzahlung_erstattung']
    summen = ['Gesamt', '', f'{ust["zahllast_kontrolle"]:,.2f} €',
              f'{ust["summe_vorauszahlungen"]:,.2f} €', f'{nachz:,.2f} €']

    col_b = [SEITENBREITE * 0.12, SEITENBREITE * 0.08,
             SEITENBREITE * 0.25, SEITENBREITE * 0.28, SEITENBREITE * 0.27]
    q_tab = Table(header_q + q_rows + [summen], colWidths=col_b)
    q_tab.setStyle(TableStyle([
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
        ('LEFTPADDING',   (0, 0), (-1, -1), PAD_H),
        ('RIGHTPADDING',  (0, 0), (-1, -1), PAD_H),
        ('TOPPADDING',    (0, 0), (-1, -1), PAD_V),
        ('BOTTOMPADDING', (0, 0), (-1, -1), PAD_V),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    nachz_text = (
        f'<b>Nachzahlung fällig: {nachz:,.2f} €</b>' if nachz > 0
        else f'<b>Erstattung zu erwarten: {abs(nachz):,.2f} €</b>' if nachz < 0
        else 'Vorauszahlungen und Jahresschuld sind ausgeglichen.'
    )

    e.append(KeepTogether([
        Paragraph('Abgleich Vorauszahlungen', styles['label']),
        q_tab,
        Spacer(1, 3 * mm),
        Paragraph(nachz_text, styles['normal']),
    ]))

    # ── KSt + GewSt ──────────────────────────────────────────────────────────
    kst_inhalt = [
        Paragraph('Sphäre D – wirtschaftlicher Geschäftsbetrieb', styles['label']),
    ]

    if not kst_gewst['steuerpflichtig']:
        kst_inhalt.append(Paragraph(
            f'Nullmeldung: {kst_gewst["grund"]}', styles['normal']
        ))
    else:
        kst_inhalt += [
            _zeilen_tabelle([
                ('Brutto-Einnahmen wirtsch. Geschäftsbetrieb (D)',
                 f'{kst_gewst["brutto_einnahmen_d"]:,.2f} €'),
                ('Gewinn Sphäre D',
                 f'{kst_gewst["gewinn_d"]:,.2f} €'),
                ('Freibetrag',
                 f'{kst_gewst["freibetrag"]:,.2f} €'),
                ('Zu versteuernder Gewinn',
                 f'{kst_gewst["zu_versteuernder_gewinn"]:,.2f} €'),
            ], styles),
            Spacer(1, 3 * mm),
            Paragraph('Körperschaftsteuer', styles['label']),
            _zeilen_tabelle([
                ('Körperschaftsteuer (15 %)',
                 f'{kst_gewst["kst"]:,.2f} €'),
                ('Solidaritätszuschlag (5,5 % auf KSt)',
                 f'{kst_gewst["solz"]:,.2f} €'),
                ('KSt gesamt',
                 f'{kst_gewst["kst_gesamt"]:,.2f} €'),
            ], styles),
            Spacer(1, 3 * mm),
            Paragraph('Gewerbesteuer', styles['label']),
            _zeilen_tabelle([
                ('Steuermessbetrag (Gewinn × 3,5 %)',
                 f'{kst_gewst["gewst_messbetrag"]:,.2f} €'),
                (f'Gewerbesteuer (Hebesatz {kst_gewst["gewst_hebesatz_prozent"]} %)',
                 f'{kst_gewst["gewst"]:,.2f} €'),
            ], styles),
            Spacer(1, 4 * mm),
            Paragraph(
                f'<b>Steuerbelastung gesamt: {kst_gewst["steuer_gesamt"]:,.2f} €</b>',
                styles['normal']
            ),
        ]

    e.append(_abschnitt(
        'Körperschaftsteuer (KSt 1) & Gewerbesteuererklärung (GewSt 1 B)',
        kst_inhalt, styles
    ))

    doc.build(e, canvasmaker=_SeitenNummernCanvasV2)
    return buffer.getvalue()
