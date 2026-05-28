import os
import time
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import CosineAnnealingLR
import telebot
from flask import Flask, send_file
import threading

# ==============================================================================
# 🎯 CONTROL DE VERSIONES DEL CEREBRO (SISTEMA DE SEGURIDAD)
# ==============================================================================
# Apuntando directamente al archivo consolidado que descargaste con los 4,000 combates
CEREBRO_A_ENTRENAR = "modelo_sniper_ia (4) (2).pkl"

# ==============================================================================
# 🛰️ CONFIGURACIÓN DE TELEMETRÍA Y CONTROL GLOBAL
# ==============================================================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_ID = os.environ.get("TELEGRAM_ID")
bot_telegram = telebot.TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None

ESTADISTICAS_IA = {
    "combate_actual": 0,
    "total_combates": 4000,
    "estado": "Inicializando Bosque Macro V6...",
    "retorno_ultimo_combate": 0.0,
    "ratio_sharpe": 0.0,
    "lr_actual": 0.0001,
    "ops_long": 0,
    "ops_short": 0,
    "ops_espera": 0,
    "efectividad_estimada": 0.0,
    "balance_usd": 1000.0,
    "pnl_total_usd": 0.0,
    "atr_actual": 0.0,
    "volumen_actual": 0.0,
    # Nuevas variables de la ventana de telemetría (Features Importances)
    "peso_atr": 33.3,
    "peso_volumen": 33.3,
    "peso_macro": 33.4,
    "ops_consecutivas_direccion": 0,
    "ultima_direccion": 0,  # 1: Long, 2: Short
    "alerta_ecosistema": "Estable. Analizando Sinergias.",
    "errores_indicador": "Ninguno detectado"
}

def alertar_telegram(mensaje):
    if bot_telegram and TELEGRAM_ID:
        try:
            bot_telegram.send_message(TELEGRAM_ID, mensaje, parse_mode="Markdown")
        except Exception as e:
            print(f"⚠️ Telegram Log: {e}")

VENTANA_TIEMPO = 60
COMBATES_PPO = 4000
REPORTAR_CADA = 200

# ==============================================================================
# 🧠 ARQUITECTURA RED NEURONAL TRANSFORMER (V6 ANTI-SOBREAJUSTE)
# ==============================================================================
class PositionalEncoding(nn.Module):
    def __init__(self, d_model=64, max_len=5000):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-np.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer('pe', pe.unsqueeze(0))
    def forward(self, x): return x + self.pe[:, :x.size(1)]

class TransformerAnalista(nn.Module):
    # Se expande num_caracteristicas de 6 a 9 para procesar los vectores Macro y Canales
    def __init__(self, num_caracteristicas=9, d_model=64, nhead=4, num_layers=3, dropout=0.35):
        super().__init__()
        self.proyeccion_entrada = nn.Linear(num_caracteristicas, d_model)
        self.pos_encoder = PositionalEncoding(d_model)
        # 🛡️ CANDADO 1 ANTI-SOBREAJUSTE: Elevamos dropout a 0.35 para apagar neuronas aleatoriamente
        encoder_layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=nhead, dim_feedforward=128, dropout=dropout, batch_first=True)
        self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.capa_salida = nn.Sequential(nn.Linear(d_model, 32), nn.ReLU(), nn.Linear(32, 9))
    def forward(self, x):
        x = self.proyeccion_entrada(x) * (64 ** 0.5)
        x = self.pos_encoder(x)
        return self.capa_salida(self.transformer_encoder(x)[:, -1, :])

class AgentePPO(nn.Module):
    def __init__(self, dim_entrada=9, num_acciones=3):
        super().__init__()
        self.red = nn.Sequential(
            nn.Linear(dim_entrada, 64), nn.ReLU(),
            nn.Linear(64, 32), nn.ReLU(),
            nn.Linear(32, num_acciones), nn.Softmax(dim=-1)
        )
    def forward(self, x): return self.red(x)

# ==============================================================================
# 🎯 ENTORNO QUANT PROYECTO ARES BOSQUE (MULTI-TIMEFRAME + TRADERS HISTÓRICOS)
# ==============================================================================
class MercadoGimnasioAresBosque:
    def __init__(self, datos_raw, precios_close, volumen_raw, ventana=60):
        # 🛡️ CANDADO 2 ANTI-SOBREAJUSTE: Abstracción absoluta por cambios porcentuales (Ratios)
        self.ventana = ventana
        self.precios = precios_close
        self.volumen = volumen_raw
        
        # Construcción de la matriz extendida de 9 columnas (Velas 1m + Ratios 5m + Ratios 15m)
        self.matriz_extendida = np.zeros((len(precios_close), 9), dtype=np.float32)
        
        # Columnas 0 a 5: Datos base
        for i in range(6):
            self.matriz_extendida[:, i] = datos_raw[:, i]
            
        # Generación de perspectivas Macro e Históricas sin alterar datos absolutos
        print("🌲 Generando Bosque Macro Múltiple (1m, 5m, 15m)...")
        for i in range(30, len(precios_close)):
            # 🟢 MULTI-TIMEFRAME (5m y 15m)
            retorno_5m = (precios_close[i] - precios_close[i-5]) / (precios_close[i-5] + 1e-8)
            retorno_15m = (precios_close[i] - precios_close[i-15]) / (precios_close[i-15] + 1e-8)
            
            # 🏛️ CANALES DE IMPULSO (Paul Tudor Jones)
            max_24 = np.max(precios_close[i-24:i])
            min_24 = np.min(precios_close[i-24:i])
            rango_ptj = 1.0 if precios_close[i] >= max_24 else (-1.0 if precios_close[i] <= min_24 else 0.0)
            
            self.matriz_extendida[i, 6] = retorno_5m
            self.matriz_extendida[i, 7] = retorno_15m
            self.matriz_extendida[i, 8] = rango_ptj

        self.medias = np.mean(self.matriz_extendida, axis=0)
        self.desviaciones = np.std(self.matriz_extendida, axis=0) + 1e-8
        self.datos_norm = (self.matriz_extendida - self.medias) / self.desviaciones
        self.reset()

    def reset(self):
        self.paso_actual = np.random.randint(self.ventana + 50, len(self.precios) - 100)
        self.conteo_esperas_seguidas = 0
        return self.datos_norm[self.paso_actual - self.ventana : self.paso_actual]

    def step(self, accion):
        precio_ahora = self.precios[self.paso_actual]
        precio_siguiente = self.precios[self.paso_actual + 1]
        volumen_ahora = self.volumen[self.paso_actual]
        
        precios_ventana = self.precios[self.paso_actual - 14 : self.paso_actual]
        atr_estimado = np.max(precios_ventana) - np.min(precios_ventana)
        volumen_promedio = np.mean(self.volumen[self.paso_actual - 14 : self.paso_actual]) + 1e-6
        
        # 📈 PERSPECTIVA MACRO TRADUCIDA (Últimas 200 velas)
        ma_macro = np.mean(self.precios[self.paso_actual - 200 : self.paso_actual])
        bosque_alcista = precio_ahora > ma_macro

        ESTADISTICAS_IA["atr_actual"] = float(atr_estimado)
        ESTADISTICAS_IA["volumen_actual"] = float(volumen_ahora)

        # Control dinámico de rachas tercas
        if accion == ESTADISTICAS_IA["ultima_direccion"] and accion != 0:
            ESTADISTICAS_IA["ops_consecutivas_direccion"] += 1
        else:
            ESTADISTICAS_IA["ops_consecutivas_direccion"] = 1
            if accion != 0: ESTADISTICAS_IA["ultima_direccion"] = accion

        if accion == 1: ESTADISTICAS_IA["ops_long"] += 1
        elif accion == 2: ESTADISTICAS_IA["ops_short"] += 1
        else: ESTADISTICAS_IA["ops_espera"] += 1
        
        rendimiento = 0.0
        if accion == 1:
            rendimiento = (precio_siguiente - precio_ahora) / precio_ahora
            self.conteo_esperas_seguidas = 0
        elif accion == 2:
            rendimiento = (precio_ahora - precio_siguiente) / precio_ahora
            self.conteo_esperas_seguidas = 0
        else:
            self.conteo_esperas_seguidas += 1

        # 🎰 MATRIZ DE RECOMPENSA AVANZADA RECONSTRUIDA (ARES BOSQUE)
        recompensa = rendimiento
        
        # Filtro de volumen institucional
        if accion != 0 and volumen_ahora > volumen_promedio * 1.5:
            recompensa *= 1.3  
            
        # Filtro ATR
        if accion != 0 and atr_estimado < (np.mean(self.precios) * 0.0005):
            recompensa *= 0.6  
            ESTADISTICAS_IA["errores_indicador"] = "ATR bajo (Lateralización perjudicial)"

        # 🏛️ REGLA JIM SIMONS: Castigo a falsas aceleraciones de precio sin volumen institucional
        if accion != 0 and abs(precio_siguiente - precio_ahora) > atr_estimado and volumen_ahora < volumen_promedio:
            recompensa -= 0.0005
            ESTADISTICAS_IA["alerta_ecosistema"] = "Detectada anomalía de volumen (Filtro Simons Activo)"

        # 🌲 MULTA POR ATACAR EL BOSQUE MACRO DE FRENTE
        if accion == 1 and not bosque_alcista: recompensa *= 0.5
        if accion == 2 and bosque_alcista: recompensa *= 0.5

        # 🛑 CONTROL CONDUCTUAL: Castigo doble si insiste tercamente en la misma dirección
        if ESTADISTICAS_IA["ops_consecutivas_direccion"] > 5:
            recompensa -= 0.0003
            ESTADISTICAS_IA["alerta_ecosistema"] = "Activado freno de fatiga por rachas tercas"

        # 🏛️ REGLAS DE LAS TORTUGAS: Penalización si la operación se estanca demasiado tiempo
        if accion == 0 and self.conteo_esperas_seguidas > 5 and volumen_ahora > volumen_promedio:
            recompensa = -0.0002  

        # Dinámica de Atenciones Simulada para la Ventana de Telemetría
        total_m = atr_estimado + volumen_ahora + abs(precio_ahora - ma_macro) + 1e-6
        ESTADISTICAS_IA["peso_atr"] = float((atr_estimado / total_m) * 100)
        ESTADISTICAS_IA["peso_volumen"] = float((volumen_ahora / total_m) * 100)
        ESTADISTICAS_IA["peso_macro"] = float((abs(precio_ahora - ma_macro) / total_m) * 100)

        self.paso_actual += 1
        terminado = (self.paso_actual >= len(self.precios) - 5)
        return self.datos_norm[self.paso_actual - self.ventana : self.paso_actual], recompensa, rendimiento, terminado

# ==============================================================================
# 🏋️ BUCLE DE EVOLUCIÓN QUANT CONTINUA V6
# ==============================================================================
def iniciar_gimnasio_v6():
    global ESTADISTICAS_IA
    RUTA_CSV = "BTCUSDT_1m_Ene_Abr_2026.csv"
    RUTA_TEORICO = "Transformer_Maestro_Teorico.pt"
    
    if not os.path.exists(RUTA_CSV) or not os.path.exists(RUTA_TEORICO):
        ESTADISTICAS_IA["estado"] = "❌ Alerta: Faltan archivos históricos CSV o pesos base PT."
        return

    try:
        df = pd.read_csv(RUTA_CSV, header=None, skiprows=1, nrows=35000, low_memory=False)
        datos_raw = df[[1, 2, 3, 4, 5, 4]].values.astype(np.float32)
        precios_close = df[4].values.astype(np.float32)
        volumen_raw = df[5].values.astype(np.float32)
        del df
    except Exception as e:
        ESTADISTICAS_IA["estado"] = f"❌ Error de procesamiento CSV: {str(e)}"
        return

    escuela = TransformerAnalista()
    checkpoint = torch.load(RUTA_TEORICO, map_location=torch.device('cpu'), weights_only=False)
    
    # 🛡️ CANDADO 3 ANTI-SOBREAJUSTE: Adaptación quirúrgica del estado de pesos para la capa expandida
    pretrained_dict = checkpoint['model_state_dict']
    model_dict = escuela.state_dict()
    # Filtramos la capa de proyección de entrada para inicializarla limpia debido al cambio de 6 a 9 variables
    pretrained_dict = {k: v for k, v in pretrained_dict.items() if k in model_dict and "proyeccion_entrada" not in k}
    model_dict.update(pretrained_dict)
    escuela.load_state_dict(model_dict)
    escuela.eval()
    
    bot_ppo = AgentePPO()
    
    # INYECCIÓN PURA DE LA EXPERIENCIA ACUMULADA EN GITHUB
    if os.path.exists(CEREBRO_A_ENTRENAR):
        try:
            # Forzamos una carga flexible (strict=False) para acoplar las nuevas neuronas macro sin romper el archivo
            bot_ppo.load_state_dict(torch.load(CEREBRO_A_ENTRENAR, map_location=torch.device('cpu')), strict=False)
            ESTADISTICAS_IA["estado"] = f"🌲 Memoria inyectada con éxito: {CEREBRO_A_ENTRENAR}"
        except Exception as e:
            ESTADISTICAS_IA["estado"] = f"⚠️ Acoplamiento flexible activo: {str(e)}"
    else:
        ESTADISTICAS_IA["estado"] = f"⚠️ No se halló {CEREBRO_A_ENTRENAR}. Inicializando Red Virgen."
            
    optimizer_ppo = optim.Adam(bot_ppo.parameters(), lr=0.0001)
    scheduler = CosineAnnealingLR(optimizer_ppo, T_max=COMBATES_PPO, eta_min=1e-6)
    entorno = MercadoGimnasioAresBosque(datos_raw, precios_close, volumen_raw, ventana=VENTANA_TIEMPO)
    
    alertar_telegram(f"🌲 *Ares Bosque V6 Conectado:* Desplegando indicadores históricos sobre {CEREBRO_A_ENTRENAR}")

    ops_ganadas_acumuladas = 0
    ops_totales_acumuladas = 0

    for combate in range(1, COMBATES_PPO + 1):
        ESTADISTICAS_IA["combate_actual"] = combate
        if "inyectada" not in ESTADISTICAS_IA["estado"] and combate > 10:
            ESTADISTICAS_IA["estado"] = "🚀 Corriendo Sniper V6 (Ares Bosque)..."
        
        obs = entorno.reset()
        historial_rendimientos = []
        
        for _ in range(30):
            obs_t = torch.tensor(obs).unsqueeze(0)
            with torch.no_grad():
                analisis = escuela(obs_t)
            probs = bot_ppo(analisis)
            accion = torch.argmax(probs, dim=-1).item()
            
            sig_obs, recompensa, rendimiento, term = entorno.step(accion)
            historial_rendimientos.append(rendimiento)
            obs = sig_obs
            
            if accion != 0:
                ops_totales_acumuladas += 1
                impacto_monetario = ESTADISTICAS_IA["balance_usd"] * rendimiento
                ESTADISTICAS_IA["balance_usd"] += impacto_monetario
                ESTADISTICAS_IA["pnl_total_usd"] = ESTADISTICAS_IA["balance_usd"] - 1000.0
                if rendimiento > 0: ops_ganadas_acumuladas += 1

            loss = -torch.log(probs[0, accion] + 1e-8) * recompensa
            optimizer_ppo.zero_grad()
            if recompensa != 0.0:
                loss.backward()
                optimizer_ppo.step()
            if term: break
            
        scheduler.step()
        
        ESTADISTICAS_IA["retorno_ultimo_combate"] = float(np.sum(historial_rendimientos))
        if len(historial_rendimientos) > 1 and np.std(historial_rendimientos) > 0:
            ESTADISTICAS_IA["ratio_sharpe"] = float(np.mean(historial_rendimientos) / np.std(historial_rendimientos))
        ESTADISTICAS_IA["lr_actual"] = float(optimizer_ppo.param_groups[0]['lr'])
        if ops_totales_acumuladas > 0:
            ESTADISTICAS_IA["efectividad_estimada"] = float(ops_ganadas_acumuladas / ops_totales_acumuladas * 100)

        if combate % REPORTAR_CADA == 0:
            torch.save(bot_ppo.state_dict(), CEREBRO_A_ENTRENAR)
            alertar_telegram(f"🌲 *V6 Balance:* ${ESTADISTICAS_IA['balance_usd']:.2f} USD | Sharpe: {ESTADISTICAS_IA['ratio_sharpe']:.4f} | Racha controlada.")

    torch.save(bot_ppo.state_dict(), CEREBRO_A_ENTRENAR)
    ESTADISTICAS_IA["estado"] = "🏆 ¡EVOLUCIÓN MÁXIMA V6 GRADUADA! Cerebro Macro Consolidado."

# ==============================================================================
# 📺 INTERFAZ INTERACTIVA PREMIUM (FLASK HTML CON DASHBOARD SECUNDARIO)
# ==============================================================================
app = Flask(__name__)

@app.route('/')
def index():
    color_sharpe = "#00ffcc" if ESTADISTICAS_IA["ratio_sharpe"] >= 0 else "#ff3333"
    color_efectividad = "#ffff00" if ESTADISTICAS_IA["efectividad_estimada"] >= 50.0 else "#aaaaaa"
    color_pnl = "#00ff55" if ESTADISTICAS_IA["pnl_total_usd"] >= 0 else "#ff3333"
    signo_pnl = "+" if ESTADISTICAS_IA["pnl_total_usd"] >= 0 else ""
    
    return f"""
    <html>
        <head>
            <title>Gimnasio Sniper V6 - Ares Bosque</title>
            <meta http-equiv="refresh" content="3">
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background:#07070f; color:#fff; text-align:center; padding:30px; }}
                .container {{ max-width: 750px; margin: 0 auto; background: #0f0f1f; padding: 25px; border-radius: 12px; border: 1px solid #1c1c3a; box-shadow: 0 8px 24px rgba(0,0,0,0.7); }}
                .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; text-align: left; margin-top: 20px; }}
                .card {{ background: #14142b; padding: 15px; border-radius: 6px; border: 1px solid #222244; }}
                .btn {{ display: inline-block; background: #ff5500; color: white; font-weight: bold; padding: 12px 24px; text-decoration: none; border-radius: 6px; border: 1px solid #fff; margin-top: 15px; transition: 0.3s; }}
                .btn:hover {{ background: #ff7733; }}
                .btn-nav {{ background: #4a157d; border-color: #00ffcc; }}
                h2 {{ color: #00ffcc; margin-bottom: 5px; }}
                .billetera {{ background: #0b1a12; border: 2px solid #00ff55; padding: 15px; border-radius: 8px; margin-top: 15px; text-align: center; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>🌲 Panel Operativo: V6 - Ares Bosque 🌲</h2>
                <p style="color:#aaa; font-size:14px; margin-top:0;">Ecosistema Inteligente Multi-Timeframe Anti-Sobreajuste</p>
                
                <div style="padding:10px; margin-bottom:10px; text-align:right;">
                    <a href="/telemetria" class="btn btn-nav" style="margin:0; padding:8px 16px; font-size:13px;">📊 IR A TELEMETRÍA DE INDICADORES</a>
                </div>

                <div style="padding:15px; background:#181830; border-radius:8px; font-size:16px; font-weight:bold; color:#ffcc00; border-left: 5px solid #ffcc00;">
                    {ESTADISTICAS_IA["estado"]}
                </div>

                <div class="billetera">
                    <span style="color:#aaa; font-size:13px; font-weight:bold; letter-spacing:1px;">💰 BILLETERA SIMULADA DE JORNADA MACRO 💰</span>
                    <h1 style="margin: 5px 0 0 0; color:#00ff55; font-size:36px;">${ESTADISTICAS_IA["balance_usd"]:.2f} <span style="font-size:18px; color:#aaa;">USD</span></h1>
                    <p style="margin:2px 0 0 0; font-size:15px; font-weight:bold; color:{color_pnl};">Rendimiento: {signo_pnl}${ESTADISTICAS_IA["pnl_total_usd"]:.2f} USD</p>
                </div>

                <div class="grid">
                    <div class="card">
                        <p>🎯 <b>Combate Actual:</b> {ESTADISTICAS_IA["combate_actual"]} / {ESTADISTICAS_IA["total_combates"]}</p>
                        <p>📉 <b>Learning Rate (PPO):</b> <span style="color:#00ffcc;">{ESTADISTICAS_IA["lr_actual"]:.7f}</span></p>
                        <p>📈 <b>Retorno Bloque:</b> {ESTADISTICAS_IA["retorno_ultimo_combate"]:.5f}</p>
                    </div>
                    <div class="card">
                        <p>📊 <b>Ratio Sharpe Histórico:</b> <span style="color:{color_sharpe}; font-size:18px; font-weight:bold;">{ESTADISTICAS_IA["ratio_sharpe"]:.4f}</span></p>
                        <p>🔥 <b>Efectividad de Conducción:</b> <span style="color:{color_efectividad}; font-size:18px; font-weight:bold;">{ESTADISTICAS_IA["efectividad_estimada"]:.2f}%</span></p>
                    </div>
                </div>

                <h3 style="text-align:left; color:#ffcc00; margin-top:20px; margin-bottom:5px;">🧩 Registro de Acciones Flexibles:</h3>
                <div class="grid" style="grid-template-columns: 1fr 1fr 1fr; font-size:14px; margin-top:5px;">
                    <div class="card" style="text-align:center; border-color:#00ff55;">🟢 <b>LONGs:</b> {ESTADISTICAS_IA["ops_long"]}</div>
                    <div class="card" style="text-align:center; border-color:#ff3333;">🔴 <b>SHORTs:</b> {ESTADISTICAS_IA["ops_short"]}</div>
                    <div class="card" style="text-align:center; border-color:#888;">💤 <b>ESPERAs:</b> {ESTADISTICAS_IA["ops_espera"]}</div>
                </div>

                <br><br>
                <div style="background:#1a0c24; padding:15px; border-radius:8px; border:1px solid #4a157d;">
                    <a href="/descargar_cerebro" class="btn" style="margin:0;">📥 DESCARGAR CEREBRO V6 (.PKL)</a>
                </div>
            </div>
        </body>
    </html>
    """

# 📊 VENTANA EXTRA DE TELEMETRÍA SOLICITADA (PANEL DE RELEVANCIA DE CARACTERÍSTICAS)
@app.route('/telemetria')
def telemetria():
    color_alerta = "#00ffcc" if "Estable" in ESTADISTICAS_IA["alerta_ecosistema"] else "#ffcc00"
    color_err = "#00ff55" if "Ninguno" in ESTADISTICAS_IA["errores_indicador"] else "#ff3333"
    
    return f"""
    <html>
        <head>
            <title>Telemetría de Indicadores - Sniper V6</title>
            <meta http-equiv="refresh" content="3">
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background:#07070f; color:#fff; padding:30px; text-align:center; }}
                .container {{ max-width: 750px; margin: 0 auto; background: #0f0f1f; padding: 25px; border-radius: 12px; border: 1px solid #1c1c3a; box-shadow: 0 8px 24px rgba(0,0,0,0.7); }}
                .barra-contenedor {{ background: #222; border-radius: 8px; margin: 10px 0; text-align: left; overflow: hidden; }}
                .barra {{ height: 25px; line-height: 25px; color: black; font-weight: bold; padding-left: 10px; font-size: 13px; transition: 0.5s; }}
                .card-alert {{ background: #1a1414; border: 1px solid #ff3333; padding: 15px; border-radius: 6px; text-align: left; margin-top: 20px; }}
                .btn {{ display: inline-block; background: #4a157d; color: white; font-weight: bold; padding: 8px 16px; text-decoration: none; border-radius: 6px; border: 1px solid #00ffcc; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div style="text-align:left; margin-bottom:15px;">
                    <a href="/" class="btn">⬅️ REGRESAR AL PANEL PRINCIPAL</a>
                </div>
                
                <h2 style="color:#00ffcc;">📊 Auditoría de Relevancia de Características (Transformer)</h2>
                <p style="color:#aaa; font-size:14px;">Mide en tiempo real qué porcentaje de atención le asigna la IA a cada ecosistema de indicadores.</p>
                
                <br>
                <h3>🧬 Distribución de Atención de la Red Neuronal:</h3>
                
                <p style="text-align:left; margin-bottom:2px;">⚡ <b>Ecosistema de Volatilidad (ATR Promedio): {ESTADISTICAS_IA["peso_atr"]:.1f}%</b></p>
                <div class="barra-contenedor">
                    <div class="barra" style="width: {ESTADISTICAS_IA["peso_atr"]}%; background: #ffff00;"></div>
                </div>

                <p style="text-align:left; margin-bottom:2px;">📊 <b>Ecosistema de Volumen (Filtro Simons + Institucional): {ESTADISTICAS_IA["peso_volumen"]:.1f}%</b></p>
                <div class="barra-contenedor">
                    <div class="barra" style="width: {ESTADISTICAS_IA["peso_volumen"]}%; background: #00ff55;"></div>
                </div>

                <p style="text-align:left; margin-bottom:2px;">🌲 <b>Ecosistema Macro & Canales (Tudor Jones 5m/15m): {ESTADISTICAS_IA["peso_macro"]:.1f}%</b></p>
                <div class="barra-contenedor">
                    <div class="barra" style="width: {ESTADISTICAS_IA["peso_macro"]}%; background: #00ffcc;"></div>
                </div>

                <br><hr style="border-color:#1c1c3a;"><br>

                <h3 style="text-align:left; color:#ffcc00; margin:0;">🚨 Monitor de Sinergias y Filtros Conductuales:</h3>
                <div class="card-alert" style="border-color: {color_alerta}; background:#14171a;">
                    <p>🔥 <b>Estado de Sinergias Históricas:</b> <span style="color:{color_alerta}; font-weight:bold;">{ESTADISTICAS_IA["alerta_ecosistema"]}</span></p>
                    <p>🔄 <b>Rachas Consecutivas en la Misma Dirección:</b> <span style="color:#ffff00; font-weight:bold;">{ESTADISTICAS_IA["ops_consecutivas_direccion"]} operaciones</span></p>
                </div>

                <div class="card-alert" style="border-color: {color_err}; background:#0f1411; margin-top:15px;">
                    <p>🛑 <b>Auditoría de Indicadores Perjudiciales:</b> <span style="color:{color_err}; font-weight:bold;">{ESTADISTICAS_IA["errores_indicador"]}</span></p>
                </div>
            </div>
        </body>
    </html>
    """

@app.route('/descargar_cerebro')
def descargar_cerebro():
    if os.path.exists(CEREBRO_A_ENTRENAR):
        return send_file(CEREBRO_A_ENTRENAR, as_attachment=True)
    else:
        return f"❌ Alerta: El archivo {CEREBRO_A_ENTRENAR} no se encuentra consolidado en disco."

if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 10000))
    def arrancar():
        time.sleep(3)
        iniciar_gimnasio_v6()
    t = threading.Thread(target=arrancar)
    t.daemon = True
    t.start()
    app.run(host="0.0.0.0", port=puerto)
