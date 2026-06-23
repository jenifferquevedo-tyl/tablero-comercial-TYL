import os
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

# ──────────────────────────────────────────────────────────────
# CONFIGURACIÓN — ENLACES DIRECTOS A GOOGLE DRIVE (CLOUD)
# ──────────────────────────────────────────────────────────────
# Transformamos tus links para que descarguen directamente el Excel en la nube
FILES = {
    "fact": "https://docs.google.com/spreadsheets/d/1ITTER6WTj1jvBKUx4N91XeWOh7gF7m-COhpgvqBQKUs/export?format=xlsx",
    "cart": "https://docs.google.com/spreadsheets/d/1XxaICclW7-E76mZ7erHJ_7lXEtVsuT-S8JzO0cIec94/export?format=xlsx",
    "vis":  "https://docs.google.com/spreadsheets/d/1XxaICclW7-E76mZ7erHJ_7lXEtVsuT-S8JzO0cIec94/export?format=xlsx", # Reemplázalo si tienes el link de Visitas separado
    "cot":  "https://docs.google.com/spreadsheets/d/1F9h0Khhpv6FbZ-EFwvjDJOEOHHZY4Z0JTXuMG_t_9ak/export?format=xlsx",
}

# ──────────────────────────────────────────────────────────────
# CONSTANTES
# ──────────────────────────────────────────────────────────────
ASESORES = [
    "DIANA ROSSMARY RAMIREZ RIAÑO",
    "INGRID YURLEY CHURIO PATIÑO",
    "JEISSON IVAN CHITIVA VALLEJO",
    "LUIS GABRIEL ACOSTA CIRO",
    "NÉSTOR ARNOLDO USECHE TRIANA",
    "ADRIANA CAROLINA CUEVAS MONSALVE",
]

SHORT = {
    "DIANA ROSSMARY RAMIREZ RIAÑO":    "Diana R.",
    "INGRID YURLEY CHURIO PATIÑO":     "Ingrid C.",
    "JEISSON IVAN CHITIVA VALLEJO":    "Jeisson C.",
    "LUIS GABRIEL ACOSTA CIRO":        "Luis A.",
    "NÉSTOR ARNOLDO USECHE TRIANA":    "Néstor U.",
    "ADRIANA CAROLINA CUEVAS MONSALVE":"Adriana C.",
}

METAS = {
    "DIANA ROSSMARY RAMIREZ RIAÑO":    150_000_000,
    "INGRID YURLEY CHURIO PATIÑO":     150_000_000,
    "JEISSON IVAN CHITIVA VALLEJO":    150_000_000,
    "LUIS GABRIEL ACOSTA CIRO":        150_000_000,
    "NÉSTOR ARNOLDO USECHE TRIANA":     60_000_000,
    "ADRIANA CAROLINA CUEVAS MONSALVE": 50_000_000,
}

VALID_STATES   = ["Pagado", "Sin pagar", "Pagado parcialmente"]
CLOSED_STAGES  = ["Ganado Terminado", "PERDIDO POR PRECIO", "PERDIDO POR STOCK"]
ACTIVE_STAGES  = ["Nuevo", "Propuesta en revision", "En despacho"]
SEMANA_LABELS  = {23: "Sem 23 (2–8 jun)", 24: "Sem 24 (9–15 jun)",
                  25: "Sem 25 (16–22 jun)", 26: "Sem 26 (23 jun)"}

COLORS = ["#378ADD", "#1D9E75", "#7F77DD", "#D85A30", "#BA7517", "#D4537E"]
COLOR_MAP = {a: COLORS[i] for i, a in enumerate(ASESORES)}

# ──────────────────────────────────────────────────────────────
# CARGA Y TRANSFORMACIÓN DE DATOS (LECTURA DESDE URL)
# ──────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Cargando datos desde Google Drive…")
def load_data(files: dict) -> dict:
    # Facturación
    df_f = pd.read_excel(files["fact"])
    df_f = df_f[
        df_f["Vendedor"].isin(ASESORES) &
        df_f["Estado en pago"].isin(VALID_STATES)
    ].copy()
    df_f["Fecha de la factura"] = pd.to_datetime(df_f["Fecha de la factura"])
    df_f["semana"] = df_f["Fecha de la factura"].dt.isocalendar().week.astype(int)

    # Cartera
    df_c = pd.read_excel(files["cart"])
    df_c = df_c[df_c["Vendedor"].isin(ASESORES)].copy()

    # Visitas
    try:
        df_v = pd.read_excel(files["vis"])
        df_v = df_v[df_v["Iniciar"].notna() & df_v["Asistentes"].isin(ASESORES)].copy()
        df_v["Iniciar"] = pd.to_datetime(df_v["Iniciar"])
        df_v["semana"] = df_v["Iniciar"].dt.isocalendar().week.astype(int)
    except Exception:
        # En caso de usar el mismo archivo temporalmente para que no falle
        df_v = pd.DataFrame(columns=["Iniciar", "Asistentes", "semana"])

    # Cotizaciones
   df_cot = pd.read_excel(files["cot"])
    df_cot.columns = df_cot.columns.str.strip()
    
    if "Vendedor" in df_cot.columns:
        df_cot = df_cot[df_cot["Vendedor"].isin(ASESORES)].copy()
    else:
        df_cot.columns = df_cot.columns.str.lower()
        if "vendedor" in df_cot.columns:
            df_cot = df_cot[df_cot["vendedor"].isin(ASESORES)].copy()
    return {"fact": df_f, "cart": df_c, "vis": df_v, "cot": df_cot}


def apply_filters(data: dict, asesores_sel: list, semanas_sel: list) -> dict:
    fact = data["fact"][
        data["fact"]["Vendedor"].isin(asesores_sel) &
        data["fact"]["semana"].isin(semanas_sel)
    ]
    cart = data["cart"][data["cart"]["Vendedor"].isin(asesores_sel)]
    
    if not data["vis"].empty:
        vis = data["vis"][data["vis"]["Asistentes"].isin(asesores_sel) & data["vis"]["semana"].isin(semanas_sel)]
    else:
        vis = data["vis"]
        
    cot  = data["cot"][data["cot"]["Vendedor"].isin(asesores_sel)]
    return {"fact": fact, "cart": cart, "vis": vis, "cot": cot}


def calc_kpis(filt: dict, asesores_sel: list, semanas_sel: list) -> dict:
    tot_fact = filt["fact"]["Total"].sum()
    n_sem    = len(semanas_sel)
    tot_meta = sum(METAS[a] * (n_sem / 4) for a in asesores_sel)
    pct_meta = (tot_fact / tot_meta * 100) if tot_meta else 0

    tot_pend = filt["cart"]["Importe pendiente firmado"].sum()
    tot_vis  = len(filt["vis"])
    avg_vis  = tot_vis / (len(asesores_sel) * n_sem) if asesores_sel else 0

    closed = filt["cot"][filt["cot"]["Etapa"].isin(CLOSED_STAGES)]
    ganadas = (closed["Etapa"] == "Ganado Terminado").sum()
    perdidas = closed[closed["Etapa"] != "Ganado Terminado"].shape[0]
    activas  = filt["cot"][filt["cot"]["Etapa"].isin(ACTIVE_STAGES)].shape[0]
    tot_cerradas = ganadas + perdidas
    tasa_conv = (ganadas / tot_cerradas * 100) if tot_cerradas else 0

    return dict(
        tot_fact=tot_fact, tot_meta=tot_meta, pct_meta=pct_meta,
        tot_pend=tot_pend, tot_vis=tot_vis, avg_vis=avg_vis,
        ganadas=ganadas, perdidas=perdidas, activas=activas,
        tasa_conv=tasa_conv,
    )


def fmt_m(n: float) -> str:
    return f"${n/1_000_000:.1f}M"

def delta_color(val: float, threshold: float) -> str:
    return "normal" if val >= threshold else "inverse"


# ──────────────────────────────────────────────────────────────
# GRÁFICOS
# ──────────────────────────────────────────────────────────────
def chart_fact_vs_meta(fact_df, asesores_sel, semanas_sel):
    rows = []
    n_sem = len(semanas_sel)
    for a in asesores_sel:
        f = fact_df[fact_df["Vendedor"] == a]["Total"].sum()
        m = METAS[a] * (n_sem / 4)
        rows.append({"Asesor": SHORT[a], "Facturación": f, "Meta": m, "_color": COLOR_MAP[a]})
    df = pd.DataFrame(rows)

    fig = go.Figure()
    for _, row in df.iterrows():
        fig.add_bar(
            x=[row["Asesor"]], y=[row["Facturación"]],
            name=row["Asesor"],
            marker_color=row["_color"],
            opacity=0.85,
            showlegend=False,
        )
    fig.add_scatter(
        x=df["Asesor"], y=df["Meta"],
        mode="lines+markers",
        name="Meta",
        line=dict(color="#888780", width=2, dash="dot"),
        marker=dict(size=6, color="#888780"),
    )
    fig.update_layout(
        barmode="group", height=280, margin=dict(l=0, r=0, t=10, b=0),
        yaxis=dict(tickformat="$,.0f", gridcolor="#f0f0f0"),
        plot_bgcolor="white", paper_bgcolor="white",
    )
    return fig


def chart_tendencia_semanal(fact_df, asesores_sel, semanas_sel):
    fig = go.Figure()
    for a in asesores_sel:
        rows = []
        for w in sorted(semanas_sel):
            val = fact_df[(fact_df["Vendedor"] == a) & (fact_df["semana"] == w)]["Total"].sum()
            rows.append({"semana": SEMANA_LABELS.get(w, f"Sem {w}"), "Total": val})
        df = pd.DataFrame(rows)
        fig.add_scatter(
            x=df["semana"], y=df["Total"], mode="lines+markers", name=SHORT[a],
            line=dict(color=COLOR_MAP[a], width=2),
            marker=dict(size=6, color=COLOR_MAP[a], line=dict(color="white", width=1.5)),
        )
    fig.update_layout(
        height=280, margin=dict(l=0, r=0, t=10, b=0),
        yaxis=dict(tickformat="$,.0f", gridcolor="#f0f0f0"),
        plot_bgcolor="white", paper_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


def chart_cartera(cart_df, asesores_sel):
    rows = []
    for a in asesores_sel:
        pend = cart_df[cart_df["Vendedor"] == a]["Importe pendiente firmado"].sum()
        if pend > 0:
            rows.append({"Asesor": SHORT[a], "Pendiente": pend, "_color": COLOR_MAP[a]})
    if not rows:
        return None
    df = pd.DataFrame(rows).sort_values("Pendiente", ascending=True)
    fig = go.Figure(go.Bar(
        x=df["Pendiente"], y=df["Asesor"], orientation="h",
        marker_color=[COLOR_MAP[a_full] for a_full in asesores_sel if cart_df[cart_df["Vendedor"] == a_full]["Importe pendiente firmado"].sum() > 0],
        opacity=0.85,
    ))
    fig.update_layout(
        height=220, margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(tickformat="$,.0f", gridcolor="#f0f0f0"),
        plot_bgcolor="white", paper_bgcolor="white", showlegend=False,
    )
    return fig


def chart_conversion(cot_df, asesores_sel):
    rows = []
    for a in asesores_sel:
        sub = cot_df[cot_df["Vendedor"] == a]
        closed = sub[sub["Etapa"].isin(CLOSED_STAGES)]
        ganadas  = (closed["Etapa"] == "Ganado Terminado").sum()
        perdidas = (closed["Etapa"] != "Ganado Terminado").sum()
        activas  = sub[sub["Etapa"].isin(ACTIVE_STAGES)].shape[0]
        tot_cerradas = ganadas + perdidas
        tasa = ganadas / tot_cerradas * 100 if tot_cerradas else 0
        rows.append({
            "Asesor": SHORT[a], "Ganadas": ganadas,
            "Perdidas": perdidas, "En proceso": activas, "Tasa": tasa,
        })
    df = pd.DataFrame(rows)

    fig = go.Figure()
    fig.add_bar(name="Ganadas", x=df["Asesor"], y=df["Ganadas"], marker_color="#97C459")
    fig.add_bar(name="Perdidas", x=df["Asesor"], y=df["Perdidas"], marker_color="#F09595")
    fig.add_bar(name="En proceso", x=df["Asesor"], y=df["En proceso"], marker_color="#85B7EB")
    
    fig.add_scatter(
        x=df["Asesor"], y=df["Tasa"], mode="markers+text", name="Tasa %", yaxis="y2",
        marker=dict(size=9, color="#444441", symbol="diamond"),
        text=[f"{t:.0f}%" for t in df["Tasa"]], textposition="top center",
    )
    fig.update_layout(
        barmode="stack", height=310, margin=dict(l=0, r=40, t=10, b=0),
        yaxis=dict(title="Cotizaciones", gridcolor="#f0f0f0"),
        yaxis2=dict(title="Tasa de éxito %", overlaying="y", side="right", range=[0, 115], showgrid=False),
        plot_bgcolor="white", paper_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


def tabla_visitas(vis_df, asesores_sel, semanas_sel):
    if vis_df.empty:
        return pd.DataFrame(columns=["Asesor", "Visitas", "Prom/semana", "Estado"])
    n_sem = len(semanas_sel)
    rows = []
    for a in asesores_sel:
        total = vis_df[vis_df["Asistentes"] == a].shape[0]
        avg   = total / n_sem if n_sem else 0
        cumple = "✅ Cumple" if avg >= 3 else "🔴 Bajo"
        rows.append({"Asesor": SHORT[a], "Visitas": total, "Prom/semana": f"{avg:.1f}", "Estado": cumple})
    return pd.DataFrame(rows)


def tabla_alertas(filt, asesores_sel, semanas_sel):
    n_sem = len(semanas_sel)
    alertas = []
    for a in asesores_sel:
        fact_a   = filt["fact"][filt["fact"]["Vendedor"] == a]["Total"].sum()
        meta_a   = METAS[a] * (n_sem / 4)
        pct_a    = fact_a / meta_a * 100 if meta_a else 0
        vis_tot  = filt["vis"][filt["vis"]["Asistentes"] == a].shape[0] if not filt["vis"].empty else 0
        avg_vis  = vis_tot / n_sem if n_sem else 0
        pend_a   = filt["cart"][filt["cart"]["Vendedor"] == a]["Importe pendiente firmado"].sum()
        
        cot_a    = filt["cot"][filt["cot"]["Vendedor"] == a]
        closed_a = cot_a[cot_a["Etapa"].isin(CLOSED_STAGES)]
        ganadas  = (closed_a["Etapa"] == "Ganado Terminado").sum()
        cerradas = len(closed_a)
        tasa_a   = ganadas / cerradas * 100 if cerradas else 0

        if pct_a < 30:
            alertas.append({"Asesor": SHORT[a], "Tipo": "🔴 Facturación crítica", "Detalle": f"{pct_a:.0f}% de meta ({fmt_m(fact_a)} / {fmt_m(meta_a)})"})
        elif pct_a < 70:
            alertas.append({"Asesor": SHORT[a], "Tipo": "🟡 Facturación baja", "Detalle": f"{pct_a:.0f}% de meta — debe acelerar cierres"})

        if avg_vis == 0:
            alertas.append({"Asesor": SHORT[a], "Tipo": "🔴 Sin visitas", "Detalle": "Ninguna visita registrada"})
        elif avg_vis < 3:
            alertas.append({"Asesor": SHORT[a], "Tipo": "🟡 Visitas bajas", "Detalle": f"{avg_vis:.1f}/sem — meta mín. 3/sem"})

        if pend_a > 20_000_000:
            alertas.append({"Asesor": SHORT[a], "Tipo": "🟡 Cartera alta", "Detalle": f"{fmt_m(pend_a)} pendiente de recaudo"})

        if tasa_a < 50:
            alertas.append({"Asesor": SHORT[a], "Tipo": "🟡 Conversión baja", "Detalle": f"Tasa histórica {tasa_a:.0f}% (meta ≥ 50%)"})

    return pd.DataFrame(alertas) if alertas else pd.DataFrame(columns=["Asesor", "Tipo", "Detalle"])


# ──────────────────────────────────────────────────────────────
# APP PRINCIPAL
# ──────────────────────────────────────────────────────────────
def main():
    st.set_page_config(page_title="Dashboard Comercial — TYL", page_icon="📊", layout="wide")

    st.markdown("""
    <style>
        .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }
        h1  { font-size: 1.35rem !important; }
        h2  { font-size: 1.1rem  !important; }
        div[data-testid="metric-container"] { background:#f8f8f6; border-radius:8px; padding:10px 14px; }
        .notice-box { background:#EFF6FF; border-left:3px solid #378ADD; border-radius:0 6px 6px 0; padding:8px 12px; font-size:0.82rem; color:#185FA5; margin-bottom:0.8rem; }
    </style>
    """, unsafe_allow_html=True)

    col_h1, col_h2 = st.columns([3, 1])
    with col_h1:
        st.title("📊 Dashboard Comercial — TYL Herramientas y Seguridad SAS")
        st.caption("Corte: Junio 2026  |  Fuente: Odoo CRM  |  6 asesores con meta asignada")
    with col_h2:
        st.markdown("<br>", unsafe_allow_html=True)
        st.info("Junio 2026")

    data = load_data(FILES)

    with st.sidebar:
        st.header("🔍 Filtros")
        asesor_opt = ["Todos"] + ASESORES
        sel_asesor = st.selectbox("Asesor", asesor_opt, format_func=lambda x: "Todos los asesores" if x == "Todos" else SHORT.get(x, x))

        semana_opts = list(SEMANA_LABELS.items())
        sel_semanas = st.multiselect("Semanas (junio 2026)", options=[w for w, _ in semana_opts], default=[w for w, _ in semana_opts], format_func=lambda w: SEMANA_LABELS[w])
        if not sel_semanas:
            sel_semanas = [w for w, _ in semana_opts]

    asesores_sel = ASESORES if sel_asesor == "Todos" else [sel_asesor]
    filt = apply_filters(data, asesores_sel, sel_semanas)
    kpi  = calc_kpis(filt, asesores_sel, sel_semanas)

    st.markdown('<div class="notice-box">ℹ️ <b>Facturación, cartera y visitas:</b> Leyendo Drive en vivo. &nbsp;|&nbsp; <b>Tasa de conversión:</b> Histórico Odoo.</div>', unsafe_allow_html=True)

    # Métricas principales
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Facturación junio", fmt_m(kpi["tot_fact"]), f"Meta: {fmt_m(kpi['tot_meta'])}")
    k2.metric("Cumplimiento meta", f"{kpi['pct_meta']:.1f}%", "✓ Alcanzada" if kpi["pct_meta"] >= 100 else "En progreso", delta_color=delta_color(kpi["pct_meta"], 70))
    k3.metric("Cartera pendiente", fmt_m(kpi["tot_pend"]), "Por recaudar", delta_color="inverse")
    k4.metric("Visitas junio", str(kpi["tot_vis"]), f"Prom: {kpi['avg_vis']:.1f}/sem", delta_color=delta_color(kpi["avg_vis"], 3))
    k5.metric("Conversión histórica", f"{kpi['tasa_conv']:.1f}%", f"Ganadas: {kpi['ganadas']}", delta_color=delta_color(kpi["tasa_conv"], 50))

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📊 Facturación vs. meta")
        st.plotly_chart(chart_fact_vs_meta(filt["fact"], asesores_sel, sel_semanas), use_container_width=True)
    with col2:
        st.subheader("📈 Tendencia semanal")
        st.plotly_chart(chart_tendencia_semanal(filt["fact"], asesores_sel, sel_semanas), use_container_width=True)

    col3, col4 = st.columns([3, 2])
    with col3:
        st.subheader("💼 Cartera pendiente")
        fig_cart = chart_cartera(filt["cart"], asesores_sel)
        if fig_cart:
            st.plotly_chart(fig_cart, use_container_width=True)
        else:
            st.success("Sin cartera pendiente.")
    with col4:
        st.subheader("🗺️ Visitas")
        st.dataframe(tabla_visitas(filt["vis"], asesores_sel, sel_semanas), use_container_width=True, hide_index=True)

    st.divider()

    col5, col6 = st.columns([3, 2])
    with col5:
        st.subheader("🔀 Embudo de conversión")
        st.plotly_chart(chart_conversion(filt["cot"], asesores_sel), use_container_width=True)
    with col6:
        st.subheader("⚠️ Alertas de gestión")
        st.dataframe(tabla_alertas(filt, asesores_sel, sel_semanas), use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
