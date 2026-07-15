"""v20260627165834
Dashboard Comercial — TYL Herramientas y Seguridad SAS
Versión 3 — limpia desde cero
Ejecutar: streamlit run dashboard_tyl.py
"""
import os, unicodedata, json
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ── CONSTANTES ────────────────────────────────────────────────────────────
def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")

def norm(s):
    if not isinstance(s, str): return ""
    return unicodedata.normalize("NFC", str(s)).strip()

ASESORES = [
    "DIANA ROSSMARY RAMIREZ RIAÑO",
    "INGRID YURLEY CHURIO PATIÑO",
    "JEISSON IVAN CHITIVA VALLEJO",
    "LUIS GABRIEL ACOSTA CIRO",
    "NÉSTOR ARNOLDO USECHE TRIANA",
    "ADRIANA CAROLINA CUEVAS MONSALVE",
]
ASESORES = [norm(a) for a in ASESORES]

SHORT = {
    "DIANA ROSSMARY RAMIREZ RIAÑO":    "Diana R.",
    "INGRID YURLEY CHURIO PATIÑO":     "Ingrid C.",
    "JEISSON IVAN CHITIVA VALLEJO":    "Jeisson C.",
    "LUIS GABRIEL ACOSTA CIRO":        "Luis A.",
    "NÉSTOR ARNOLDO USECHE TRIANA":    "Néstor U.",
    "ADRIANA CAROLINA CUEVAS MONSALVE":"Adriana C.",
}
SHORT = {norm(k): v for k, v in SHORT.items()}

# Metas por mes. Cada mes puede traer una meta distinta por asesor (así lo
# maneja la gerencia comercial). Para añadir un mes nuevo (agosto, etc.)
# basta con agregar su clave (año, mes) aquí con los valores del memo/imagen
# de metas correspondiente. Si un mes con datos aún no tiene metas cargadas,
# la app usa automáticamente las metas del mes definido más reciente y lo
# avisa en pantalla (ver `metas_para_mes` más abajo).
METAS_POR_MES = {
    (2026, 6): {  # Junio 2026
        "DIANA ROSSMARY RAMIREZ RIAÑO":    150_000_000,
        "INGRID YURLEY CHURIO PATIÑO":     150_000_000,
        "JEISSON IVAN CHITIVA VALLEJO":    150_000_000,
        "LUIS GABRIEL ACOSTA CIRO":        150_000_000,
        "NÉSTOR ARNOLDO USECHE TRIANA":     60_000_000,
        "ADRIANA CAROLINA CUEVAS MONSALVE": 50_000_000,
    },
    (2026, 7): {  # Julio 2026
        "DIANA ROSSMARY RAMIREZ RIAÑO":    150_000_000,
        "INGRID YURLEY CHURIO PATIÑO":     150_000_000,
        "JEISSON IVAN CHITIVA VALLEJO":    150_000_000,
        "LUIS GABRIEL ACOSTA CIRO":        150_000_000,
        "NÉSTOR ARNOLDO USECHE TRIANA":     70_000_000,
        "ADRIANA CAROLINA CUEVAS MONSALVE": 60_000_000,
    },
}
METAS_POR_MES = {ym: {norm(k): v for k, v in metas.items()}
                  for ym, metas in METAS_POR_MES.items()}

def metas_para_mes(anio, mes):
    """Devuelve (metas_dict, es_exacta). Si (anio,mes) no tiene metas
    cargadas todavia, usa las del mes definido mas reciente que sea
    <= (anio,mes) -- o si no hay ninguno anterior, el mas antiguo disponible --
    y marca es_exacta=False para que la UI pueda avisar."""
    if (anio, mes) in METAS_POR_MES:
        return METAS_POR_MES[(anio, mes)], True
    anteriores = [ym for ym in METAS_POR_MES if ym <= (anio, mes)]
    ref = max(anteriores) if anteriores else min(METAS_POR_MES)
    return METAS_POR_MES[ref], False

# Se recalcula en main() segun el mes seleccionado. Queda como dict vacio
# por defecto (nunca se usa sin pasar antes por main()).
METAS = {}

VALID_STATES   = ["Pagado", "Sin pagar", "Pagado parcialmente"]
CLOSED_STAGES  = ["Ganado Terminado", "PERDIDO POR PRECIO", "PERDIDO POR STOCK"]
ACTIVE_STAGES  = ["Nuevo", "Propuesta en revision", "En despacho"]
MESES_ES = {1:"ene",2:"feb",3:"mar",4:"abr",5:"may",6:"jun",
            7:"jul",8:"ago",9:"sep",10:"oct",11:"nov",12:"dic"}
MESES_ES_FULL = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",
                  7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",
                  11:"Noviembre",12:"Diciembre"}

import calendar as _calendar
import datetime as _dt

def build_semana_info(dates):
    """Construye, a partir de las fechas REALES presentes en los datos
    (facturación + visitas):
      - labels:    {semana_iso: "Sem NN (rango de fechas)"}
      - dias_semana: {semana_iso: nº de días de esa semana que caen dentro
                      del mes analizado} — una semana partida a caballo entre
                      dos meses (típico en la última semana) cuenta solo sus
                      días reales, no 7 parejos.
      - total_dias_mes: días calendario del mes analizado.
    Esto evita dos problemas del enfoque anterior con lista fija de semanas:
      1) Semanas fuera de la lista quedaban invisibles en el filtro y su
         facturación se perdía sin aviso (p.ej. la semana 27 con el 29-30 jun).
      2) Prorratear la meta como (nº semanas seleccionadas / 4) sobre-estima
         el objetivo cuando una de esas "semanas" en realidad son solo 2 días.
    """
    dates = pd.to_datetime(dates).dropna()
    if dates.empty:
        return {}, {}, 30

    # Mes analizado = mes de la fecha más reciente en los datos.
    fecha_max = dates.max()
    anio_mes, mes_mes = fecha_max.year, fecha_max.month
    total_dias_mes = _calendar.monthrange(anio_mes, mes_mes)[1]

    iso = dates.dt.isocalendar()
    labels, dias_semana = {}, {}
    for w in sorted(iso["week"].unique()):
        mask = iso["week"] == w
        sub_dates = dates[mask]
        iso_anio = int(iso.loc[mask, "year"].mode()[0])
        # Los 7 días calendario de esa semana ISO (para saber cuántos caen
        # dentro del mes que estamos analizando, aunque no haya factura
        # registrada cada uno de esos días).
        dias_semana_completa = [_dt.date.fromisocalendar(iso_anio, int(w), wd) for wd in range(1, 8)]
        n_dias_en_mes = sum(1 for d in dias_semana_completa
                            if d.year == anio_mes and d.month == mes_mes)
        dias_semana[int(w)] = max(n_dias_en_mes, 1)

        d_min, d_max = sub_dates.min(), sub_dates.max()
        if d_min.month == d_max.month:
            mes = MESES_ES[d_min.month]
            rango = f"{d_min.day} {mes}" if d_min.day == d_max.day else f"{d_min.day}-{d_max.day} {mes}"
        else:
            rango = f"{d_min.day} {MESES_ES[d_min.month]}-{d_max.day} {MESES_ES[d_max.month]}"
        labels[int(w)] = f"Sem {w} ({rango})"
    return labels, dias_semana, total_dias_mes

# Se recalculan en main() a partir de los datos reales; quedan vacíos por
# defecto para que nunca "oculten" semanas silenciosamente.
SEMANA_LABELS   = {}
SEMANA_DIAS     = {}
TOTAL_DIAS_MES  = 30
COLORS = ["#378ADD","#1D9E75","#7F77DD","#D85A30","#BA7517","#D4537E"]
COLOR_MAP = {a: COLORS[i] for i, a in enumerate(ASESORES)}

FOLDER = os.path.dirname(os.path.abspath(__file__))
FILES = {
    "fact": os.path.join(FOLDER, "FACTURACION JUNIO 23 2026 (account.move).xlsx"),
    "cart": os.path.join(FOLDER, "CARTERA (account.move).xlsx"),
    "vis":  os.path.join(FOLDER, "VISITAS JUNIO(calendar.event).xlsx"),
    "cot":  os.path.join(FOLDER, "Cotizaciones crm (crm.lead)-2.xlsx"),
}

# ── REGISTRO DE APERTURAS DEL DASHBOARD ──────────────────────────────────
# Indicador de "¿han entrado a verlo?": cada vez que alguien abre la app en
# el navegador (una vez por sesión, no en cada clic de filtro) se guarda un
# registro en un JSON local junto al script. Esto permite mostrar cuántas
# veces se ha abierto el tablero y cuándo fue el último acceso.
# LIMITACIÓN HONESTA: si el dashboard corre en Streamlit Community Cloud,
# este archivo vive en el contenedor de la app. Se mantiene mientras la app
# esté activa, pero puede reiniciarse si la app se "duerme" por inactividad
# prolongada o si se vuelve a desplegar desde cero. Para un conteo 100%
# permanente e infalible haría falta una base de datos externa (p.ej. Google
# Sheets, Supabase); esto cubre el caso de uso real: saber si el equipo
# comercial/gerencia está entrando a revisar el tablero.
LOG_FILE = os.path.join(FOLDER, "visor_log.json")

def registrar_visita():
    """Registra una apertura del dashboard. Usa session_state para contar
    una sola vez por sesión de navegador (evita inflar el contador con cada
    rerun que dispara un filtro)."""
    if st.session_state.get("_visita_registrada"):
        return st.session_state.get("_visita_log", {"total": 0, "accesos": []})
    st.session_state["_visita_registrada"] = True
    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                log = json.load(f)
        else:
            log = {"total": 0, "accesos": []}
    except Exception:
        log = {"total": 0, "accesos": []}
    ahora = _dt.datetime.now()
    log["total"] = log.get("total", 0) + 1
    log["accesos"] = log.get("accesos", []) + [ahora.strftime("%Y-%m-%d %H:%M")]
    log["accesos"] = log["accesos"][-300:]  # cap para no crecer indefinido
    try:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)
    except Exception:
        pass  # si el filesystem es de solo lectura, no rompe la app
    st.session_state["_visita_log"] = log
    return log

# ── CARGA DE DATOS ────────────────────────────────────────────────────────
def match_name(nombre, lista):
    """Compara ignorando tildes: NESTOR == NÉSTOR (Odoo exporta inconsistente)."""
    if not isinstance(nombre, str): return None
    n = strip_accents(norm(nombre)).upper()
    for a in lista:
        if strip_accents(norm(a)).upper() == n:
            return a
    return None

def load_data(files, _mod_times=None):
    # Facturación — usar valor sin IVA
    # NOTA: se suman TODAS las filas de cada asesor (sin filtrar por
    # "Estado en pago" ni excluir DMC manualmente). Los pares Revertido+DMC
    # ya se cancelan matemáticamente solos (monto positivo + su negativo = 0),
    # y las revertidas que Odoo no compensó con una DMC de monto exacto sí
    # deben contarse (así calcula Odoo el subtotal real por vendedor).
    # Filtrar por VALID_STATES + excluir DMC "a mano" descuadraba el total
    # cada vez que una Revertida no tenía una DMC con el monto exacto.
    df_raw = pd.read_excel(files["fact"])
    df_raw["_vend"] = df_raw["Vendedor"].apply(lambda x: match_name(x, ASESORES))
    df_f = df_raw[df_raw["_vend"].notna()].copy()
    df_f["Vendedor"] = df_f["_vend"]
    # "Int64" (nullable) en vez de "int": algunas facturas llegan sin
    # "Fecha de la factura" (NaT) -- con int estricto esto rompía toda la
    # carga (ValueError al convertir NaN a int). Con Int64 esas filas quedan
    # con semana/anio_mes en blanco: no se pueden ubicar en ningun mes o
    # semana (no tienen fecha), asi que no aparecen en las vistas Mensual ni
    # Trimestral ni en el grafico Historico -- pero no rompen la app, y se
    # avisa en pantalla cuantas son para que se puedan corregir en Odoo.
    df_f["semana"]   = df_f["Fecha de la factura"].dt.isocalendar().week.astype("Int64")
    df_f["anio_mes"] = df_f["Fecha de la factura"].dt.to_period("M")
    df_f["Total"]    = df_f["Importe sin impuestos en la moneda firmada"]
    df_f["_sin_fecha_valor"] = df_f["Total"].where(df_f["Fecha de la factura"].isna(), 0)

    # Cartera
    df_c = pd.read_excel(files["cart"])
    df_c["_vend"] = df_c["Vendedor"].apply(lambda x: match_name(x, ASESORES))
    df_c = df_c[df_c["_vend"].notna()].copy()
    df_c["Vendedor"] = df_c["_vend"]

    # Visitas — comparación robusta con norm() en ambos lados
    df_v = pd.read_excel(files["vis"])
    df_v["_asist"] = df_v["Asistentes"].apply(lambda x: match_name(x, ASESORES))
    df_v = df_v[df_v["_asist"].notna()].copy()
    df_v["Asistentes"] = df_v["_asist"]
    df_v["semana"] = df_v["Iniciar"].apply(
        lambda x: int(x.isocalendar()[1]) if pd.notna(x) else 0
    )
    df_v["anio_mes"] = df_v["Iniciar"].dt.to_period("M")

    # Cotizaciones — histórico completo
    df_cot = pd.read_excel(files["cot"])
    df_cot["_vend"] = df_cot["Vendedor"].apply(lambda x: match_name(x, ASESORES))
    df_cot = df_cot[df_cot["_vend"].notna()].copy()
    df_cot["Vendedor"] = df_cot["_vend"]

    sin_fecha_n = int(df_f["Fecha de la factura"].isna().sum())
    sin_fecha_valor = float(df_f["_sin_fecha_valor"].sum())
    df_f = df_f.drop(columns=["_sin_fecha_valor"])

    return {"fact": df_f, "cart": df_c, "vis": df_v, "cot": df_cot,
            "sin_fecha_n": sin_fecha_n, "sin_fecha_valor": sin_fecha_valor}


def meses_disponibles(data):
    """Lista ordenada (ascendente) de periodos (Year-Month) presentes en
    facturacion y/o visitas -- asi el selector de mes se arma solo con los
    meses que realmente tienen datos, sin listas fijas que haya que tocar
    cada vez que llega un mes nuevo."""
    periodos = pd.concat([data["fact"]["anio_mes"], data["vis"]["anio_mes"]]).dropna()
    return sorted(periodos.unique())


def filter_por_mes(data, periodo):
    """Recorta facturacion y visitas al mes/anio seleccionado. Cartera y
    cotizaciones se mantienen completas: cartera es el saldo pendiente
    vigente (no un evento del mes) y cotizaciones se analiza en historico
    acumulado, como ya hacia el resto del dashboard."""
    fact = data["fact"][data["fact"]["anio_mes"] == periodo].copy()
    vis  = data["vis"][data["vis"]["anio_mes"] == periodo].copy()
    return {"fact": fact, "cart": data["cart"], "vis": vis, "cot": data["cot"]}


def trimestre_de(periodo):
    """Recibe un Period('M') y devuelve el número de trimestre (1-4)."""
    return (periodo.month - 1) // 3 + 1

def trimestres_disponibles(periodos):
    """Lista ordenada de (anio, trimestre) presentes en los meses con datos."""
    return sorted(set((p.year, trimestre_de(p)) for p in periodos))

def meses_del_trimestre(periodos, anio, trimestre):
    """Sub-lista (ordenada) de los Period('M') que caen dentro de un
    trimestre específico y que sí tienen datos reales."""
    return sorted(p for p in periodos if p.year == anio and trimestre_de(p) == trimestre)

def filter_por_trimestre(data, meses_incluidos):
    """Igual que filter_por_mes pero para un conjunto de meses (un trimestre).
    Cartera y cotizaciones se mantienen completas, como en filter_por_mes."""
    fact = data["fact"][data["fact"]["anio_mes"].isin(meses_incluidos)].copy()
    vis  = data["vis"][data["vis"]["anio_mes"].isin(meses_incluidos)].copy()
    return {"fact": fact, "cart": data["cart"], "vis": vis, "cot": data["cot"]}

def apply_filters(data, asesores_sel, semanas_sel):
    fact = data["fact"][
        data["fact"]["Vendedor"].isin(asesores_sel) &
        data["fact"]["semana"].isin(semanas_sel)
    ]
    cart = data["cart"][data["cart"]["Vendedor"].isin(asesores_sel)]
    vis  = data["vis"][
        data["vis"]["Asistentes"].isin(asesores_sel) &
        data["vis"]["semana"].isin(semanas_sel)
    ]
    cot  = data["cot"][data["cot"]["Vendedor"].isin(asesores_sel)]
    return {"fact": fact, "cart": cart, "vis": vis, "cot": cot}


def filter_por_asesor(data, asesores_sel):
    """Filtra por asesor(es) sin filtrar por semana -- usado en Trimestral
    e Histórico, donde el concepto de 'semana seleccionada' no aplica."""
    return {
        "fact": data["fact"][data["fact"]["Vendedor"].isin(asesores_sel)],
        "cart": data["cart"][data["cart"]["Vendedor"].isin(asesores_sel)],
        "vis":  data["vis"][data["vis"]["Asistentes"].isin(asesores_sel)],
        "cot":  data["cot"][data["cot"]["Vendedor"].isin(asesores_sel)],
    }

def frac_mes(semanas_sel):
    """Fracción del mes cubierta por las semanas seleccionadas, en días
    reales (no en nº de semanas/4) — así una semana partida de 2 días no
    pesa igual que una semana completa de 7 al prorratear la meta."""
    if not SEMANA_DIAS or not TOTAL_DIAS_MES:
        return len(semanas_sel) / 4  # fallback si aún no se calculó
    dias = sum(SEMANA_DIAS.get(w, 0) for w in semanas_sel)
    return dias / TOTAL_DIAS_MES

def calc_kpis(filt, asesores_sel, semanas_sel):
    n_sem    = len(semanas_sel)
    frac     = frac_mes(semanas_sel)
    tot_fact = filt["fact"]["Total"].sum()
    tot_meta = sum(METAS.get(a, 0) * frac for a in asesores_sel)
    pct_meta = (tot_fact / tot_meta * 100) if tot_meta else 0
    tot_pend = filt["cart"]["Importe pendiente firmado"].sum()
    tot_vis  = len(filt["vis"])
    avg_vis  = tot_vis / (len(asesores_sel) * n_sem) if asesores_sel else 0
    closed   = filt["cot"][filt["cot"]["Etapa"].isin(CLOSED_STAGES)]
    ganadas  = (closed["Etapa"] == "Ganado Terminado").sum()
    perdidas = (closed["Etapa"] != "Ganado Terminado").sum()
    activas  = filt["cot"][filt["cot"]["Etapa"].isin(ACTIVE_STAGES)].shape[0]
    cerradas = ganadas + perdidas
    tasa     = (ganadas / cerradas * 100) if cerradas else 0
    return dict(tot_fact=tot_fact, tot_meta=tot_meta, pct_meta=pct_meta,
                tot_pend=tot_pend, tot_vis=tot_vis, avg_vis=avg_vis,
                ganadas=ganadas, perdidas=perdidas, activas=activas, tasa=tasa)

def calc_kpis_periodo(filt, asesores_sel, meses_incluidos):
    """Version de calc_kpis para Trimestral/Histórico: en vez de prorratear
    la meta por semanas del mes, suma la meta OFICIAL de cada mes incluido
    (cada mes puede tener una meta distinta, ver METAS_POR_MES)."""
    tot_fact = filt["fact"]["Total"].sum()
    tot_meta = 0
    for p in meses_incluidos:
        metas_mes, _ = metas_para_mes(p.year, p.month)
        tot_meta += sum(metas_mes.get(a, 0) for a in asesores_sel)
    pct_meta = (tot_fact / tot_meta * 100) if tot_meta else 0
    tot_pend = filt["cart"]["Importe pendiente firmado"].sum()
    tot_vis  = len(filt["vis"])
    n_meses  = len(meses_incluidos) if meses_incluidos else 1
    avg_vis_mes = tot_vis / (len(asesores_sel) * n_meses) if asesores_sel else 0
    closed   = filt["cot"][filt["cot"]["Etapa"].isin(CLOSED_STAGES)]
    ganadas  = (closed["Etapa"] == "Ganado Terminado").sum()
    perdidas = (closed["Etapa"] != "Ganado Terminado").sum()
    activas  = filt["cot"][filt["cot"]["Etapa"].isin(ACTIVE_STAGES)].shape[0]
    cerradas = ganadas + perdidas
    tasa     = (ganadas / cerradas * 100) if cerradas else 0
    return dict(tot_fact=tot_fact, tot_meta=tot_meta, pct_meta=pct_meta,
                tot_pend=tot_pend, tot_vis=tot_vis, avg_vis_mes=avg_vis_mes,
                ganadas=ganadas, perdidas=perdidas, activas=activas, tasa=tasa)

# ── GRÁFICOS ──────────────────────────────────────────────────────────────
def fmt_m(n): return f"${n/1_000_000:.1f}M"
def fmt_k(n):
    if n >= 1_000_000: return f"${n/1_000_000:.1f}M"
    if n >= 1_000:     return f"${n/1_000:.0f}K"
    return f"${n:.0f}"

def chart_fact_vs_meta(fact_df, asesores_sel, semanas_sel):
    frac = frac_mes(semanas_sel)
    labels, dF, dM = [], [], []
    for a in asesores_sel:
        labels.append(SHORT.get(a, a))
        dF.append(fact_df[fact_df["Vendedor"] == a]["Total"].sum())
        dM.append(METAS.get(a, 0) * frac)
    fig = go.Figure()
    for i, (lbl, f) in enumerate(zip(labels, dF)):
        fig.add_bar(x=[lbl], y=[f], marker_color=COLORS[i % len(COLORS)],
                    opacity=0.85, showlegend=False)
    fig.add_scatter(x=labels, y=dM, mode="lines+markers", name="Meta",
                    line=dict(color="#888780", width=1.5, dash="dot"),
                    marker=dict(size=5, color="#888780"))
    fig.update_layout(height=260, margin=dict(l=0,r=0,t=10,b=0),
                      yaxis=dict(tickformat="$,.0f", gridcolor="#f0f0f0"),
                      plot_bgcolor="white", paper_bgcolor="white",
                      legend=dict(orientation="h", y=1.1))
    return fig

def chart_tendencia(fact_df, asesores_sel, semanas_sel):
    fig = go.Figure()
    for i, a in enumerate(asesores_sel):
        ys, xs = [], []
        for w in sorted(semanas_sel):
            xs.append(SEMANA_LABELS.get(w, f"Sem {w}"))
            ys.append(fact_df[(fact_df["Vendedor"] == a) &
                               (fact_df["semana"] == w)]["Total"].sum())
        fig.add_scatter(x=xs, y=ys, mode="lines+markers",
                        name=SHORT.get(a, a),
                        line=dict(color=COLORS[i % len(COLORS)], width=2),
                        marker=dict(size=5, color=COLORS[i % len(COLORS)],
                                    line=dict(color="white", width=1.5)))
    fig.update_layout(height=260, margin=dict(l=0,r=0,t=10,b=0),
                      yaxis=dict(tickformat="$,.0f", gridcolor="#f0f0f0"),
                      plot_bgcolor="white", paper_bgcolor="white",
                      legend=dict(orientation="h", y=1.1, font=dict(size=10)))
    return fig

def chart_por_mes(fact_df, asesores_sel, meses_incluidos):
    """Facturación por mes (barras, uno por asesor apilado) + línea de meta
    por mes -- usado en la vista Trimestral para comparar los meses que
    componen el trimestre."""
    fig = go.Figure()
    labels = [f"{MESES_ES[p.month]} {p.year}" for p in meses_incluidos]
    for i, a in enumerate(asesores_sel):
        ys = [fact_df[(fact_df["Vendedor"] == a) & (fact_df["anio_mes"] == p)]
              ["Total"].sum() for p in meses_incluidos]
        fig.add_bar(x=labels, y=ys, name=SHORT.get(a, a),
                    marker_color=COLORS[i % len(COLORS)], opacity=0.85)
    metas_mes = []
    for p in meses_incluidos:
        m, _ = metas_para_mes(p.year, p.month)
        metas_mes.append(sum(m.get(a, 0) for a in asesores_sel))
    fig.add_scatter(x=labels, y=metas_mes, mode="lines+markers", name="Meta",
                    line=dict(color="#888780", width=1.5, dash="dot"),
                    marker=dict(size=6, color="#888780"))
    fig.update_layout(barmode="stack", height=280, margin=dict(l=0,r=0,t=10,b=0),
                      yaxis=dict(tickformat="$,.0f", gridcolor="#f0f0f0"),
                      plot_bgcolor="white", paper_bgcolor="white",
                      legend=dict(orientation="h", y=1.15, font=dict(size=10)))
    return fig

def chart_visitas_por_mes(vis_df, asesores_sel, meses_incluidos):
    fig = go.Figure()
    labels = [f"{MESES_ES[p.month]} {p.year}" for p in meses_incluidos]
    for i, a in enumerate(asesores_sel):
        ys = [vis_df[(vis_df["Asistentes"] == a) & (vis_df["anio_mes"] == p)]
              .shape[0] for p in meses_incluidos]
        fig.add_bar(x=labels, y=ys, name=SHORT.get(a, a),
                    marker_color=COLORS[i % len(COLORS)], opacity=0.85)
    fig.update_layout(barmode="stack", height=280, margin=dict(l=0,r=0,t=10,b=0),
                      yaxis=dict(gridcolor="#f0f0f0", title="Visitas"),
                      plot_bgcolor="white", paper_bgcolor="white",
                      legend=dict(orientation="h", y=1.15, font=dict(size=10)))
    return fig

def chart_historico(data, asesores_sel, periodos):
    """Vista Histórico: evolución mes a mes de TODOS los meses disponibles
    en los datos (facturación vs. meta en barras/línea, visitas en un eje
    secundario). A medida que se suban más meses, esta gráfica los va
    incorporando automáticamente sin tocar código."""
    fact = data["fact"][data["fact"]["Vendedor"].isin(asesores_sel)]
    vis  = data["vis"][data["vis"]["Asistentes"].isin(asesores_sel)]
    labels    = [f"{MESES_ES[p.month]} {p.year}" for p in periodos]
    fact_vals = [fact[fact["anio_mes"] == p]["Total"].sum() for p in periodos]
    vis_vals  = [vis[vis["anio_mes"] == p].shape[0] for p in periodos]
    meta_vals = []
    for p in periodos:
        m, _ = metas_para_mes(p.year, p.month)
        meta_vals.append(sum(m.get(a, 0) for a in asesores_sel))
    fig = go.Figure()
    fig.add_bar(x=labels, y=fact_vals, name="Facturación",
                marker_color="#378ADD", opacity=0.85)
    fig.add_scatter(x=labels, y=meta_vals, name="Meta", mode="lines+markers",
                    line=dict(color="#888780", width=1.5, dash="dot"),
                    marker=dict(size=6, color="#888780"))
    fig.add_scatter(x=labels, y=vis_vals, name="Visitas", mode="lines+markers",
                    yaxis="y2", line=dict(color="#1D9E75", width=2.5),
                    marker=dict(size=6, color="#1D9E75"))
    fig.update_layout(height=340, margin=dict(l=0,r=40,t=10,b=0),
                      yaxis=dict(title="Facturación", tickformat="$,.0f",
                                 gridcolor="#f0f0f0"),
                      yaxis2=dict(title="Visitas", overlaying="y",
                                  side="right", showgrid=False),
                      legend=dict(orientation="h", y=1.15, font=dict(size=10)),
                      plot_bgcolor="white", paper_bgcolor="white")
    return fig

def chart_cartera(cart_df, asesores_sel):
    rows = [(SHORT.get(a,a), cart_df[cart_df["Vendedor"]==a]
             ["Importe pendiente firmado"].sum(), COLORS[i % len(COLORS)])
            for i, a in enumerate(asesores_sel)]
    rows = [(l, v, c) for l, v, c in rows if v > 0]
    if not rows: return None
    rows.sort(key=lambda x: x[1])
    fig = go.Figure(go.Bar(
        x=[r[1] for r in rows], y=[r[0] for r in rows],
        orientation="h",
        marker_color=[r[2] for r in rows], opacity=0.85))
    fig.update_layout(height=210, margin=dict(l=0,r=0,t=10,b=0),
                      xaxis=dict(tickformat="$,.0f", gridcolor="#f0f0f0"),
                      plot_bgcolor="white", paper_bgcolor="white",
                      showlegend=False)
    return fig

def chart_conversion(cot_df, asesores_sel):
    rows = []
    for a in asesores_sel:
        sub    = cot_df[cot_df["Vendedor"] == a]
        closed = sub[sub["Etapa"].isin(CLOSED_STAGES)]
        gan    = (closed["Etapa"] == "Ganado Terminado").sum()
        per    = (closed["Etapa"] != "Ganado Terminado").sum()
        proc   = sub[sub["Etapa"].isin(ACTIVE_STAGES)].shape[0]
        total_c = gan + per
        tasa   = gan / total_c * 100 if total_c else 0
        rows.append({"A": SHORT.get(a,a), "Gan": gan, "Per": per,
                     "Proc": proc, "Tasa": tasa})
    fig = go.Figure()
    fig.add_bar(name="Ganadas",    x=[r["A"] for r in rows],
                y=[r["Gan"] for r in rows], marker_color="#97C459")
    fig.add_bar(name="Perdidas",   x=[r["A"] for r in rows],
                y=[r["Per"] for r in rows], marker_color="#F09595")
    fig.add_bar(name="En proceso", x=[r["A"] for r in rows],
                y=[r["Proc"] for r in rows], marker_color="#85B7EB")
    fig.add_scatter(x=[r["A"] for r in rows], y=[r["Tasa"] for r in rows],
                    mode="markers+text", name="Tasa %", yaxis="y2",
                    marker=dict(size=8, color="#444441", symbol="diamond"),
                    text=[f"{r['Tasa']:.0f}%" for r in rows],
                    textposition="top center",
                    textfont=dict(size=10, color="#444441"))
    fig.add_hline(y=50, line_dash="dot", line_color="#BA7517",
                  annotation_text="Meta 50%", annotation_position="right",
                  yref="y2")
    fig.update_layout(barmode="stack", height=300,
                      margin=dict(l=0,r=40,t=10,b=0),
                      yaxis=dict(title="Cotizaciones", gridcolor="#f0f0f0"),
                      yaxis2=dict(overlaying="y", side="right",
                                  range=[0, 115], showgrid=False),
                      legend=dict(orientation="h", y=1.1, font=dict(size=10)),
                      plot_bgcolor="white", paper_bgcolor="white")
    return fig

def tabla_visitas(vis_df, asesores_sel, semanas_sel):
    n_sem = len(semanas_sel)
    rows = []
    for a in asesores_sel:
        tv  = vis_df[vis_df["Asistentes"] == a].shape[0]
        avg = tv / n_sem if n_sem else 0
        rows.append({"Asesor": SHORT.get(a,a), "Visitas": tv,
                     "Prom/semana": f"{avg:.1f}",
                     "Estado": "✅ Cumple" if avg >= 3 else "🔴 Bajo"})
    return pd.DataFrame(rows)

def tabla_resumen_periodo(filt, asesores_sel, meses_incluidos):
    """Tabla comparativa por asesor para Trimestral/Histórico -- las
    alertas semanales (tabla_alertas) no aplican aquí porque no hay una
    sola cadencia semanal cuando se agrupan varios meses."""
    n_meses = len(meses_incluidos) if meses_incluidos else 1
    rows = []
    for a in asesores_sel:
        ft   = filt["fact"][filt["fact"]["Vendedor"] == a]["Total"].sum()
        meta = 0
        for p in meses_incluidos:
            m, _ = metas_para_mes(p.year, p.month)
            meta += m.get(a, 0)
        pct  = ft / meta * 100 if meta else 0
        vis  = filt["vis"][filt["vis"]["Asistentes"] == a].shape[0]
        avg_mes = vis / n_meses if n_meses else 0
        pend = filt["cart"][filt["cart"]["Vendedor"] == a]["Importe pendiente firmado"].sum()
        cl   = filt["cot"][filt["cot"]["Vendedor"] == a]
        clo  = cl[cl["Etapa"].isin(CLOSED_STAGES)]
        gan  = (clo["Etapa"] == "Ganado Terminado").sum()
        cer  = len(clo)
        tasa = gan / cer * 100 if cer else 0
        rows.append({
            "Asesor": SHORT.get(a, a),
            "Facturación": fmt_m(ft),
            "Meta": fmt_m(meta),
            "% Meta": f"{pct:.0f}%",
            "Visitas": vis,
            "Prom/mes": f"{avg_mes:.1f}",
            "Cartera": fmt_m(pend),
            "Conversión": f"{tasa:.0f}%",
        })
    return pd.DataFrame(rows)

def tabla_alertas(filt, asesores_sel, semanas_sel):
    n_sem = len(semanas_sel)
    frac  = frac_mes(semanas_sel)
    alertas = []
    for a in asesores_sel:
        ft   = filt["fact"][filt["fact"]["Vendedor"] == a]["Total"].sum()
        meta = METAS.get(a, 0) * frac
        pct  = ft / meta * 100 if meta else 0
        vis  = filt["vis"][filt["vis"]["Asistentes"] == a].shape[0]
        avg  = vis / n_sem if n_sem else 0
        pend = filt["cart"][filt["cart"]["Vendedor"] == a]["Importe pendiente firmado"].sum()
        cl   = filt["cot"][filt["cot"]["Vendedor"] == a]
        clo  = cl[cl["Etapa"].isin(CLOSED_STAGES)]
        gan  = (clo["Etapa"] == "Ganado Terminado").sum()
        cer  = len(clo)
        tasa = gan / cer * 100 if cer else 0
        s    = SHORT.get(a, a)
        if pct < 30:
            alertas.append({"Asesor":s,"Tipo":"🔴 Facturación crítica",
                            "Detalle":f"{pct:.0f}% de meta ({fmt_m(ft)}/{fmt_m(meta)})"})
        elif pct < 70:
            alertas.append({"Asesor":s,"Tipo":"🟡 Facturación baja",
                            "Detalle":f"{pct:.0f}% de meta — debe acelerar cierres"})
        if avg == 0:
            alertas.append({"Asesor":s,"Tipo":"🔴 Sin visitas",
                            "Detalle":"Ninguna visita en el periodo"})
        elif avg < 3:
            alertas.append({"Asesor":s,"Tipo":"🟡 Visitas bajas",
                            "Detalle":f"{avg:.1f}/sem — meta mín. 3/sem"})
        if pend > 20_000_000:
            alertas.append({"Asesor":s,"Tipo":"🟡 Cartera alta",
                            "Detalle":f"{fmt_m(pend)} pendiente de recaudo"})
        if tasa < 50 and cer > 0:
            alertas.append({"Asesor":s,"Tipo":"🟡 Conversión baja",
                            "Detalle":f"Tasa histórica {tasa:.0f}% (meta ≥ 50%)"})
    return pd.DataFrame(alertas) if alertas else pd.DataFrame(
        columns=["Asesor","Tipo","Detalle"])

# ── APP ───────────────────────────────────────────────────────────────────
def main():
    st.set_page_config(page_title="Dashboard Comercial — TYL",
                       page_icon="📊", layout="wide")
    st.markdown("""
    <style>
    .block-container{padding-top:1.5rem;padding-bottom:1rem}
    div[data-testid="metric-container"]{background:#f8f8f6;border-radius:8px;padding:10px 14px}
    .notice-box{background:#EFF6FF;border-left:3px solid #378ADD;border-radius:0 6px 6px 0;
                padding:8px 12px;font-size:0.82rem;color:#185FA5;margin-bottom:0.8rem}
    </style>""", unsafe_allow_html=True)

    # Registra esta apertura del dashboard (una vez por sesión de navegador).
    log_visitas = registrar_visita()

    try:
        mod_times = {k: os.path.getmtime(v) if os.path.exists(v) else 0 for k, v in FILES.items()}
        data = load_data(FILES, _mod_times=json.dumps(mod_times))
    except FileNotFoundError as e:
        st.error(f"⚠️ Archivo no encontrado: `{e.filename}`\n\n"
                 "Verifica que los 4 archivos Excel estén en la misma carpeta que el script.")
        st.stop()

    # Meses reales presentes en los datos (facturacion + visitas) -- el
    # selector se arma solo con esto, asi que al subir un archivo con un
    # mes nuevo aparece automaticamente sin tocar codigo.
    periodos = meses_disponibles(data)
    if not periodos:
        st.error("⚠️ No se encontraron fechas válidas en facturación/visitas.")
        st.stop()

    if data.get("sin_fecha_n", 0) > 0:
        st.warning(
            f"⚠️ {data['sin_fecha_n']} factura(s) llegaron sin 'Fecha de la "
            f"factura' en el Excel (total {fmt_m(data['sin_fecha_valor'])}). "
            "No se pueden ubicar en ningún mes/semana/trimestre, así que no "
            "aparecen en Mensual, Trimestral ni en la gráfica Histórica -- "
            "revisa esas facturas en Odoo si el monto es significativo.")

    global METAS
    # Sidebar
    with st.sidebar:
        # Boton para forzar recarga de datos
        if st.button("🔄 Recargar datos", help="Limpia el caché y lee los archivos más recientes de GitHub"):
            st.cache_data.clear()
            st.rerun()

        st.header("🔍 Filtros")
        vista = st.radio("Vista", ["Mensual", "Trimestral", "Histórico"],
                         horizontal=True,
                         help="Mensual: detalle semana a semana de un mes. "
                              "Trimestral: compara los meses de un trimestre. "
                              "Histórico: evolución de todos los meses cargados.")

        sel_asesor = st.selectbox(
            "Asesor", ["Todos"] + ASESORES,
            format_func=lambda x: "Todos los asesores" if x=="Todos" else SHORT.get(x, x))
        asesores_sel = ASESORES if sel_asesor == "Todos" else [sel_asesor]

        sel_periodo = sel_semanas = data_mes = None
        meses_incluidos = periodo_label = None

        if vista == "Mensual":
            sel_periodo = st.selectbox(
                "Mes", periodos, index=len(periodos) - 1,
                format_func=lambda p: f"{MESES_ES_FULL[p.month]} {p.year}")

            periodo_label = f"{MESES_ES_FULL[sel_periodo.month]} {sel_periodo.year}"
            METAS, metas_exactas = metas_para_mes(sel_periodo.year, sel_periodo.month)

            data_mes = filter_por_mes(data, sel_periodo)

            # Semanas reales del mes seleccionado -- asi ninguna semana queda
            # invisible en el filtro, y la meta se prorratea por dias reales
            # del mes, no por nro de semanas.
            global SEMANA_LABELS, SEMANA_DIAS, TOTAL_DIAS_MES
            SEMANA_LABELS, SEMANA_DIAS, TOTAL_DIAS_MES = build_semana_info(
                pd.concat([data_mes["fact"]["Fecha de la factura"], data_mes["vis"]["Iniciar"]])
            )

            st.caption(f"Facturación, cartera y visitas: {periodo_label}.")
            semana_opts = list(SEMANA_LABELS.items())
            sel_semanas = st.multiselect(
                f"Semanas ({periodo_label})",
                options=[w for w,_ in semana_opts],
                default=[w for w,_ in semana_opts],
                format_func=lambda w: SEMANA_LABELS[w])
            if not sel_semanas:
                st.warning("Selecciona al menos una semana.")
                sel_semanas = [w for w,_ in semana_opts]

        elif vista == "Trimestral":
            trims = trimestres_disponibles(periodos)
            sel_trim = st.selectbox(
                "Trimestre", trims, index=len(trims) - 1,
                format_func=lambda t: f"T{t[1]} {t[0]}")
            meses_incluidos = meses_del_trimestre(periodos, sel_trim[0], sel_trim[1])
            periodo_label = f"T{sel_trim[1]} {sel_trim[0]}"
            meses_txt = ", ".join(f"{MESES_ES_FULL[p.month]}" for p in meses_incluidos)
            st.caption(f"Meses con datos en este trimestre: {meses_txt}.")

        else:  # Histórico
            meses_incluidos = periodos
            periodo_label = (f"{MESES_ES_FULL[periodos[0].month]} {periodos[0].year} "
                             f"– {MESES_ES_FULL[periodos[-1].month]} {periodos[-1].year}")
            st.caption(f"Todos los meses cargados: {len(periodos)}.")

        st.divider()
        st.caption("Tasa de conversión: histórico acumulado (ciclo de venta supera un mes).")

        # Indicador de uso del dashboard -- "¿han entrado a verlo?"
        st.divider()
        st.subheader("👀 Uso del dashboard")
        accesos = log_visitas.get("accesos", [])
        hoy = _dt.date.today().isoformat()
        vistas_hoy = sum(1 for x in accesos if x.startswith(hoy))
        st.metric("Aperturas totales registradas", log_visitas.get("total", 0),
                  f"Hoy: {vistas_hoy}")
        if accesos:
            st.caption(f"Último acceso: {accesos[-1]}")
        with st.expander("Ver últimos accesos"):
            for a in reversed(accesos[-10:]):
                st.caption(a)
        st.caption("Se cuenta una vez por sesión de navegador abierta. Si el "
                   "dashboard se redespliega o pasa mucho tiempo sin uso, el "
                   "contador puede reiniciarse.")

    col_h1, col_h2 = st.columns([3,1])
    with col_h1:
        st.title("📊 Dashboard Comercial — TYL Herramientas y Seguridad SAS")
        fecha_ref = data_mes["fact"]["Fecha de la factura"] if vista == "Mensual" \
                    else data["fact"]["Fecha de la factura"]
        fecha_max = fecha_ref.max()
        fecha_str = fecha_max.strftime("%-d de %B de %Y") if pd.notna(fecha_max) else "N/D"
        st.caption(f"Corte: {fecha_str}  |  Fuente: Odoo CRM  |  Facturación: valor sin IVA")
    with col_h2:
        st.markdown("<br>", unsafe_allow_html=True)
        st.info(periodo_label)

    if vista == "Mensual" and not metas_exactas:
        st.warning(f"⚠️ Aún no se han cargado las metas de {periodo_label} en el código. "
                   "Se están usando temporalmente las metas del mes definido más "
                   "reciente — pide que se agreguen las metas oficiales de este mes "
                   "en `METAS_POR_MES`.")

    # ── VISTA MENSUAL (comportamiento original, semana a semana) ──────────
    if vista == "Mensual":
        filt = apply_filters(data_mes, asesores_sel, sel_semanas)
        kpi  = calc_kpis(filt, asesores_sel, sel_semanas)

        st.markdown(
            f'<div class="notice-box">ℹ️ <b>Facturación, cartera y visitas:</b> {periodo_label} '
            '(valor sin IVA; cartera = saldo pendiente vigente). &nbsp;|&nbsp; '
            '<b>Tasa de conversión:</b> histórico acumulado en Odoo.</div>',
            unsafe_allow_html=True)

        k1,k2,k3,k4,k5 = st.columns(5)
        k1.metric(f"Facturación {MESES_ES_FULL[sel_periodo.month].lower()}", fmt_m(kpi["tot_fact"]),
                  f"Meta: {fmt_m(kpi['tot_meta'])}")
        k2.metric("Cumplimiento meta", f"{kpi['pct_meta']:.1f}%",
                  "✓ Alcanzada" if kpi["pct_meta"]>=100
                  else ("En progreso" if kpi["pct_meta"]>=70 else "⚠ Por debajo"),
                  delta_color="normal" if kpi["pct_meta"]>=70 else "inverse")
        k3.metric("Cartera pendiente", fmt_m(kpi["tot_pend"]),
                  "Por recaudar", delta_color="inverse")
        k4.metric(f"Visitas {MESES_ES_FULL[sel_periodo.month].lower()}", str(kpi["tot_vis"]),
                  f"Prom: {kpi['avg_vis']:.1f}/sem  |  Meta: 3/sem",
                  delta_color="normal" if kpi["avg_vis"]>=3 else "inverse")
        k5.metric("Conversión histórica", f"{kpi['tasa']:.1f}%",
                  f"Ganadas: {kpi['ganadas']}  |  En proceso: {kpi['activas']}",
                  delta_color="normal" if kpi["tasa"]>=50 else "inverse")

        st.divider()

        c1, c2 = st.columns(2)
        with c1:
            st.subheader(f"📊 Facturación vs. meta — {periodo_label}")
            st.plotly_chart(chart_fact_vs_meta(filt["fact"], asesores_sel, sel_semanas),
                            use_container_width=True, config={"displayModeBar":False})
        with c2:
            st.subheader(f"📈 Tendencia semanal — {periodo_label}")
            st.plotly_chart(chart_tendencia(filt["fact"], asesores_sel, sel_semanas),
                            use_container_width=True, config={"displayModeBar":False})

        c3, c4 = st.columns([3,2])
        with c3:
            st.subheader("💼 Cartera pendiente (saldo actual)")
            fig_cart = chart_cartera(filt["cart"], asesores_sel)
            if fig_cart:
                st.plotly_chart(fig_cart, use_container_width=True,
                                config={"displayModeBar":False})
            else:
                st.success("Sin cartera pendiente para el filtro seleccionado.")
        with c4:
            st.subheader(f"🗺️ Visitas — {periodo_label}")
            df_vis = tabla_visitas(filt["vis"], asesores_sel, sel_semanas)
            st.dataframe(df_vis, use_container_width=True, hide_index=True)
            st.caption("Meta: mínimo 3 visitas por semana por asesor.")

        st.divider()

        c5, c6 = st.columns([3,2])
        with c5:
            st.subheader("🔀 Embudo de conversión — histórico acumulado")
            st.caption("Ciclos de venta superiores a un mes — se usa todo el histórico de Odoo.")
            st.plotly_chart(chart_conversion(filt["cot"], asesores_sel),
                            use_container_width=True, config={"displayModeBar":False})
        with c6:
            st.subheader("⚠️ Alertas de gestión")
            df_al = tabla_alertas(filt, asesores_sel, sel_semanas)
            if df_al.empty:
                st.success("✅ Sin alertas para el filtro seleccionado.")
            else:
                st.dataframe(df_al, use_container_width=True, hide_index=True)

    # ── VISTA TRIMESTRAL / HISTÓRICO (comparativo entre meses) ────────────
    else:
        if vista == "Trimestral":
            base = filter_por_trimestre(data, meses_incluidos)
        else:
            # Histórico usa todos los meses disponibles -- se excluyen las
            # facturas/visitas sin fecha (no pertenecen a ningún mes real),
            # asi el KPI total coincide con la suma de las barras por mes.
            base = filter_por_trimestre(data, periodos)
        filt = filter_por_asesor(base, asesores_sel)
        kpi  = calc_kpis_periodo(filt, asesores_sel, meses_incluidos)

        etiqueta_vista = "Trimestral" if vista == "Trimestral" else "Histórico"
        st.markdown(
            f'<div class="notice-box">ℹ️ <b>Vista {etiqueta_vista}:</b> {periodo_label} '
            '(valor sin IVA; cartera = saldo pendiente vigente, no varía por periodo). '
            '&nbsp;|&nbsp; <b>Tasa de conversión:</b> histórico acumulado en Odoo.</div>',
            unsafe_allow_html=True)

        n_meses = len(meses_incluidos) if meses_incluidos else 1
        k1,k2,k3,k4,k5 = st.columns(5)
        k1.metric(f"Facturación — {periodo_label}", fmt_m(kpi["tot_fact"]),
                  f"Meta: {fmt_m(kpi['tot_meta'])}")
        k2.metric("Cumplimiento meta", f"{kpi['pct_meta']:.1f}%",
                  "✓ Alcanzada" if kpi["pct_meta"]>=100
                  else ("En progreso" if kpi["pct_meta"]>=70 else "⚠ Por debajo"),
                  delta_color="normal" if kpi["pct_meta"]>=70 else "inverse")
        k3.metric("Cartera pendiente", fmt_m(kpi["tot_pend"]),
                  "Por recaudar", delta_color="inverse")
        k4.metric("Visitas totales", str(kpi["tot_vis"]),
                  f"Prom: {kpi['avg_vis_mes']:.1f}/mes  |  {n_meses} mes(es)")
        k5.metric("Conversión histórica", f"{kpi['tasa']:.1f}%",
                  f"Ganadas: {kpi['ganadas']}  |  En proceso: {kpi['activas']}",
                  delta_color="normal" if kpi["tasa"]>=50 else "inverse")

        st.divider()

        if vista == "Trimestral":
            c1, c2 = st.columns(2)
            with c1:
                st.subheader(f"📊 Facturación por mes — {periodo_label}")
                st.plotly_chart(chart_por_mes(filt["fact"], asesores_sel, meses_incluidos),
                                use_container_width=True, config={"displayModeBar":False})
            with c2:
                st.subheader(f"🗺️ Visitas por mes — {periodo_label}")
                st.plotly_chart(chart_visitas_por_mes(filt["vis"], asesores_sel, meses_incluidos),
                                use_container_width=True, config={"displayModeBar":False})
        else:
            st.subheader("📈 Evolución histórica — facturación vs. meta y visitas")
            st.caption("Se actualiza automáticamente a medida que se carguen más meses "
                       "en los archivos de facturación y visitas.")
            st.plotly_chart(chart_historico(data, asesores_sel, periodos),
                            use_container_width=True, config={"displayModeBar":False})

        c3, c4 = st.columns([3,2])
        with c3:
            st.subheader("💼 Cartera pendiente (saldo actual)")
            fig_cart = chart_cartera(filt["cart"], asesores_sel)
            if fig_cart:
                st.plotly_chart(fig_cart, use_container_width=True,
                                config={"displayModeBar":False})
            else:
                st.success("Sin cartera pendiente para el filtro seleccionado.")
        with c4:
            st.subheader(f"📋 Resumen por asesor — {periodo_label}")
            df_res = tabla_resumen_periodo(filt, asesores_sel, meses_incluidos)
            st.dataframe(df_res, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("🔀 Embudo de conversión — histórico acumulado")
        st.caption("Ciclos de venta superiores a un mes — se usa todo el histórico de Odoo.")
        st.plotly_chart(chart_conversion(filt["cot"], asesores_sel),
                        use_container_width=True, config={"displayModeBar":False})

    st.divider()
    st.caption("TYL Herramientas y Seguridad SAS  |  Streamlit + Pandas + Plotly  |  Odoo CRM")

if __name__ == "__main__":
    main()
