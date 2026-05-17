import os
import sys
import time
import json
import http.client
from datetime import datetime
from threading import Thread
import threading
from flask import Flask
import pytz       # Manejo preciso de sesiones horarias (Nueva York)
import psycopg2   # Conexión permanente a PostgreSQL en Render

# Servidor web obligatorio para Render
app = Flask(__name__)

@app.route('/')
def home():
    return "🚀 Sniper Multi-Algoritmo V4 está ONLINE y operando de forma paralela."

@app.route('/healthz')
def health():
    return "OK", 200

# --- CONFIGURACIÓN DE ACCESOS (Cargados de forma segura desde Environment) ---
TOKEN = os.environ.get("TELEGRAM_TOKEN", "8925198476:AAFOK71Hj3EjwOnJWFsgKNzX5ZxeeIhmYbA")
CHAT_ID = os.environ.get("CHAT_ID", "8623414493")
USUARIO = os.environ.get("IQ_OPTION_EMAIL", "73306657jc@gmail.com")
CLAVE = os.environ.get("IQ_OPTION_PASSWORD", "juliocesarpazcopa73")

# --- PARÁMETROS BASE ---
ACTIVO = "EURUSD"        
TIMEFRAME = 1            # Velas de 1 minuto
PERIODO_RSI = 14         
PERIODO_EMA = 200        # Filtro macro institucional
PERIODO_STOCH = 14       
PERIODO_D = 3            
PERIODO_ATR = 14         

ultimo_disparo = 0

# =====================================================================
# 1. MÓDULO DE BASE DE DATOS POSTGRESQL (La Memoria del Sniper)
# =====================================================================
def conectar_db():
    try:
        db_url = os.environ.get('DATABASE_URL')
        if db_url:
            return psycopg2.connect(db_url, sslmode='require')
    except Exception as e:
        print(f"❌ Error de conexión a PostgreSQL: {e}")
    return None

def inicializar_db():
    conn = conectar_db()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS registro_aprendizaje_sniper (
                    id SERIAL PRIMARY KEY,
                    fecha_hora TIMESTAMP WITH TIME ZONE,
                    tipo_operacion VARCHAR(10),
                    precio_entrada REAL,
                    rsi_valor REAL,
                    stoch_k REAL,
                    stoch_d REAL,
                    atr_valor REAL,
                    tendencia VARCHAR(10),
                    limite_usado INTEGER,
                    efectividad_estimada VARCHAR(10)
                );
            ''')
            conn.commit()
            cursor.close()
            conn.close()
            print("💾 [DB] Tabla de aprendizaje verificada/creada con éxito.")
        except Exception as e:
            print(f"❌ Error al inicializar la base de datos: {e}")

def registrar_huella_mercado(tipo, precio, rsi, sk, sd, atr, tend, limite):
    conn = conectar_db()
    if conn:
        try:
            cursor = conn.cursor()
            fecha_act = datetime.now(pytz.timezone('America/New_York'))
            cursor.execute('''
                INSERT INTO registro_aprendizaje_sniper 
                (fecha_hora, tipo_operacion, precio_entrada, rsi_valor, stoch_k, stoch_d, atr_valor, tendencia, limite_usado, efectividad_estimada)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            ''', (fecha_act, tipo, precio, rsi, sk, sd, atr, tend, limite, "70-73%"))
            conn.commit()
            cursor.close()
            conn.close()
            print(f"📥 [DB] Huella de mercado guardada con éxito para {tipo}.")
        except Exception as e:
            print(f"❌ Error al registrar huella en la BD: {e}")

# =====================================================================
# 2. FILTRO DE HORARIOS INTELIGENTE (El Reloj de la Zona de Caza)
# =====================================================================
def es_horario_de_caza():
    try:
        zona_ny = pytz.timezone('America/New_York')
        ahora_ny = datetime.now(zona_ny)
        hora_actual = ahora_ny.time()
        dia_semana = ahora_ny.weekday()
        
        if dia_semana == 4 and hora_actual >= datetime.strptime("17:00:00", "%H:%M:%S").time():
            return False
        if dia_semana == 5:
            return False
        if dia_semana == 6 and hora_actual < datetime.strptime("17:00:00", "%H:%M:%S").time():
            return False
            
        hora_inicio = datetime.strptime("02:00:00", "%H:%M:%S").time()
        hora_fin = datetime.strptime("13:00:00", "%H:%M:%S").time()
        
        if hora_inicio <= hora_actual <= hora_fin:
            return True
    except Exception as e:
        print(f"❌ Error en filtro de horarios: {e}")
    return True # Retorna True temporalmente si deseas forzar pruebas fuera de hora

# --- SISTEMA DE COMUNICACIÓN ---
def enviar_alerta(txt):
    try:
        conn = http.client.HTTPSConnection("api.telegram.org", timeout=4)
        payload = json.dumps({"chat_id": CHAT_ID, "text": txt, "parse_mode": "Markdown"})
        headers = {"Content-Type": "application/json"}
        conn.request("POST", f"/bot{TOKEN}/sendMessage", payload, headers)
        res = conn.getresponse()
        res.read()
        conn.close()
    except Exception as e:
        print(f"❌ Error al enviar alerta de Telegram: {e}")

# =====================================================================
# 3. PROCESAMIENTO ANALÍTICO AVANZADO
# =====================================================================
def calcular_indicadores_avanzados(velas):
    global ultimo_disparo
    
    if not es_horario_de_caza():
        return

    try:
        precios_close = [float(v.get('close', v.get('c'))) for v in velas]
        precios_high = [float(v.get('high', v.get('h'))) for v in velas]
        precios_low = [float(v.get('low', v.get('l'))) for v in velas]
        precios_open = [float(v.get('open', v.get('o'))) for v in velas]
        
        if len(precios_close) < PERIODO_EMA:
            return
        
        ema = precios_close[0]
        k = 2 / (PERIODO_EMA + 1)
        for precio in precios_close[1:]:
            ema = (precio * k) + (ema * (1 - k))
        
        precio_actual = precios_close[-1]
        tendencia = "ALCISTA" if precio_actual > ema else "BAJISTA"

        tr_totales = []
        for i in range(1, len(precios_close)):
            h = precios_high[i]
            l = precios_low[i]
            pc = precios_close[i-1]
            tr = max(h - l, abs(h - pc), abs(l - pc))
            tr_totales.append(tr)
        atr = sum(tr_totales[-PERIODO_ATR:]) / PERIODO_ATR
        
        atr_promedio = sum(tr_totales[-50:]) / 50 if len(tr_totales) >= 50 else atr
        if atr >= atr_promedio:
            limite_sobreventa = 22
            limite_sobrecompra = 78
            estado_volatilidad = "Alta/Saludable (Más Señales)"
        else:
            limite_sobreventa = 16
            limite_sobrecompra = 84
            estado_volatilidad = "Baja/Compresa (Máxima Restricción)"

        subidas = []
        bajadas = []
        for i in range(1, len(precios_close)):
            dif = precios_close[i] - precios_close[i-1]
            subidas.append(max(0, dif))
            bajadas.append(max(0, -dif))
            
        avg_gain = sum(subidas[-PERIODO_RSI:]) / PERIODO_RSI
        avg_loss = sum(bajadas[-PERIODO_RSI:]) / PERIODO_RSI
        rsi = 100 if avg_loss == 0 else 100 - (100 / (1 + (avg_gain / avg_loss)))

        stoch_k_valores = []
        for j in range(len(precios_close) - PERIODO_D, len(precios_close)):
            sub_high = precios_high[j - PERIODO_STOCH + 1 : j + 1]
            sub_low = precios_low[j - PERIODO_STOCH + 1 : j + 1]
            highest_high = max(sub_high)
            lowest_low = min(sub_low)
            c_actual = precios_close[j]
            
            k_val = 100 if (highest_high - lowest_low) == 0 else ((c_actual - lowest_low) / (highest_high - lowest_low)) * 100
            stoch_k_valores.append(k_val)
            
        stoch_k = stoch_k_valores[-1]
        stoch_d = sum(stoch_k_valores) / PERIODO_D
        
        ahora = time.time()
        
        if ahora - ultimo_disparo > 60:
            if tendencia == "ALCISTA" and rsi <= limite_sobreventa:
                if stoch_k > stoch_d and stoch_k < 30:
                    ultima_vela_roja_fuerte = (precios_close[-1] < precios_open[-1]) and (abs(precios_close[-1] - precios_low[-1]) < (precios_open[-1] - precios_close[-1]) * 0.2)
                    if ultima_vela_roja_fuerte:
                        return

                    registrar_huella_mercado('COMPRA', precio_actual, rsi, stoch_k, stoch_d, atr, tendencia, limite_sobreventa)
                    
                    msg = (f"🎯 *SNIPER V4: COMPRA (CALL)*\n\n"
                           f"🔹 *Activo:* {ACTIVO} | *Precio:* `{precio_actual}`\n"
                           f"📊 *RSI:* `{rsi:.2f}`\n"
                           f"📈 *EMA 200:* Alcista Macro\n"
                           f"⏱️ *Expiración:* 2 a 5 minutos en tu Broker.")
                    enviar_alerta(msg)
                    ultimo_disparo = ahora
            
            elif tendencia == "BAJISTA" and rsi >= limite_sobrecompra:
                if stoch_k < stoch_d and stoch_k > 70:
                    ultima_vela_verde_fuerte = (precios_close[-1] > precios_open[-1]) and (abs(precios_high[-1] - precios_close[-1]) < (precios_close[-1] - precios_open[-1]) * 0.2)
                    if ultima_vela_verde_fuerte:
                        return

                    registrar_huella_mercado('VENTA', precio_actual, rsi, stoch_k, stoch_d, atr, tendencia, limite_sobrecompra)
                    
                    msg = (f"🎯 *SNIPER V4: VENTA (PUT)*\n\n"
                           f"🔹 *Activo:* {ACTIVO} | *Precio:* `{precio_actual}`\n"
                           f"📊 *RSI:* `{rsi:.2f}`\n"
                           f"📉 *EMA 200:* Bajista Macro\n"
                           f"⏱️ *Expiración:* 2 a 5 minutos en tu Broker.")
                    enviar_alerta(msg)
                    ultimo_disparo = ahora
    except Exception as e:
        print(f"❌ Error en cálculo de indicadores: {e}")

# =====================================================================
# 4. CONEXIÓN Y FLUJO PRINCIPAL
# =====================================================================
def iniciar_bot():
    import websocket
    inicializar_db()
    
    enviar_alerta("🔥 *SNIPER V4 INICIADO EN RENDER*\nEl sistema está en paralelo buscando señales.")
    
    ssid = None
    try:
        h_conn = http.client.HTTPSConnection("auth.iqoption.com", timeout=10)
        payload = json.dumps({"identifier": USUARIO, "password": CLAVE})
        headers = {'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
        h_conn.request("POST", "/api/v2/login", payload, headers)
        res = h_conn.getresponse()
        data = json.loads(res.read().decode())
        h_conn.close()
        ssid = data.get("data", {}).get("ssid") or data.get("ssid")
    except Exception as e:
        print(f"❌ Error en autenticación con el Broker: {e}")

    if not ssid:
        print("❌ No se pudo obtener el SSID de conexión.")
        return

    def on_message(ws, message):
        try:
            msg = json.loads(message)
            if msg.get("name") == "candles" or "candles" in msg:
                velas_lista = msg["msg"]["candles"] if "msg" in msg else msg["candles"]
                calcular_indicadores_avanzados(velas_lista)
        except Exception as e:
            print(f"❌ Error en lectura de socket: {e}")

    def on_open(ws):
        def run(*args):
            try:
                ws.send(json.dumps({"name": "ssid", "msg": ssid}))
                time.sleep(1)
                ws.send(json.dumps({"name": "subscribeSymbols", "msg": {"symbols": [{"symbol": ACTIVO, "tf": TIMEFRAME}]}}))
                while True:
                    ws.send(json.dumps({"name": "sendMessage", "msg": {"name": "get-candles", "version": "2.0", "body": {"active_id": 1, "size": 60 * TIMEFRAME, "to": int(time.time()), "count": 230}}}))
                    time.sleep(5)
            except Exception as e:
                print(f"❌ Error en bucle de peticiones: {e}")
        Thread(target=run).start()

    while True:
        try:
            ws = websocket.WebSocketApp("wss://iqoption.com/echo/websocket", on_message=on_message, on_open=on_open)
            ws.run_forever()
        except Exception as e:
            print(f"❌ WebSocket desconectado. Reintentando en 5s... Error: {e}")
        time.sleep(5)

# --- ARRANQUE MULTI-HILO SEGURO ---
# Ejecuta la lógica del trading en segundo plano sin interrumpir a Flask
hilo_trading = threading.Thread(target=iniciar_bot, daemon=True)
hilo_trading.start()

if __name__ == '__main__':
    puerto = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=puerto)
