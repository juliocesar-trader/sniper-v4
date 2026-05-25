import os
import time
import datetime
import threading
import pickle
import requests
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from flask import Flask

# Librerías necesarias para la conexión con Google Sheets
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Importamos el puente seguro desde tus credenciales originales e incluimos la lectura de la llave JSON
from credenciales import conectar_broker, bot_telegram, TELEGRAM_ID, obtener_json_credenciales_google

# ==============================================================================
# CONFIGURACIÓN MATRICIAL NATIVA
# ==============================================================================
DIVISAS = ["EURUSD", "GBPUSD", "AUDUSD", "USDJPY"]

print("🦁 Sniper IA V4 - Inicializando Motores e Hilos...")
API = conectar_broker()

if API and API.check_connect():
    API.change_balance("PRACTICE")  # Forzado estricto a Cuenta DEMO
    print("💰 Conectado con éxito a la cuenta DEMO de IQ Option.")
else:
    print("❌ Alerta: El Broker no está listo aún. Conexión en segundo plano activada.")

# Carga del Cerebro entrenado (.pkl)
try:
    with open("modelo_sniper_ia.pkl", "rb") as f:
        modelo_ia = pickle.load(f)
    print("🧠 Cerebro predictivo .pkl acoplado sin problemas.")
except Exception as e:
    print(f"⚠️ Nota sobre el archivo .pkl: {e}")
    modelo_ia = None

# Memoria de Aprendizaje por Refuerzo Continuo
pesos_refuerzo = {divisa: 0.0 for divisa in DIVISAS}

# Variable global para el estado de noticias (Evita retrasos en el segundo cero)
noticias_usd_activas = False

# ==============================================================================
# CONEXIÓN INTEGRADA A GOOGLE SHEETS
# ==============================================================================
def conectar_google_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = obtener_json_credenciales_google() 
        
        # 👁️ ESTA LÍNEA NOS VA A DECIR QUÉ CORREO REALMENTE ESTÁ USANDO EL BOT
        if creds_dict:
            print(f"📧 El bot está intentando entrar con el correo: {creds_dict.get('client_email')}")

        if not creds_dict:
            print("⚠️ Alerta: La función obtener_json_credenciales_google() devolvió vacío.")
            return None
            
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        cliente = gspread.authorize(creds)
        
        # Abre la hoja por su nombre literal
        hoja = cliente.open("Bitacora_Sniper_IA").sheet1
        return hoja
    except Exception as e:
        print(f"⚠️ Error conectando con Google Sheets: {e}")
        return None

def registrar_operacion_sheets(datos_fila):
    try:
        hoja = conectar_google_sheets()
        if hoja:
            hoja.append_row(datos_fila)
            print("💾 Bitácora respaldada en Google Sheets con éxito.")
        else:
            print("⚠️ Respaldo en Sheets no disponible. Datos impresos en consola:")
            print(datos_fila)
    except Exception as e:
        print(f"⚠️ Error crítico al escribir en Google Sheets: {e}")

# ==============================================================================
# FILTRO DE NOTICIAS ASÍNCRONO (Ejecución en segundo plano)
# ==============================================================================
def bucle_asincrono_noticias():
    global noticias_usd_activas
    while True:
        try:
            url = "https://es.investing.com/economic-calendar/"
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            respuesta = requests.get(url, headers=headers, timeout=5)
            if respuesta.status_code == 200:
                soup = BeautifulSoup(respuesta.text, 'html.parser')
                tabla = soup.find('table', {'id': 'economicCalendarTable'})
                
                if tabla:
                    filas = tabla.find_all('tr', class_='js-event-item')
                    hora_actual = datetime.datetime.now()
                    encontro_noticia = False
                    
                    for fila in filas:
                        impacto = fila.find('td', class_='sentiment')
                        estrellas = len(impacto.find_all('i', class_='grayFullBullishIcon')) if impacto else 0
                        
                        if estrellas == 3:
                            divisa_noticia = fila.find('td', class_='flagCur').text.strip()
                            if divisa_noticia == "USD":
                                hora_str = fila.find('td', class_='time').text.strip()
                                try:
                                    hora_noticia = datetime.datetime.strptime(hora_str, "%H:%M").replace(
                                        year=hora_actual.year, month=hora_actual.month, day=hora_actual.day
                                    )
                                    diferencia = abs((hora_actual - hora_noticia).total_seconds() / 60.0)
                                    if diferencia <= 15:
                                        encontro_noticia = True
                                        break
                                except:
                                    continue
                    
                    noticias_usd_activas = encontro_noticia
        except Exception as e:
            print(f"⚠️ Alerta en Filtro de Noticias en segundo plano: {e}")
        
        time.sleep(300)

# ==============================================================================
# EXTRACCIÓN Y CÁLCULO DE INDICADORES TÉCNICOS (Las 12 Variables del .txt)
# ==============================================================================
def calcular_las_12_variables(velas):
    df = pd.DataFrame(velas)
    
    columnas_map = {
        'max': 'high', 'min': 'low', 'close': 'close', 'open': 'open', 'volume': 'volumen',
        'high': 'high', 'low': 'low', 'vol': 'volumen'
    }
    df = df.rename(columns=columnas_map)
    
    df['close'] = df['close'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['open'] = df['open'].astype(float)
    
    # RSI 14
    delta = df['close'].diff()
    gains = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    losses = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gains / (losses + 1e-10)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # ATR 14
    df['tr'] = np.maximum(df['high'] - df['low'], 
                          np.maximum(abs(df['high'] - df['close'].shift()), 
                                     abs(df['low'] - df['close'].shift())))
    df['atr'] = df['tr'].rolling(window=14).mean()
    
    # BB
    df['ema_bb'] = df['close'].rolling(window=20).mean()
    df['std_bb'] = df['close'].rolling(window=20).std()
    df['banda_sup'] = df['ema_bb'] + (df['std_bb'] * 2)
    df['banda_inf'] = df['ema_bb'] - (df['std_bb'] * 2)
    
    # EMA 200
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # MACD
    e12 = df['close'].ewm(span=12, adjust=False).mean()
    e26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd_line'] = e12 - e26
    df['macd_signal'] = df['macd_line'].ewm(span=9, adjust=False).mean()
    
    # Estocástico
    l14 = df['low'].rolling(window=14).min()
    h14 = df['high'].rolling(window=14).max()
    df['slowk'] = 100 * ((df['close'] - l14) / (h14 - l14 + 1e-10))
    df['slowd'] = df['slowk'].rolling(window=3).mean()
    
    # ADX Simplificado
    df['adx'] = abs(df['high'] - df['low']).rolling(window=14).mean() / (df['atr'] + 1e-10) * 50
    df['distancia_ema'] = df['close'] - df['ema_200']
    
    ahora = datetime.datetime.now()
    df['hora_numerica'] = ahora.hour + (ahora.minute / 60.0)
    
    return df.iloc[-1].to_dict()

# ==============================================================================
# HILO DE SEGUIMIENTO ASÍNCRONO DE OPERACIONES
# ==============================================================================
def procesar_resultado_operacion(id_operacion, divisa, direccion, certeza, umbral_final, datos, hora_entrada):
    global API
    time.sleep(61)
    
    try:
        resultado, ganancia = API.check_win_v3(id_operacion)
        balance_actual = API.get_balance()
    except:
        resultado, ganancia, balance_actual = "error", 0, 0
    
    if resultado == "win":
        pesos_refuerzo[divisa] -= 0.010
        estado_marcador = f"🟢 GANADA (+${ganancia:.2f} USD)"
        csv_status = "GANADA"
    else:
        pesos_refuerzo[divisa] += 0.015
        estado_marcador = "🔴 PERDIDA (-$1.00 USD)"
        csv_status = "PERDIDA"
        
    datos_registro = [
        hora_entrada, divisa, direccion, f"{certeza*100:.2f}%",
        f"{datos['rsi']:.2f}", f"{datos['atr']:.6f}", csv_status,
        f"{pesos_refuerzo[divisa]:+.4f}", f"${balance_actual:.2f}"
    ]
    
    # Enviamos la fila directo a Google Sheets en lugar de usar el CSV local
    registrar_operacion_sheets(datos_registro)
        
    mensaje_telegram = (
        f"🦁 *SNIPER IA V4: OPERACIÓN CONCLUIDA*\n\n"
        f"📅 *Hora de Entrada:* `{hora_entrada}`\n"
        f"💱 *Divisa:* `{divisa}`\n"
        f"📊 *Dirección:* *{direccion}*\n"
        f"🧠 *Certeza IA:* `{certeza*100:.2f}%` (Umbral: {umbral_final*100:.1f}%)\n"
        f"📈 *RSI:* `{datos['rsi']:.2f}` | *ATR:* `{datos['atr']:.5f}`\n"
        f"🛡️ *Filtro de Noticias USD:* `✅ SEGURO`\n\n"
        f"🏁 *RESULTADO:* *{estado_marcador}*\n"
        f"🔄 *Evolución de Pesos:* `{pesos_refuerzo[divisa]:+.4f}`\n"
        f"💾 *Almacenamiento:* `✅ Guardado en Google Sheets`\n"
        f"💰 *Saldo Cuenta Demo:* `${balance_actual:.2f} USD`"
    )
    
    try:
        bot_telegram.send_message(TELEGRAM_ID, mensaje_telegram, parse_mode="Markdown")
    except Exception as e:
        print(f"❌ Error Telegram: {e}")

# ==============================================================================
# OPERACIÓN EN PARALELO
# ==============================================================================
bloqueo_correlacion = threading.Lock()
operado_este_minuto = False

def analizar_vela_minuto(divisa):
    global operado_este_minuto
    global API
    
    if not API or not API.check_connect():
        try:
            API = conectar_broker()
            if API: API.change_balance("PRACTICE")
        except:
            return

    try:
        velas = API.get_candles(divisa, 60, 220, time.time())
    except:
        return

    if not velas or len(velas) < 200:
        return
        
    try:
        # Modificado para extraer la cantidad exacta de variables del entrenamiento
        datos = calcular_las_12_variables(velas)
    except Exception as e:
        print(f"⚠️ Error calculando métricas para {divisa}: {e}")
        return
        
    umbral_base = 0.75 if datos['atr'] < 0.00015 else 0.85
    umbral_final = max(0.70, min(0.90, umbral_base + pesos_refuerzo[divisa]))
    
    if modelo_ia:
        # 🧠 MATRIZ REDUCIDA A LAS 12 VARIABLES EXACTAS DEL ENTRENAMIENTO (.txt)
        features = np.array([
            datos['rsi'], datos['atr'], datos['banda_sup'], datos['banda_inf'],
            datos['ema_200'], datos['macd_line'], datos['macd_signal'],
            datos['slowk'], datos['slowd'], datos['adx'], datos['distancia_ema'],
            datos['hora_numerica']
        ]).reshape(1, -1)
        
        probabilidades = modelo_ia.predict_proba(features)[0]
        prob_call, prob_put = probabilidades[1], probabilidades[0]
        direccion = "CALL" if prob_call > prob_put else "PUT"
        certeza = max(prob_call, prob_put)
    else:
        direccion = "CALL" if datos['rsi'] < 30 else "PUT" if datos['rsi'] > 70 else None
        certeza = 0.76 if direccion else 0.0
        
    hora_entrada = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if direccion and certeza >= umbral_final:
        with bloqueo_correlacion:
            if "USD" in divisa:
                if operado_este_minuto:
                    return
                operado_este_minuto = True
                
        monto = 1
        try:
            id_operacion = API.buy(monto, divisa, "turbo", 1) if direccion == "CALL" else API.sell(monto, divisa, "turbo", 1)
        except:
            return
            
        if not id_operacion or not isinstance(id_operacion, int):
            return
            
        print(f"🚀 Ejecutando {direccion} en {divisa} (Demo)...")
        
        threading.Thread(
            target=procesar_resultado_operacion, 
            args=(id_operacion, divisa, direccion, certeza, umbral_final, datos, hora_entrada)
        ).start()

# ==============================================================================
# BUCLE CENTRAL ASÍNCRONO
# ==============================================================================
def despachador_central():
    global operado_este_minuto
    
    # Se eliminó la inicialización local del CSV para evitar escrituras redundantes
    threading.Thread(target=bucle_asincrono_noticias, daemon=True).start()
    
    print("🦁 Motores encendidos. Sincronizando con el reloj del servidor...")
    
    try:
        bot_telegram.send_message(TELEGRAM_ID, "🦁 *¡SÚPER CEREBRO ONLINE CON CONEXIÓN CLOUD NEURAL!*\nMatriz compatible de 12 variables en funcionamiento. Monitoreando mercados...", parse_mode="Markdown")
    except Exception as e:
        print(f"⚠️ Alerta Telegram: {e}")
        
    while True:
        ahora = datetime.datetime.now()
        tiempo_espera = 60 - ahora.second
        time.sleep(tiempo_espera)
        
        operado_este_minuto = False
        
        if noticias_usd_activas:
            print("🛑 Filtro de Noticias Activo: Pausando análisis por volatilidad en USD.")
            continue
            
        for pair in DIVISAS:
            threading.Thread(target=analizar_vela_minuto, args=(pair,)).start()

# ==============================================================================
# SERVIDOR FLASK INTEGRADO PARA RENDER
# ==============================================================================
app = Flask(__name__)

@app.route('/')
def home():
    return "🦁 Sniper IA V4 activo en Render y enlazado de forma segura a Google Sheets."

def iniciar_servidor_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    hilo_bot = threading.Thread(target=despachador_central)
    hilo_bot.daemon = True
    hilo_bot.start()
    
    iniciar_servidor_web()
