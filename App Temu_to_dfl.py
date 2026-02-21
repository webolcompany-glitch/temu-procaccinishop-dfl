import streamlit as st
import pandas as pd
import math
from io import BytesIO
import sys
import subprocess

# Assicurati che openpyxl sia installato
try:
    import openpyxl
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl"])
    import openpyxl

# -----------------------------
# Funzioni di supporto
# -----------------------------
def calcola_peso_volumetrico(volume_m3, coeff=5000):
    if pd.isna(volume_m3):
        return 0
    volume_cm3 = volume_m3 * 1_000_000
    return volume_cm3 / coeff

def calcola_spedizione(peso):
    if peso <= 2:
        return 5.71
    elif peso <= 3:
        return 5.81
    elif peso <= 5:
        return 7.02
    elif peso <= 10:
        return 9.66
    elif peso <= 25:
        return 13.92
    elif peso <= 49:
        return 21.73
    else:
        return None

def arrotondamento_psicologico(prezzo):
    return math.ceil(prezzo) - 0.01

# -----------------------------
# Streamlit UI
# -----------------------------
st.title("Generatore Listino Temu")

uploaded_file = st.file_uploader("Carica il file fornitore (CSV o Excel)", type=['csv','xlsx'])
markup = st.number_input("Inserisci markup %", min_value=0.0, max_value=100.0, value=20.0, step=0.1)

if uploaded_file:
    # Lettura file
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file, engine='openpyxl')
    except Exception as e:
        st.error(f"Errore lettura file: {e}")
    
    # -----------------------------
    # Filtri preliminari
    # -----------------------------
    df = df.dropna(subset=['PrezzoNetto', 'PesoPezzoKg'])
    df = df[df['PrezzoNetto'] > 0]
    df = df[df['Disponibilita'].isin(['Disponibile'])]

    # -----------------------------
    # Calcolo Peso Totale e volumetrico con MV
    # -----------------------------
    df['MV'] = df['MV'].fillna(1)
    df['PesoTot'] = df['PesoPezzoKg'] * df['MV']
    df['VolumeTot'] = df['VolumeMt3'].fillna(0) * df['MV']
    
    df['PesoVolumetrico'] = df['VolumeTot'].apply(calcola_peso_volumetrico)
    df['PesoSpedizione'] = df[['PesoTot','PesoVolumetrico']].max(axis=1)
    
    # Esclusione prodotti troppo pesanti
    df = df[df['PesoSpedizione'] <= 49]
    
    # -----------------------------
    # Calcolo spedizione
    # -----------------------------
    df['Spedizione'] = df['PesoSpedizione'].apply(calcola_spedizione)
    
    # -----------------------------
    # Prezzo Base
    # -----------------------------
    df['PrezzoNettoEff'] = df['PrezzoNetto'] * df['MV']
    df['IVA'] = df['PrezzoNettoEff'] * 0.22
    df['PrezzoBase'] = df['PrezzoNettoEff'] + df['IVA'] + df['Spedizione']
    
    # -----------------------------
    # Applicazione markup (UNA SOLA VOLTA)
    # -----------------------------
    df['PrezzoFinale'] = df['PrezzoBase'] * (1 + markup / 100)
    df['PrezzoFinale'] = df['PrezzoFinale'].apply(arrotondamento_psicologico)
    
    # -----------------------------
    # Prezzo Temu (nessun markup aggiuntivo)
    # -----------------------------
    df['PrezzoTemu'] = (df['PrezzoFinale'] / 1.22) * 0.85
    
    # -----------------------------
    # Mappatura colonne Temu
    # -----------------------------
    def genera_nome_articolo(row):
        if row['MV'] > 1:
            return f"x{int(row['MV'])} {row['TitoloModello']}"
        else:
            return row['TitoloModello']
    
    df_out = pd.DataFrame()
    df_out['Nome dell\'Articolo'] = df.apply(genera_nome_articolo, axis=1)
    df_out['outGoodsSn'] = 'DFL_' + df['CodiceArticolo'].astype(str)
    df_out['outSkuSn'] = 'DFL_' + df['CodiceArticolo'].astype(str)
    df_out['Descrizione dell\'articolo'] = df['DescrizioneEstesa']
    df_out['Punto elenco 1'] = 'Spedizioni in 24/48 ore dall\'Italia'
    df_out['Punto elenco 2'] = 'Modello:' + df['Modello'].astype(str)
    df_out['Punto elenco 3'] = df['DescrizioneEstesa']
    df_out['URL delle immagini dei dettagli'] = df['LinkImmagine']
    df_out['Tema della variante'] = 'Modello'
    df_out['Modello'] = df['Modello']
    df_out['URL delle immagini SKU'] = df['LinkImmagine']
    df_out['Quantità'] = 10
    df_out['Prezzo base - EUR'] = df['PrezzoTemu'].round(2)
    df_out['Prezzo di listino - EUR'] = df['PrezzoFinale'].round(2)
    df_out['Peso pacco - g'] = (df['PesoPezzoKg'] * 1000).round(0)
    df_out['Lunghezza - cm'] = 30
    df_out['Larghezza - cm'] = 30
    df_out['Altezza - cm'] = 30
    
    # -----------------------------
    # Download Excel
    # -----------------------------
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_out.to_excel(writer, index=False, sheet_name='ListinoTemu')
    output.seek(0)
    
    st.download_button(
        label="Scarica listino Temu (Excel)",
        data=output,
        file_name='listino_temu.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    
    st.success("Listino generato con successo! ✅")
