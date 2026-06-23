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
        vis = data["vis"][
            data["vis"]["Vendedor"].isin(asesores_sel) &
            data["vis"]["semana"].isin(semanas_sel)
        ]
    else:
        vis = data["vis"]
        
    if not data["cot"].empty:
        # Validación de columna segura en filtros de cotizaciones
        col_vendedor = "Vendedor" if "Vendedor" in data["cot"].columns else "vendedor"
        vis_cot = data["cot"][data["cot"][col_vendedor].isin(asesores_sel)]
    else:
        vis_cot = data["cot"]
        
    return {"fact": fact, "cart": cart, "vis": vis, "cot": vis_cot}
