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
# INFRAESTRUCTURA Y LOGS DE MONITOREO EN TIEMPO REAL
# ==============================================================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_ID = os.environ.get("TELEGRAM_ID")
bot_telegram = telebot.TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None

# Variables globales para la telemetría del panel visual
ESTADISTICAS_IA = {
    "combate_actual": 0,
    "total_combates": 4000,
    "estado": "Inicializando Motores...",
    "retorno_ultimo_combate": 0.0,
    "ratio_sharpe": 0.0,
    "lr_actual": 0.0001,
    "ops_long": 0,
    "ops_short": 0,
    "ops_espera": 0,
    "efectividad_estimada": 0.0
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
RUTA_CEREBRO_LOCAL = "modelo_sniper_ia.pkl"

# ==============================================================================
# ARQUITECTURA RED NEURONAL TRANSFORMER
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
# ENTORNO QUANT CON RECOMPENSA DE CONSISTENCIA (SHARPE RATIO)
# ==============================================================================
class MercadoGimnasioFuturos:
    def __init__(self, datos_raw, precios_close, ventana=60):
        self.medias = np.mean(datos_raw, axis=0)
        self.desviaciones = np.std(datos_raw, axis=0) + 1e-8
        self.datos_norm = (datos_raw - self.medias) / self.desviaciones
        self.precios = precios_close
        self.ventana = ventana
        self.reset()

    def reset(self):
        self.paso_actual = np.random.randint(self.ventana, len(self.precios) - 100)
        return self.datos_norm[self.paso_actual - self.ventana : self.paso_actual]

    def step(self, accion):
        precio_ahora = self.precios[self.paso_actual]
        precio_siguiente = self.precios[self.paso_actual + 1]
        
        # Guardar telemetría de acciones tomadas
        if accion == 1: ESTADISTICAS_IA["ops_long"] += 1
        elif accion == 2: ESTADISTICAS_IA["ops_short"] += 1
        else: ESTADISTICAS_IA["ops_espera"] += 1
        
        rendimiento = 0.0
        if accion == 1:  # LONG
            rendimiento = (precio_siguiente - precio_ahora) / precio_ahora
        elif accion == 2:  # SHORT
            rendimiento = (precio_ahora - precio_siguiente) / precio_ahora
            
        self.paso_actual += 1
        terminado = (self.paso_actual >= len(self.precios) - 5)
        return self.datos_norm[self.paso_actual - self.ventana : self.paso_actual], rendimiento, terminado

# ==============================================================================
# BUCLE PRINCIPAL DE ENTRENAMIENTO GUIADO
# ==============================================================================
def iniciar_gimnasio_v5():
    global ESTADISTICAS_IA
    RUTA_CSV = "BTCUSDT_1m_Ene_Abr_2026.csv"
    RUTA_TEORICO = "Transformer_Maestro_Teorico.pt"
    
    if not os.path.exists(RUTA_CSV) or not os.path.exists(RUTA_TEORICO):
        ESTADISTICAS_IA["estado"] = "❌ Error: Faltan archivos CSV o PT base."
        return

    try:
        df = pd.read_csv(RUTA_CSV, header=None, skiprows=1, nrows=35000, low_memory=False)
        datos_raw = df[[1, 2, 3, 4, 5, 4]].values.astype(np.float32)
        precios_close = df[4].values.astype(np.float32)
        del df
    except Exception as e:
        ESTADISTICAS_IA["estado"] = f"❌ Error leyendo CSV: {str(e)}"
        return

    escuela = TransformerAnalista()
    checkpoint = torch.load(RUTA_TEORICO, map_location=torch.device('cpu'), weights_only=False)
    escuela.load_state_dict(checkpoint['model_state_dict'])
    escuela.eval()
    
    bot_ppo = AgentePPO()
    
    # NUEVA CARACTERÍSTICA: Si ya bajaste un cerebro y quieres continuar desde ahí,
    # el bot automáticamente detectará el .pkl en GitHub y cargará su progreso.
    if os.path.exists(RUTA_CEREBRO_LOCAL):
        try:
            bot_ppo.load_state_dict(torch.load(RUTA_CEREBRO_LOCAL, map_location=torch.device('cpu')))
            ESTADISTICAS_IA["estado"] = "🔄 Cerebro previo detectado. Continuando evolución..."
        except:
            pass
            
    optimizer_ppo = optim.Adam(bot_ppo.parameters(), lr=0.0001)
    scheduler = CosineAnnealingLR(optimizer_ppo, T_max=COMBATES_PPO, eta_min=1e-6)
    entorno = MercadoGimnasioFuturos(datos_raw, precios_close, ventana=VENTANA_TIEMPO)
    
    np.save("medias.npy", entorno.medias)
    np.save("desviaciones.npy", entorno.desviaciones)

    alertar_telegram("⚡ *Fénix V5 Encendido:* Entorno interactivo activado.")

    ops_ganadas_acumuladas = 0
    ops_totales_acumuladas = 0

    for combate in range(1, COMBATES_PPO + 1):
        ESTADISTICAS_IA["combate_actual"] = combate
        ESTADISTICAS_IA["estado"] = "🏋️ Entrenando y Calibrando Sharpe..."
        
        obs = entorno.reset()
        historial_rendimientos = []
        
        for _ in range(30):
            obs_t = torch.tensor(obs).unsqueeze(0)
            with torch.no_grad():
                analisis = escuela(obs_t)
            probs = bot_ppo(analisis)
            accion = torch.argmax(probs, dim=-1).item()
            
            sig_obs, rendimiento, term = entorno.step(accion)
            historial_rendimientos.append(rendimiento)
            obs = sig_obs
            
            if accion != 0:
                ops_totales_acumuladas += 1
                if rendimiento > 0: ops_ganadas_acumuladas += 1

            # MATEMÁTICA DE PREMIO POR CONSISTENCIA
            # Calculamos la recompensa final basándonos en el Sharpe de la racha de operaciones
            if len(historial_rendimientos) > 5 and np.std(historial_rendimientos) > 0:
                recompensa_sharpe = np.mean(historial_rendimientos) / (np.std(historial_rendimientos) + 1e-6)
            else:
                recompensa_sharpe = rendimiento
                
            loss = -torch.log(probs[0, accion] + 1e-8) * recompensa_sharpe
            optimizer_ppo.zero_grad()
            if recompensa_sharpe != 0.0:
                loss.backward()
                optimizer_ppo.step()
            if term: break
            
        scheduler.step()
        
        # Actualizar telemetría para la pantalla web
        ESTADISTICAS_IA["retorno_ultimo_combate"] = float(np.sum(historial_rendimientos))
        if len(historial_rendimientos) > 1 and np.std(historial_rendimientos) > 0:
            ESTADISTICAS_IA["ratio_sharpe"] = float(np.mean(historial_rendimientos) / np.std(historial_rendimientos))
        ESTADISTICAS_IA["lr_actual"] = float(optimizer_ppo.param_groups[0]['lr'])
        if ops_totales_acumuladas > 0:
            ESTADISTICAS_IA["efectividad_estimada"] = float(ops_ganadas_acumuladas / ops_totales_acumuladas * 100)

        if combate % REPORTAR_CADA == 0:
            torch.save(bot_ppo.state_dict(), RUTA_CEREBRO_LOCAL)
            alertar_telegram(f"📌 *Punto de Control:* Combate [{combate}/{COMBATES_PPO}] | Sharpe: {ESTADISTICAS_IA['ratio_sharpe']:.4f} | Efectividad: {ESTADISTICAS_IA['efectividad_estimada']:.2f}%")

    torch.save(bot_ppo.state_dict(), RUTA_CEREBRO_LOCAL)
    ESTADISTICAS_IA["estado"] = "🏆 ¡GRADUACIÓN COMPLETADA! Modelo Sniper Élite consolidado."

# ==============================================================================
# INTERFAZ DE CONTROL E INYECCIÓN HUMANA (FLASK INTERACTIVO)
# ==============================================================================
app = Flask(__name__)

@app.route('/')
def index():
    color_sharpe = "#00ffcc" if ESTADISTICAS_IA["ratio_sharpe"] >= 0 else "#ff3333"
    color_efectividad = "#ffff00" if ESTADISTICAS_IA["efectividad_estimada"] >= 60.0 else "#aaaaaa"
    
    return f"""
    <html>
        <head>
            <title>Gimnasio Sniper V5 - Élite</title>
            <meta http-equiv="refresh" content="3">
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background:#0a0a14; color:#fff; text-align:center; padding:30px; }}
                .container {{ max-width: 700px; margin: 0 auto; background: #121224; padding: 25px; border-radius: 12px; border: 1px solid #23234b; box-shadow: 0 8px 24px rgba(0,0,0,0.6); }}
                .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; text-align: left; margin-top: 20px; }}
                .card {{ background: #1a1a36; padding: 15px; border-radius: 6px; border: 1px solid #2d2d5f; }}
                .btn {{ display: inline-block; background: #ff5500; color: white; font-weight: bold; padding: 12px 24px; text-decoration: none; border-radius: 6px; border: 1px solid #fff; margin-top: 15px; transition: 0.3s; }}
                .btn:hover {{ background: #ff7733; }}
                h2 {{ color: #00ffcc; margin-bottom: 5px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>📊 Panel Operativo: Sniper V5 Élite 📊</h2>
                <p style="color:#aaa; font-size:14px; margin-top:0;">Gimnasio Quant de Aprendizaje por Consistencia (Binance Futuros)</p>
                
                <div style="padding:15px; background:#1f1f3d; border-radius:8px; font-size:18px; font-weight:bold; color:#ffcc00; border-left: 5px solid #ffcc00;">
                    {ESTADISTICAS_IA["estado"]}
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

                <h3 style="text-align:left; color:#ffcc00; margin-top:25px; margin-bottom:5px;">🧩 Comportamiento Conductual en Vivo:</h3>
                <div class="grid" style="grid-template-columns: 1fr 1fr 1fr; font-size:14px;">
                    <div class="card" style="text-align:center; border-color:#00ff55;">🟢 <b>LONGs:</b> {ESTADISTICAS_IA["ops_long"]}</div>
                    <div class="card" style="text-align:center; border-color:#ff3333;">🔴 <b>SHORTs:</b> {ESTADISTICAS_IA["ops_short"]}</div>
                    <div class="card" style="text-align:center; border-color:#888;">💤 <b>ESPERAs:</b> {ESTADISTICAS_IA["ops_espera"]}</div>
                </div>

                <br><hr style="border-color:#23234b;"><br>
                
                <div style="background:#221133; padding:15px; border-radius:8px; border:1px solid #4a157d;">
                    🚨 <b>SISTEMA INTERACTIVO HUMAN-IN-THE-LOOP:</b><br>
                    Si notas un mal comportamiento o quieres inyectar código nuevo, descarga el cerebro de inmediato:<br>
                    <a href="/descargar_cerebro" class="btn">📥 DESCARGAR CEREBRO (.PKL) POR CHROME</a>
                </div>
            </div>
        </body>
    </html>
    """

@app.route('/descargar_cerebro')
def descargar_cerebro():
    if os.path.exists(RUTA_CEREBRO_LOCAL):
        return send_file(RUTA_CEREBRO_LOCAL, as_attachment=True)
    else:
        return "❌ Alerta: El archivo .pkl aún no se ha consolidado en el disco de Render."

if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 10000))
    def arrancar():
        time.sleep(3)
        iniciar_gimnasio_v5()
    t = threading.Thread(target=arrancar)
    t.daemon = True
    t.start()
    app.run(host="0.0.0.0", port=puerto)
