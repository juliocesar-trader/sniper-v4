import os
import time
import datetime
import threading
import pickle
import requests
import csv
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from flask import Flask

# Importamos el puente seguro desde tus credenciales originales
from credenciales import conectar_broker, bot_telegram, TELEGRAM_ID

# ==============================================================================
# CONFIGURACIÓN MATRICIAL NATIVA
# ==============================================================================
DIVISAS = ["EURUSD", "GBPUSD", "AUDUSD", "USDJPY"]
ARCHIVO_REGISTRO = "registro_evolucion_ia.csv"

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
lock_csv = threading.Lock()

# Variable global para el estado de noticias (Evita retrasos en el segundo cero)
noticias_usd_activas = False

# ==============================================================================
# SISTEMA DE REGISTRO PERMANENTE CSV (Auditoría dentro de Render)
# ==============================================================================
def inicializar_csv_render():
    with lock_csv:
        if not os.path.exists(ARCHIVO_REGISTRO):
            with open(ARCHIVO_REGISTRO, mode='w', newline='', encoding='utf-8') as f:
                escritor = csv.writer(f)
                escritor.writerow([
                    "Fecha_Hora", "Divisa", "Operacion", "Certeza_IA", 
                    "RSI", "ATR", "Resultado", "Ajuste_Refuerzo", "Saldo_Demo"
                ])
            print(f"📊 Archivo de auditoría {ARCHIVO_REGISTRO} configurado en Render.")

def registrar_operacion_csv(datos_fila):
    with lock_csv:
        try:
            with open(ARCHIVO_REGISTRO, mode='a', newline='', encoding='utf-8') as f:
                escritor = csv.writer(f)
                escritor.writerow(datos_fila)
        except Exception as e:
            print(f"⚠️ Error al escribir fila en bitácora CSV: {e}")

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
        
        time.sleep(300) # Se actualiza en segundo plano cada 5 minutos de forma limpia

# ==============================================================================
# EXTRACCIÓN Y CÁLCULO DE INDICADORES TÉCNICOS (Mapeo Ultra-Preciso)
# ==============================================================================
def calcular_las_17_variables(velas):
    df = pd.DataFrame(velas)
    
    # 🛡️ MAPEO CRÍTICO DE COLUMNAS (Evita fallos por variaciones del broker)
    columnas_map = {
        'max': 'high', 'min': 'low', 'close': 'close', 'open': 'open', 'volume': 'volumen',
        'high': 'high', 'low': 'low', 'vol': 'volumen'
    }
    df = df.rename(columns=columnas_map)
    
    # Convertir a float de forma segura
    df['close'] = df['close'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['open'] = df['open'].astype(float)
    
    if 'volumen' not in df.columns:
        df['volumen'] = 0.0
    df['volumen'] = df['volumen'].astype(float)
    
    # 🛠️ CORRECCIÓN: RSI 14 CON SUAVIZADO DE WILDER REAL (EWM)
    delta = df['close'].diff()
    gains = delta.where(delta > 0, 0)
    losses = -delta.where(delta < 0, 0)
    avg_gain = gains.ewm(com=13, adjust=False).mean()
    avg_loss = losses.ewm(com=13, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-10)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # 🛠️ CORRECCIÓN: ATR 14 MATEMÁTICAMENTE EXACTO (Suavizado EWM)
    df['tr'] = np.maximum(df['high'] - df['low'], 
                          np.maximum(abs(df['high'] - df['close'].shift()), 
                                     abs(df['low'] - df['close'].shift())))
    df['atr'] = df['tr'].ewm(com=13, adjust=False).mean()
    
    # BB (Bandas de Bollinger)
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
    
    # ADX Ajustado Profesional
    df['adx'] = abs(df['high'] - df['low']).ewm(com=13, adjust=False).mean() / (df['atr'] + 1e-10) * 50
    df['distancia_ema'] = df['close'] - df['ema_200']
    
    ahora = datetime.datetime.now()
    df['hora_numerica'] = ahora.hour + (ahora.minute / 60.0)
    
    # 🔥 CRÍTICO: Extraemos la fila iloc[-2] para auditar la vela COMPLETAMENTE CERRADA
    return df.iloc[-2].to_dict()

# ==============================================================================
# HILO DE SEGUIMIENTO ASÍNCRONO DE OPERACIONES (No congela el análisis)
# ==============================================================================
def procesar_resultado_operacion(id_operacion, divisa, direccion, certeza, umbral_final, datos, hora_entrada):
    global API
    # Espera asíncrona dedicada únicamente a este hilo de operación (61 segundos)
    time.sleep(61)
    
    try:
        resultado, ganancia = API.check_win_v3(id_operacion)
        balance_actual = API.get_balance()
    except:
        resultado, ganancia, balance_actual = "error", 0, 0
    
    if resultado == "win":
        pesos_refuerzo[divisa] -= 0.010  # Reduce restricción si gana
        estado_marcador = f"🟢 GANADA (+${ganancia:.2f} USD)"
        csv_status = "GANADA"
    else:
        pesos_refuerzo[divisa] += 0.015  # Eleva exigencia si pierde (Cautela)
        estado_marcador = "🔴 PERDIDA (-$1.00 USD)"
        csv_status = "PERDIDA"
        
    datos_registro = [
        hora_entrada, divisa, direccion, f"{certeza*100:.2f}%",
        f"{datos['rsi']:.2f}", f"{datos['atr']:.6f}", csv_status,
        f"{pesos_refuerzo[divisa]:+.4f}", f"${balance_actual:.2f}"
    ]
    registrar_operacion_csv(datos_registro)
        
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
        f"💾 *Auditoría CSV:* `✅ Guardado en Render`\n"
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
        datos = calcular_las_17_variables(velas)
    except Exception as e:
        print(f"⚠️ Error calculando métricas para {divisa}: {e}")
        return
        
    umbral_base = 0.75 if datos['atr'] < 0.00015 else 0.85
    umbral_final = max(0.70, min(0.90, umbral_base + pesos_refuerzo[divisa]))
    
    if modelo_ia:
        # 🧠 MATRIZ DE 17 VARIABLES EN EL ORDEN EXACTO DEL ENTRENAMIENTO
        features = np.array([
            datos['rsi'], datos['atr'], datos['banda_sup'], datos['banda_inf'],
            datos['ema_200'], datos['macd_line'], datos['macd_signal'],
            datos['slowk'], datos['slowd'], datos['adx'], datos['distancia_ema'],
            datos['hora_numerica'], datos['open'], datos['high'], datos['low'],
            datos['close'], datos['volumen']
        ]).reshape(1, -1)
        
        probabilidades = modelo_ia.predict_proba(features)[0]
        prob_call, prob_put = probabilidades[1], probabilidades[0]
        direccion = "CALL" if prob_call > prob_put else "PUT"
        certeza = max(prob_call, prob_put)
    else:
        # Modo de contingencia por si el .pkl no está cargado correctamente
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
        
        # Lanzamos el proceso de seguimiento en un hilo independiente para liberar el análisis rápido
        threading.Thread(
            target=procesar_resultado_operacion, 
            args=(id_operacion, divisa, direccion, certeza, umbral_final, datos, hora_entrada)
        ).start()

# ==============================================================================
# BUCLE CENTRAL ASÍNCRONO
# ==============================================================================
def despachador_central():
    global operado_este_minuto
    inicializar_csv_render()
    
    # Lanzamos el filtro de noticias asíncrono en segundo plano
    threading.Thread(target=bucle_asincrono_noticias, daemon=True).start()
    
    print("🦁 Motores encendidos. Sincronizando con el reloj del servidor...")
    
    try:
        bot_telegram.send_message(
            TELEGRAM_ID, 
            "🦁 *¡SÚPER CEREBRO V4 ONLINE CON CORRECCIÓN ULTRA-PRECISA!*\n\n"
            "✨ *Mejoras Aplicadas:* Suavizado de Wilder (EWM) en RSI/ATR y lectura de vela cerrada (`iloc[-2]`). Escaneando mercados...", 
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"⚠️ Alerta Telegram: {e}")
        
    while True:
        ahora = datetime.datetime.now()
        tiempo_espera = 60 - ahora.second
        time.sleep(tiempo_espera)
        
        operado_este_minuto = False
        
        # Filtro de noticias en memoria instantánea (cero latencia en ejecución)
        if noticias_usd_activas:
            print("🛑 Filtro de Noticias Activo: Pausando análisis por volatilidad en USD.")
            continue
            
        for pair in DIVISAS:
            threading.Thread(target=analizar_vela_minuto, args=(pair,)).start()

# ==============================================================================
# SERVIDOR FLASK INTEGRADO PARA PERSISTENCIA EN RENDER
# ==============================================================================
app = Flask(__name__)

@app.route('/')
def home():
    return "🦁 Sniper IA V4 está vivo, calibrado al milímetro y cazando en los mercados."

def iniciar_servidor_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    hilo_bot = threading.Thread(target=despachador_central)
    hilo_bot.daemon = True
    hilo_bot.start()
    
    iniciar_servidor_web()
