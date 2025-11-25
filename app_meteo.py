import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import MultipleLocator
from datetime import date, timedelta
import io
import sys
import numpy as np # Mantenuto solo se utile per le funzioni di plotting

# --- CONFIGURAZIONI GLOBALI ---
st.set_page_config(layout="wide", page_title="Meteogrammi") 
plt.rcParams['figure.dpi'] = 300 
plt.rcParams['figure.figsize'] = [12, 28] 
try:
    plt.style.use('seaborn-v0_8-darkgrid')
except:
    plt.style.use('ggplot')

# --- FUNZIONI DI SERVIZIO ---

@st.cache_data
def get_coordinates_from_city(city_name):
    """Cerca una città e restituisce Lat, Lon, Nome e Altitudine."""
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": city_name, "count": 1, "language": "it", "format": "json"}
    try:
        response = requests.get(url, params=params)
        data = response.json()
        if "results" in data:
            result = data["results"][0]
            # Percorso di SUCCESSO: Restituisce 5 valori
            return result["latitude"], result["longitude"], result["name"], result.get("country", ""), result.get("elevation", 0)
        else:
            # Percorso di FALLIMENTO (Città non trovata): Restituisce 5 valori
            return None, None, None, None, 0
    except Exception:
        # Percorso di ECCEZIONE (Errore di rete): Restituisce 5 valori
        return None, None, None, None, 0

@st.cache_data(ttl=3600)
def fetch_and_process_data(LAT, LON, start_d, end_d):
    """
    Scarica i dati meteo, trova la lunghezza minima comune e crea il DataFrame.
    (FIX: Isola e allinea gli array per prevenire ValueError)
    """

    url = "https://api.open-meteo.com/v1/forecast"
    
    params = {
        "latitude": LAT,
        "longitude": LON,
        "hourly": "temperature_2m,dew_point_2m,relative_humidity_2m,cloud_cover_low,cloud_cover_mid,cloud_cover_high,surface_pressure,wind_speed_10m,wind_direction_10m,wind_gusts_10m,rain,snowfall,freezing_level_height",
        "timezone": "Europe/Rome",
        "start_date": start_d.strftime("%Y-%m-%d"),
        "end_date": end_d.strftime("%Y-%m-%d"),
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Errore API Meteo: {e}")
        return None

    hourly = data['hourly']
    
    # --- 1. CONTROLLO E TRONCAMENTO ALLA LUNGHEZZA MINIMA ---
    array_lengths = [len(v) for k, v in hourly.items() if k not in ['time', 'interval']]
    
    if not array_lengths:
        st.error("L'API non ha restituito dati validi. Prova a modificare le date.")
        return None
        
    min_length = min(array_lengths)

    # Crea un DataFrame temporaneo con gli array troncati per facilità di calcolo
    df_temp = pd.DataFrame({
        'time': pd.to_datetime(hourly['time'][:min_length]),
        'temp': hourly['temperature_2m'][:min_length],
        'dew_point': hourly['dew_point_2m'][:min_length],
        'humidity': hourly['relative_humidity_2m'][:min_length],
        'clouds_low': hourly['cloud_cover_low'][:min_length],
        'clouds_mid': hourly['cloud_cover_mid'][:min_length],
        'clouds_high': hourly['cloud_cover_high'][:min_length],
        'pressure': hourly['surface_pressure'][:min_length],
        'wind_speed': hourly['wind_speed_10m'][:min_length],
        'wind_gusts': hourly['wind_gusts_10m'][:min_length],
        'wind_dir': hourly['wind_direction_10m'][:min_length],
        'rain': hourly['rain'][:min_length],
        'snowfall': hourly['snowfall'][:min_length],
        'freezing_lvl': hourly['freezing_level_height'][:min_length],
    })
    
    # 2. CALCOLO FINALE E RETURN
    
    # Calcolo Total Clouds (operazione su serie allineate)
    df_temp['clouds_total'] = df_temp['clouds_low'] + df_temp['clouds_mid'] + df_temp['clouds_high']
    
    df_temp['accumulated_rain'] = df_temp['rain'].cumsum()
    df_temp['accumulated_snow'] = df_temp['snowfall'].cumsum()
    
    # Applicazione del filtro data e ritorno
    df_temp = df_temp[(df_temp['time'] >= start_d.strftime("%Y-%m-%d")) & (df_temp['time'] <= end_d.strftime("%Y-%m-%d") + " 23:59:59")]
    return df_temp
    min_length = min(array_lengths)

    # Tronca tutti gli array alla lunghezza minima per forzare l'allineamento
    df = pd.DataFrame({
        'time': pd.to_datetime(hourly['time'][:min_length]),
        'temp': hourly['temperature_2m'][:min_length],
        'dew_point': hourly['dew_point_2m'][:min_length],
        'humidity': hourly['relative_humidity_2m'][:min_length],
        'clouds_low': hourly['cloud_cover_low'][:min_length],
        'clouds_mid': hourly['cloud_cover_mid'][:min_length],
        'clouds_high': hourly['cloud_cover_high'][:min_length],
        'pressure': hourly['surface_pressure'][:min_length],
        'wind_speed': hourly['wind_speed_10m'][:min_length],
        'wind_gusts': hourly['wind_gusts_10m'][:min_length],
        'wind_dir': hourly['wind_direction_10m'][:min_length],
        'rain': hourly['rain'][:min_length],
        'snowfall': hourly['snowfall'][:min_length],
        'freezing_lvl': hourly['freezing_level_height'][:min_length],
        
        # Calcoli Necessari per Grafici
        'clouds_total': hourly['cloud_cover_low'][:min_length] + hourly['cloud_cover_mid'][:min_length] + hourly['cloud_cover_high'][:min_length],
    })
    
    df['accumulated_rain'] = df['rain'].cumsum()
    df['accumulated_snow'] = df['snowfall'].cumsum()
    
    df = df[(df['time'] >= start_d.strftime("%Y-%m-%d")) & (df['time'] <= end_d.strftime("%Y-%m-%d") + " 23:59:59")]
    return df
        
    min_length = min(array_lengths)

    # Tronca tutti gli array alla lunghezza minima per forzare l'allineamento
    df = pd.DataFrame({
        'time': pd.to_datetime(hourly['time'][:min_length]),
        'temp': hourly['temperature_2m'][:min_length],
        'dew_point': hourly['dew_point_2m'][:min_length],
        'humidity': hourly['relative_humidity_2m'][:min_length],
        # MANTENUTI STRATI NUVOLOSI PER PLOTTING
        'clouds_low': hourly['cloud_cover_low'][:min_length],
        'clouds_mid': hourly['cloud_cover_mid'][:min_length],
        'clouds_high': hourly['cloud_cover_high'][:min_length],
        'pressure': hourly['surface_pressure'][:min_length],
        'wind_speed': hourly['wind_speed_10m'][:min_length],
        'wind_gusts': hourly['wind_gusts_10m'][:min_length],
        'wind_dir': hourly['wind_direction_10m'][:min_length],
        'rain': hourly['rain'][:min_length],
        'snowfall': hourly['snowfall'][:min_length],
        'freezing_lvl': hourly['freezing_level_height'][:min_length]
    })
    
    # Calcolo Total Clouds e Cumulative per i grafici
    df['clouds_total'] = df['clouds_low'] + df['clouds_mid'] + df['clouds_high']
    df['accumulated_rain'] = df['rain'].cumsum()
    df['accumulated_snow'] = df['snowfall'].cumsum()
    
    df = df[(df['time'] >= start_d.strftime("%Y-%m-%d")) & (df['time'] <= end_d.strftime("%Y-%m-%d") + " 23:59:59")]
    return df

# --- 4. PLOTTING ---
def plot_meteogram(df, location_label, start_s, end_s, altitude):
    # Setup Grafico
    plt.rcParams['figure.dpi'] = 300 
    plt.rcParams['figure.figsize'] = [12, 28] 

    try:
        plt.style.use('seaborn-v0_8-darkgrid')
    except:
        plt.style.use('ggplot')
        
    fig, (ax1, ax2, ax3, ax4, ax5, ax6) = plt.subplots(6, 1, sharex=True)
    
    # Aumento la spaziatura verticale tra i subplots a 1.2 (separazione massima)
    plt.subplots_adjust(hspace=1.2) 
    
    # Manteniamo y=0.99 per separare il titolo dal primo subplot
    fig.suptitle(f'Previsioni: {location_label}\nDal {start_s.strftime("%Y-%m-%d")} al {end_s.strftime("%Y-%m-%d")}', 
                 fontsize=18, 
                 fontweight='bold',
                 y=0.94) 

    # --- Parametri Legenda (Separazione max) ---
    LEGEND_BBOX = (0.5, -0.55) # Spinge la legenda molto in basso, fuori dall'area del grafico
    LEGEND_LOC = 'upper center'

    # 1. TEMPERATURA 
    ax1.plot(df['time'], df['temp'], color='#d62728', marker='.', markersize=4, label='Temperatura')
    ax1.plot(df['time'], df['dew_point'], color='#1f77b4', linestyle='--', label='Temperatura di rugiada')
    ax1.axhline(0, color='gray', linestyle='-', linewidth=1) 
    ax1.yaxis.set_major_locator(MultipleLocator(5))
    ax1.set_title('1. Temperatura °C', loc='left', fontweight='bold')
    ax1.set_ylabel('°C')
    # MODIFICA: Legenda sotto il grafico
    ax1.legend(loc=LEGEND_LOC, bbox_to_anchor=LEGEND_BBOX, frameon=True, ncol=2) 
    ax1.grid(True, axis='y', which='major', linestyle='-', alpha=0.5, color='gray') 

    # 2. NUVOLE (Stackplot originale corretto)
    ax2.stackplot(df['time'], df['clouds_low'], df['clouds_mid'], df['clouds_high'], 
                  labels=['Basse', 'Medie', 'Alte'], colors=['#5f5f5f', '#969696', '#cccccc'], alpha=0.6)
    ax2.set_ylim(0, 105)
    ax2_twin = ax2.twinx() 
    ax2_twin.plot(df['time'], df['humidity'], color='blue', linestyle=':', label='Umidità')
    ax2_twin.set_ylim(0, 105) 
    ax2.set_ylabel('% Copertura')
    ax2_twin.set_ylabel('% Umidità', color='blue')
    ax2.set_title('2. Strati Nuvole (Basse/Medie/Alte)', loc='left', fontweight='bold')
    # MODIFICA: Legenda sotto il grafico
    ax2.legend(loc=LEGEND_LOC, bbox_to_anchor=LEGEND_BBOX, frameon= True, ncol=3)
    ax2.grid(True, axis='y', which='major', linestyle='-', alpha=0.5, color='gray') 

# 3. PRECIPITAZIONI 
    bar_width = 0.035 
    ax3_twin = ax3.twinx()
    
    # 2. PLOT HOURLY BARS (On the Left/Primary Axis: ax3)
    ax3.bar(df['time'], df['rain'], width=bar_width, color='#17becf', label='Pioggia oraria (mm)', align='center', alpha=0.9)
    ax3.bar(df['time'], df['snowfall'], width=bar_width, bottom=df['rain'], color='pink', label='Neve oraria (cm)', align='center', alpha=0.95)

    # 3. PLOT ACCUMULATION LINES (On the Right/Secondary Axis: ax3_twin)
    ax3_twin.plot(df['time'], df['accumulated_rain'], color='#007fbf', label='Accumulo pioggia (mm)', linewidth=2)
    ax3_twin.plot(df['time'], df['accumulated_snow'], color='#800080', label='Accumulo neve (cm)', linestyle='-', linewidth=2)

    # 4. SCALATURA E ETICHETTE (omissis)
    max_total_accum = df['accumulated_rain'].max() + df['accumulated_snow'].max()
    ax3_twin.set_ylim(0, max(10, max_total_accum * 1.1)) 
    ax3_twin.set_ylabel('') 
    ax3_twin.set_yticks([]) 
    ax3_twin.grid(False) 
    ax3.set_ylim(0, df['rain'].max() * 1.5 + df['snowfall'].max() * 1.5 + 1)
    ax3.set_ylabel('Quantità Oraria (mm/cm)', color='black')
    ax3.yaxis.set_major_locator(MultipleLocator(2)) 
    ax3_twin.axhline(0, color='gray', linewidth=0.5, zorder=0)

    # 5. TESTO CUMULATO (omissis)
    total_rain = df['accumulated_rain'].iloc[-1]
    total_snow = df['accumulated_snow'].iloc[-1]
    start_date_text = start_s.strftime('%d/%m')
    end_date_text = end_s.strftime('%d/%m')
    cumulative_text = f"Totale cumulato ({start_date_text} - {end_date_text}):\n"
    cumulative_text += f"💧 Pioggia: {total_rain:.1f} mm\n"
    cumulative_text += f"❄️ Neve: {total_snow:.1f} cm"
    ax3.text(0.98, 0.95, cumulative_text, 
             transform=ax3.transAxes, 
             horizontalalignment='right', 
             verticalalignment='top', 
             bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', boxstyle='round,pad=0.5'),
             fontsize=10, 
             fontweight='bold',
             color='gray')

    # 6. LEGENDS - COMBINATE
    ax3.set_title('3. Precipitazioni orarie e accumulo cumulativo', loc='left', fontweight='bold')
    h1, l1 = ax3.get_legend_handles_labels()
    h2, l2 = ax3_twin.get_legend_handles_labels()
    
    # MODIFICA: Legenda combinata sotto il grafico
    ax3.legend(h1 + h2, l1 + l2, 
               loc=LEGEND_LOC, 
               bbox_to_anchor=LEGEND_BBOX, frameon = True, ncol=4) 
    ax3.grid(True, axis='y', which='major', linestyle='-', alpha=0.5, color='gray')

    # 4. VENTO
    ax4.plot(df['time'], df['wind_speed'], color='#2ca02c', label='Velocità Media', linewidth=2)
    ax4.plot(df['time'], df['wind_gusts'], color="#001fce", linestyle='--', label='Raffiche', linewidth=1.5)
    ax4_twin = ax4.twinx()
    ax4_twin.scatter(df['time'], df['wind_dir'], color='purple', s=15, label='Direz.')
    ax4.yaxis.set_major_locator(MultipleLocator(10))
    ax4.set_ylabel('km/h')
    ax4_twin.set_yticks([0, 90, 180, 270, 360])
    ax4_twin.set_yticklabels(['N', 'E', 'S', 'W', 'N'])
    ax4.set_title('4. Vento e raffiche', loc='left', fontweight='bold')
    
    h1, l1 = ax4.get_legend_handles_labels()
    h2, l2 = ax4_twin.get_legend_handles_labels()
    
    # MODIFICA: Legenda sotto il grafico
    ax4.legend(h1 + h2, l1 + l2, 
               loc=LEGEND_LOC, 
               bbox_to_anchor=LEGEND_BBOX, frameon = True,
               ncol=3) 
    ax4.grid(True, axis='y', which='major', linestyle='-', alpha=0.5, color='gray') 

  # 5. PRESSIONE ATMOSFERICA
    p_min_data = df['pressure'].min()
    p_max_data = df['pressure'].max()
    ax5.set_ylim(p_min_data - 5, p_max_data + 5)
    ax5.plot(df['time'], df['pressure'], color='orange', linewidth=2, label='Pressione (MSL)')
    ax5.yaxis.set_major_locator(MultipleLocator(2)) 
    ax5.set_ylabel('hPa')
    ax5.set_title('5. Pressione atmosferica', loc='left', fontweight='bold')
    ax5.axhline(1013, color='red', linestyle=':', alpha=0.6, label='1013 hPa')
    # MODIFICA: Legenda sotto il grafico
    ax5.legend(loc=LEGEND_LOC, bbox_to_anchor=LEGEND_BBOX, frameon = True,  ncol=2)
    ax5.grid(True, axis='y', which='major', linestyle='-', alpha=0.5, color='gray') 

    # 6. ZERO TERMICO
    ax6.plot(df['time'], df['freezing_lvl'], color='red', label='Zero Termico')
    ax6.axhline(altitude, color='blue', linestyle='--', alpha=0.6, label=f'Altitudine loc. ({altitude:.0f}m)')
    ax6.set_ylabel('Metri')
    ax6.set_title('6. Quota zero termico', loc='left', fontweight='bold')
    # MODIFICA: Legenda sotto il grafico
    ax6.legend(loc=LEGEND_LOC, bbox_to_anchor=LEGEND_BBOX, frameon = True,  ncol=2)
    ax6.grid(True, axis='y', which='major', linestyle='-', alpha=0.5, color='gray') 

   # --- FORMATTAZIONE GLOBALE (CON LOCATOR DINAMICO) ---
    all_axes = [ax1, ax2, ax3, ax4, ax5, ax6] 
    
    # 1. Definizione di un Formatter Personalizzato
    class CustomDateFormatter(mdates.DateFormatter):
        def __call__(self, x, pos=0):
            dt = mdates.num2date(x, self.tz)
            if dt.hour == 0:
                return dt.strftime('%d %b %H:%M') 
            else:
                return dt.strftime('%H:%M') 

    # 2. CALCOLO E DEFINIZIONE DEL LOCATOR DINAMICO
    duration_days = (end_s - start_s).days + 1 
    
    if duration_days <= 1:
        tick_interval = 1 
    elif duration_days <= 3:
        tick_interval = 3 
    else:
        tick_interval = 6 
        
    for ax in all_axes:
        ax.grid(True, axis='y', which='major', linestyle='-', alpha=0.5, color='gray')
        ax.grid(False, axis='x')
        
        # 3. FREQUENZA DELLE ETICHETTE: USA IL VALORE DINAMICO CALCOLATO
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=tick_interval))
        
        # 4. FORMATTAZIONE DEL TESTO: Applica il formatter personalizzato
        ax.xaxis.set_major_formatter(CustomDateFormatter('%d %b %H:%M'))
        
        ax.tick_params(labelbottom=True) 
        ax.tick_params(axis='x', labelsize=10, rotation=65) 

    # IMPORTANTE: tight_layout forza l'adattamento della figura alle legende esterne
    #plt.tight_layout()

    return fig

   # --- FORMATTAZIONE GLOBALE (CON LOCATOR DINAMICO) ---
    all_axes = [ax1, ax2, ax3, ax4, ax5, ax6] 
    
    # 1. Definizione di un Formatter Personalizzato
    class CustomDateFormatter(mdates.DateFormatter):
        def __call__(self, x, pos=0):
            dt = mdates.num2date(x, self.tz)
            if dt.hour == 0:
                # Se è mezzanotte, mostra Giorno, Mese e Ora:Minuto (su una riga)
                return dt.strftime('%d %b %H:%M') 
            else:
                # Altrimenti, mostra solo l'Ora:Minuto
                return dt.strftime('%H:%M') 

    # 2. CALCOLO E DEFINIZIONE DEL LOCATOR DINAMICO
    duration_days = (end_s - start_s).days + 1 
    
    if duration_days <= 1:
        tick_interval = 1 # Ogni 1 ora
    elif duration_days <= 3:
        tick_interval = 3 # Ogni 3 ore
    else:
        tick_interval = 6 # Ogni 6 ore
        
    for ax in all_axes:
        ax.grid(True, axis='y', which='major', linestyle='-', alpha=0.5, color='gray')
        ax.grid(False, axis='x')
        
        # 3. FREQUENZA DELLE ETICHETTE: USA IL VALORE DINAMICO CALCOLATO
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=tick_interval))
        
        # 4. FORMATTAZIONE DEL TESTO: Applica il formatter personalizzato
        ax.xaxis.set_major_formatter(CustomDateFormatter('%d %b %H:%M'))
        
        ax.tick_params(labelbottom=True) 
        # Rotazione a 65 gradi (Mantenuta)
        ax.tick_params(axis='x', labelsize=10, rotation=65) 

    # IMPORTANTE: tight_layout è essenziale per forzare l'adattamento della figura alle legende esterne
    #plt.tight_layout()

    return fig

  # --- FORMATTAZIONE GLOBALE (Modifica) ---
    all_axes = [ax1, ax2, ax3, ax4, ax5, ax6] 
    
    # 1. Definizione di un Formatter Personalizzato
    # Questa classe controlla se l'ora è 00 per stampare giorno e mese.
    class CustomDateFormatter(mdates.DateFormatter):
        def __call__(self, x, pos=0):
            dt = mdates.num2date(x, self.tz)
            if dt.hour == 0:
                # Se è mezzanotte, mostra Giorno e Ora
                return dt.strftime('%d %b %H:%M')
            else:
                # Altrimenti, mostra solo l'Ora
                return dt.strftime('%H:%M')

    for ax in all_axes:
        ax.grid(True, axis='y', which='major', linestyle='-', alpha=0.5, color='gray')
        ax.grid(False, axis='x')
        
        # 2. FREQUENZA DELLE ETICHETTE: IMPOSTATA A OGNI 3 ORE
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=3))
        
        # 3. FORMATTAZIONE DEL TESTO: Applica il formatter personalizzato
        ax.xaxis.set_major_formatter(CustomDateFormatter('%d %b\n%H'))
        
        ax.tick_params(labelbottom=True) 
        # Rotazione a 45 gradi (mantenuta)
        ax.tick_params(axis='x', labelsize=9, rotation=60) 

    # Aggiungere un layout stretto per gestire la rotazione e la densità delle etichette
    #plt.tight_layout()

    return fig





# --- INTERFACCIA UTENTE ---
st.title("🌍 Meteogrammi per tutte le località")
st.markdown("Analisi dei vari parametri meteorologici.")


# Inizializzazione per prevenire NameError
btn_generate = False
stop_exec = False
location_altitude = 0 # INIZIALIZZAZIONE AGGIUNTA
final_lat = None
final_lon = None
location_name = "Località"
today = date.today()
default_end_date = today + timedelta(days=2)


# --- INPUT SECTION 
st.header("1. Dove?")
search_method = st.radio("Metodo:", ["🔍 Cerca località", "📍 Coordinate"])

if search_method == "🔍 Cerca località":
    city_input = st.text_input("Inserisci il nome della località", "")
    if city_input:
        lat_f, lon_f, name_f, country_f, altitude_f = get_coordinates_from_city(city_input)
        if lat_f:
            st.success(f"📍 {name_f} ({country_f})")
            final_lat = lat_f
            final_lon = lon_f
            location_name = name_f
            location_altitude = altitude_f # <--- CORREZIONE: Altitudine della località assegnata
            # (Altitudine viene usata dal plot)
        else:
            st.error("Città non trovata.")
else:
    # --- MODIFICA APPLICATA QUI: default a 0.0 ---
    final_lat = st.number_input("Latitudine", value=0.0, format="%.4f")
    final_lon = st.number_input("Longitudine", value=0.0, format="%.4f")
    location_name = st.text_input("Nome località", "Località")
    # L'altitudine viene prelevata dall'input manuale se usi le coordinate
    location_altitude = st.number_input("Altitudine in metri (per grafico 6)", value=0, step=10)


# Separazione tra le sezioni
st.text("") 
st.markdown("---")
st.text("") 

st.header("2. Quando?")

col1, col2 = st.columns(2)

start_date = col1.date_input("Dal:", today, key="start_date_input", format="DD/MM/YYYY")
end_date = col2.date_input("Al:", default_end_date, key="end_date_input", format="DD/MM/YYYY")

if start_date > end_date:
    st.error("Date non valide!")
    stop_exec = True
else:
    stop_exec = False

# Separazione prima del pulsante
st.text("") 
st.markdown("---")
st.text("") 
st.text("") 
st.text("") 

btn_generate = st.button("Genera previsione", type="primary")



# --- OUTPUT ---
if btn_generate and not stop_exec:
    if final_lat is None:
        st.error("Coordinate non valide.")
    else:
        st.subheader(f"Analisi per: {location_name}")
        with st.spinner("Elaborazione dati e generazione griglie..."):
            df_meteo = fetch_and_process_data(final_lat, final_lon, start_date, end_date)

            if df_meteo is not None and not df_meteo.empty:
                
                # 1. Genera e mostra il grafico (UNICO OUTPUT)
                st.subheader(f"Grafico Dettagliato")
                fig = plot_meteogram(df_meteo, location_name, start_date, end_date, location_altitude)
                st.pyplot(fig)

                st.markdown("---")
                st.subheader("📥 Area Download")
                col_dl1, col_dl2 = st.columns(2)

                # Download Vettoriale (SVG)
                fn_svg = f"meteo_{location_name}.svg"
                img_svg = io.BytesIO()
                fig.savefig(img_svg, format='svg', bbox_inches='tight')

                with col_dl1:
                    st.download_button(
                        label="🔎 Scarica grafico in alta qualità",
                        data=img_svg,
                        file_name=fn_svg,
                        mime="image/svg+xml",
                        help="Formato perfetto per zoom infinito e stampa professionale."
                    )

                # Download Dati (CSV)
                csv = df_meteo.to_csv(index=False).encode('utf-8')
                with col_dl2:
                    st.download_button(
                        label="📊 Scarica dati (CSV)",
                        data=csv,
                        file_name=f"meteo_{location_name}.csv",
                        mime="text/csv"
                    )
            else:
                st.warning("Nessun dato disponibile per il periodo selezionato.")

