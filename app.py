# -*- coding: utf-8 -*-
"""
app.py – talKIT Steuermodul
Streamlit-Oberfläche für die Steuervorbereitung.
"""

import streamlit as st
import pandas as pd
import base64
import difflib
from pathlib import Path
from berechnung import (
    pruefe_spalten, pruefe_mwst_konsistenz, erkenne_zeitraeume,
    bereite_daten_vor, berechne_voranmeldung, berechne_eur,
    berechne_ust_jahres, berechne_kst_gewst
)
from export import exportiere_voranmeldung, exportiere_jahressteuer

# ── SEITENKONFIGURATION ───────────────────────────────────────────────────────

st.set_page_config(
    page_title='talKIT Steuermodul',
    page_icon='📊',
    layout='centered',
)

# Darkmode-kompatibles CSS: nur strukturelle Styles, keine Farbüberschreibungen
st.markdown("""
<style>
    .main { max-width: 760px; margin: 0 auto; }
    .stAlert { border-radius: 6px; }
    .elster-zeile {
        font-family: monospace;
        padding: 6px 10px;
        border-left: 3px solid #4A90D9;
        margin: 3px 0;
        border-radius: 0 4px 4px 0;
    }
    .elster-zeile-nr {
        font-size: 0.75em;
        opacity: 0.6;
        display: block;
    }
    .elster-zeile-inhalt {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
    }
    .elster-zeile-betrag {
        font-size: 1.05em;
        font-weight: bold;
        white-space: nowrap;
        margin-left: 12px;
    }
</style>
""", unsafe_allow_html=True)


# ── HILFSFUNKTIONEN ───────────────────────────────────────────────────────────

def formatiere_betrag(wert: float) -> str:
    return f'{wert:,.2f} €'.replace(',', 'X').replace('.', ',').replace('X', '.')


def zeige_elster_zeile(zeilen_nr: str, bezeichnung: str, wert: float):
    """Einheitliche Darstellung einer Elster-Zeile – darkmode-kompatibel."""
    st.markdown(
        f'<div class="elster-zeile">'
        f'<span class="elster-zeile-nr">Zeile {zeilen_nr}</span>'
        f'<div class="elster-zeile-inhalt">'
        f'<span>{bezeichnung}</span>'
        f'<span class="elster-zeile-betrag">{formatiere_betrag(wert)}</span>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True
    )


def zeige_logo():
    """Logo anzeigen falls vorhanden, sonst Textfallback."""
    basis = Path(__file__).parent
    kandidaten = [
        basis / 'talKITlogogruen.png',
        basis / 'talKIT logo gruen.png',
        basis / 'assets' / 'talKITlogogruen.png',
    ]
    logo_pfad = next((p for p in kandidaten if p.exists()), None)
    if logo_pfad:
        with open(logo_pfad, 'rb') as f:
            data = base64.b64encode(f.read()).decode()
        st.markdown(
            f'<img src="data:image/png;base64,{data}" '
            f'style="height:36px; margin-bottom:4px;" alt="talKIT">',
            unsafe_allow_html=True
        )
    else:
        st.markdown('**talKIT e.V.**')


def neue_datei_button():
    """Setzt den Session State zurück – upload_key-Increment zwingt file_uploader zum Reset."""
    if st.button('Neue Datei wählen', type='secondary', key='neue_datei'):
        upload_key = st.session_state.get('upload_key', 0) + 1
        st.session_state.clear()
        st.session_state['upload_key'] = upload_key
        st.rerun()


# ── SCHRITT 1: UPLOAD ─────────────────────────────────────────────────────────

zeige_logo()
st.title('Steuermodul')
st.caption('Vorbereitung der Steuerunterlagen auf Basis des Podio-Exports')

st.divider()

# upload_key wird hochgezählt um den file_uploader zuverlässig zurückzusetzen
if 'upload_key' not in st.session_state:
    st.session_state['upload_key'] = 0

uploaded_file = st.file_uploader(
    'Podio-Export hochladen',
    type=['xlsx'],
    key=f'uploader_{st.session_state["upload_key"]}',
    help='Lade die aus Podio exportierte Excel-Datei hoch. '
         'Die Datei muss genau ein Tabellenblatt enthalten.'
)

if uploaded_file is None:
    st.info('Lade die aus Podio exportierte Excel-Datei hoch um zu beginnen.')
    st.stop()


# ── SCHRITT 2: EINLESEN & VALIDIERUNG ────────────────────────────────────────

with st.spinner('Datei wird eingelesen …'):
    try:
        xls = pd.ExcelFile(uploaded_file)
        if len(xls.sheet_names) != 1:
            st.error(
                f'Die Datei enthält {len(xls.sheet_names)} Tabellenblätter. '
                f'Bitte eine Datei mit genau einem Blatt hochladen.'
            )
            neue_datei_button()
            st.stop()
        df_roh = pd.read_excel(xls, sheet_name=xls.sheet_names[0])
    except Exception as e:
        st.error(f'Datei konnte nicht eingelesen werden: {e}')
        neue_datei_button()
        st.stop()

# ── SPALTEN-MATCHING ─────────────────────────────────────────────────────────

def matche_spalten(
    vorhandene: list[str],
    pflicht: list[str],
    schwelle: float = 0.75
) -> dict[str, str | None]:
    """
    Versucht Pflicht-Spalten auf vorhandene Spalten zu matchen.
    Reihenfolge: exakt → exakt lowercase → Ähnlichkeit (difflib).
    Gibt dict zurück: {pflicht_spalte: gefundene_spalte | None}
    """
    vorhandene_lower = {s.lower(): s for s in vorhandene}
    mapping = {}
    for pflicht_spalte in pflicht:
        # 1. Exakter Match
        if pflicht_spalte in vorhandene:
            mapping[pflicht_spalte] = pflicht_spalte
            continue
        # 2. Case-insensitiver Match
        if pflicht_spalte.lower() in vorhandene_lower:
            mapping[pflicht_spalte] = vorhandene_lower[pflicht_spalte.lower()]
            continue
        # 3. Ähnlichkeitssuche
        treffer = difflib.get_close_matches(
            pflicht_spalte, vorhandene, n=1, cutoff=schwelle
        )
        mapping[pflicht_spalte] = treffer[0] if treffer else None
    return mapping

from berechnung import PFLICHT_SPALTEN as _PFLICHT

vorhandene_spalten = list(df_roh.columns)
mapping = matche_spalten(vorhandene_spalten, _PFLICHT)

exakt    = {k: v for k, v in mapping.items() if v == k}
aehnlich = {k: v for k, v in mapping.items() if v is not None and v != k}
fehlend  = {k: v for k, v in mapping.items() if v is None}

# Mapping-Korrekturen aus Session State übernehmen
if 'spalten_mapping' not in st.session_state:
    st.session_state['spalten_mapping'] = {**exakt, **aehnlich}

hat_probleme = bool(aehnlich or fehlend)

if hat_probleme:
    st.warning(
        f'Spalten-Zuordnung: {len(exakt)} eindeutig · '
        f'{len(aehnlich)} unsicher · {len(fehlend)} nicht gefunden'
    )
    with st.expander('Spalten-Zuordnung prüfen und anpassen', expanded=True):
        st.caption(
            'Das System hat versucht, die Spalten automatisch zuzuordnen. '
            'Bitte prüfe unsichere Zuordnungen und ergänze fehlende Spalten.'
        )

        neues_mapping = dict(st.session_state['spalten_mapping'])

        if aehnlich:
            st.markdown('**Unsichere Zuordnungen – bitte bestätigen oder korrigieren:**')
            for pflicht_sp, gefunden in aehnlich.items():
                optionen = ['– nicht vorhanden –'] + vorhandene_spalten
                default = optionen.index(gefunden) if gefunden in optionen else 0
                auswahl = st.selectbox(
                    f'`{pflicht_sp}`',
                    options=optionen,
                    index=default,
                    key=f'match_{pflicht_sp}',
                    help=f'Automatisch zugeordnet zu: {gefunden}'
                )
                neues_mapping[pflicht_sp] = None if auswahl == '– nicht vorhanden –' else auswahl

        if fehlend:
            st.markdown('**Nicht gefundene Spalten – bitte manuell zuordnen:**')
            for pflicht_sp in fehlend:
                optionen = ['– nicht vorhanden –'] + vorhandene_spalten
                auswahl = st.selectbox(
                    f'`{pflicht_sp}`',
                    options=optionen,
                    index=0,
                    key=f'match_{pflicht_sp}',
                )
                neues_mapping[pflicht_sp] = None if auswahl == '– nicht vorhanden –' else auswahl

        st.session_state['spalten_mapping'] = neues_mapping

        noch_fehlend = [k for k, v in neues_mapping.items() if v is None]
        if noch_fehlend:
            st.error(
                'Folgende Pflicht-Spalten sind noch nicht zugeordnet:

' +
                '
'.join(f'- `{s}`' for s in noch_fehlend)
            )
            neue_datei_button()
            st.stop()
        else:
            if st.button('Zuordnung bestätigen', type='primary'):
                st.session_state['mapping_bestaetigt'] = True
                st.rerun()
            if not st.session_state.get('mapping_bestaetigt', False):
                st.stop()

    # DataFrame umbenennen nach bestätigtem Mapping
    umbenennungen = {
        v: k for k, v in st.session_state['spalten_mapping'].items() if v != k
    }
    if umbenennungen:
        df_roh = df_roh.rename(columns=umbenennungen)
else:
    st.session_state['mapping_bestaetigt'] = True

# MwSt-Konsistenzprüfung
fehler_df, andere_df = pruefe_mwst_konsistenz(df_roh)

hat_fehler = len(fehler_df) > 0
hat_andere = len(andere_df) > 0

if hat_fehler or hat_andere:
    with st.expander(
        f'⚠️ {len(fehler_df)} MwSt-Fehler gefunden · '
        f'{len(andere_df)} GV(s) mit anderem Steuersatz – Details anzeigen',
        expanded=True
    ):
        if hat_fehler:
            st.markdown('**Folgende GVs haben inkonsistente MwSt-Felder. '
                        'Bitte in Podio korrigieren und Datei neu exportieren:**')
            st.dataframe(fehler_df, use_container_width=True, hide_index=True)

        if hat_andere:
            st.markdown('**Folgende GVs haben einen anderen Steuersatz – bitte manuell prüfen:**')
            st.dataframe(andere_df, use_container_width=True, hide_index=True)

    if hat_fehler:
        col1, col2 = st.columns(2)
        with col1:
            if st.button('Trotzdem fortfahren', type='secondary'):
                st.session_state['fehler_bestaetigt'] = True
                st.rerun()
        with col2:
            if st.button('Neue Datei wählen', type='primary', key='neue_datei_fehler'):
                upload_key = st.session_state.get('upload_key', 0) + 1
                st.session_state.clear()
                st.session_state['upload_key'] = upload_key
                st.rerun()

        if not st.session_state.get('fehler_bestaetigt', False):
            st.stop()
else:
    st.success(f'✅ {len(df_roh)} Buchungen geladen – keine MwSt-Fehler gefunden.')

# Daten aufbereiten
df, unbekannte_typen = bereite_daten_vor(df_roh)

if unbekannte_typen > 0:
    st.warning(
        f'{unbekannte_typen} GV(s) haben einen unbekannten Typ '
        f'(weder "Einnahme" noch "Ausgabe") und wurden übersprungen.'
    )

# Zeiträume erkennen
zeitraeume = erkenne_zeitraeume(df)

st.divider()


# ── SCHRITT 3: STEUERART ──────────────────────────────────────────────────────

st.subheader('Was möchtest du berechnen?')

steuerart = st.radio(
    'Steuerart',
    options=['Umsatzsteuer-Voranmeldung', 'Jahressteuererklärung'],
    captions=[
        'Für ein einzelnes Quartal – aktuelle Elster-Voranmeldung',
        'USt, EÜR, KSt, GewSt + Quartalskontrolle für ein vollständiges Jahr'
    ],
    label_visibility='collapsed'
)

st.divider()


# ── SCHRITT 4A: ZEITRAUM WÄHLEN – VORANMELDUNG ───────────────────────────────

if steuerart == 'Umsatzsteuer-Voranmeldung':
    st.subheader('Zeitraum auswählen')

    vorschlag = zeitraeume.sort_values('Buchungen', ascending=False).iloc[0]
    vorschlag_q = int(vorschlag['Quartal'])
    vorschlag_j = int(vorschlag['Jahr'])

    verfuegbare_jahre = sorted(zeitraeume['Jahr'].unique().tolist(), reverse=True)

    col1, col2 = st.columns(2)
    with col1:
        gewaehltes_jahr = st.selectbox(
            'Jahr', options=verfuegbare_jahre,
            index=verfuegbare_jahre.index(vorschlag_j)
        )
    with col2:
        gewaehltes_quartal = st.selectbox(
            'Quartal', options=[1, 2, 3, 4],
            index=vorschlag_q - 1,
            format_func=lambda q: f'Q{q}'
        )

    treffer = zeitraeume[
        (zeitraeume['Jahr'] == gewaehltes_jahr) &
        (zeitraeume['Quartal'] == gewaehltes_quartal)
    ]
    if not treffer.empty:
        anzahl = int(treffer.iloc[0]['Buchungen'])
        st.caption(
            f'ℹ️ Vorschlag: Q{vorschlag_q} {vorschlag_j} '
            f'({int(vorschlag["Buchungen"])} Buchungen) · '
            f'Gewählt: Q{gewaehltes_quartal} {gewaehltes_jahr} ({anzahl} Buchungen)'
        )
    else:
        st.warning(f'Keine Buchungen für Q{gewaehltes_quartal} {gewaehltes_jahr} in der Datei.')

    with st.expander('Alle Zeiträume in der Datei'):
        anzeige = zeitraeume.copy()
        anzeige['Quartal'] = anzeige['Quartal'].apply(lambda q: f'Q{q}')
        st.dataframe(anzeige, use_container_width=True, hide_index=True)

    st.divider()

    if st.button('🧮 Voranmeldung berechnen', type='primary'):
        ergebnis = berechne_voranmeldung(df, quartal=gewaehltes_quartal, jahr=gewaehltes_jahr)

        if ergebnis is None:
            st.error(
                f'Keine steuerrelevanten Buchungen für '
                f'Q{gewaehltes_quartal} {gewaehltes_jahr} gefunden.'
            )
        else:
            st.subheader(f'📄 USt-Voranmeldung Q{gewaehltes_quartal} {gewaehltes_jahr}')
            st.caption('Formular USt 1 A · Alle Beträge in Euro (netto)')

            zeige_elster_zeile('13', 'Steuerpflichtige Umsätze 19 %',
                               ergebnis['zeile_13_netto_19'])
            zeige_elster_zeile('14', 'Steuerpflichtige Umsätze 7 %',
                               ergebnis['zeile_14_netto_7'])
            zeige_elster_zeile('15', 'Steuerfreie / nicht steuerbare Umsätze',
                               ergebnis['zeile_15_netto_0'])
            zeige_elster_zeile('16', 'Umsätze zu anderen Steuersätzen',
                               ergebnis['zeile_16_netto_andere'])
            zeige_elster_zeile('38', 'Abziehbare Vorsteuerbeträge',
                               ergebnis['zeile_38_vorsteuer'])

            st.divider()
            zahllast = ergebnis['zahllast_kontrolle']
            st.metric(
                'Interne Zahllast (Kontrolle)',
                formatiere_betrag(zahllast),
                help='Positiv = Zahlung ans Finanzamt · Negativ = Erstattung vom Finanzamt. '
                     'Nur zur internen Kontrolle – maßgeblich sind die Zeilen 13–38.'
            )

            pdf_bytes = exportiere_voranmeldung(ergebnis)
            st.download_button(
                label='📥 Als PDF exportieren',
                data=pdf_bytes,
                file_name=f'talKIT_UStVA_Q{gewaehltes_quartal}_{gewaehltes_jahr}.pdf',
                mime='application/pdf',
            )


# ── SCHRITT 4B: ZEITRAUM WÄHLEN – JAHRESSTEUER ───────────────────────────────

else:
    st.subheader('Jahr auswählen')

    verfuegbare_jahre = sorted(zeitraeume['Jahr'].unique().tolist(), reverse=True)
    gewaehltes_jahr = st.selectbox('Jahr', options=verfuegbare_jahre)

    jahr_info = zeitraeume[zeitraeume['Jahr'] == gewaehltes_jahr]
    vorhandene_quartale = sorted(jahr_info['Quartal'].tolist())
    fehlende_q = [q for q in [1, 2, 3, 4] if q not in vorhandene_quartale]

    if not fehlende_q:
        st.success(f'✅ {gewaehltes_jahr}: Alle 4 Quartale vorhanden.')
    else:
        st.warning(
            f'⚠️ {gewaehltes_jahr} ist unvollständig – '
            f'keine Buchungsdaten für: {", ".join(f"Q{q}" for q in fehlende_q)}. '
            f'Für diese Quartale wird die Zahllast als 0,00 € angenommen. '
            f'Bitte die Vorauszahlungen vollständig eintragen.'
        )

    st.divider()

    # ── SCHRITT 5: VORAUSZAHLUNGEN ────────────────────────────────────────────

    st.subheader('Geleistete USt-Vorauszahlungen')
    st.caption(
        'Trage hier die tatsächlich abgeführten Beträge ein. '
        'Positiv = Zahlung ans Finanzamt · Negativ = Rückzahlung vom Finanzamt'
    )

    col1, col2 = st.columns(2)
    col3, col4 = st.columns(2)
    with col1:
        vz_q1 = st.number_input('Q1', value=0.0, step=0.01, format='%.2f', key='vz_q1',
                                 help='Positiv = gezahlt · Negativ = erstattet')
    with col2:
        vz_q2 = st.number_input('Q2', value=0.0, step=0.01, format='%.2f', key='vz_q2')
    with col3:
        vz_q3 = st.number_input('Q3', value=0.0, step=0.01, format='%.2f', key='vz_q3')
    with col4:
        vz_q4 = st.number_input('Q4', value=0.0, step=0.01, format='%.2f', key='vz_q4')

    vorauszahlungen = {1: vz_q1, 2: vz_q2, 3: vz_q3, 4: vz_q4}

    st.divider()

    # ── SCHRITT 6B: BERECHNUNG JAHRESSTEUER ──────────────────────────────────

    if st.button('🧮 Jahressteuer berechnen', type='primary'):

        eur = berechne_eur(df, jahr=gewaehltes_jahr)
        ust = berechne_ust_jahres(df, jahr=gewaehltes_jahr, vorauszahlungen=vorauszahlungen)

        if eur is None or ust is None:
            st.error(f'Keine ausreichenden Daten für das Jahr {gewaehltes_jahr}.')
            st.stop()

        kst_gewst = berechne_kst_gewst(eur, jahr=gewaehltes_jahr)

        # ── EÜR ──
        st.subheader(f'📊 Anlage EÜR – {gewaehltes_jahr}')
        st.caption('Einnahmenüberschussrechnung · Basis: Überweisungsdatum')

        if eur['ohne_ueberweisung_ausgeschlossen'] > 0:
            st.info(
                f'{eur["ohne_ueberweisung_ausgeschlossen"]} GV(s) ohne Überweisungsdatum '
                f'wurden nicht berücksichtigt.'
            )

        st.markdown('**Betriebseinnahmen (wirtschaftlicher Geschäftsbetrieb D)**')
        zeige_elster_zeile('15', 'Steuerpflichtige Betriebseinnahmen (Netto)',
                           eur['zeile_15_betriebseinnahmen_netto'])
        zeige_elster_zeile('17', 'Vereinnahmte Umsatzsteuer',
                           eur['zeile_17_vereinnahmte_ust'])
        zeige_elster_zeile('21', 'Steuerfreie / nicht steuerbare Einnahmen (Sphären A+C)',
                           eur['zeile_21_steuerfreie_einnahmen'])

        st.markdown('**Betriebsausgaben (wirtschaftlicher Geschäftsbetrieb D)**')
        zeige_elster_zeile('46', 'Sonstige Betriebsausgaben (Netto)',
                           eur['zeile_46_betriebsausgaben_netto'])
        zeige_elster_zeile('48', 'Gezahlte Vorsteuerbeträge',
                           eur['zeile_48_vorsteuer'])

        st.metric(
            'Gewinn / Verlust Sphäre D (Zeile 75)',
            formatiere_betrag(eur['gewinn_verlust_d'])
        )

        st.divider()

        # ── USt Jahreserklärung ──
        st.subheader(f'📄 USt-Jahreserklärung – {gewaehltes_jahr}')
        st.caption('Formular USt 2 · Jahressummen basierend auf Rechnungsdatum')

        zeige_elster_zeile('13', 'Netto-Umsatz 19 %', ust['zeile_13_netto_19'])
        zeige_elster_zeile('14', 'Netto-Umsatz 7 %', ust['zeile_14_netto_7'])
        zeige_elster_zeile('15', 'Umsätze 0 %', ust['zeile_15_netto_0'])
        zeige_elster_zeile('16', 'Umsätze andere Steuersätze', ust['zeile_16_netto_andere'])
        zeige_elster_zeile('38', 'Abziehbare Vorsteuer gesamt', ust['zeile_38_vorsteuer'])

        # Quartalskontrolle – alle 4 Quartale zeigen, auch ohne Buchungsdaten
        st.markdown('**Quartalskontrolle**')
        if fehlende_q:
            st.caption(
                f'ℹ️ Quartale ohne Buchungsdaten in der Datei '
                f'({", ".join(f"Q{q}" for q in fehlende_q)}): '
                f'berechnete Zahllast = 0,00 €. '
                f'Vorauszahlungen dieser Quartale fließen trotzdem in den Saldo ein.'
            )

        q_data = []
        for q in [1, 2, 3, 4]:
            q_erg = ust['quartalsergebnisse'].get(q)
            vz = vorauszahlungen[q]
            if q_erg:
                zahllast = q_erg['zahllast_kontrolle']
                q_data.append({
                    'Quartal': f'Q{q}',
                    'Buchungsdaten': '✅',
                    'Zahllast berechnet': formatiere_betrag(zahllast),
                    'Vorauszahlung geleistet': formatiere_betrag(vz),
                    'Differenz': formatiere_betrag(zahllast - vz),
                })
            else:
                q_data.append({
                    'Quartal': f'Q{q}',
                    'Buchungsdaten': '⚠️ fehlt',
                    'Zahllast berechnet': '0,00 €',
                    'Vorauszahlung geleistet': formatiere_betrag(vz),
                    'Differenz': formatiere_betrag(0.0 - vz),
                })

        st.dataframe(pd.DataFrame(q_data), use_container_width=True, hide_index=True)

        nachz = ust['nachzahlung_erstattung']
        if nachz > 0:
            st.warning(f'⚠️ Nachzahlung fällig: **{formatiere_betrag(nachz)}**')
        elif nachz < 0:
            st.success(f'✅ Erstattung zu erwarten: **{formatiere_betrag(abs(nachz))}**')
        else:
            st.success('✅ Kein Saldo – Vorauszahlungen und Jahresschuld ausgeglichen.')

        st.divider()

        # ── KSt + GewSt ──
        st.subheader(f'🏛️ Körperschaft- & Gewerbesteuer – {gewaehltes_jahr}')
        st.caption('KSt 1 & GewSt 1 B · Sphäre D (wirtschaftlicher Geschäftsbetrieb)')

        if not kst_gewst['steuerpflichtig']:
            st.success(f'✅ Nullmeldung: {kst_gewst["grund"]}')
        else:
            st.markdown('**Berechnungsgrundlage**')
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric('Brutto-Einnahmen D',
                          formatiere_betrag(kst_gewst['brutto_einnahmen_d']))
            with col2:
                st.metric('Gewinn D', formatiere_betrag(kst_gewst['gewinn_d']))
            with col3:
                st.metric('Zu versteuern',
                          formatiere_betrag(kst_gewst['zu_versteuernder_gewinn']))

            st.markdown('**Körperschaftsteuer**')
            zeige_elster_zeile('–', 'Körperschaftsteuer 15 %', kst_gewst['kst'])
            zeige_elster_zeile('–', 'Solidaritätszuschlag (5,5 % auf KSt)', kst_gewst['solz'])
            zeige_elster_zeile('–', 'KSt gesamt', kst_gewst['kst_gesamt'])

            st.markdown('**Gewerbesteuer**')
            zeige_elster_zeile('–', 'Steuermessbetrag (× 3,5 %)',
                               kst_gewst['gewst_messbetrag'])
            zeige_elster_zeile(
                '–',
                f'Gewerbesteuer (Hebesatz {kst_gewst["gewst_hebesatz_prozent"]} %)',
                kst_gewst['gewst']
            )
            st.metric('Steuerbelastung gesamt',
                      formatiere_betrag(kst_gewst['steuer_gesamt']))

        st.divider()

        for q in [1, 2, 3, 4]:
            if ust['quartalsergebnisse'].get(q):
                ust[f'vz_q{q}'] = vorauszahlungen[q]

        pdf_bytes = exportiere_jahressteuer(eur, ust, kst_gewst)
        st.download_button(
            label='📥 Jahressteuer als PDF exportieren',
            data=pdf_bytes,
            file_name=f'talKIT_Jahressteuer_{gewaehltes_jahr}.pdf',
            mime='application/pdf',
        )
