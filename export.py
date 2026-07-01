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
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image, KeepTogether
)
from reportlab.lib.enums import TA_RIGHT, TA_LEFT
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

SEITENBREITE  = A4[0] - 30 * mm
PAD_V         = 5
PAD_H         = 6


# ── SEITENNUMMERN (zuverlässiger Zähler) ──────────────────────────────────────

class _SeitenCanvas(rl_canvas.Canvas):
    """
    Zwei-Pass-Canvas für 'Seite X von Y'.
    Speichert jeden Seitenzustand als Snapshot, schreibt Fußzeilen im zweiten Pass.
    Seitenzahl wird als einfacher Index gezählt – keine dict-Vergleiche.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._snapshots = []

    def showPage(self):
        # Zustand einfrieren: nur die Felder die für den zweiten Pass nötig sind
        self._snapshots.append({
            '_x': self._x, '_y': self._y,
            '_fontname': self._fontname, '_fontsize': self._fontsize,
            '_fillColorObj': self._fillColorObj,
            '_strokeColorObj': self._strokeColorObj,
            # Gesamter Zustand für korrekten Wiederaufbau
            '_saved': dict(self.__dict__),
        })
        self._startPage()

    def save(self):
        gesamt = len(self._snapshots)
        for i, snap in enumerate(self._snapshots):
            self.__dict__.update(snap['_saved'])
            self._fusszeile(seite=i + 1, gesamt=gesamt)
            rl_canvas.Canvas.showPage(self)
        rl_canvas.Canvas.save(self)

    def _fusszeile(self, seite: int, gesamt: int):
        self.saveState()
        self.setFont('Helvetica', 7)
        self.setFillColor(colors.HexColor('#AAAAAA'))
        self.drawString(15 * mm, 8 * mm, 'talKIT e.V. · Steuermodul')
        self.drawRightString(A4[0] - 15 * mm, 8 * mm, f'Seite {seite} von {gesamt}')
        # dünne Trennlinie über Fußzeile
        self.setStrokeColor(colors.HexColor('#DDDDDD'))
        self.setLineWidth(0.3)
        self.line(15 * mm, 12 * mm, A4[0] - 15 * mm, 12 * mm)
        self.restoreState()


# ── LOGO ──────────────────────────────────────────────────────────────────────

def _logo_pfad() -> Path | None:
    basis = Path(__file__).parent
    for name in ['talKITlogogruen.png', 'talKIT logo gruen.png']:
        for ordner in [basis, basis / 'assets']:
            p = ordner / name
            if p.exists():
                return p
    return None


# ── STYLES ────────────────────────────────────────────────────────────────────

def _styles() -> dict:
    return {
        'titel': ParagraphStyle(
            'TKTitel', fontName='Helvetica-Bold', fontSize=15,
            textColor=FARBE_DUNKEL, spaceAfter=1 * mm, leading=18,
        ),
        'meta': ParagraphStyle(
            'TKMeta', fontName='Helvetica', fontSize=8,
            textColor=colors.HexColor('#888899'), spaceAfter=0, leading=11,
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


# ── HEADER ────────────────────────────────────────────────────────────────────

def _header(zeitraum: str, dokument: str, s: dict) -> KeepTogether:
    """
    Professioneller Kopfbereich: Logo rechts, Titel+Meta links, in einer Tabellenzeile.
    Dadurch stehen Logo und Text auf gleicher Basislinie – kein gestapeltes Layout.
    """
    logo_p = _logo_pfad()

    if logo_p:
        # Logo auf 28 mm Breite skalieren, Höhe proportional (1722:510)
        logo_breite = 28 * mm
        logo_hoehe = logo_breite * (510 / 1722)
        logo_img = Image(str(logo_p), width=logo_breite, height=logo_hoehe)
    else:
        logo_img = Paragraph('talKIT e.V.', ParagraphStyle(
            'TKFallback', fontName='Helvetica-Bold', fontSize=10,
            textColor=FARBE_AKZENT, alignment=TA_RIGHT,
        ))

    titel_block = [
        Paragraph(dokument, s['titel']),
        Paragraph(
            f'Zeitraum: <b>{zeitraum}</b> &nbsp;·&nbsp; '
            f'Erstellt am: {date.today().strftime("%d.%m.%Y")}',
            s['meta']
        ),
    ]

    # Zweispaltige Tabelle: Titel links, Logo rechts
    header_tab = Table(
        [[titel_block, logo_img]],
        colWidths=[SEITENBREITE * 0.65, SEITENBREITE * 0.35],
    )
    header_tab.setStyle(TableStyle([
        ('VALIGN',       (0, 0), (-1, -1), 'BOTTOM'),
        ('ALIGN',        (1, 0), (1, 0),   'RIGHT'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING',   (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 0),
    ]))

    trennlinie = HRFlowable(
        width=SEITENBREITE, thickness=1.5, color=FARBE_AKZENT,
        spaceBefore=3 * mm, spaceAfter=5 * mm
    )

    return KeepTogether([header_tab, trennlinie])


# ── ABSCHNITT ─────────────────────────────────────────────────────────────────

def _abschnitt(titel: str, inhalt: list, s: dict) -> KeepTogether:
    """Hält Abschnittsüberschrift + ersten Inhalt zusammen (kein Waisentitel)."""
    return KeepTogether([
        HRFlowable(
            width=SEITENBREITE, thickness=0.5, color=FARBE_LINIE,
            spaceBefore=6 * mm, spaceAfter=0
        ),
        Paragraph(titel, s['abschnitt']),
    ] + inhalt)


# ── TABELLE ───────────────────────────────────────────────────────────────────

def _tabelle(zeilen: list[tuple], s: dict) -> Table:
    data = []
    for z in zeilen:
        if len(z) == 3:
            bezeichnung, wert, nr = z
            label = f'Zeile {nr} – {bezeichnung}'
        else:
            bezeichnung, wert = z
            label = bezeichnung
        data.append([Paragraph(label, s['normal']), Paragraph(f'<b>{wert}</b>', s['wert'])])

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


# ── VORANMELDUNG ──────────────────────────────────────────────────────────────

def exportiere_voranmeldung(ergebnis: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=15*mm, bottomMargin=18*mm)
    s = _styles()
    e = [_header(ergebnis['zeitraum'],
                 f'Umsatzsteuer-Voranmeldung {ergebnis["zeitraum"]}', s)]

    zahllast = ergebnis['zahllast_kontrolle']
    farbe = FARBE_FEHLER if zahllast > 0 else FARBE_OK
    richtung = 'Zahlung ans Finanzamt' if zahllast > 0 else 'Erstattung vom Finanzamt'

    e.append(KeepTogether([
        Paragraph('Formular USt 1 A', s['label']),
        _tabelle([
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
        ], s),
        Spacer(1, 5 * mm),
        Paragraph(
            f'<b>Interne Zahllast (Kontrolle):</b> '
            f'<font color="{farbe.hexval()}">{zahllast:,.2f} €</font> – {richtung}',
            s['normal']
        ),
        Paragraph(
            'Dieser Wert dient der internen Plausibilitätskontrolle. '
            'Maßgeblich für Elster sind die Zeilen 13–38.',
            s['hinweis']
        ),
    ]))

    doc.build(e, canvasmaker=_SeitenCanvas)
    return buf.getvalue()


# ── JAHRESSTEUER ──────────────────────────────────────────────────────────────

def exportiere_jahressteuer(eur: dict, ust: dict, kst_gewst: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=15*mm, bottomMargin=18*mm)
    s = _styles()
    e = [_header(str(eur['jahr']), f'Jahressteuererklärung {eur["jahr"]}', s)]

    # ── EÜR ──
    eur_inhalt = []
    if eur.get('ohne_ueberweisung_ausgeschlossen', 0) > 0:
        eur_inhalt.append(Paragraph(
            f'Hinweis: {eur["ohne_ueberweisung_ausgeschlossen"]} GV(s) ohne '
            f'Überweisungsdatum wurden nicht berücksichtigt.', s['hinweis']
        ))
    eur_inhalt += [
        Paragraph('Betriebseinnahmen – wirtschaftlicher Geschäftsbetrieb (D)', s['label']),
        _tabelle([
            ('Steuerpflichtige Betriebseinnahmen (Netto)',
             f'{eur["zeile_15_betriebseinnahmen_netto"]:,.2f} €', 15),
            ('Vereinnahmte Umsatzsteuer',
             f'{eur["zeile_17_vereinnahmte_ust"]:,.2f} €', 17),
            ('Steuerfreie / nicht steuerbare Einnahmen (Sphären A+C)',
             f'{eur["zeile_21_steuerfreie_einnahmen"]:,.2f} €', 21),
        ], s),
        Spacer(1, 3 * mm),
        Paragraph('Betriebsausgaben – wirtschaftlicher Geschäftsbetrieb (D)', s['label']),
        _tabelle([
            ('Sonstige Betriebsausgaben (Netto)',
             f'{eur["zeile_46_betriebsausgaben_netto"]:,.2f} €', 46),
            ('Gezahlte Vorsteuerbeträge',
             f'{eur["zeile_48_vorsteuer"]:,.2f} €', 48),
        ], s),
        Spacer(1, 4 * mm),
    ]
    gewinn = eur['gewinn_verlust_d']
    farbe_g = FARBE_OK if gewinn >= 0 else FARBE_FEHLER
    eur_inhalt.append(Paragraph(
        f'<b>Gewinn / Verlust Sphäre D (Zeile 75):</b> '
        f'<font color="{farbe_g.hexval()}">{gewinn:,.2f} €</font>',
        s['normal']
    ))
    e.append(_abschnitt('Anlage EÜR – Einnahmenüberschussrechnung', eur_inhalt, s))

    # ── USt Jahres ──
    e.append(_abschnitt('Umsatzsteuer-Jahreserklärung (USt 2)', [
        Paragraph('Jahressummen – Basis Rechnungsdatum', s['label']),
        _tabelle([
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
        ], s),
    ], s))

    # Quartalskontrolle
    nachz = ust['nachzahlung_erstattung']
    header_q = [['Quartal', 'Daten', 'Zahllast\nberechnet',
                 'Vorauszahlung\ngeleistet', 'Differenz']]
    q_rows = []
    for q in [1, 2, 3, 4]:
        q_erg = ust['quartalsergebnisse'].get(q)
        vz = ust.get(f'vz_q{q}', 0.0)
        if q_erg:
            zl = q_erg['zahllast_kontrolle']
            q_rows.append([f'Q{q}', '✓', f'{zl:,.2f} €',
                           f'{vz:,.2f} €', f'{zl - vz:,.2f} €'])
        else:
            q_rows.append([f'Q{q}', '–', '0,00 €',
                           f'{vz:,.2f} €', f'{-vz:,.2f} €'])

    summen = ['Gesamt', '',
              f'{ust["zahllast_kontrolle"]:,.2f} €',
              f'{ust["summe_vorauszahlungen"]:,.2f} €',
              f'{nachz:,.2f} €']

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
        Paragraph('Abgleich Vorauszahlungen', s['label']),
        q_tab,
        Spacer(1, 3 * mm),
        Paragraph(nachz_text, s['normal']),
    ]))

    # ── KSt + GewSt ──
    kst_inhalt = [
        Paragraph('Sphäre D – wirtschaftlicher Geschäftsbetrieb', s['label']),
    ]
    if not kst_gewst['steuerpflichtig']:
        kst_inhalt.append(Paragraph(
            f'Nullmeldung: {kst_gewst["grund"]}', s['normal']
        ))
    else:
        kst_inhalt += [
            _tabelle([
                ('Brutto-Einnahmen wirtsch. Geschäftsbetrieb (D)',
                 f'{kst_gewst["brutto_einnahmen_d"]:,.2f} €'),
                ('Gewinn Sphäre D', f'{kst_gewst["gewinn_d"]:,.2f} €'),
                ('Freibetrag', f'{kst_gewst["freibetrag"]:,.2f} €'),
                ('Zu versteuernder Gewinn',
                 f'{kst_gewst["zu_versteuernder_gewinn"]:,.2f} €'),
            ], s),
            Spacer(1, 3 * mm),
            Paragraph('Körperschaftsteuer', s['label']),
            _tabelle([
                ('Körperschaftsteuer (15 %)', f'{kst_gewst["kst"]:,.2f} €'),
                ('Solidaritätszuschlag (5,5 % auf KSt)', f'{kst_gewst["solz"]:,.2f} €'),
                ('KSt gesamt', f'{kst_gewst["kst_gesamt"]:,.2f} €'),
            ], s),
            Spacer(1, 3 * mm),
            Paragraph('Gewerbesteuer', s['label']),
            _tabelle([
                ('Steuermessbetrag (Gewinn × 3,5 %)',
                 f'{kst_gewst["gewst_messbetrag"]:,.2f} €'),
                (f'Gewerbesteuer (Hebesatz {kst_gewst["gewst_hebesatz_prozent"]} %)',
                 f'{kst_gewst["gewst"]:,.2f} €'),
            ], s),
            Spacer(1, 4 * mm),
            Paragraph(
                f'<b>Steuerbelastung gesamt: {kst_gewst["steuer_gesamt"]:,.2f} €</b>',
                s['normal']
            ),
        ]
    e.append(_abschnitt(
        'Körperschaftsteuer (KSt 1) & Gewerbesteuererklärung (GewSt 1 B)',
        kst_inhalt, s
    ))

    doc.build(e, canvasmaker=_SeitenCanvas)
    return buf.getvalue()
