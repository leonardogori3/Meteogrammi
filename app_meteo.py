import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import MultipleLocator
from datetime import date, timedelta
import io
import sys
import numpy as np 

# --- CONFIGURAZIONI GLOBALI ---
st.set_page_config(layout="wide", page_title="Meteogrammi") 
plt.rcParams['figure.dpi'] = 300 
plt.rcParams['figure.figsize'] = [12, 35] # Manteniamo l'altezza aumentata
try:
    plt.style.use('seaborn-v0_8-darkgrid')
except:
    plt.style.use('ggplot')

# --- FUNZIONI DI SERVIZIO ---

# CLASSE MANTENUTA (NECESSARIA PER L'ASSE X)
class CustomDateFormatter(mdates.DateFormatter):
    """
    Formatter personalizzato per l'asse X che mostra la data completa
    solo a mezzanotte (00:00).
    """
    def __call__(self, x, pos=0):
        dt = mdates.num2date(x, self.tz)
        if dt.hour == 0 and dt.minute == 0: 
            return dt.strftime('%d %b %H:%M') 
        else:
            return dt.strftime('%H:%M') 

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
            return result["latitude"], result["longitude"], result["name"], result.get("country", ""), result.get("elevation", 0)
        else:
            return None, None, None, None, 0
    except Exception:
        return None, None, None, None, 0

@st.cache_data(ttl=3600)
def fetch_and_process_data(LAT, LON, start_d, end_d):
    """
    Scarica i dati meteo, trova la lunghezza minima comune e crea il DataFrame.
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

    # Crea un DataFrame con gli array troncati e converti il tempo
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
    
    df_temp['clouds_total'] = df_temp['clouds_low'] + df_temp['clouds_mid'] + df_temp['clouds_high']
    df_temp['accumulated_rain'] = df_temp['rain'].cumsum()
    df_temp['accumulated_snow'] = df_temp['snowfall'].cumsum()
    
    # Filtra i dati in base al giorno
    df_temp = df_temp[
        (df_temp['time'].dt.date >= start_d) & 
        (df_temp['time'].dt.date <= end_d)
        ]
    
    # Riporta l'indice temporale per un plotting corretto
    df_temp = df_temp.set_index('time')
    return df_temp

# --- 4. PLOTTING ---
@st.cache_data
def plot_meteogram(df, location_label, start_s, end_s, altitude):
    # Setup Grafico
    
    try:
        plt.style.use('seaborn-v0_8-darkgrid')
    except:
        plt.style.use('ggplot')
        
    fig, (ax1, ax2, ax3, ax4, ax5, ax6) = plt.subplots(6, 1, sharex=True)
    
    # FIX LAYOUT: hspace 1.0 per spazio tra i grafici, bottom ridotto
    plt.subplots_adjust(hspace=1.0, bottom=0.08, top=0.9) 
    
    # FIX TITOLO
    fig.suptitle(f'Previsioni: {location_label}\nDal {start_s.strftime("%Y-%m-%d")} al {end_s.strftime("%Y-%m-%d")}', 
                 fontsize=18, 
                 fontweight='bold',
                 y=0.95) 

    # --- Parametri Legenda (Locazione: Sotto l'asse) ---
    LEGEND_BBOX = (0.5, -0.4) 
    LEGEND_LOC = 'upper center'

    # 1. TEMPERATURA 
    ax1.plot(df.index, df['temp'], color='#d62728', marker='.', markersize=4, label='Temperatura')
    ax1.plot(df.index, df['dew_point'], color='#1f77b4', linestyle='--', label='Temperatura di rugiada')
    ax1.axhline(0, color='gray', linestyle='-', linewidth=1) 
    ax1.yaxis.set_major_locator(MultipleLocator(5))
    ax1.set_title('1. Temperatura °C', loc='left', fontweight='bold')
    ax1.set_ylabel('°C')
    # RIPRISTINO LEGENDA SOTTO AX1
    ax1.legend(loc=LEGEND_LOC, bbox_to_anchor=LEGEND_BBOX, frameon=True, ncol=2) 
    ax1.grid(True, axis='y', which='major', linestyle='-', alpha=0.5, color='gray') 

    # 2. NUVOLE (Stackplot originale corretto)
    ax2.stackplot(df.index, df['clouds_low'], df['clouds_mid'], df['clouds_high'], 
                  labels=['Basse', 'Medie', 'Alte'], colors=['#5f5f5f', '#969696', '#cccccc'], alpha=0.6)
    ax2.set_ylim(0, 105)
    ax2_twin = ax2.twinx() 
    # Rinominata label per l'umidità per evitare sovrapposizioni con i colori dello stackplot
    ax2_twin.plot(df.index, df['humidity'], color='blue', linestyle=':', label='Umidità') 
    ax2_twin.set_ylim(0, 105) 
    ax2.set_ylabel('% Copertura')
    ax2_twin.set_ylabel('% Umidità', color='blue')
    ax2.set_title('2. Strati Nuvole (Basse/Medie/Alte)', loc='left', fontweight='bold')
    
    # RIPRISTINO LEGENDA SOTTO AX2 (combinando nuvole e umidità)
    h2_a, l2_a = ax2.get_legend_handles_labels()
    h2_b, l2_b = ax2_twin.get_legend_handles_labels()
    ax2.legend(h2_a + h2_b, l2_a + l2_b, loc=LEGEND_LOC, bbox_to_anchor=LEGEND_BBOX, frameon=True, ncol=4)
    ax2.grid(True, axis='y', which='major', linestyle='-', alpha=0.5, color='gray') 

# 3. PRECIPITAZIONI 
    bar_width = 0.035 
    ax3_twin = ax3.twinx()
    
    ax3.bar(df.index, df['rain'], width=bar_width, color='#17becf', label='Pioggia oraria (mm)', align='center', alpha=0.9)
    ax3.bar(df.index, df['snowfall'], width=bar_width, bottom=df['rain'], color='pink', label='Neve oraria (cm)', align='center', alpha=0.95)

    ax3_twin.plot(df.index, df['accumulated_rain'], color='#007fbf', label='Accumulo pioggia (mm)', linewidth=2)
    ax3_twin.plot(df.index, df['accumulated_snow'], color='#800080', label='Accumulo neve (cm)', linestyle='-', linewidth=2)

    max_total_accum = df['accumulated_rain'].max() + df['accumulated_snow'].max()
    ax3_twin.set_ylim(0, max(10, max_total_accum * 1.1)) 
    ax3_twin.set_ylabel('') 
    ax3_twin.set_yticks([]) 
    ax3_twin.grid(False) 
    ax3.set_ylim(0, df['rain'].max() * 1.5 + df['snowfall'].max() * 1.5 + 1)
    ax3.set_ylabel('Quantità Oraria (mm/cm)', color='black')
    ax3.yaxis.set_major_locator(MultipleLocator(2)) 
    ax3_twin.axhline(0, color='gray', linewidth=0.5, zorder=0)

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

    # RIPRISTINO LEGENDA SOTTO AX3
    ax3.set_title('3. Precipitazioni orarie e accumulo cumulativo', loc='left', fontweight='bold')
    h3_a, l3_a = ax3.get_legend_handles_labels()
    h3_b, l3_b = ax3_twin.get_legend_handles_labels()
    ax3.legend(h3_a + h3_b, l3_a + l3_b, loc=LEGEND_LOC, bbox_to_anchor=LEGEND_BBOX, frameon=True, ncol=4)
    ax3.grid(True, axis='y', which='major', linestyle='-', alpha=0.5, color='gray')

    # 4. VENTO
    ax4.plot(df.index, df['wind_speed'], color='#2ca02c', label='Velocità Media', linewidth=2)
    ax4.plot(df.index, df['wind_gusts'], color="#001fce", linestyle='--', label='Raffiche', linewidth=1.5)
    ax4_twin = ax4.twinx()
    # Usando un placeholder per la direzione per farla apparire in legenda, nonostante sia uno scatter
    ax4_twin.plot([], [], color='purple', marker='o', linestyle='', label='Direzione Vento') 
    ax4_twin.scatter(df.index, df['wind_dir'], color='purple', s=15) # Lo scatterplot mantiene la stessa logica di colore
    ax4.yaxis.set_major_locator(MultipleLocator(10))
    ax4.set_ylabel('km/h')
    ax4_twin.set_yticks([0, 90, 180, 270, 360])
    ax4_twin.set_yticklabels(['N', 'E', 'S', 'W', 'N'])
    ax4.set_title('4. Vento e raffiche', loc='left', fontweight='bold')
    
    # RIPRISTINO LEGENDA SOTTO AX4
    h4_a, l4_a = ax4.get_legend_handles_labels()
    h4_b, l4_b = ax4_twin.get_legend_handles_labels()
    ax4.legend(h4_a + h4_b, l4_a + l4_b, loc=LEGEND_LOC, bbox_to_anchor=LEGEND_BBOX, frameon=True, ncol=3) 
    ax4.grid(True, axis='y', which='major', linestyle='-', alpha=0.5, color='gray') 

  # 5. PRESSIONE ATMOSFERICA
    p_min_data = df['pressure'].min()
    p_max_data = df['pressure'].max()
    ax5.set_ylim(p_min_data - 5, p_max_data + 5)
    
    ax5.plot(df.index, df['pressure'], color='orange', linewidth=2, label='Pressione (MSL)')
    
    ax5.yaxis.set_major_locator(MultipleLocator(2)) 
    ax5.set_ylabel('hPa')
    ax5.set_title('5. Pressione atmosferica', loc='left', fontweight='bold')
    ax5.axhline(1013, color='red', linestyle=':', alpha=0.6, label='1013 hPa (Std)')
    # RIPRISTINO LEGENDA SOTTO AX5
    ax5.legend(loc=LEGEND_LOC, bbox_to_anchor=LEGEND_BBOX, frameon=True, ncol=2)
    ax5.grid(True, axis='y', which='major', linestyle='-', alpha=0.5, color='gray') 

    # 6. ZERO TERMICO
    ax6.plot(df.index, df['freezing_lvl'], color='red', label='Zero Termico')
    ax6.axhline(altitude, color='blue', linestyle='--', alpha=0.6, label=f'Altitudine loc. ({altitude:.0f}m)')
    ax6.set_ylabel('Metri')
    ax6.set_title('6. Quota zero termico', loc='left', fontweight='bold')
    # RIPRISTINO LEGENDA SOTTO AX6
    ax6.legend(loc=LEGEND_LOC, bbox_to_anchor=LEGEND_BBOX, frameon=True, ncol=2)
    ax6.grid(True, axis='y', which='major', linestyle='-', alpha=0.5, color='gray') 

   # --- FORMATTAZIONE GLOBALE ---
    all_axes = [ax1, ax2, ax3, ax4, ax5, ax6] 
    
    # 2. CALCOLO E DEFINIZIONE DEL LOCATOR DINAMICO (Mantenuto)
    duration_days = (end_s - start_s).days + 1 
    # ... (restante codice di formattazione X axis invariato)
    if duration_days <= 1:
        minor_hours = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23]
    elif duration_days <= 3:
        minor_hours = [3, 6, 9, 12, 15, 18, 21]
    else:
        minor_hours = [6, 12, 18]
        
    for ax in all_axes:
        ax.grid(True, axis='y', which='major', linestyle='-', alpha=0.5, color='gray')
        ax.grid(False, axis='x')
        
        ax.xaxis.set_major_locator(mdates.DayLocator())
        ax.xaxis.set_minor_locator(mdates.HourLocator(byhour=minor_hours))
        ax.xaxis.set_major_formatter(CustomDateFormatter('%d %b %H:%M'))
        ax.xaxis.set_minor_formatter(mdates.DateFormatter('%H:%M'))
        
        start_dt = pd.to_datetime(start_s.strftime("%Y-%m-%d 00:00:00"))
        end_dt = pd.to_datetime(end_s.strftime("%Y-%m-%d 23:59:59")) 
        ax.set_xlim(start_dt, end_dt) 
        
        ax.tick_params(axis='x', which='major', rotation=65, labelsize=10, labelbottom=True) 
        ax.tick_params(axis='x', which='minor', rotation=65, labelsize=10, labelbottom=True)
        
    # NESSUNA CHIAMATA fig.legend QUI.
    return fig

# --- INTERFACCIA UTENTE ---
st.title("🌍 Meteogrammi per tutte le località")
st.markdown("Analisi dei vari parametri meteorologici.")


# Aggiunge spazio extra dopo il blocco iniziale
st.text("") 
st.text("") 
st.text("") 


# Inizializzazione per prevenire NameError
btn_generate = False
stop_exec = False
location_altitude = 0 
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
            location_altitude = altitude_f 
        else:
            st.error("Città non trovata.")
else:
    final_lat = st.number_input("Latitudine", value=0.0, format="%.4f")
    final_lon = st.number_input("Longitudine", value=0.0, format="%.4f")
    location_name = st.text_input("Nome località", "Località")
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
                
                # 1. Grafico Dettagliato
                st.subheader(f"Grafico Dettagliato")
                fig = plot_meteogram(df_meteo, location_name, start_date, end_date, location_altitude)
                st.pyplot(fig)
                plt.close(fig) # Libera la memoria

                st.markdown("---")
                
                # --- DOWNLOAD AREA ---
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
