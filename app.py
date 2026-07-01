# -*- coding: utf-8 -*-
"""
app.py – talKIT Steuermodul
Streamlit-Oberfläche für die Steuervorbereitung.
"""

import streamlit as st
import pandas as pd
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

st.markdown("""
<style>
    .main { max-width: 760px; margin: 0 auto; }
    .stAlert { border-radius: 6px; }
    div[data-testid="metric-container"] {
        background: #F5F7FA;
        border: 1px solid #D0D7E3;
        border-radius: 6px;
        padding: 12px 16px;
    }
    h1 { color: #1A1A2E; }
    h2, h3 { color: #4A90D9; }
    .elster-zeile {
        font-family: monospace;
        background: #F5F7FA;
        padding: 4px 8px;
        border-left: 3px solid #4A90D9;
        margin: 2px 0;
    }
</style>
""", unsafe_allow_html=True)


# ── HILFSFUNKTIONEN ───────────────────────────────────────────────────────────

def formatiere_betrag(wert: float) -> str:
    return f'{wert:,.2f} €'.replace(',', 'X').replace('.', ',').replace('X', '.')


def zeige_elster_zeile(zeilen_nr: str, bezeichnung: str, wert: float):
    """Einheitliche Darstellung einer Elster-Zeile."""
    st.markdown(
        f'<div class="elster-zeile">'
        f'<span style="color:#888;font-size:0.8em;">Zeile {zeilen_nr}</span><br>'
        f'<b>{bezeichnung}</b> &nbsp; '
        f'<span style="float:right;font-size:1.1em;">{formatiere_betrag(wert)}</span>'
        f'</div>',
        unsafe_allow_html=True
    )


# ── SCHRITT 1: UPLOAD ─────────────────────────────────────────────────────────

st.title('talKIT Steuermodul')
st.caption('Vorbereitung der Steuerunterlagen auf Basis des Podio-Exports')

st.divider()

uploaded_file = st.file_uploader(
    'Podio-Export hochladen',
    type=['xlsx'],
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
            st.stop()
        df_roh = pd.read_excel(xls, sheet_name=xls.sheet_names[0])
    except Exception as e:
        st.error(f'Datei konnte nicht eingelesen werden: {e}')
        st.stop()

# Spaltenprüfung
fehlende = pruefe_spalten(df_roh)
if fehlende:
    st.error(
        'Die folgenden Pflicht-Spalten fehlen in der Datei. '
        'Bitte prüfe den Podio-Export:\n\n' +
        '\n'.join(f'- `{s}`' for s in fehlende)
    )
    st.stop()

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
                        'Bitte in Podio prüfen und korrigieren:**')
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
            st.button('Abbrechen', type='primary',
                      on_click=lambda: st.session_state.clear())

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

    # Vorschlag: Quartal mit den meisten Buchungen
    vorschlag = zeitraeume.sort_values('Buchungen', ascending=False).iloc[0]
    vorschlag_q = int(vorschlag['Quartal'])
    vorschlag_j = int(vorschlag['Jahr'])

    verfuegbare_jahre = sorted(zeitraeume['Jahr'].unique().tolist(), reverse=True)
    verfuegbare_quartale = [1, 2, 3, 4]

    col1, col2 = st.columns(2)
    with col1:
        gewaehltes_jahr = st.selectbox(
            'Jahr', options=verfuegbare_jahre,
            index=verfuegbare_jahre.index(vorschlag_j)
        )
    with col2:
        gewaehltes_quartal = st.selectbox(
            'Quartal', options=verfuegbare_quartale,
            index=vorschlag_q - 1,
            format_func=lambda q: f'Q{q}'
        )

    # Buchungsanzahl für gewählten Zeitraum
    treffer = zeitraeume[
        (zeitraeume['Jahr'] == gewaehltes_jahr) &
        (zeitraeume['Quartal'] == gewaehltes_quartal)
    ]
    if not treffer.empty:
        anzahl = int(treffer.iloc[0]['Buchungen'])
        st.caption(
            f'ℹ️ Vorschlag basierend auf deinen Daten: '
            f'Q{vorschlag_q} {vorschlag_j} ({int(vorschlag["Buchungen"])} Buchungen) · '
            f'Gewählt: Q{gewaehltes_quartal} {gewaehltes_jahr} ({anzahl} Buchungen)'
        )
    else:
        st.warning(
            f'Keine Buchungen für Q{gewaehltes_quartal} {gewaehltes_jahr} gefunden.'
        )

    # Alle verfügbaren Zeiträume
    with st.expander('Alle Zeiträume in der Datei'):
        anzeige = zeitraeume.copy()
        anzeige['Quartal'] = anzeige['Quartal'].apply(lambda q: f'Q{q}')
        st.dataframe(anzeige, use_container_width=True, hide_index=True)

    st.divider()

    # ── SCHRITT 6A: BERECHNUNG VORANMELDUNG ──────────────────────────────────

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
            if zahllast > 0:
                st.metric('Interne Zahllast (Kontrolle)', formatiere_betrag(zahllast),
                          help='Zahlung ans Finanzamt. Positiv = du zahlst.')
            else:
                st.metric('Interne Zahllast (Kontrolle)', formatiere_betrag(zahllast),
                          help='Erstattung vom Finanzamt. Negativ = du bekommst Geld zurück.')

            st.caption(
                'Die Zahllast ist eine interne Kontrollgröße. '
                'Maßgeblich sind die Zeilen 13–38 im Elster-Formular.'
            )

            # PDF-Export
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

    # Vollständigkeitsprüfung
    jahr_info = zeitraeume[zeitraeume['Jahr'] == gewaehltes_jahr]
    vorhandene_quartale = sorted(jahr_info['Quartal'].tolist())
    ist_vollstaendig = len(vorhandene_quartale) == 4

    if ist_vollstaendig:
        st.success(f'✅ {gewaehltes_jahr}: Alle 4 Quartale vorhanden.')
    else:
        fehlende_q = [q for q in [1, 2, 3, 4] if q not in vorhandene_quartale]
        st.warning(
            f'⚠️ {gewaehltes_jahr} ist unvollständig – '
            f'fehlende Quartale: {", ".join(f"Q{q}" for q in fehlende_q)}. '
            f'Die Jahressteuererklärung wird nur auf Basis der vorhandenen Daten berechnet.'
        )

    st.divider()

    # ── SCHRITT 5: VORAUSZAHLUNGEN ────────────────────────────────────────────

    st.subheader('Geleistete USt-Vorauszahlungen')
    st.caption(
        'Trage hier die tatsächlich abgeführten Beträge ein. '
        'Positiver Wert = Zahlung ans Finanzamt · Negativer Wert = Rückzahlung vom Finanzamt'
    )

    col1, col2 = st.columns(2)
    col3, col4 = st.columns(2)
    with col1:
        vz_q1 = st.number_input('Q1', value=0.0, step=0.01, format='%.2f',
                                 key='vz_q1', help='Positiv = gezahlt, Negativ = erstattet')
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

        # EÜR
        eur = berechne_eur(df, jahr=gewaehltes_jahr)
        # USt Jahres
        ust = berechne_ust_jahres(df, jahr=gewaehltes_jahr, vorauszahlungen=vorauszahlungen)

        if eur is None or ust is None:
            st.error(f'Keine ausreichenden Daten für das Jahr {gewaehltes_jahr}.')
            st.stop()

        # KSt/GewSt
        kst_gewst = berechne_kst_gewst(eur, jahr=gewaehltes_jahr)

        # ── EÜR Ausgabe ──
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
            f'Gewinn / Verlust Sphäre D (Zeile 75)',
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

        st.markdown('**Quartalskontrolle**')
        q_data = []
        for q in [1, 2, 3, 4]:
            q_erg = ust['quartalsergebnisse'].get(q)
            if q_erg:
                zahllast = q_erg['zahllast_kontrolle']
                vz = vorauszahlungen[q]
                q_data.append({
                    'Quartal': f'Q{q}',
                    'Zahllast berechnet': formatiere_betrag(zahllast),
                    'Vorauszahlung geleistet': formatiere_betrag(vz),
                    'Differenz': formatiere_betrag(zahllast - vz),
                })
            else:
                q_data.append({
                    'Quartal': f'Q{q}', 'Zahllast berechnet': '–',
                    'Vorauszahlung geleistet': '–', 'Differenz': '–'
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
                st.metric('Brutto-Einnahmen D', formatiere_betrag(kst_gewst['brutto_einnahmen_d']))
            with col2:
                st.metric('Gewinn D', formatiere_betrag(kst_gewst['gewinn_d']))
            with col3:
                st.metric('Zu versteuern', formatiere_betrag(kst_gewst['zu_versteuernder_gewinn']))

            st.markdown('**Körperschaftsteuer**')
            zeige_elster_zeile('–', 'Körperschaftsteuer 15 %', kst_gewst['kst'])
            zeige_elster_zeile('–', 'Solidaritätszuschlag (5,5 % auf KSt)', kst_gewst['solz'])
            zeige_elster_zeile('–', 'KSt gesamt', kst_gewst['kst_gesamt'])

            st.markdown('**Gewerbesteuer**')
            zeige_elster_zeile('–', 'Steuermessbetrag (× 3,5 %)', kst_gewst['gewst_messbetrag'])
            zeige_elster_zeile(
                '–',
                f'Gewerbesteuer (Hebesatz {kst_gewst["gewst_hebesatz_prozent"]} %)',
                kst_gewst['gewst']
            )
            st.metric('Steuerbelastung gesamt', formatiere_betrag(kst_gewst['steuer_gesamt']))

        st.divider()

        # ── PDF-Export ────────────────────────────────────────────────────────
        # Vorauszahlungen für Quartalstabelle im PDF mitgeben
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
