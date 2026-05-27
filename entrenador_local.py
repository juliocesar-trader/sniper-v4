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
# Cambia este texto si en el futuro subes el "modelo_sniper_ia (5).pkl", etc.
CEREBRO_A_ENTRENAR = "modelo_sniper_ia (4).pkl"

# ==============================================================================
# 🛰️ CONFIGURACIÓN DE TELEMETRÍA Y CONTROL GLOBAL
# ==============================================================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_ID = os.environ.get("TELEGRAM_ID")
bot_telegram = telebot.TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None

ESTADISTICAS_IA = {
    "combate_actual": 0,
    "total_combates": 4000,
    "estado": "Inicializando Sensores Ares...",
    "retorno_ultimo_combate": 0.0,
    "ratio_sharpe": 0.0,
    "lr_actual": 0.0001,
    "ops_long": 0,
    "ops_short": 0,
    "ops_espera": 0,
    "efectividad_estimada": 0.0,
    "balance_usd": 1000.0,       # Billetera simulada inicial
    "pnl_total_usd": 0.0,        # Rendimiento acumulado en dólares
    "atr_actual": 0.0,           # Telemetría de Volatilidad
    "volumen_actual": 0.0        # Telemetría de Volumen Institucional
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
# 🧠 ARQUITECTURA RED NEURONAL TRANSFORMER
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
    def __init__(self, num_caracteristicas=6, d_model=64, nhead=4, num_layers=3, dropout=0.3):
        super().__init__()
        self.proyeccion_entrada = nn.Linear(num_caracteristicas, d_model)
        self.pos_encoder = PositionalEncoding(d_model)
        encoder_layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=nhead, dim_feedforward=128, dropout=dropout, batch_first=True)
        self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.capa_salida = nn.Sequential(nn.Linear(d_model, 32), nn.ReLU(), nn.Linear(32, 6))
    def forward(self, x):
        x = self.proyeccion_entrada(x) * (64 ** 0.5)
        x = self.pos_encoder(x)
        return self.capa_salida(self.transformer_encoder(x)[:, -1, :])

class AgentePPO(nn.Module):
    def __init__(self, dim_entrada=6, num_acciones=3):
        super().__init__()
        self.red = nn.Sequential(
            nn.Linear(dim_entrada, 64), nn.ReLU(),
            nn.Linear(64, 32), nn.ReLU(),
            nn.Linear(32, num_acciones), nn.Softmax(dim=-1)
        )
    def forward(self, x): return self.red(x)

# ==============================================================================
# 🎯 ENTORNO QUANT CON MATRIZ DE RECOMPENSA "ARES" (ATR + VOLUMEN + MULTAS)
# ==============================================================================
class MercadoGimnasioAres:
    def __init__(self, datos_raw, precios_close, volumen_raw, ventana=60):
        self.medias = np.mean(datos_raw, axis=0)
        self.desviaciones = np.std(datos_raw, axis=0) + 1e-8
        self.datos_norm = (datos_raw - self.medias) / self.desviaciones
        self.precios = precios_close
        self.volumen = volumen_raw
        self.ventana = ventana
        self.reset()

    def reset(self):
        self.paso_actual = np.random.randint(self.ventana + 20, len(self.precios) - 100)
        self.conteo_esperas_seguidas = 0
        return self.datos_norm[self.paso_actual - self.ventana : self.paso_actual]

    def step(self, accion):
        precio_ahora = self.precios[self.paso_actual]
        precio_siguiente = self.precios[self.paso_actual + 1]
        volumen_ahora = self.volumen[self.paso_actual]
        
        # 🟢 MEJORA 1 & 2: CÁLCULO EN VIVO DE INDICE ATR Y VOLUMEN PROMEDIO
        precios_ventana = self.precios[self.paso_actual - 14 : self.paso_actual]
        atr_estimado = np.max(precios_ventana) - np.min(precios_ventana)
        volumen_promedio = np.mean(self.volumen[self.paso_actual - 14 : self.paso_actual]) + 1e-6
        
        ESTADISTICAS_IA["atr_actual"] = float(atr_estimado)
        ESTADISTICAS_IA["volumen_actual"] = float(volumen_ahora)

        if accion == 1: ESTADISTICAS_IA["ops_long"] += 1
        elif accion == 2: ESTADISTICAS_IA["ops_short"] += 1
        else: ESTADISTICAS_IA["ops_espera"] += 1
        
        rendimiento = 0.0
        if accion == 1:  # LONG
            rendimiento = (precio_siguiente - precio_ahora) / precio_ahora
            self.conteo_esperas_seguidas = 0
        elif accion == 2:  # SHORT
            rendimiento = (precio_ahora - precio_siguiente) / precio_ahora
            self.conteo_esperas_seguidas = 0
        else:  # ESPERA
            self.conteo_esperas_seguidas += 1

        # 🎰 SISTEMA DE RECOMPENSAS AVANZADO (ARES)
        recompensa = rendimiento
        
        # Filtro de volumen institucional
        if accion != 0 and volumen_ahora > volumen_promedio * 1.5:
            recompensa *= 1.3  
            
        # Filtro ATR (Evitar laterales muertos)
        if accion != 0 and atr_estimado < (np.mean(self.precios) * 0.0005):
            recompensa *= 0.7  
            
        # 🔴 MEJORA 3: PENALIZACIÓN POR INACTIVIDAD ABSURDA
        if accion == 0 and self.conteo_esperas_seguidas > 7 and volumen_ahora > volumen_promedio:
            recompensa = -0.0002  
            
        self.paso_actual += 1
        terminado = (self.paso_actual >= len(self.precios) - 5)
        return self.datos_norm[self.paso_actual - self.ventana : self.paso_actual], recompensa, rendimiento, terminado

# ==============================================================================
# 🏋️ BUCLE DE EVOLUCIÓN QUANT CONTINUA
# ==============================================================================
def iniciar_gimnasio_v5_1():
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
    escuela.load_state_dict(checkpoint['model_state_dict'])
    escuela.eval()
    
    bot_ppo = AgentePPO()
    
    # INYECCIÓN DEL CEREBRO SELECCIONADO POR EL USUARIO
    if os.path.exists(CEREBRO_A_ENTRENAR):
        try:
            bot_ppo.load_state_dict(torch.load(CEREBRO_A_ENTRENAR, map_location=torch.device('cpu')))
            ESTADISTICAS_IA["estado"] = f"🔄 Memoria táctica inyectada desde: {CEREBRO_A_ENTRENAR}"
            print(f"🧠 Éxito: Pesos neuronales cargados desde {CEREBRO_A_ENTRENAR}")
        except Exception as e:
            ESTADISTICAS_IA["estado"] = f"⚠️ Error cargando {CEREBRO_A_ENTRENAR}: {str(e)}. Base limpia activa."
    else:
        ESTADISTICAS_IA["estado"] = f"⚠️ Archivo {CEREBRO_A_ENTRENAR} no hallado en raíz. Iniciando red virgen."
            
    optimizer_ppo = optim.Adam(bot_ppo.parameters(), lr=0.0001)
    scheduler = CosineAnnealingLR(optimizer_ppo, T_max=COMBATES_PPO, eta_min=1e-6)
    entorno = MercadoGimnasioAres(datos_raw, precios_close, volumen_raw, ventana=VENTANA_TIEMPO)
    
    np.save("medias.npy", entorno.medias)
    np.save("desviaciones.npy", entorno.desviaciones)

    alertar_telegram(f"🚀 *Ares V5.1 Conectado:* Sincronizado con cerebro: {CEREBRO_A_ENTRENAR}")

    ops_ganadas_acumuladas = 0
    ops_totales_acumuladas = 0

    for combate in range(1, COMBATES_PPO + 1):
        ESTADISTICAS_IA["combate_actual"] = combate
        if "inyectada" not in ESTADISTICAS_IA["estado"]:
            ESTADISTICAS_IA["estado"] = "🎯 Calibrando Sharpe con Filtros Avanzados (Ares)..."
        
        obs = entorno.reset()
        historial_rendimientos = []
        
        for _ in range(30):
            obs_t = torch.tensor(obs).unsqueeze(0)
            with torch.no_grad():
                analisis = school_output = escuela(obs_t)
            probs = bot_ppo(analisis)
            accion = torch.argmax(probs, dim=-1).item()
            
            sig_obs, recompensa, rendimiento, term = entorno.step(accion)
            historial_rendimientos.append(rendimiento)
            obs = sig_obs
            
            # 💰 CONTABILIDAD FINANCIERA EN DÓLARES (Apalancamiento 1x)
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
            alertar_telegram(f"⚡ *Ares:* [{combate}/{COMBATES_PPO}] | Billetera: ${ESTADISTICAS_IA['balance_usd']:.2f} USD | Sharpe: {ESTADISTICAS_IA['ratio_sharpe']:.4f}")

    torch.save(bot_ppo.state_dict(), CEREBRO_A_ENTRENAR)
    ESTADISTICAS_IA["estado"] = "🏆 ¡EVOLUCIÓN MÁXIMA! Francotirador de Élite Graduado."

# ==============================================================================
# 📺 INTERFAZ INTERACTIVA PREMIUM (FLASK HTML)
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
            <title>Gimnasio Sniper V5.1 - Ares Élite</title>
            <meta http-equiv="refresh" content="3">
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background:#0a0a14; color:#fff; text-align:center; padding:30px; }}
                .container {{ max-width: 700px; margin: 0 auto; background: #121224; padding: 25px; border-radius: 12px; border: 1px solid #23234b; box-shadow: 0 8px 24px rgba(0,0,0,0.6); }}
                .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; text-align: left; margin-top: 20px; }}
                .card {{ background: #1a1a36; padding: 15px; border-radius: 6px; border: 1px solid #2d2d5f; }}
                .btn {{ display: inline-block; background: #ff5500; color: white; font-weight: bold; padding: 12px 24px; text-decoration: none; border-radius: 6px; border: 1px solid #fff; margin-top: 15px; transition: 0.3s; }}
                .btn:hover {{ background: #ff7733; }}
                h2 {{ color: #00ffcc; margin-bottom: 5px; }}
                .billetera {{ background: #13271b; border: 2px solid #00ff55; padding: 15px; border-radius: 8px; margin-top: 15px; text-align: center; }}
                .indicadores {{ background: #1c1c38; border: 1px dashed #00ffcc; padding: 12px; border-radius: 6px; margin-top: 15px; text-align: left; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>📊 Panel Operativo: V5.1 - Ares Élite 📊</h2>
                <p style="color:#aaa; font-size:14px; margin-top:0;">Gimnasio Quant de Aprendizaje por Consistencia (Binance Futuros)</p>
                
                <div style="padding:15px; background:#1f1f3d; border-radius:8px; font-size:16px; font-weight:bold; color:#ffcc00; border-left: 5px solid #ffcc00;">
                    {ESTADISTICAS_IA["estado"]}
                </div>

                <div class="billetera">
                    <span style="color:#aaa; font-size:13px; font-weight:bold; letter-spacing:1px;">💰 BILLETERA SIMULADA EN TIEMPO REAL 💰</span>
                    <h1 style="margin: 5px 0 0 0; color:#00ff55; font-size:36px;">${ESTADISTICAS_IA["balance_usd"]:.2f} <span style="font-size:18px; color:#aaa;">USD</span></h1>
                    <p style="margin:2px 0 0 0; font-size:15px; font-weight:bold; color:{color_pnl};">Rendimiento: {signo_pnl}${ESTADISTICAS_IA["pnl_total_usd"]:.2f} USD</p>
                </div>

                <div class="grid">
                    <div class="card">
                        <p>🎯 <b>Combate:</b> {ESTADISTICAS_IA["combate_actual"]} / {ESTADISTICAS_IA["total_combates"]}</p>
                        <p>📉 <b>Learning Rate:</b> <span style="color:#00ffcc;">{ESTADISTICAS_IA["lr_actual"]:.7f}</span></p>
                        <p>📈 <b>Retorno Última Racha:</b> {ESTADISTICAS_IA["retorno_ultimo_combate"]:.5f}</p>
                    </div>
                    <div class="card">
                        <p>📊 <b>Ratio Sharpe:</b> <span style="color:{color_sharpe}; font-size:18px; font-weight:bold;">{ESTADISTICAS_IA["ratio_sharpe"]:.4f}</span></p>
                        <p>🔥 <b>Efectividad Acumulada:</b> <span style="color:{color_efectividad}; font-size:18px; font-weight:bold;">{ESTADISTICAS_IA["efectividad_estimada"]:.2f}%</span></p>
                    </div>
                </div>

                <div class="indicadores">
                    <h4 style="margin:0 0 8px 0; color:#00ffcc; text-transform:uppercase; font-size:13px;">⚙️ Filtros de Entrada Radáricos (Ares):</h4>
                    <p style="margin:4px 0;">⚡ <b>ATR (Volatilidad de Rango Abierto):</b> <span style="color:#ffff00;">{ESTADISTICAS_IA["atr_actual"]:.4f}</span></p>
                    <p style="margin:4px 0;">📊 <b>Volumen Institucional Actual:</b> <span style="color:#00ff55;">{ESTADISTICAS_IA["volumen_actual"]:.1f} m³</span></p>
                </div>

                <h3 style="text-align:left; color:#ffcc00; margin-top:20px; margin-bottom:5px;">🧩 Comportamiento Conductual en Vivo:</h3>
                <div class="grid" style="grid-template-columns: 1fr 1fr 1fr; font-size:14px; margin-top:5px;">
                    <div class="card" style="text-align:center; border-color:#00ff55;">🟢 <b>LONGs:</b> {ESTADISTICAS_IA["ops_long"]}</div>
                    <div class="card" style="text-align:center; border-color:#ff3333;">🔴 <b>SHORTs:</b> {ESTADISTICAS_IA["ops_short"]}</div>
                    <div class="card" style="text-align:center; border-color:#888;">💤 <b>ESPERAs:</b> {ESTADISTICAS_IA["ops_espera"]}</div>
                </div>

                <br><hr style="border-color:#23234b;"><br>
                
                <div style="background:#221133; padding:15px; border-radius:8px; border:1px solid #4a157d;">
                    🚨 <b>SISTEMA INTERACTIVO HUMAN-IN-THE-LOOP:</b><br>
                    Descarga el cerebro activo en cualquier momento:<br>
                    <a href="/descargar_cerebro" class="btn">📥 DESCARGAR CEREBRO (.PKL) POR CHROME</a>
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
        iniciar_gimnasio_v5_1()
    t = threading.Thread(target=arrancar)
    t.daemon = True
    t.start()
    app.run(host="0.0.0.0", port=puerto)
