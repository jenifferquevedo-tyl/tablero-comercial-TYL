import streamlit as st
import pandas as pd
import datetime

# Lista oficial de asesores de TYL Herramientas y Seguridad SAS
ASESORES = [
    "Diana Rossmary Ramirez Riaño",
    "Ingrid Yurley Churio Patiño",
    "Jeisson Ivan Chitiva Vallejo",
    "Luis Gabriel Acosta Ciro",
    "Néstor Arnoldo Useche Triana",
    "Adriana Carolina Cuevas"
]

# Definición de archivos directamente desde la raíz de GitHub
FILES = {
    "fact": "FACTURACION JUNIO 23 2026 (account.move).xlsx",
    "cart": "CARTERA (account.move).xlsx",
    "vis": "VISITAS JUNIO(calendar.event).xlsx",
    "cot": "Cotizaciones crm (crm.lead)-2.xlsx"
}

@st.cache_data
def load_data(files: dict) -> dict:
    # Facturacion
    df_f = pd.read_excel(files["fact"])
    df_f.columns = df_f.columns.str.strip()
    df_f["semana"] = df_f["Iniciar"].dt.isocalendar().week.astype(int)

    # Cartera
    df_c = pd.read_excel(files["cart"])
    df_c.columns = df_c.columns.str.strip()

    # Visitas
    try:
        df_v = pd.read_excel(files["vis"])
        df_v.columns = df_v.columns.str.strip()
        df_v["semana"] = df_v["Iniciar"].dt.isocalendar().week.astype(int)
    except Exception:
        df_v = pd.DataFrame(columns=["Iniciar", "Asistentes", "semana"])

    # Cotizaciones
    df_cot = pd.read_excel(files["cot"])
    df_cot.columns = df_cot.columns.str.strip()
    
    # Forzar a que la columna se llame 'Vendedor' si viene en minúsculas en el Excel
    df_cot = df_cot.rename(columns={"vendedor": "Vendedor"})
    
    if "Vendedor" in df_cot.columns:
        df_cot = df_cot[df_cot["Vendedor"].isin(ASESORES)].copy()

    return {"fact": df_f, "cart": df_c, "vis": df_v, "cot": df_cot}

def apply_filters(data: dict, asesores_sel: list, semanas_sel: list) -> dict:
    fact = data["fact"][
        data["fact"]["Vendedor"].isin(asesores_sel) &
        data["fact"]["semana"].isin(semanas_sel)
    ]
    
    cart = data["cart"][data["cart"]["Vendedor"].isin(asesores_sel)]
    
    if not data["vis"].empty:
        vis = data["vis"][
            data["vis"]["Vendedor"].isin(asesores_sel) &
            data["vis"]["semana"].isin(semanas_sel)
        ]
    else:
        vis = data["vis"]
        
    if not data["cot"].empty:
        df_cot_temp = data["cot"].rename(columns={"vendedor": "Vendedor"})
        vis_cot = df_cot_temp[df_cot_temp["Vendedor"].isin(asesores_sel)]
    else:
        vis_cot = data["cot"]
        
    return {"fact": fact, "cart": cart, "vis": vis, "cot": vis_cot}

