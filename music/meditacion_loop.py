#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MEDITACION_LOOP — generador de música de fondo para meditaciones
================================================================

REQUISITOS:  python3, numpy, scipy      (pip install numpy scipy)

DOS MODOS
---------
1) LOOP (por defecto): un trozo de 96 s que se repite sin costura. Ideal para pegar en Audacity.
2) SESIÓN LARGA (--sesion SEGUNDOS): una pista continua de la duración que pidas, que viaja
   lentamente por distintos acordes (I - IV - I - V), con entrada y salida suaves. No se repite.

USO RÁPIDO
----------
  python3 meditacion_loop.py                             # loop suave (sin bombo)
  python3 meditacion_loop.py --preset bombo              # loop con bombo lento
  python3 meditacion_loop.py --preset bombo --sesion 1200   # sesión de 20 minutos
  python3 meditacion_loop.py --preset drone --sesion 600 --acorde-fijo
  python3 meditacion_loop.py --semilla 4                 # otra versión (cambia notas y momentos)
  python3 meditacion_loop.py --dinamica 0.5              # volumen más parejo (menos "respiración")
  python3 meditacion_loop.py --hueco-voz 5               # más espacio para la voz
  python3 meditacion_loop.py --campanitas 0 --bombo 1 --volumen -30
  python3 meditacion_loop.py --tonalidad F --duracion 120
  python3 meditacion_loop.py --ayuda-presets

python meditacion_loop.py --preset bombo --sesion 600 --bombo-patron  corazon --bombo-bpm 43 --dinamica 0.5
python meditacion_loop.py --preset bombo --sesion 630 --bombo-patron  simple --bombo-bpm 48 --dinamica 0.5 --fundido-in 0 --fundido-out 0 

También puedes editar el bloque CONFIG de abajo y correr sin argumentos;
lo que pases por línea de comandos pisa a CONFIG.

QUÉ HACE CADA PARÁMETRO DE "SENSACIÓN"
--------------------------------------
* hueco-voz  (0-8 dB, por defecto 3): baja la música justo donde vive la voz (1-4 kHz), así tu voz
  se entiende mejor sin bajar el volumen general. 0 = apagado.
* dinamica   (0-1, por defecto 1): cuánto "respira" el volumen. La música sube y baja unos 8 dB de
  forma lenta y natural; ya está activada con 1 (como antes). Bájala (0.5, 0.3...) para un volumen más
  parejo, mejor debajo de una voz hablada. 0 = completamente plano.
* semilla    : 0 = la versión original. Otros números = otra versión del tema (otras notas de cuerda
  y campanitas, en otros momentos, siempre en la escala pentatónica, siempre suena bien).

A PRUEBA DE TONTOS
------------------
* Todos los valores se limitan a rangos seguros (si te pasas, avisa y ajusta).
* En modo loop todo es múltiplo exacto de la duración: el loop SIEMPRE cierra.
* En modo sesión las secciones se mezclan con fundidos largos de potencia constante.
* El bombo se ajusta solo al bpm más cercano que cierra con la duración.
* Volumen final por nivel medio + tope de pico en -6 dBFS: no satura nunca.

NIVELES  (0 = apagado, 1 = valor de fábrica, 2 = el doble)
-------
pad, sub, viento, cuerdas, campanitas, bombo
(el brillo del aire alto, antes "shimmer", ahora va junto con el viento)
"""
import argparse
import os
import sys

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

# =====================================================================================
#  CONFIG  —  EDITA AQUÍ  (la línea de comandos pisa estos valores)
# =====================================================================================
CONFIG = {
    "preset": "suave",       # suave | bombo | drone | dormir   (ver --ayuda-presets)
    "duracion": 96,          # segundos del loop (60 a 180)
    "tonalidad": "D",        # C, C#, D, D#, E, F, F#, G, G#, A, A#, B
    "volumen": -26.0,        # nivel medio en dBFS (-40 muy bajo ... -14 fuerte). -26 = fondo
    "semilla": 0,            # cambia el número para obtener otra "versión" del mismo tema
    "brillo": 1.0,           # 0 = muy oscuro y cálido ... 2 = más abierto
    "espacio": 1.0,          # cantidad de reverb: 0 = seco ... 2 = catedral
    "movimiento_viento": 1.0,  # cuánto viaja el viento de lado a lado: 0 = quieto ... 2 = mucho
    "bombo_bpm": 50,         # 40 a 70 (se ajusta solo para que cierre el loop)
    "bombo_patron": "simple",  # simple (un golpe por pulso) | corazon (lub-dub)
    "bombo_difuso": 0.7,     # 0 = golpe marcado y seco ... 1 = muy blando y difuso
    "dinamica": 1.0,         # 0 = volumen plano ... 1 = respira como siempre (0.5 = más parejo)
    "hueco_voz": 3.0,        # dB que baja la música donde vive la voz (1-4 kHz). 0 = apagado
    "sesion": 0,             # 0 = modo loop. Un número de segundos (30-3600) = sesión larga continua
    "fundido_in": 6,         # (solo sesión) segundos de entrada suave
    "fundido_out": 12,       # (solo sesión) segundos de salida suave
    "acorde_fijo": False,    # (solo sesión) True = no cambia de acorde, solo evoluciona
    "previa": 1,             # >1: además guarda un WAV con el loop repetido N veces (para probar la unión)
    # niveles por capa (None = los del preset). 0 apaga la capa.
    "niveles": {},
}

PRESETS = {
    "suave":  {"desc": "Pad + sub + viento + cuerdas y campanitas. Sin bombo.",
               "niveles": dict(pad=1, sub=1, viento=1, cuerdas=1, campanitas=1, bombo=0)},
    "bombo":  {"desc": "Igual que 'suave' + bombo lento tipo pulso de corazón.",
               "niveles": dict(pad=1, sub=1, viento=1, cuerdas=1, campanitas=1, bombo=1)},
    "drone":  {"desc": "Solo lo esencial: pad, sub y viento. Ideal para guiar con tu propio ritmo.",
               "niveles": dict(pad=1, sub=1, viento=1, cuerdas=0, campanitas=0, bombo=0)},
    "dormir": {"desc": "Más oscuro y quieto: sin bombo, pocas campanitas, viento suave.",
               "niveles": dict(pad=1, sub=1.1, viento=0.7, cuerdas=0.5, campanitas=0.3, bombo=0),
               "brillo": 0.6, "movimiento_viento": 0.6},
}

CAPAS = ["pad", "sub", "viento", "cuerdas", "campanitas", "bombo"]
NOTAS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# =====================================================================================
#  Validación (aquí nace lo de "a prueba de tontos")
# =====================================================================================
AVISOS = []

def clamp(valor, lo, hi, nombre):
    try:
        v = float(valor)
    except (TypeError, ValueError):
        AVISOS.append(f"'{nombre}'={valor!r} no es un número; uso {lo}.")
        return lo
    if not np.isfinite(v):
        AVISOS.append(f"'{nombre}' no es finito; uso {lo}.")
        return lo
    if v < lo or v > hi:
        AVISOS.append(f"'{nombre}'={v:g} fuera de rango [{lo:g}, {hi:g}]; lo ajusto.")
    return min(max(v, lo), hi)


def validar(cfg):
    c = dict(cfg)
    base = dict(CONFIG)
    base.update(c)
    c = base
    if c["preset"] not in PRESETS:
        AVISOS.append(f"Preset '{c['preset']}' no existe ({', '.join(PRESETS)}); uso 'suave'.")
        c["preset"] = "suave"
    p = PRESETS[c["preset"]]
    niveles = dict(p["niveles"])
    for k, v in (c.get("niveles") or {}).items():
        if k == "shimmer":
            AVISOS.append("'shimmer' ya no es una capa aparte: ahora va junto con 'viento'.")
            continue
        if k not in CAPAS:
            AVISOS.append(f"Capa '{k}' desconocida (válidas: {', '.join(CAPAS)}); la ignoro.")
            continue
        if v is not None:
            niveles[k] = v
    out = {}
    out["niveles"] = {k: clamp(niveles[k], 0.0, 2.0, f"nivel {k}") for k in CAPAS}
    if sum(out["niveles"][k] for k in ("pad", "sub", "viento")) == 0:
        AVISOS.append("Pad, sub y viento estaban en 0: enciendo el pad para que haya base.")
        out["niveles"]["pad"] = 1.0
    out["duracion"] = int(round(clamp(c["duracion"], 60, 180, "duracion")))
    t = str(c["tonalidad"]).strip().upper().replace("♯", "#")
    if t not in NOTAS:
        AVISOS.append(f"Tonalidad '{c['tonalidad']}' no válida ({', '.join(NOTAS)}); uso D.")
        t = "D"
    out["tonalidad"] = t
    out["volumen"] = clamp(c["volumen"], -40, -14, "volumen")
    out["semilla"] = int(clamp(c["semilla"], 0, 9999, "semilla"))
    # brillo/espacio/viento: si el preset trae valor propio y el usuario dejó el de fábrica, usa el del preset
    def con_preset(nombre, defecto=1.0):
        v = c[nombre]
        if v == defecto and nombre in p:
            v = p[nombre]
        return v
    out["brillo"] = clamp(con_preset("brillo"), 0.0, 2.0, "brillo")
    out["espacio"] = clamp(con_preset("espacio"), 0.0, 2.0, "espacio")
    out["movimiento_viento"] = clamp(con_preset("movimiento_viento"), 0.0, 2.0, "movimiento_viento")
    out["bombo_bpm"] = clamp(c["bombo_bpm"], 40, 70, "bombo_bpm")
    pat = str(c["bombo_patron"]).strip().lower()
    if pat not in ("simple", "corazon", "corazón"):
        AVISOS.append(f"Patrón de bombo '{c['bombo_patron']}' no válido (simple | corazon); uso simple.")
        pat = "simple"
    out["bombo_patron"] = "corazon" if pat.startswith("coraz") else "simple"
    out["bombo_difuso"] = clamp(c["bombo_difuso"], 0.0, 1.0, "bombo_difuso")
    out["dinamica"] = clamp(c["dinamica"], 0.0, 1.0, "dinamica")
    out["hueco_voz"] = clamp(c["hueco_voz"], 0.0, 8.0, "hueco_voz")
    ses = clamp(c["sesion"], 0, 3600, "sesion")
    if 0 < ses < 30:
        AVISOS.append(f"'sesion'={ses:g} es muy corta; uso 30 s.")
        ses = 30
    out["sesion"] = int(round(ses))
    out["fundido_in"] = clamp(c["fundido_in"], 0, 60, "fundido_in")
    out["fundido_out"] = clamp(c["fundido_out"], 0, 120, "fundido_out")
    out["acorde_fijo"] = bool(c["acorde_fijo"])
    out["previa"] = int(clamp(c["previa"], 1, 10, "previa"))
    out["preset"] = c["preset"]
    return out


# =====================================================================================
#  Estado global del "reloj" (se fija en preparar(); todo depende de L)
# =====================================================================================
SR = 44100
L = N = NB = 0
freqs = t = None


def preparar(duracion):
    global L, N, NB, freqs, t
    L = int(duracion)
    N = SR * L
    NB = N // 2 + 1
    freqs = np.fft.rfftfreq(N, 1 / SR)
    t = np.arange(N) / SR


# ---------------------------------------------------------------- utilidades de señal
def snap(f):
    """Frecuencia -> bin entero: ciclos enteros por loop (clave para que cierre)."""
    return max(1, int(round(f * L)))


def lp(fc, order=2):
    return 1.0 / np.sqrt(1.0 + (freqs / fc) ** (2 * order))


def hp(fc, order=2):
    return 1.0 / np.sqrt(1.0 + (fc / np.maximum(freqs, 1e-3)) ** (2 * order))


def lfo(ciclos, fase=0.0):
    """Seno con un número ENTERO de vueltas por loop."""
    return np.sin(2 * np.pi * (int(ciclos) * t / L + fase))


def to_time(spec):
    return np.fft.irfft(spec, n=N)


def norm_rms(x, rms):
    r = np.sqrt(np.mean(x ** 2))
    return x * (rms / r) if r > 1e-12 else x


def saw_spec(f_hz, rng, nharm=40, rolloff=1.4):
    spec = np.zeros(NB, dtype=complex)
    b = snap(f_hz)
    for k in range(1, nharm + 1):
        idx = b * k
        if idx >= NB - 1:
            break
        spec[idx] += (1.0 / k ** rolloff) * np.exp(1j * rng.uniform(0, 2 * np.pi))
    return spec


def voice_spec(f_hz, rng, detune_bins):
    spec = np.zeros(NB, dtype=complex)
    for d in detune_bins:
        spec += saw_spec(f_hz + d / L, rng)
    return spec


def add_wrap(buf, sig, start):
    """Suma sig en buf desde 'start' y da la vuelta al final: las colas cruzan la costura."""
    n = len(sig)
    start %= N
    first = min(n, N - start)
    buf[start:start + first] += sig[:first]
    if first < n:
        buf[:n - first] += sig[first:]


# =====================================================================================
#  Capas
# =====================================================================================
# (nombre, Hz en Re, ciclos de la envolvente, fase, nivel)
VOICES = [
    ("D2", 73.416, 1, 0.00, 1.00), ("A2", 110.000, 1, 0.25, 0.80), ("D3", 146.832, 1, 0.50, 0.85),
    ("A3", 220.000, 2, 0.10, 0.70), ("E4", 329.628, 2, 0.60, 0.55), ("F#4", 369.994, 3, 0.30, 0.50),
    ("G3", 196.000, 1, 0.85, 0.45), ("A4", 440.000, 3, 0.70, 0.35),
]


def build_pad(canal, k, brillo, seed):
    rng = np.random.default_rng(100 + canal + 10007 * seed)
    oscuro = np.zeros(N)
    claro = np.zeros(N)
    flip = -1 if canal else 1
    for _, f, cyc, ph, lvl in VOICES:
        sp = voice_spec(f * k, rng, (flip * -14, 0, flip * 17 + canal * 3))
        env = lvl * (0.55 + 0.45 * lfo(cyc, ph + 0.13 * canal))
        oscuro += env * to_time(sp * lp(650))
        claro += env * to_time(sp * lp(2600))
    w = np.clip(0.5 + 0.5 * (0.7 * lfo(1, 0.1 + 0.2 * canal) + 0.3 * lfo(3, 0.4)), 0, 1)
    return (1 - w) * oscuro + w * claro * (0.62 * brillo)


def build_air(canal, seed):
    rs = np.random.default_rng(500 + canal + 10007 * seed)
    ns = lambda: np.exp(1j * rs.uniform(0, 2 * np.pi, NB))
    lo = to_time(ns() * hp(180) * lp(900, 3))
    hi = to_time(ns() * hp(1400, 2) * lp(6500, 2))
    lo /= lo.std()
    hi /= hi.std()
    swell_lo = 0.55 + 0.45 * lfo(3, 0.15 * canal)
    swell_hi = 0.50 + 0.50 * lfo(5, 0.5 + 0.2 * canal)
    sweep = 0.5 + 0.5 * lfo(2, 0.3)
    return 0.55 * swell_lo * lo * (1 - 0.4 * sweep) + 0.22 * swell_hi * hi * sweep


def build_shimmer(canal, k, seed):
    rs = np.random.default_rng(900 + canal + 10007 * seed)
    out = np.zeros(N)
    for f, cyc, ph, a in [(587.33, 2, 0.1, 1.0), (739.99, 3, 0.55, 0.7), (880.0, 4, 0.8, 0.6)]:
        sp = np.zeros(NB, dtype=complex)
        sp[min(snap(f * k) + 2 * canal, NB - 2)] = np.exp(1j * rs.uniform(0, 2 * np.pi))
        out += a * np.clip(0.5 + 0.5 * lfo(cyc, ph), 0, 1) ** 2 * to_time(sp)
    return out / (np.abs(out).max() + 1e-9)


def build_ir(canal, seed, rt60=6.0):
    rs = np.random.default_rng(1300 + canal + 10007 * seed)
    n_ir = int(SR * rt60 * 1.1)
    tt = np.arange(n_ir) / SR
    ir = rs.standard_normal(n_ir) * np.exp(-6.91 * tt / rt60)
    a = int(0.03 * SR)
    ir[:a] *= np.linspace(0, 1, a)
    full = np.zeros(N)
    full[:n_ir] = ir
    spec = np.fft.rfft(full) * lp(3800, 2) * hp(120, 1)
    return spec / np.sqrt(np.sum(np.abs(spec) ** 2) / NB)


def reverb(x, ir_spec):
    return np.fft.irfft(np.fft.rfft(x) * ir_spec, n=N)  # circular -> cierra


def build_sub(k):
    d2 = 73.416 * k
    s = np.sin(2 * np.pi * snap(d2) / L * t) + 0.45 * np.sin(2 * np.pi * snap(d2 / 2) / L * t + 0.7)
    s = np.tanh(1.7 * s)
    s = to_time(np.fft.rfft(s) * lp(220, 2))
    return s * (0.85 + 0.15 * lfo(4, 0.2))


# ---------------------------------------------------------------- cuerdas y campanitas
def pluck(f, seed, dur=5.0):
    r = np.random.default_rng(seed)
    tt = np.arange(int(dur * SR)) / SR
    out = np.zeros_like(tt)
    for kk in range(1, 14):
        fk = f * kk * np.sqrt(1 + 0.00012 * kk * kk)
        if fk > 7000:
            break
        out += (1.0 / kk ** 1.25) * np.exp(-tt / (2.2 / (1 + 0.55 * kk))) * np.sin(2 * np.pi * fk * tt + r.uniform(0, 6.28))
    th = r.standard_normal(len(tt)) * np.exp(-tt / 0.012)
    th = np.fft.irfft(np.fft.rfft(th) / np.sqrt(1 + (np.fft.rfftfreq(len(tt), 1 / SR) / 1500) ** 4), n=len(tt))
    out += 0.25 * th
    out *= np.minimum(1, tt / 0.004) * np.exp(-tt / (dur / 2.2))
    return out / np.abs(out).max()


def chime(f, seed, dur=7.0):
    r = np.random.default_rng(seed)
    tt = np.arange(int(dur * SR)) / SR
    out = np.zeros_like(tt)
    for ratio, a, tau in [(1.0, 1.0, 3.2), (2.756, 0.38, 1.7), (5.404, 0.16, 0.8), (8.93, 0.06, 0.4)]:
        out += a * np.exp(-tt / tau) * np.sin(2 * np.pi * f * ratio * tt + r.uniform(0, 6.28))
    out *= np.minimum(1, tt / 0.006)
    return out / np.abs(out).max()


# Frases de cuerda: (inicio como fracción del loop, [(segundos desde el inicio, Hz en Re, nivel, paneo)])
_D4, _E4, _F4s, _A4, _B3, _A3 = 293.66, 329.63, 369.99, 440.0, 246.94, 220.0
FRASES0 = [
    (8 / 96,  [(0, _A3, 1.0, -.3), (1.4, _D4, .8, .2), (2.9, _F4s, .8, .4), (4.6, _E4, .7, -.1)]),
    (33 / 96, [(0, _D4, .9, .1), (1.5, _E4, .75, -.3), (3.2, _A4, .7, .3), (5.0, _F4s, .65, 0)]),
    (58 / 96, [(0, _B3, .9, -.2), (1.6, _D4, .8, .3), (3.2, _F4s, .75, -.4), (5.2, _A4, .65, .2)]),
    (80 / 96, [(0, _A3, .9, .3), (1.7, _E4, .75, -.2), (3.6, _D4, .7, .1)]),
]
# Campanitas: (fracción del loop, Hz en Re, nivel, paneo)
CAMPANAS0 = [
    (15 / 96, 1174.66, .9, .5), (22.5 / 96, 880.0, .8, -.5), (22.7 / 96, 1318.5, .7, -.2), (22.95 / 96, 1760.0, .55, .3),
    (43 / 96, 987.77, .8, .4), (49.5 / 96, 1174.66, .85, -.4), (49.75 / 96, 739.99, .6, -.1),
    (68 / 96, 1318.5, .8, .5), (73 / 96, 880.0, .9, -.3), (73.3 / 96, 1174.66, .65, .4), (73.6 / 96, 1760.0, .5, -.5),
    (89 / 96, 987.77, .85, .2),
]


POOL_CUERDA = [220.0, 246.94, 293.66, 329.63, 369.99, 440.0]                       # La3 Si3 Re4 Mi4 Fa#4 La4
POOL_CAMP = [587.33, 659.26, 739.99, 880.0, 987.77, 1174.66, 1318.5, 1480.0, 1760.0]  # Re5 ... La6 (pentatónica de Re)


def eventos(seed):
    """seed 0 = las frases y campanitas originales. Otras semillas = otras notas y momentos (misma escala)."""
    if seed == 0:
        return FRASES0, CAMPANAS0
    r = np.random.default_rng(7000 + seed)
    frases = []
    for i in range(4):
        ini = (0.083 + 0.25 * i + r.uniform(-0.04, 0.04)) % 1.0
        idx = int(r.integers(0, len(POOL_CUERDA)))
        notas, dt = [], 0.0
        for j in range(int(r.integers(3, 5))):
            notas.append((dt, POOL_CUERDA[idx], max(0.6, 1.0 - 0.1 * j) * float(r.uniform(0.85, 1.0)),
                          float(r.uniform(-0.45, 0.45))))
            dt += float(r.uniform(1.3, 1.9))
            idx = int(np.clip(idx + int(r.choice([-2, -1, 1, 2])), 0, len(POOL_CUERDA) - 1))
        frases.append((ini, notas))
    camp = []
    for a in (0.12, 0.25, 0.44, 0.58, 0.72, 0.88):
        fr = (a + r.uniform(-0.04, 0.04)) % 1.0
        idx = int(r.integers(3, len(POOL_CAMP)))
        if r.random() < 0.45:                                    # racimo tipo wind chime: 2-3 notas que caen
            for j in range(int(r.integers(2, 4))):
                camp.append(((fr + j * float(r.uniform(0.2, 0.3)) / L) % 1.0, POOL_CAMP[max(0, idx - j)],
                             max(0.5, 0.9 - 0.15 * j), float(r.uniform(-0.55, 0.55))))
        else:
            camp.append((fr, POOL_CAMP[idx], float(r.uniform(0.7, 0.95)), float(r.uniform(-0.55, 0.55))))
    return frases, camp


def pan_gains(p):
    a = (p + 1) * np.pi / 4
    return np.cos(a), np.sin(a)


def build_events(k, lv_cuerdas, lv_campanas, seed):
    frases, campanas = eventos(seed)
    z = lambda: np.zeros(N)
    dL, dR, sL, sR = z(), z(), z(), z()
    n = 0
    if lv_cuerdas > 0:
        for fr, notas in frases:
            for dt, f, lv, p in notas:
                s = pluck(f * k, seed=n + 977 * seed) * lv
                n += 1
                gl, gr = pan_gains(p)
                st = int((fr * L + dt) * SR)
                add_wrap(dL, 0.55 * gl * s, st); add_wrap(dR, 0.55 * gr * s, st)
                add_wrap(sL, gl * s, st);        add_wrap(sR, gr * s, st)
        for a in (dL, dR, sL, sR):
            a *= lv_cuerdas
    if lv_campanas > 0:
        cL, cR, tL, tR = z(), z(), z(), z()
        for i, (fr, f, lv, p) in enumerate(campanas):
            s = chime(f * k, seed=50 + i + 977 * seed) * lv
            gl, gr = pan_gains(p)
            st = int(fr * L * SR)
            add_wrap(cL, 0.30 * gl * s, st); add_wrap(cR, 0.30 * gr * s, st)
            add_wrap(tL, gl * s, st);        add_wrap(tR, gr * s, st)
        dL += lv_campanas * cL; dR += lv_campanas * cR
        sL += lv_campanas * tL; sR += lv_campanas * tR
    return dL, dR, sL, sR


# ---------------------------------------------------------------- bombo
def build_bombo(bpm, patron, difuso):
    """Bombo redondo y blando (tipo mazo de fieltro). 'difuso' 0..1: más alto = más suave y menos marcado."""
    pulsos = max(1, int(round(L * bpm / 60.0)))           # pulsos enteros -> cierra el loop
    paso = N / pulsos
    d = difuso
    tt = np.arange(int(0.8 * SR)) / SR
    f = 48 + 105 * (1 - 0.6 * d) * np.exp(-tt / (0.030 + 0.030 * d))      # barrido de tono más lento y corto = menos "electrónico"
    ataque = 0.003 + 0.014 * d                                            # ataque más lento = golpe menos marcado
    k = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.minimum(1, tt / ataque) * np.exp(-tt / (0.20 - 0.05 * d))
    k = np.tanh((2.2 - 1.3 * d) * k)                                      # menos saturación = menos sintético
    # un poquito de "madera/fieltro": ruido grave muy corto, para que no suene a seno puro
    r = np.random.default_rng(11)
    th = r.standard_normal(len(tt)) * np.exp(-tt / 0.02) * np.minimum(1, tt / ataque)
    th = np.fft.irfft(np.fft.rfft(th) * (1 / np.sqrt(1 + (np.fft.rfftfreq(len(tt), 1 / SR) / 180) ** 4)), n=len(tt))
    k = k + 0.18 * th / (np.abs(th).max() + 1e-9)
    corte = 380 - 170 * d
    k = np.fft.irfft(np.fft.rfft(k) / np.sqrt(1 + (np.fft.rfftfreq(len(k), 1 / SR) / corte) ** 4), n=len(k))
    k /= np.abs(k).max()
    out = np.zeros(N)
    hr = np.random.default_rng(5)
    for i in range(pulsos):
        jitter = int(hr.uniform(-0.006, 0.006) * SR * d)                  # microvariación humana (determinista)
        amp = (1.0 if i % 2 == 0 else 0.86) * (1 + hr.uniform(-0.07, 0.07) * d)
        st = int(round(i * paso)) + jitter
        add_wrap(out, k * amp, st)
        if patron == "corazon":
            add_wrap(out, k * 0.55 * amp, st + int(0.30 * SR))
    out /= np.abs(out).max()
    return out, pulsos, 60.0 * pulsos / L


# =====================================================================================
#  Piezas de mezcla
# =====================================================================================
def hueco_voz(st, db):
    """Campana ancha que baja 'db' dB alrededor de 2 kHz (1-4 kHz): deja espacio a la voz."""
    if db <= 0:
        return st
    f = np.maximum(freqs, 1.0)
    campana = np.exp(-0.5 * (np.log2(f / 2000.0) / 0.9) ** 2)
    curva = 10 ** (-(db * campana) / 20.0)
    return np.fft.irfft(np.fft.rfft(st, axis=1) * curva, n=N, axis=1)


def aplanar(st, dinamica):
    """dinamica=1 no toca nada. Menos de 1: compensa lentamente las subidas y bajadas de volumen."""
    if dinamica >= 0.999:
        return st
    env2 = np.fft.irfft(np.fft.rfft(np.mean(st ** 2, axis=0)) * lp(0.25, 1), n=N)   # envolvente lenta, circular
    env = np.sqrt(np.maximum(env2, 1e-12))
    g = (np.mean(env) / env) ** (1.0 - dinamica)
    return st * np.clip(g, 0.4, 2.5)


def componer_musica(cfg, seed, k):
    """Pad + viento + sub + cuerdas + campanitas con reverb, hueco de voz y dinámica. Sin bombo. -> (2, N)"""
    niv = cfg["niveles"]
    zero = np.zeros(N)
    on = lambda nombre: niv[nombre] > 0
    padL = norm_rms(build_pad(0, k, cfg["brillo"], seed), 0.13) * niv["pad"] if on("pad") else zero
    padR = norm_rms(build_pad(1, k, cfg["brillo"], seed), 0.13) * niv["pad"] if on("pad") else zero
    airL = norm_rms(build_air(0, seed), 0.05) * niv["viento"] if on("viento") else zero
    airR = norm_rms(build_air(1, seed), 0.05) * niv["viento"] if on("viento") else zero
    shL = norm_rms(build_shimmer(0, k, seed), 0.018) * niv["viento"] if on("viento") else zero
    shR = norm_rms(build_shimmer(1, k, seed), 0.018) * niv["viento"] if on("viento") else zero
    sub = norm_rms(build_sub(k), 0.065) * niv["sub"] if on("sub") else zero
    irL, irR = build_ir(0, seed), build_ir(1, seed)

    wL = reverb(0.6 * padL + 0.5 * airL + 6.0 * shL, irR)
    wR = reverb(0.6 * padR + 0.5 * airR + 6.0 * shR, irL)
    wL = norm_rms(wL, 0.09) * cfg["espacio"] if np.any(wL) else wL
    wR = norm_rms(wR, 0.09) * cfg["espacio"] if np.any(wR) else wR

    pan = 0.5 * cfg["movimiento_viento"] * lfo(1, 0.0)
    Lo = padL + airL * (1 - pan) + sub + wL
    Ro = padR + airR * (1 + pan) + sub + wR

    if on("cuerdas") or on("campanitas"):
        dL, dR, sL, sR = build_events(k, niv["cuerdas"], niv["campanitas"], seed)
        ref = 0.13 * 0.55
        e = max(cfg["espacio"], 0.25)
        Lo += ref * (dL + 0.9 * e * reverb(sL, irR))
        Ro += ref * (dR + 0.9 * e * reverb(sR, irL))

    st = np.stack([Lo, Ro])
    st = hueco_voz(st, cfg["hueco_voz"])
    st = aplanar(st, cfg["dinamica"])
    return st


def componer_bombo(cfg, seed):
    niv = cfg["niveles"]["bombo"]
    if niv <= 0:
        return None, ""
    irL, irR = build_ir(0, seed), build_ir(1, seed)
    kick, pulsos, bpm_real = build_bombo(cfg["bombo_bpm"], cfg["bombo_patron"], cfg["bombo_difuso"])
    g = 0.34 * niv
    kL = g * kick + 0.004 * niv * reverb(kick, irL)
    kR = g * kick + 0.004 * niv * reverb(kick, irR)
    return np.stack([kL, kR]), f" | bombo {bpm_real:.1f} bpm ({pulsos} pulsos)"


def masterizar(st, cfg, circular):
    """Saturación suave, corte de infra-graves, volumen por nivel medio y tope de pico (-6 dBFS)."""
    st = np.tanh(1.2 * st) / 1.2
    if circular:
        st = np.fft.irfft(np.fft.rfft(st, axis=1) * hp(24, 2), n=st.shape[1], axis=1)
    else:
        st = sosfilt(butter(2, 24, "highpass", fs=SR, output="sos"), st, axis=1)
    rms = np.sqrt(np.mean(st * st, dtype=np.float64))
    st = st * np.float32(10 ** (cfg["volumen"] / 20.0) / rms) if st.dtype == np.float32 else st * (10 ** (cfg["volumen"] / 20.0) / rms)
    pico = float(np.abs(st).max())
    if pico > 0.5:
        st = st * (0.5 / pico)
        AVISOS.append("El pico habría pasado de -6 dBFS; bajé el volumen general para protegerte.")
    return st


def guardar_wav(ruta, st):
    """st: (2, muestras) float -> WAV 16 bit con dither, por trozos (cuida la memoria en sesiones largas)."""
    n = st.shape[1]
    pcm = np.empty((n, 2), dtype=np.int16)
    g = np.random.default_rng(3)
    for i in range(0, n, 8_000_000):
        tr = st[:, i:i + 8_000_000].T.astype(np.float32)
        d = (g.random(tr.shape, dtype=np.float32) - g.random(tr.shape, dtype=np.float32)) / 32768.0
        pcm[i:i + len(tr)] = np.int16(np.round(np.clip(tr + d, -1, 1) * 32767))
    wavfile.write(ruta, SR, pcm)
    return pcm


def semitonos(tonalidad, offset=0):
    s = ((NOTAS.index(tonalidad) - 2 + 6) % 12) - 6          # respecto a Re, entre -6 y +5
    s += offset
    return s - 12 if s > 6 else s


# =====================================================================================
#  Modo LOOP
# =====================================================================================
def render_loop(cfg, outdir, nombre):
    preparar(cfg["duracion"])
    seed = cfg["semilla"]
    k = 2 ** (semitonos(cfg["tonalidad"]) / 12.0)
    print(f"LOOP · {cfg['tonalidad']} · {L} s · semilla {seed} · {cfg['volumen']:g} dBFS · preset '{cfg['preset']}'"
          f" · hueco voz {cfg['hueco_voz']:g} dB · dinámica {cfg['dinamica']:g}")
    st = componer_musica(cfg, seed, k)
    bombo, info = componer_bombo(cfg, seed)
    if bombo is not None:
        st = st + bombo
    st = masterizar(st, cfg, circular=True)

    seam = np.abs(st[:, 0] - st[:, -1]).max()
    paso_max = np.abs(np.diff(st, axis=1)).max()
    ok = seam < paso_max * 0.35
    print(f"  RMS {20*np.log10(np.sqrt(np.mean(st**2))):.1f} dBFS · pico {20*np.log10(np.abs(st).max()):.1f} dBFS"
          f" · costura {'OK' if ok else 'REVISAR'} ({seam:.4f} vs {paso_max:.4f}){info}")
    ruta = os.path.join(outdir, nombre + ".wav")
    pcm = guardar_wav(ruta, st)
    print(f"  -> {ruta}")
    if cfg["previa"] > 1:
        rp = os.path.join(outdir, nombre + f"_previa_x{cfg['previa']}.wav")
        wavfile.write(rp, SR, np.tile(pcm, (cfg["previa"], 1)))
        print(f"  -> {rp}  (el loop repetido, para comprobar la unión)")
    return st


# =====================================================================================
#  Modo SESIÓN LARGA
# =====================================================================================
PROGRESION = [0, 5, 0, 7]      # I - IV - I - V (semitonos sobre la tónica), se repite


def render_sesion(cfg, outdir, nombre):
    T = cfg["sesion"]
    preparar(cfg["duracion"])                                    # cada sección es un trozo de 'duracion' s
    Ls = L
    ov = int(round(min(14.0, Ls / 4.0) * SR))                    # fundido entre secciones
    step = N - ov
    total = T * SR
    n_sec = 1 if total <= N else int(np.ceil((total - ov) / step))
    print(f"SESIÓN · {cfg['tonalidad']} · {T} s ({T/60:.1f} min) · {n_sec} secciones de {Ls} s · semilla {cfg['semilla']}"
          f" · preset '{cfg['preset']}' · {'acorde fijo' if cfg['acorde_fijo'] else 'viaja I-IV-I-V'}")

    out = np.zeros((2, total), dtype=np.float32)
    x = np.linspace(0.0, np.pi / 2, ov)
    entra, sale = np.sin(x), np.cos(x)                           # potencia constante
    for i in range(n_sec):
        off = 0 if cfg["acorde_fijo"] else PROGRESION[i % len(PROGRESION)]
        k = 2 ** (semitonos(cfg["tonalidad"], off) / 12.0)
        sec = componer_musica(cfg, cfg["semilla"] + 17 * i, k)
        g = np.ones(N)
        if i > 0:
            g[:ov] = entra
        if i < n_sec - 1:
            g[-ov:] = sale
        a = i * step
        m = min(N, total - a)
        out[:, a:a + m] += (sec * g)[:, :m].astype(np.float32)
        print(f"  sección {i+1}/{n_sec} lista", end="\r", flush=True)
    print()

    bombo, info = componer_bombo(cfg, cfg["semilla"])
    if bombo is not None:                                        # el bombo es periódico: se repite sin fundidos
        b32 = bombo.astype(np.float32)
        for a in range(0, total, N):
            m = min(N, total - a)
            out[:, a:a + m] += b32[:, :m]

    out = masterizar(out, cfg, circular=False)
    fi = int(min(cfg["fundido_in"], T / 3.0) * SR)
    fo = int(min(cfg["fundido_out"], T / 3.0) * SR)
    if fi > 1:
        out[:, :fi] *= (0.5 - 0.5 * np.cos(np.linspace(0, np.pi, fi))).astype(np.float32)
    if fo > 1:
        out[:, -fo:] *= (0.5 + 0.5 * np.cos(np.linspace(0, np.pi, fo))).astype(np.float32)

    # informe: nivel por minuto (para ver que no hay huecos ni saltos en las uniones)
    por_min = [20 * np.log10(np.sqrt(np.mean(out[:, i:i + 60 * SR] ** 2, dtype=np.float64)) + 1e-9)
               for i in range(0, total - 10 * SR, 60 * SR)]
    print(f"  pico {20*np.log10(np.abs(out).max()):.1f} dBFS · nivel por minuto (dBFS): "
          + ", ".join(f"{v:.1f}" for v in por_min[:12]) + (" ..." if len(por_min) > 12 else "") + info)
    ruta = os.path.join(outdir, nombre + ".wav")
    guardar_wav(ruta, out)
    print(f"  -> {ruta}")
    return out


# =====================================================================================
#  Línea de comandos
# =====================================================================================
def main(argv=None):
    ap = argparse.ArgumentParser(description="Generador de música de fondo para meditaciones.",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--preset", choices=list(PRESETS))
    ap.add_argument("--duracion", type=float, help="segundos del loop (60-180). En sesión: largo de cada sección")
    ap.add_argument("--sesion", type=float, help="modo sesión larga: segundos totales (30-3600)")
    ap.add_argument("--fundido-in", dest="fundido_in", type=float, help="(sesión) segundos de entrada suave")
    ap.add_argument("--fundido-out", dest="fundido_out", type=float, help="(sesión) segundos de salida suave")
    ap.add_argument("--acorde-fijo", dest="acorde_fijo", action="store_true", help="(sesión) no cambiar de acorde")
    ap.add_argument("--tonalidad", help="C, C#, D, ... B")
    ap.add_argument("--volumen", type=float, help="dBFS medio (-40 a -14). Por defecto -26")
    ap.add_argument("--semilla", type=int, help="otra versión del mismo tema (0 = la original)")
    ap.add_argument("--hueco-voz", dest="hueco_voz", type=float, help="dB que baja la música en 1-4 kHz (0-8, por defecto 3)")
    ap.add_argument("--dinamica", type=float, help="0 volumen plano ... 1 respira (por defecto 1)")
    ap.add_argument("--brillo", type=float, help="0-2")
    ap.add_argument("--espacio", type=float, help="reverb 0-2")
    ap.add_argument("--movimiento-viento", dest="movimiento_viento", type=float, help="0-2")
    ap.add_argument("--bombo-bpm", dest="bombo_bpm", type=float, help="40-70")
    ap.add_argument("--bombo-patron", dest="bombo_patron", help="simple | corazon")
    ap.add_argument("--bombo-difuso", dest="bombo_difuso", type=float, help="0 marcado ... 1 muy blando (por defecto 0.7)")
    ap.add_argument("--previa", type=int, help="(loop) guardar además el loop repetido N veces")
    for capa in CAPAS:
        ap.add_argument(f"--{capa}", type=float, help=f"nivel de {capa} (0 apaga, 1 normal, 2 doble)")
    ap.add_argument("-o", "--salida", default=".", help="carpeta de salida")
    ap.add_argument("--nombre", help="nombre del archivo (sin extensión)")
    ap.add_argument("--ayuda-presets", action="store_true")
    a = ap.parse_args(argv)

    if a.ayuda_presets:
        for n, p in PRESETS.items():
            print(f"  {n:8s} {p['desc']}")
        return

    cfg = dict(CONFIG)
    cfg["niveles"] = dict(CONFIG.get("niveles") or {})
    for key in ("preset", "duracion", "sesion", "fundido_in", "fundido_out", "tonalidad", "volumen", "semilla",
                "hueco_voz", "dinamica", "brillo", "espacio", "movimiento_viento", "bombo_bpm", "bombo_patron",
                "bombo_difuso", "previa"):
        v = getattr(a, key)
        if v is not None:
            cfg[key] = v
    if a.acorde_fijo:
        cfg["acorde_fijo"] = True
    for capa in CAPAS:
        v = getattr(a, capa)
        if v is not None:
            cfg["niveles"][capa] = v

    final = validar(cfg)
    os.makedirs(a.salida, exist_ok=True)
    base = f"{final['preset']}_{final['tonalidad'].replace('#', 's')}"
    if final["sesion"] > 0:
        render_sesion(final, a.salida, a.nombre or f"sesion_{base}_{final['sesion']}s")
    else:
        render_loop(final, a.salida, a.nombre or f"fondo_{base}_{final['duracion']}s")
    if AVISOS:
        print("\nAvisos:")
        for m in dict.fromkeys(AVISOS):
            print("  •", m)


if __name__ == "__main__":
    main()