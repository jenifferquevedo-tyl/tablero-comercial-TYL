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
    df_f["semana"]   = df_f["Fecha de la factura"].dt.isocalendar().week.astype(int)
    df_f["anio_mes"] = df_f["Fecha de la factura"].dt.to_period("M")
    df_f["Total"]    = df_f["Importe sin impuestos en la moneda firmada"]

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

    return {"fact": df_f, "cart": df_c, "vis": df_v, "cot": df_cot}


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

    global METAS
    # Sidebar
    with st.sidebar:
        # Boton para forzar recarga de datos
        if st.button("🔄 Recargar datos", help="Limpia el caché y lee los archivos más recientes de GitHub"):
            st.cache_data.clear()
            st.rerun()

        st.header("🔍 Filtros")
        sel_periodo = st.selectbox(
            "Mes", periodos, index=len(periodos) - 1,
            format_func=lambda p: f"{MESES_ES_FULL[p.month]} {p.year}")

        mes_label = f"{MESES_ES_FULL[sel_periodo.month]} {sel_periodo.year}"
        METAS, metas_exactas = metas_para_mes(sel_periodo.year, sel_periodo.month)

        data_mes = filter_por_mes(data, sel_periodo)

        # Semanas reales del mes seleccionado -- asi ninguna semana queda
        # invisible en el filtro, y la meta se prorratea por dias reales
        # del mes, no por nro de semanas.
        global SEMANA_LABELS, SEMANA_DIAS, TOTAL_DIAS_MES
        SEMANA_LABELS, SEMANA_DIAS, TOTAL_DIAS_MES = build_semana_info(
            pd.concat([data_mes["fact"]["Fecha de la factura"], data_mes["vis"]["Iniciar"]])
        )

        st.caption(f"Facturación, cartera y visitas: {mes_label}.")
        sel_asesor = st.selectbox(
            "Asesor", ["Todos"] + ASESORES,
            format_func=lambda x: "Todos los asesores" if x=="Todos" else SHORT.get(x, x))
        semana_opts = list(SEMANA_LABELS.items())
        sel_semanas = st.multiselect(
            f"Semanas ({mes_label})",
            options=[w for w,_ in semana_opts],
            default=[w for w,_ in semana_opts],
            format_func=lambda w: SEMANA_LABELS[w])
        if not sel_semanas:
            st.warning("Selecciona al menos una semana.")
            sel_semanas = [w for w,_ in semana_opts]
        st.divider()
        st.caption("Tasa de conversión: histórico acumulado (ciclo de venta supera un mes).")

    col_h1, col_h2 = st.columns([3,1])
    with col_h1:
        st.title("📊 Dashboard Comercial — TYL Herramientas y Seguridad SAS")
        fecha_max = data_mes["fact"]["Fecha de la factura"].max()
        fecha_str = fecha_max.strftime("%-d de %B de %Y") if pd.notna(fecha_max) else "N/D"
        st.caption(f"Corte: {fecha_str}  |  Fuente: Odoo CRM  |  Facturación: valor sin IVA")
    with col_h2:
        st.markdown("<br>", unsafe_allow_html=True)
        st.info(mes_label)

    if not metas_exactas:
        st.warning(f"⚠️ Aún no se han cargado las metas de {mes_label} en el código. "
                   "Se están usando temporalmente las metas del mes definido más "
                   "reciente — pide que se agreguen las metas oficiales de este mes "
                   "en `METAS_POR_MES`.")

    asesores_sel = ASESORES if sel_asesor == "Todos" else [sel_asesor]
    filt = apply_filters(data_mes, asesores_sel, sel_semanas)
    kpi  = calc_kpis(filt, asesores_sel, sel_semanas)

    st.markdown(
        f'<div class="notice-box">ℹ️ <b>Facturación, cartera y visitas:</b> {mes_label} '
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
        st.subheader(f"📊 Facturación vs. meta — {mes_label}")
        st.plotly_chart(chart_fact_vs_meta(filt["fact"], asesores_sel, sel_semanas),
                        use_container_width=True, config={"displayModeBar":False})
    with c2:
        st.subheader(f"📈 Tendencia semanal — {mes_label}")
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
        st.subheader(f"🗺️ Visitas — {mes_label}")
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

    st.divider()
    st.caption("TYL Herramientas y Seguridad SAS  |  Streamlit + Pandas + Plotly  |  Odoo CRM")

if __name__ == "__main__":
    main()
