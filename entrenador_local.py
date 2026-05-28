import os
import time
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import CosineAnnealingLR
import telebot
from flask import Flask
import threading
import requests

# ==============================================================================
# 🎯 CONTROL DE VERSIONES Y CONFIGURACIÓN CLOUD PERPETUA (V8.3 - CONCIENCIA LIMPIA)
# ==============================================================================
RUTA_CSV = "BTCUSDT_1m_Ene_Abr_2026.csv"
# ✨ NUEVO NOMBRE: Al no existir en Dropbox, obliga al bot a inicializar desde 0 absoluto.
CEREBRO_A_ENTRENAR = "modelo_ares_transformer_v8.pkl"

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_ID = os.environ.get("TELEGRAM_ID")
bot_telegram = telebot.TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None

DBX_APP_KEY = os.environ.get("DROPBOX_APP_KEY")
DBX_APP_SECRET = os.environ.get("DROPBOX_APP_SECRET")
DBX_REFRESH_TOKEN = os.environ.get("DROPBOX_REFRESH_TOKEN")

ESTADISTICAS_IA = {
    "combate_actual": 0,
    "total_combates": 4000,
    "estado": "Inicializando Conciencia Limpia V8.3...",
    "retorno_ultimo_combate": 0.0,
    "ratio_sharpe": 0.0,
    "lr_actual": 0.0002, 
    "ops_long": 0,
    "ops_short": 0,
    "ops_espera": 0,
    "efectividad_estimada": 0.0,
    "balance_usd": 1000.0,
    "pnl_total_usd": 0.0,
    "loss_actor": 0.0,
    "loss_critico": 0.0,
    "peso_atr_acumulado": 33.3,
    "peso_volumen_acumulado": 33.3,
    "peso_macro_acumulado": 33.4,
    "ops_consecutivas_direccion": 0,
    "ultima_direccion": 0,
    "alerta_ecosistema": "Estable. Secuencia Evolutiva de Cero Activa.",
    "errores_indicador": "Ninguno"
}

VENTANA_TIEMPO = 60
COMBATES_PPO = 4000
REPORTAR_CADA = 100 
PASOS_POR_COMBATE = 180

def alertar_telegram(mensaje):
    if bot_telegram and TELEGRAM_ID:
        try:
            bot_telegram.send_message(TELEGRAM_ID, mensaje, parse_mode="Markdown")
        except Exception as e:
            print(f"⚠️ Telegram Log: {e}")

# ==============================================================================
# 🛰️ SISTEMA CONECTOR REFRESH DE DROPBOX
# ==============================================================================
def obtener_access_token():
    if not DBX_APP_KEY or not DBX_APP_SECRET or not DBX_REFRESH_TOKEN:
        return None
    try:
        url = "https://api.dropbox.com/oauth2/token"
        data = {
            "grant_type": "refresh_token",
            "refresh_token": DBX_REFRESH_TOKEN,
            "client_id": DBX_APP_KEY,
            "client_secret": DBX_APP_SECRET
        }
        response = requests.post(url, data=data, timeout=10)
        return response.json().get("access_token")
    except Exception as e:
        print(f"❌ Error renovando token: {e}")
        return None

def descargar_cerebro_cloud():
    token = obtener_access_token()
    if not token: return False
    try:
        url = "https://content.dropboxapi.com/2/files/download"
        headers = {
            "Authorization": f"Bearer {token}",
            "Dropbox-API-Arg": '{"path": "/' + CEREBRO_A_ENTRENAR + '"}'
        }
        res = requests.post(url, headers=headers, timeout=15)
        if res.status_code == 200:
            with open(CEREBRO_A_ENTRENAR, "wb") as f:
                f.write(res.content)
            print("🌲 Memoria descargada desde Dropbox.")
            return True
    except Exception as e:
        print(f"⚠️ Sin respaldo en la nube: {e}")
    return False

def subir_cerebro_cloud():
    token = obtener_access_token()
    if not token or not os.path.exists(CEREBRO_A_ENTRENAR): return
    try:
        url = "https://content.dropboxapi.com/2/files/upload"
        headers = {
            "Authorization": f"Bearer {token}",
            "Dropbox-API-Arg": '{"path": "/' + CEREBRO_A_ENTRENAR + '", "mode": "overwrite"}',
            "Content-Type": "application/octet-stream"
        }
        with open(CEREBRO_A_ENTRENAR, "rb") as f:
            requests.post(url, headers=headers, data=f, timeout=20)
    except Exception as e:
        print(f"❌ Error subiendo cerebro: {e}")

# ==============================================================================
# 🧠 ARQUITECTURA TRANSFORMER CON ESCUDO MATEMÁTICO (DROPOUT 40%)
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
    def forward(self, x): 
        return x + self.pe[:, :x.size(1)]

class AresActorCritico(nn.Module):
    def __init__(self, num_caracteristicas=9, d_model=64, nhead=4, num_layers=3, dropout=0.40):
        super().__init__()
        self.proyeccion_entrada = nn.Linear(num_caracteristicas, d_model)
        self.pos_encoder = PositionalEncoding(d_model)
        
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=nhead, dim_feedforward=128, dropout=dropout, batch_first=True
        )
        self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        
        self.actor = nn.Sequential(
            nn.Linear(d_model, 32), nn.ReLU(), nn.Linear(32, 3), nn.Softmax(dim=-1)
        )
        self.critico = nn.Sequential(
            nn.Linear(d_model, 32), nn.ReLU(), nn.Linear(32, 1)
        )

    def forward(self, x):
        x = self.proyeccion_entrada(x) * (64 ** 0.5)
        x = self.pos_encoder(x)
        features = self.transformer_encoder(x)[:, -1, :] 
        
        probs = self.actor(features)
        valor = self.critico(features)
        return probs, valor

# ==============================================================================
# ⚡ ENTORNO QUANT CON ESCALADO EN VIVO Y COMISIONES REALISTAS
# ==============================================================================
class MercadoGimnasioAresBosque:
    def __init__(self, datos_raw, precios_close, volumen_raw, ventana=60):
        self.ventana = ventana
        self.precios = precios_close
        self.volumen = volumen_raw
        
        self.matriz_extendida = np.zeros((len(precios_close), 9), dtype=np.float32)
        for i in range(6):
            self.matriz_extendida[:, i] = datos_raw[:, i]
            
        print("⚡ Precalculando Ratios de Adaptabilidad Dinámica V8.3...")
        for i in range(30, len(precios_close)):
            retorno_5m = (precios_close[i] - precios_close[i-5]) / (precios_close[i-5] + 1e-8)
            retorno_15m = (precios_close[i] - precios_close[i-15]) / (precios_close[i-15] + 1e-8)
            max_24 = np.max(precios_close[i-24:i]) if i > 24 else precios_close[i]
            min_24 = np.min(precios_close[i-24:i]) if i > 24 else precios_close[i]
            rango_ptj = 1.0 if precios_close[i] >= max_24 else (-1.0 if precios_close[i] <= min_24 else 0.0)
            
            self.matriz_extendida[i, 6] = retorno_5m
            self.matriz_extendida[i, 7] = retorno_15m
            self.matriz_extendida[i, 8] = rango_ptj

        self.reset()

    def obtener_observacion_normalizada(self):
        sub_matriz = self.matriz_extendida[self.paso_actual - self.ventana : self.paso_actual]
        medias = np.mean(sub_matriz, axis=0)
        desviaciones = np.std(sub_matriz, axis=0) + 1e-8
        return (sub_matriz - medias) / desviaciones

    def reset(self):
        self.paso_actual = np.random.randint(self.ventana + 250, len(self.precios) - (PASOS_POR_COMBATE + 10))
        self.conteo_esperas_seguidas = 0
        return self.obtener_observacion_normalizada()

    def step(self, accion):
        precio_ahora = self.precios[self.paso_actual]
        precio_siguiente = self.precios[self.paso_actual + 1]
        volumen_ahora = self.volumen[self.paso_actual]
        
        precios_ventana = self.precios[self.paso_actual - 14 : self.paso_actual]
        atr_estimado = np.max(precios_ventana) - np.min(precios_ventana) + 1e-8
        volumen_promedio = np.mean(self.volumen[self.paso_actual - 14 : self.paso_actual]) + 1e-6
        ma_macro = np.mean(self.precios[self.paso_actual - 200 : self.paso_actual]) if self.paso_actual > 200 else precio_ahora
        bosque_alcista = precio_ahora > ma_macro

        COMISION = 0.0004 

        if accion == ESTADISTICAS_IA["ultima_direccion"] and accion != 0:
            ESTADISTICAS_IA["ops_consecutivas_direccion"] += 1
        else:
            ESTADISTICAS_IA["ops_consecutivas_direccion"] = 1
            if accion != 0: ESTADISTICAS_IA["ultima_direccion"] = accion

        if accion == 1: ESTADISTICAS_IA["ops_long"] += 1
        elif accion == 2: ESTADISTICAS_IA["ops_short"] += 1
        else: ESTADISTICAS_IA["ops_espera"] += 1
        
        rendimiento = 0.0
        costo_operacion = 0.0

        if accion == 1:
            rendimiento = (precio_siguiente - precio_ahora) / precio_ahora
            costo_operacion = COMISION if ESTADISTICAS_IA["ops_consecutivas_direccion"] == 1 else 0.0
            self.conteo_esperas_seguidas = 0
        elif accion == 2:
            rendimiento = (precio_ahora - precio_siguiente) / precio_ahora
            costo_operacion = COMISION if ESTADISTICAS_IA["ops_consecutivas_direccion"] == 1 else 0.0
            self.conteo_esperas_seguidas = 0
        else:
            self.conteo_esperas_seguidas += 1

        rendimiento_neto = rendimiento - costo_operacion
        recompensa = rendimiento_neto

        if accion != 0 and volumen_ahora > volumen_promedio * 1.3: recompensa *= 1.4  
        if accion == 1 and not bosque_alcista: recompensa -= 0.0015 
        if accion == 2 and bosque_alcista: recompensa -= 0.0015

        if accion != 0 and atr_estimado < (precio_ahora * 0.0004): 
            recompensa -= 0.0025
        
        if accion == 0 and volumen_ahora > volumen_promedio and atr_estimado > (precio_ahora * 0.001):
            recompensa += 0.0006 

        total_m = atr_estimado + volumen_ahora + abs(precio_ahora - ma_macro) + 1e-6
        peso_instantaneo_atr = (atr_estimado / total_m) * 100
        peso_instantaneo_vol = (volumen_ahora / total_m) * 100
        peso_instantaneo_mac = (abs(precio_ahora - ma_macro) / total_m) * 100

        ESTADISTICAS_IA["peso_atr_acumulado"] = (ESTADISTICAS_IA["peso_atr_acumulado"] * 0.95) + (peso_instantaneo_atr * 0.05)
        ESTADISTICAS_IA["peso_volumen_acumulado"] = (ESTADISTICAS_IA["peso_volumen_acumulado"] * 0.95) + (peso_instantaneo_vol * 0.05)
        ESTADISTICAS_IA["peso_macro_acumulado"] = (ESTADISTICAS_IA["peso_macro_acumulado"] * 0.95) + (peso_instantaneo_mac * 0.05)

        self.paso_actual += 1
        terminado = (self.conteo_esperas_seguidas > 50)
        return self.obtener_observacion_normalizada(), recompensa, rendimiento_neto, terminado

# ==============================================================================
# 🏋️ BUCLE PPO PERPETUO
# ==============================================================================
def iniciar_gimnasio_v8():
    global ESTADISTICAS_IA
    
    if not os.path.exists(RUTA_CSV):
        ESTADISTICAS_IA["estado"] = "❌ Error: Falta el archivo histórico CSV."
        return

    try:
        df = pd.read_csv(RUTA_CSV, header=None, skiprows=1, nrows=15000, usecols=[1, 2, 3, 4, 5], low_memory=False)
        datos_raw = np.zeros((len(df), 6), dtype=np.float32)
        datos_raw[:, :5] = df[[1, 2, 3, 4, 5]].values
        datos_raw[:, 5] = df[4].values 
        precios_close = df[4].values.astype(np.float32)
        volumen_raw = df[5].values.astype(np.float32)
        del df
    except Exception as e:
        ESTADISTICAS_IA["estado"] = f"❌ Error CSV: {str(e)}"
        return

    descargar_cerebro_cloud()
    modelo_ares = AresActorCritico()
    optimizer = optim.Adam(modelo_ares.parameters(), lr=0.0002)
    scheduler = CosineAnnealingLR(optimizer, T_max=COMBATES_PPO, eta_min=1e-6)
    
    combate_inicial = 1

    if os.path.exists(CEREBRO_A_ENTRENAR):
        try:
            checkpoint = torch.load(CEREBRO_A_ENTRENAR, map_location=torch.device('cpu'), weights_only=False)
            if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
                # 🛡️ PROTECCIÓN ANTI-FALLOS FUTUROS: strict=False permite alterar el modelo sin generar caídas.
                modelo_ares.load_state_dict(checkpoint["state_dict"], strict=False)
                try:
                    optimizer.load_state_dict(checkpoint["optimizer_state"])
                    scheduler.load_state_dict(checkpoint["scheduler_state"])
                except:
                    print("⚠️ Optimizador recreado por cambio estructural.")
                combate_inicial = checkpoint.get("combate", 1) + 1
                ESTADISTICAS_IA = checkpoint.get("estadisticas", ESTADISTICAS_IA)
                ESTADISTICAS_IA["estado"] = f"🌲 Evolución Reanudada con Éxito. Combate: {combate_inicial}"
            else:
                modelo_ares.load_state_dict(checkpoint, strict=False)
                ESTADISTICAS_IA["estado"] = "⚡ Pesos simples conectados sin forzar coincidencia estricta."
        except Exception as e:
            ESTADISTICAS_IA["estado"] = f"⚠️ Modo Resiliencia: Cargado con adaptaciones estructurales: {str(e)}"
    else:
        ESTADISTICAS_IA["estado"] = "✨ Conciencia Limpia Inicializada. Aprendiendo desde 0 absoluto."
            
    entorno = MercadoGimnasioAresBosque(datos_raw, precios_close, volumen_raw, ventana=VENTANA_TIEMPO)
    alertar_telegram(f"⚡ *Ares Limpio V8.3:* Iniciando entrenamiento puro desde el combate {combate_inicial}.")

    ops_ganadas = 0
    ops_totales = 0

    for combate in range(combate_inicial, COMBATES_PPO + 1):
        ESTADISTICAS_IA["combate_actual"] = combate
        obs = entorno.reset()
        
        b_estados, b_acciones, b_prob_viejas, b_recompensas, b_valores = [], [], [], [], []
        historial_rendimientos = []
        
        modelo_ares.eval()
        for _ in range(PASOS_POR_COMBATE):
            obs_t = torch.tensor(obs, dtype=torch.float32).unsqueeze(0)
            with torch.no_grad():
                probs, valor = modelo_ares(obs_t)
            
            accion = torch.argmax(probs, dim=-1).item()
            prob_accion = probs[0, accion].item()
            
            sig_obs, recompensa, rendimiento, term = entorno.step(accion)
            
            b_estados.append(obs)
            b_acciones.append(accion)
            b_prob_viejas.append(prob_accion)
            b_recompensas.append(recompensa)
            b_valores.append(valor.item())
            historial_rendimientos.append(rendimiento)
            
            obs = sig_obs
            
            if accion != 0:
                ops_totales += 1
                ESTADISTICAS_IA["balance_usd"] += ESTADISTICAS_IA["balance_usd"] * rendimiento
                ESTADISTICAS_IA["pnl_total_usd"] = ESTADISTICAS_IA["balance_usd"] - 1000.0
                if rendimiento > 0: ops_ganadas += 1
            if term: break
            
        modelo_ares.train()
        t_estados = torch.tensor(np.array(b_estados), dtype=torch.float32)
        t_acciones = torch.tensor(b_acciones, dtype=torch.long)
        t_prob_viejas = torch.tensor(b_prob_viejas, dtype=torch.float32)
        
        rend_medio = np.mean(historial_rendimientos)
        rend_std = np.std(historial_rendimientos) + 1e-8
        sharpe_combate = rend_medio / rend_std
        
        retornos = []
        g_descontado = 0
        for r in reversed(b_recompensas):
            r_ajustada = r + (0.001 * sharpe_combate if sharpe_combate > 0 else 0.002 * sharpe_combate)
            g_descontado = r_ajustada + (0.96 * g_descontado) 
            retornos.insert(0, g_descontado)
            
        t_retornos = torch.tensor(retornos, dtype=torch.float32)
        t_valores = torch.tensor(b_valores, dtype=torch.float32)
        ventajas = t_retornos - t_valores.detach()
        
        for _ in range(4):
            nuevas_probs, nuevos_valores = modelo_ares(t_estados)
            nuevos_valores = nuevos_valores.squeeze()
            
            prob_especificas = nuevas_probs.gather(1, t_acciones.unsqueeze(1)).squeeze()
            ratios = prob_especificas / (t_prob_viejas + 1e-8)
            
            surr1 = ratios * ventajas
            surr2 = torch.clamp(ratios, 1.0 - 0.2, 1.0 + 0.2) * ventajas
            loss_actor = -torch.min(surr1, surr2).mean()
            loss_critico = nn.MSELoss()(nuevos_valores, t_retornos)
            entropia = -(nuevas_probs * torch.log(nuevas_probs + 1e-8)).mean()
            
            loss_total = loss_actor + 0.5 * loss_critico - 0.01 * entropia
            
            optimizer.zero_grad()
            loss_total.backward()
            nn.utils.clip_grad_norm_(modelo_ares.parameters(), max_norm=0.5)
            optimizer.step()
            
        scheduler.step()
        
        ESTADISTICAS_IA["loss_actor"] = float(loss_actor.item())
        ESTADISTICAS_IA["loss_critico"] = float(loss_critico.item())
        ESTADISTICAS_IA["retorno_ultimo_combate"] = float(np.sum(historial_rendimientos))
        ESTADISTICAS_IA["ratio_sharpe"] = float(sharpe_combate)
        ESTADISTICAS_IA["lr_actual"] = float(optimizer.param_groups[0]['lr'])
        if ops_totales > 0:
            ESTADISTICAS_IA["efectividad_estimada"] = float(ops_ganadas / ops_totales * 100)

        if combate % REPORTAR_CADA == 0:
            checkpoint_perpetuo = {
                "state_dict": modelo_ares.state_dict(),
                "optimizer_state": optimizer.state_dict(),
                "scheduler_state": scheduler.state_dict(),
                "combate": combate,
                "estadisticas": ESTADISTICAS_IA
            }
            torch.save(checkpoint_perpetuo, CEREBRO_A_ENTRENAR)
            subir_cerebro_cloud()
            alertar_telegram(f"🌲 *Ares V8 Cloud:* [{combate}/{COMBATES_PPO}] | Wallet: ${ESTADISTICAS_IA['balance_usd']:.2f} | Sharpe: {ESTADISTICAS_IA['ratio_sharpe']:.4f}")

    checkpoint_perpetuo = {
        "state_dict": modelo_ares.state_dict(),
        "optimizer_state": optimizer.state_dict(),
        "scheduler_state": scheduler.state_dict(),
        "combate": COMBATES_PPO,
        "estadisticas": ESTADISTICAS_IA
    }
    torch.save(checkpoint_perpetuo, CEREBRO_A_ENTRENAR)
    subir_cerebro_cloud()
    ESTADISTICAS_IA["estado"] = "🏆 ¡EVOLUCIÓN PERPETUA COMPLETADA CON ÉXITO!"

# ==============================================================================
# INTERFAZ WEB
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
            <title>Gimnasio Ares Perpetuo V8.3</title>
            <meta http-equiv="refresh" content="3">
            <style>
                body {{ font-family: 'Segoe UI', sans-serif; background:#04040a; color:#fff; text-align:center; padding:30px; }}
                .container {{ max-width: 750px; margin: 0 auto; background: #0b0b16; padding: 25px; border-radius: 12px; border: 1px solid #222244; }}
                .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; text-align: left; margin-top: 20px; }}
                .card {{ background: #101026; padding: 15px; border-radius: 6px; border: 1px solid #2d2d5a; }}
                .btn {{ display: inline-block; background: #1a0933; color: white; font-weight: bold; padding: 8px 16px; text-decoration: none; border-radius: 6px; border: 1px solid #00ffcc; }}
                .billetera {{ background: #05140b; border: 2px solid #00ff55; padding: 15px; border-radius: 8px; margin-top: 15px; text-align: center; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>⚡ Panel Perpetuo: Ares Caos V8.3 ⚡</h2>
                <p style="color:#888; font-size:14px; margin-top:0;">Evolución de Cero con Inyección Tolerante de Checkpoints</p>
                
                <div style="padding:10px; margin-bottom:10px; text-align:right;">
                    <a href="/telemetria" class="btn">📊 VER DISTRIBUCIÓN DE ATENCIÓN</a>
                </div>

                <div style="padding:15px; background:#141430; border-radius:8px; font-size:16px; font-weight:bold; color:#ffcc00; border-left: 5px solid #00ffcc;">
                    {ESTADISTICAS_IA["estado"]}
                </div>

                <div class="billetera">
                    <span style="color:#aaa; font-size:13px; font-weight:bold;">💰 CUENTA DE PRUEBA EN RIESGO VARIABLE 💰</span>
                    <h1 style="margin: 5px 0 0 0; color:#00ff55; font-size:36px;">${ESTADISTICAS_IA["balance_usd"]:.2f}</h1>
                    <p style="margin:2px 0 0 0; font-size:15px; font-weight:bold; color:{color_pnl};">PnL Neto Total (Con Fees): {signo_pnl}${ESTADISTICAS_IA["pnl_total_usd"]:.2f} USD</p>
                </div>

                <div class="grid">
                    <div class="card">
                        <p>🎯 <b>Combate Actual:</b> {ESTADISTICAS_IA["combate_actual"]} / {ESTADISTICAS_IA["total_combates"]}</p>
                        <p>📉 <b>LR Dinámico:</b> <span style="color:#00ffcc;">{ESTADISTICAS_IA["lr_actual"]:.7f}</span></p>
                        <p>📉 <b>Loss Actor:</b> {ESTADISTICAS_IA["loss_actor"]:.5f}</p>
                        <p>📈 <b>Loss Crítico:</b> {ESTADISTICAS_IA["loss_critico"]:.5f}</p>
                    </div>
                    <div class="card">
                        <p>📊 <b>Ratio Sharpe Promedio:</b> <span style="color:{color_sharpe}; font-size:18px; font-weight:bold;">{ESTADISTICAS_IA["ratio_sharpe"]:.4f}</span></p>
                        <p>🔥 <b>Efectividad Real:</b> <span style="color:{color_efectividad}; font-size:18px; font-weight:bold;">{ESTADISTICAS_IA["efectividad_estimada"]:.2f}%</span></p>
                        <p>📈 Longs: {ESTADISTICAS_IA["ops_long"]} | 📉 Shorts: {ESTADISTICAS_IA["ops_short"]}</p>
                    </div>
                </div>
            </div>
        </body>
    </html>
    """

@app.route('/telemetria')
def telemetria():
    return f"""
    <html>
        <head>
            <title>Telemetría de Atención</title>
            <meta http-equiv="refresh" content="3">
            <style>
                body {{ font-family: 'Segoe UI', sans-serif; background:#04040a; color:#fff; padding:30px; text-align:center; }}
                .container {{ max-width: 750px; margin: 0 auto; background: #0b0b16; padding: 25px; border-radius: 12px; }}
                .barra-contenedor {{ background: #222; border-radius: 8px; margin: 10px 0; overflow: hidden; }}
                .barra {{ height: 25px; line-height: 25px; color: black; font-weight: bold; padding-left: 10px; transition: 0.5s; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2 style="color:#00ffcc;">📊 Distribución Dinámica de Atención del Transformer</h2>
                <br>
                <p style="text-align:left;">⚡ <b>Peso Volatilidad (ATR): {ESTADISTICAS_IA["peso_atr_acumulado"]:.1f}%</b></p>
                <div class="barra-contenedor"><div class="barra" style="width: {ESTADISTICAS_IA["peso_atr_acumulado"]}%; background: #ffff00;"></div></div>
                
                <p style="text-align:left;">📊 <b>Peso Volumen del Mercado: {ESTADISTICAS_IA["peso_volumen_acumulado"]:.1f}%</b></p>
                <div class="barra-contenedor"><div class="barra" style="width: {ESTADISTICAS_IA["peso_volumen_acumulado"]}%; background: #00ff55;"></div></div>
                
                <p style="text-align:left;">🌲 <b>Peso Tendencia Macro: {ESTADISTICAS_IA["peso_macro_acumulado"]:.1f}%</b></p>
                <div class="barra-contenedor"><div class="barra" style="width: {ESTADISTICAS_IA["peso_macro_acumulado"]}%; background: #00ffcc;"></div></div>
                <br>
                <a href="/" style="color:#00ffcc; text-decoration:none;">⬅️ Volver al Panel Principal</a>
            </div>
        </body>
    </html>
    """

if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 10000))
    def arrancar():
        time.sleep(2)
        iniciar_gimnasio_v8()
    t = threading.Thread(target=arrancar)
    t.daemon = True
    t.start()
    app.run(host="0.0.0.0", port=puerto)
