import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import MultipleLocator, AutoMinorLocator
from datetime import date, timedelta
import io
import sys

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(layout="wide", page_title="Meteo Expert Pro - Definitivo")


# --- FUNZIONI DI SERVIZIO ---

@st.cache_data
def get_coordinates_from_city(city_name):
    """Cerca una città e restituisce Lat, Lon e Nome."""
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": city_name, "count": 1, "language": "it", "format": "json"}
    try:
        response = requests.get(url, params=params)
        data = response.json()
        if "results" in data:
            result = data["results"][0]
            return result["latitude"], result["longitude"], result["name"], result.get("country", "")
        else:
            return None, None, None, None
    except Exception:
        return None, None, None, None


@st.cache_data(ttl=3600)
def fetch_and_process_data(LAT, LON, start_d, end_d):
    """Scarica i dati meteo e calcola l'accumulo di precipitazioni."""

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": LAT,
        "longitude": LON,
        "hourly": "temperature_2m,dew_point_2m,relative_humidity_2m,cloud_cover_low,cloud_cover_mid,cloud_cover_high,surface_pressure,precipitation_probability,wind_speed_10m,wind_direction_10m,wind_gusts_10m,weather_code,rain,snowfall,freezing_level_height",
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
    df = pd.DataFrame({
        'time': pd.to_datetime(hourly['time']),
        'temp': hourly['temperature_2m'],
        'dew_point': hourly['dew_point_2m'],
        'humidity': hourly['relative_humidity_2m'],
        'clouds_low': hourly['cloud_cover_low'],
        'clouds_mid': hourly['cloud_cover_mid'],
        'clouds_high': hourly['cloud_cover_high'],
        'pressure': hourly['surface_pressure'],
        'precip_prob': hourly['precipitation_probability'],
        'wind_speed': hourly['wind_speed_10m'],
        'wind_gusts': hourly['wind_gusts_10m'],
        'wind_dir': hourly['wind_direction_10m'],
        'rain': hourly['rain'],
        'snowfall': hourly['snowfall'],
        'freezing_lvl': hourly['freezing_level_height']
    })

    # CALCOLO CUMULATIVO PER IL GRAFICO (PIOGGIA in mm e NEVE in cm)
    df['accumulated_rain'] = df['rain'].cumsum()
    df['accumulated_snow'] = df['snowfall'].cumsum()

    # Applicazione del filtro data
    df = df[(df['time'] >= start_d.strftime("%Y-%m-%d")) & (df['time'] <= end_d.strftime("%Y-%m-%d") + " 23:59:59")]
    return df


# --- 3. PLOTTING ---
def plot_meteogram(df, location_label, start_s, end_s):
    # Setup Grafico
    plt.rcParams['figure.dpi'] = 300
    plt.rcParams['figure.figsize'] = [12, 24]

    try:
        plt.style.use('seaborn-v0_8-darkgrid')
    except:
        plt.style.use('ggplot')

    fig, (ax1, ax2, ax3, ax4, ax5, ax6) = plt.subplots(6, 1, sharex=True)
    plt.subplots_adjust(hspace=0.5)
    fig.suptitle(f'Previsioni: {location_label}\nDal {start_s} al {end_s}', fontsize=18, fontweight='bold')

    # 1. TEMPERATURA (Step 5°C)
    ax1.plot(df['time'], df['temp'], color='#d62728', marker='.', markersize=4, label='Temp')
    ax1.plot(df['time'], df['dew_point'], color='#1f77b4', linestyle='--', label='Dew Point')
    ax1.axhline(0, color='gray', linestyle='-', linewidth=1)
    ax1.yaxis.set_major_locator(MultipleLocator(5))
    ax1.set_title('1. Temperatura °C', loc='left', fontweight='bold')
    ax1.set_ylabel('°C')
    ax1.legend(loc='upper right', frameon=True)

    # 2. NUVOLE (Y-axis 0-100% e Umidità)
    ax2.stackplot(df['time'], df['clouds_low'], df['clouds_mid'], df['clouds_high'],
                  labels=['Basse', 'Medie', 'Alte'], colors=['#5f5f5f', '#969696', '#cccccc'], alpha=0.6)
    ax2.set_ylim(0, 100)
    ax2_twin = ax2.twinx()
    ax2_twin.plot(df['time'], df['humidity'], color='blue', linestyle=':', label='Umidità')
    ax2_twin.set_ylim(0, 100)

    ax2.set_ylabel('% Copertura')
    ax2_twin.set_ylabel('% Umidità', color='blue')
    ax2.set_title('2. Strati nuvolosi', loc='left', fontweight='bold')
    ax2.legend(loc='upper left')

    # 3. PRECIPITAZIONI ORARIE E ACCUMULO CUMULATIVO
    bar_width = 0.035 
    
    # Barre Pioggia
    ax3.bar(df['time'], df['rain'], width=bar_width, color='#17becf', label='Pioggia Oraria (mm)', align='center', alpha=0.9)
    # Barre Neve
    ax3.bar(df['time'], df['snowfall'], width=bar_width, bottom=df['rain'], color='#b0c4de', label='Neve Oraria (cm)', align='center', alpha=0.95)

    ax3_twin = ax3.twinx()
    ax3_twin.plot(df['time'], df['accumulated_rain'], color='#007fbf', label='Accumulo Pioggia (mm)', linewidth=2)
    ax3_twin.plot(df['time'], df['accumulated_snow'], color='#800080', label='Accumulo Neve (cm)', linestyle='-', linewidth=2)

    # --- FIX ASSI PRECIPITAZIONI ---
    # Calcoliamo il massimo valore di precipitazione oraria per scalare l'asse correttamente
    max_precip = max(df['rain'].max(), df['snowfall'].max(), 1.0) # Minimo 1.0 per non far sparire l'asse se zero
    
    # Impostiamo un limite superiore dinamico con un po' di margine
    ax3.set_ylim(0, max_precip * 1.2) 
    
    # Forziamo la visualizzazione delle etichette
    ax3.yaxis.set_major_locator(MultipleLocator(5)) # Tacche ogni 5
    ax3.yaxis.set_minor_locator(MultipleLocator(1)) # Tacche minori ogni 1
    
    # Se i valori sono tutti piccoli (sotto 5), usiamo uno step più fine (es. 1)
    if max_precip < 5:
        ax3.yaxis.set_major_locator(MultipleLocator(1))

    ax3.set_ylabel('Quantità Oraria (mm/cm)')
    ax3_twin.set_ylabel('Accumulo Totale (mm/cm)', color='black')
    ax3.set_title('3. Precipitazioni orarie e accumulo cumulativo (Step 5)', loc='left', fontweight='bold')
    ax3.legend(loc='upper left')
    ax3_twin.legend(loc='lower right')

    # 4. VENTO (Step 10 km/h)
    ax4.plot(df['time'], df['wind_speed'], color='#2ca02c', label='Velocità Media', linewidth=2)
    ax4.plot(df['time'], df['wind_gusts'], color="#001fce", linestyle='--', label='Raffiche', linewidth=1.5)
    ax4_twin = ax4.twinx()
    ax4_twin.scatter(df['time'], df['wind_dir'], color='purple', s=15, label='Direz.')
    ax4.yaxis.set_major_locator(MultipleLocator(10))
    ax4.set_ylabel('km/h')
    ax4_twin.set_yticks([0, 90, 180, 270, 360])
    ax4_twin.set_yticklabels(['N', 'E', 'S', 'W', 'N'])
    ax4.set_title('4. Vento e raffiche', loc='left', fontweight='bold')
    ax4.legend(loc='upper left')

    # 5. PRESSIONE (Step 2 hPa)
    ax5.plot(df['time'], df['pressure'], color='orange', linewidth=2)
    ax5.yaxis.set_major_locator(MultipleLocator(2))
    ax5.set_ylabel('hPa')
    ax5.set_title('5. Pressione atmosferica', loc='left', fontweight='bold')
    ax5.axhline(1000, color='red', linestyle=':', alpha=0.6, label='1000 hPa')
    ax5.legend(loc='upper right')

    # 6. ZERO TERMICO
    ax6.plot(df['time'], df['freezing_lvl'], color='red')
    ax6.set_ylabel('Metri')
    ax6.set_title('6. Quota zero termico', loc='left', fontweight='bold')
    ax6.legend()

    # --- FORMATTAZIONE GLOBALE ---
    all_axes = [ax1, ax2, ax3, ax4, ax5, ax6]

    for ax in all_axes:
        ax.grid(True, axis='y', which='major', linestyle='-', alpha=0.5, color='gray')
        ax.grid(False, axis='x')
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b\n%H'))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=12))
        ax.tick_params(labelbottom=True)
        ax.tick_params(axis='x', labelsize=10)

    # Visualizzazione Streamlit
    return fig


# --- INTERFACCIA UTENTE ---
st.title("🌍 Meteogrammi ")
st.markdown("Analisi dei vari parametri meteorologici.")

# --- SIDEBAR (INPUT) ---
with st.sidebar:
    st.header("1. Dove?")
    search_method = st.radio("Metodo:", ["🔍 Cerca Città", "📍 Coordinate"])

    final_lat = None
    final_lon = None
    location_name = "Località"

    # Impostazioni di default per testare l'errore Livorno/Pressione
    default_lat = 43.5518
    default_lon = 10.3080

    if search_method == "🔍 Cerca Città":
        city_input = st.text_input("Città (es. Livorno, Abetone)", "Livorno")
        if city_input:
            lat_f, lon_f, name_f, country_f = get_coordinates_from_city(city_input)
            if lat_f:
                st.success(f"📍 {name_f} ({country_f})")
                final_lat = lat_f
                final_lon = lon_f
                location_name = name_f
            else:
                st.error("Città non trovata.")
    else:
        final_lat = st.number_input("Latitudine", value=default_lat, format="%.4f")
        final_lon = st.number_input("Longitudine", value=default_lon, format="%.4f")
        location_name = st.text_input("Nome località", "Livorno")

    st.markdown("---")
    st.header("2. Quando?")

    col1, col2 = st.columns(2)
    today = date(2025, 11, 23)
    default_end_date = date(2025, 11, 25)

    start_date = col1.date_input("Dal:", today)
    end_date = col2.date_input("Al:", default_end_date)

    if start_date > end_date:
        st.error("Date non valide!")
        stop_exec = True
    else:
        stop_exec = False

    st.markdown("---")
    btn_generate = st.button("Genera grafico", type="primary")

# --- OUTPUT ---
if btn_generate and not stop_exec:
    if final_lat is None:
        st.error("Coordinate non valide.")
    else:
        st.subheader(f"Analisi per: {location_name}")
        with st.spinner("Elaborazione dati e generazione griglie..."):
            df_meteo = fetch_and_process_data(final_lat, final_lon, start_date, end_date)

            if df_meteo is not None and not df_meteo.empty:
                st.info(
                    "Nota Pressione: Valori sotto 1000 hPa sono normali in presenza di forte maltempo (depressione).")

                fig = plot_meteogram(df_meteo, location_name, start_date, end_date)
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
                        label="🔎 Scarica Grafico Vettoriale (SVG)",
                        data=img_svg,
                        file_name=fn_svg,
                        mime="image/svg+xml",
                        help="Formato perfetto per zoom infinito e stampa professionale."
                    )

                # Download Dati (CSV)
                csv = df_meteo.to_csv(index=False).encode('utf-8')
                with col_dl2:
                    st.download_button(
                        label="📊 Scarica Dati (CSV)",
                        data=csv,
                        file_name=f"meteo_{location_name}.csv",
                        mime="text/csv"
                    )
            else:
                st.warning("Nessun dato disponibile per il periodo selezionato.")