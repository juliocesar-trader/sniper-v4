import os
import time
import datetime
import threading
import pickle
import requests
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup

# Importamos tu puente seguro ya existente para jalar la conexión y Telegram
from credenciales import conectar_broker, bot_telegram, TELEGRAM_ID, DIVISAS

# ==============================================================================
# INICIALIZACIÓN DE ENTORNO Y MATRICES CUÁNTICAS
# ==============================================================================
print("🦁 Súper Cerebro Adaptativo - Inicializando Conexiones...")
API = conectar_broker()

if API and API.check_connect():
    API.change_balance("PRACTICE")  # Forzado estricto a Cuenta DEMO para ver evolución limpia
    print("💰 Conectado con éxito a la cuenta DEMO de IQ Option.")
else:
    print("❌ Error crítico: No se pudo enlazar el Broker. Verifica Render .env")

# Carga del Cerebro entrenado en Colab (79.23% Precisión)
with open("modelo_sniper_ia.pkl", "rb") as f:
    modelo_ia = pickle.load(f)

# Memoria volátil para el Aprendizaje por Refuerzo Continuo (Premios/Castigos)
pesos_refuerzo = {divisa: 0.0 for divisa in DIVISAS}

# ==============================================================================
# FASE 3: FILTRO TEMPRANO DE NOTICIAS DE ALTO IMPACTO (Investing.com)
# ==============================================================================
def verificar_noticias_usd():
    """
    Escanea Investing.com en tiempo real. Bloquea el bot si hay eventos de 3 toros/estrellas
    en el USD dentro de una ventana de 15 minutos antes o después.
    """
    try:
        url = "https://es.investing.com/economic-calendar/"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        respuesta = requests.get(url, headers=headers, timeout=5)
        if respuesta.status_code != 200:
            return False
            
        soup = BeautifulSoup(respuesta.text, 'html.parser')
        tabla = soup.find('table', {'id': 'economicCalendarTable'})
        if not tabla:
            return False
            
        filas = tabla.find_all('tr', class_='js-event-item')
        hora_actual = datetime.datetime.now()
        
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
                            return True
                    except:
                        continue
    except Exception as e:
        print(f"⚠️ Alerta en Filtro de Noticias: {e}")
    return False

# ==============================================================================
# EXTRACCIÓN Y CÁLCULO DE LAS VARIABLES MAESTRAS (Indicadores Técnicos)
# ==============================================================================
def calcular_las_17_variables(velas):
    df = pd.DataFrame(velas)
    df['close'] = df['close'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    
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
# FLUJO DE TRABAJO EN TIEMPO REAL (Cada Minuto)
# ==============================================================================
bloqueo_correlacion = threading.Lock()
operado_este_minuto = False

def analizar_vela_minuto(divisa):
    global operado_este_minuto
    
    # 1. Extracción de velas en tiempo real (0.2s latencia)
    velas = API.get_candles(divisa, 60, 220, time.time())
    if not velas:
        return
        
    datos = calcular_las_17_variables(velas)
    
    # Lógica de Umbral Dinámico Adaptativo
    umbral_base = 0.75 if datos['atr'] < 0.00015 else 0.85
    
    # Aplicar la corrección por Aprendizaje por Refuerzo
    umbral_final = max(0.70, min(0.90, umbral_base + pesos_refuerzo[divisa]))
    
    # 2. Evaluación por Inteligencia Artificial
    features = np.array([datos['rsi'], datos['atr'], datos['banda_sup'], datos['banda_inf'],
                         datos['ema_200'], datos['macd_line'], datos['macd_signal'],
                         datos['slowk'], datos['slowd'], datos['adx'],
                         datos['distancia_ema'], datos['hora_numerica']]).reshape(1, -1)
                         
    probabilidades = modelo_ia.predict_proba(features)[0]
    prob_call, prob_put = probabilidades[1], probabilidades[0]
    
    direccion = "CALL" if prob_call > prob_put else "PUT"
    certeza = max(prob_call, prob_put)
    
    hora_entrada = datetime.datetime.now().strftime("%H:%M:%S")
    
    # 3. Decisiones y Filtros de Riesgo
    if certeza >= umbral_final:
        
        # Filtro de Correlación Anti-Multirriesgo
        with bloqueo_correlacion:
            if "USD" in divisa:
                if operado_este_minuto:
                    print(f"🛡️ Filtro de Correlación Activo: Operación omitida en {divisa}")
                    return
                operado_este_minuto = True
                
        # Ejecución fija de $1 USD (Gestión estricta de riesgo)
        monto = 1
        id_operacion = API.buy(monto, divisa, "turbo", 1) if direccion == "CALL" else API.sell(monto, divisa, "turbo", 1)
        
        print(f"🚀 Operación lanzada en {divisa} ({direccion}) - Esperando vencimiento...")
        
        # Esperar la finalización de la vela de 1 minuto
        time.sleep(61)
        resultado, ganancia = API.check_win_v3(id_operacion)
        balance_actual = API.get_balance()
        
        # FASE 4: PREMIOS Y CASTIGOS (Evolución en la sombra sin detenerse)
        if resultado == "win":
            pesos_refuerzo[divisa] -= 0.010  # Premio: se vuelve un poco más flexible
            estado_marcador = f"🟢 GANADA (+${ganancia:.2f} USD)"
        else:
            pesos_refuerzo[divisa] += 0.015  # Castigo pesado: sube la exigencia drásticamente
            estado_marcador = "🔴 PERDIDA (-$1.00 USD)"
            
        # MÓDULO DE NOTIFICACIONES REQUERIDO A TELEGRAM
        mensaje_telegram = (
            f"🦁 *SNIPER IA V4: OPERACIÓN DETECTADA*\n\n"
            f"📅 *Hora de Entrada:* `{hora_entrada}`\n"
            f"💱 *Divisa:* `{divisa}`\n"
            f"📊 *Dirección:* *{direccion}*\n"
            f"🧠 *Certeza Matemática:* `{certeza*100:.2f}%` (Umbral requerido: {umbral_final*100:.1f}%)\n"
            f"📈 *RSI Actual:* `{datos['rsi']:.2f}` | *ATR:* `{datos['atr']:.5f}`\n"
            f"🛡️ *Filtro de Noticias USD:* `✅ SEGURO`\n\n"
            f"🏁 *RESULTADO:* *{estado_marcador}*\n"
            f"🔄 *Ajuste de Aprendizaje:* `{pesos_refuerzo[divisa]:+.4f}`\n"
            f"💰 *Saldo Restante Demo:* `${balance_actual:.2f} USD`"
        )
        
        try:
            bot_telegram.send_message(TELEGRAM_ID, mensaje_telegram, parse_mode="Markdown")
        except Exception as e:
            print(f"❌ Error al enviar reporte a Telegram: {e}")

# ==============================================================================
# BUCLE DE CONTROL Y DESPACHADOR CENTRAL ASÍNCRONO
# ==============================================================================
def despachador_central():
    global operado_este_minuto
    print("🦁 Motores encendidos. Sincronizando con el reloj del servidor...")
    
    try:
        bot_telegram.send_message(TELEGRAM_ID, "🦁 *¡SÚPER CEREBRO ADAPTATIVO OPERATIVO!*\nEl bot está enlazado con éxito a Render, GitHub y Telegram. Monitoreando mercados tradicionales en Demo las 24/7.", parse_mode="Markdown")
    except Exception as e:
        print(f"⚠️ Alerta de inicio en Telegram: {e}")
        
    while True:
        ahora = datetime.datetime.now()
        tiempo_espera = 60 - ahora.second
        time.sleep(tiempo_espera)
        
        # Resetear filtro de correlación cada minuto nuevo
        operado_este_minuto = False
        
        # Filtro de Noticias Económicas (Freno de mano automático)
        if verificar_noticias_usd():
            print("🛑 Filtro de Noticias Activo: Pausando análisis por volatilidad extrema en USD.")
            continue
            
        # Disparo en paralelo multihilo (Ultra-baja latencia para las 4 divisas)
        for pair in DIVISAS:
            threading.Thread(target=analizar_vela_minuto, args=(pair,)).start()

if __name__ == "__main__":
    despachador_central()
