import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf
import plotly.graph_objects as go
import matplotlib.pyplot as plt
from fpdf import FPDF
import os

# Configuración de página
st.set_page_config(page_title="Simulador ESCO EMCALI", layout="wide")

# Función para formatear moneda
def fmt_cop(valor):
    return f"${valor:,.0f}".replace(",", ".")

st.title("Simulador Dinámico de Factibilidad: Modelo ESCO")
st.markdown("Evaluación financiera interactiva para la vinculación de capital privado.")

# --- 1. PANEL LATERAL ---
st.sidebar.header("1. Cargar Matriz Financiera")
uploaded_file = st.sidebar.file_uploader("Sube el archivo Excel de EMCALI", type=["xlsx"])

st.sidebar.header("2. Variables de Iteración")
split_ahorros = st.sidebar.slider("% Ahorro Cedido al Privado", min_value=10, max_value=100, value=100, step=5) / 100.0
anos_contrato = st.sidebar.slider("Horizonte del Contrato (Años)", min_value=5, max_value=20, value=15, step=1)
wacc = st.sidebar.number_input("Costo de Capital Privado (WACC %)", min_value=5.0, max_value=25.0, value=12.0, step=0.5) / 100.0

# --- FUNCIONES DE APOYO (GENERADOR PDF CON GRÁFICA) ---
def generar_pdf(vpn, tir, payback, capex_total, split, anos, wacc, flujo_inversionista, flujo_acumulado):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_left_margin(15)
    pdf.set_right_margin(15)
    
    # Encabezado
    pdf.set_font("Arial", 'B', 15)
    pdf.cell(0, 8, txt="INFORME EJECUTIVO DE FACTIBILIDAD FINANCIERA", ln=True, align='C')
    pdf.ln(5)
    
    # Proyecto
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(30, 6, txt="Proyecto:", ln=False)
    pdf.set_font("Arial", '', 11)
    pdf.multi_cell(0, 6, txt="Mejoramiento de los Sistemas Electromecanicos de las Unidades Operacionales Conectadas al Anillo 34,5KV y Planta Rio Cali Fase I")
    
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(45, 6, txt="Metodologia Evaluada:", ln=False)
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 6, txt=f"Modelo ESCO (Energy Service Company) - {split*100:.0f}% Ahorros", ln=True)
    pdf.ln(5)
    
    # 1. Contexto
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, txt="1. Contexto y Metodologia Aplicada", ln=True)
    pdf.set_font("Arial", '', 11)
    
    texto_ctx1 = "El presente modelo evalua la viabilidad de modernizar los sistemas electromecanicos de las plantas de EMCALI bajo un esquema ESCO. En este escenario, EMCALI no compromete recursos de capital (CAPEX) en la etapa constructiva ni afecta la tarifa del usuario final (ingresos POIR excluidos)."
    pdf.multi_cell(0, 6, txt=texto_ctx1)
    pdf.ln(2)
    
    texto_ctx2 = f"En su lugar, un inversionista privado asume el 100% de la inversion requerida, que asciende a {fmt_cop(capex_total)} COP (distribuidos durante los anos 0 al 3). El repago de esta inversion se estructura pignorando exclusivamente el {split*100:.0f}% de los ahorros energeticos y operativos comprobados que generaran los nuevos equipos, durante un horizonte contractual de {anos} anos."
    pdf.multi_cell(0, 6, txt=texto_ctx2)
    pdf.ln(5)

    # 2. Resultados
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, txt="2. Resultados de la Simulacion Financiera", ln=True)
    pdf.set_font("Arial", '', 11)
    pdf.multi_cell(0, 6, txt="Basado en las cifras extraidas del presupuesto y flujo de caja base, el proyecto bajo modelo ESCO presenta los siguientes indicadores desde la perspectiva del inversionista privado:")
    pdf.ln(2)

    tir_text = f"{tir:.2f}%" if not np.isnan(tir) else "No calculable"
    payback_text = f"Ano {payback}" if isinstance(payback, int) else "N/A"

    # Bullets
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(10, 6, txt="-", align='R')
    pdf.cell(70, 6, txt="Tasa de Descuento Aplicada (WACC):", ln=False)
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 6, txt=f"{wacc*100:.1f}%", ln=True)

    pdf.set_font("Arial", 'B', 11)
    pdf.cell(10, 6, txt="-", align='R')
    pdf.cell(70, 6, txt="Tasa Interna de Retorno (TIR):", ln=False)
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 6, txt=f"{tir_text}", ln=True)

    pdf.set_font("Arial", 'B', 11)
    pdf.cell(10, 6, txt="-", align='R')
    pdf.cell(70, 6, txt="Valor Presente Neto (VPN):", ln=False)
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 6, txt=f"{fmt_cop(vpn)} COP", ln=True)

    pdf.set_font("Arial", 'B', 11)
    pdf.cell(10, 6, txt="-", align='R')
    pdf.cell(70, 6, txt="Periodo de Recuperacion (Payback):", ln=False)
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 6, txt=f"{payback_text}", ln=True)
    pdf.ln(5)

    # 3. Comportamiento y Gráfica
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, txt="3. Comportamiento del Flujo de Caja", ln=True)
    pdf.set_font("Arial", '', 11)
    texto_graf = f"La siguiente grafica ilustra la evolucion financiera del contrato. Las barras representan los desembolsos e ingresos netos anuales. La curva (Flujo Acumulado) demuestra como el proyecto permanece en deficit hasta el {payback_text}, momento en el cual los ahorros logran superar la inversion inicial."
    pdf.multi_cell(0, 6, txt=texto_graf)
    
    # Generar imagen de la gráfica temporalmente con Matplotlib
    plt.figure(figsize=(8, 4))
    x_vals = np.arange(anos)
    colores_plt = ['#ef4444' if val < 0 else '#22c55e' for val in flujo_inversionista]
    plt.bar(x_vals, flujo_inversionista, color=colores_plt, alpha=0.8, label='Flujo Anual')
    plt.plot(x_vals, flujo_acumulado, color='#3b82f6', marker='o', linewidth=2, label='Acumulado')
    plt.axhline(0, color='black', linewidth=1)
    plt.title('Proyeccion de Rentabilidad ESCO')
    plt.xlabel('Anos')
    plt.ylabel('Flujo (COP)')
    plt.grid(axis='y', linestyle='--', alpha=0.5)
    plt.tight_layout()
    chart_path = "temp_chart_pdf.png"
    plt.savefig(chart_path)
    plt.close()

    # Insertar gráfica
    pdf.image(chart_path, x=20, w=170)
    if os.path.exists(chart_path):
        os.remove(chart_path)
    
    pdf.ln(5)

    # 4. Conclusión Estratégica
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, txt="4. Conclusion Estrategica", ln=True)
    
    if vpn > 0:
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(0, 6, txt="VIABLE.", ln=True)
        pdf.set_font("Arial", '', 11)
        texto_concl1 = f"Bajo las condiciones iteradas ({anos} anos cediendo el {split*100:.0f}% del ahorro), el proyecto es financieramente atractivo para el sector privado. El flujo de ahorros es robusto y suficiente para cubrir la inversion inicial de mas de 118 mil millones, absorber el costo de capital del {wacc*100:.1f}%, y generar un excedente (VPN) superior a {fmt_cop(vpn)} COP."
        pdf.multi_cell(0, 6, txt=texto_concl1)
        pdf.ln(2)
        texto_concl2 = f"Al recuperar la inversion en el {payback_text}, existe margen para que EMCALI y el DNP negocien una reduccion en el porcentaje de ahorro cedido (ej. 80% / 20%), garantizando que la entidad publica reciba flujo de caja libre desde el primer ano del contrato, sin destruir la viabilidad para el inversionista."
        pdf.multi_cell(0, 6, txt=texto_concl2)
    else:
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(0, 6, txt="NO VIABLE.", ln=True)
        pdf.set_font("Arial", '', 11)
        texto_concl1 = f"Bajo las condiciones iteradas ({anos} anos cediendo el {split*100:.0f}% del ahorro), el proyecto destruye valor para el inversionista. Los flujos pignorados no alcanzan a compensar la inversion frente al costo de oportunidad del capital."
        pdf.multi_cell(0, 6, txt=texto_concl1)
        pdf.ln(2)
        pdf.multi_cell(0, 6, txt="Se requiere aumentar el porcentaje cedido o extender el horizonte del contrato.")

    # Retornar PDF
    pdf_out = pdf.output(dest='S')
    return pdf_out.encode('latin-1') if isinstance(pdf_out, str) else bytes(pdf_out)

# --- 2. MOTOR DE CÁLCULO FINANCIERO ---
if uploaded_file is not None:
    try:
        xls = pd.ExcelFile(uploaded_file)
        
        # Extracción
        df_flujo = pd.read_excel(xls, sheet_name='3.  FLUJO DE CAJA', header=None)
        capex_raw = df_flujo.iloc[29, 2:2+anos_contrato].fillna(0).values
        capex_base = [float(x) for x in capex_raw]
        
        df_ingresos = pd.read_excel(xls, sheet_name='2. INGRESOS-BENEFICIOS', header=None)
        ahorros_df = df_ingresos.iloc[16:23, 2:2+anos_contrato].apply(pd.to_numeric, errors='coerce').fillna(0)
        ahorros_base = ahorros_df.sum(axis=0).values

        # Construcción de Flujos
        flujo_inversionista = []
        flujo_acumulado = []

        for i in range(anos_contrato):
            inversion = -capex_base[i] if i < len(capex_base) else 0
            ingreso = ahorros_base[i] * split_ahorros if i < len(ahorros_base) else 0
            flujo_neto = inversion + ingreso
            flujo_inversionista.append(flujo_neto)
            
            if i == 0:
                flujo_acumulado.append(flujo_neto)
            else:
                flujo_acumulado.append(flujo_acumulado[-1] + flujo_neto)

        # Cálculos Financieros
        capex_total = sum(capex_base)
        vpn = npf.npv(wacc, flujo_inversionista)
        tir = npf.irr(flujo_inversionista) * 100

        # Lógica del Payback
        last_negative_idx = -1
        for i, val in enumerate(flujo_acumulado):
            if val < 0:
                last_negative_idx = i
                
        if last_negative_idx != -1 and last_negative_idx + 1 < len(flujo_acumulado):
            payback_year = last_negative_idx + 1
        elif last_negative_idx == -1 and flujo_acumulado[0] >= 0:
            payback_year = 0
        else:
            payback_year = "No recupera"

        tir_text = f"{tir:.2f}%" if not np.isnan(tir) else "No calculable"
        payback_text = f"Año {payback_year}" if isinstance(payback_year, int) else "N/A"

        # --- 3. INTERFAZ EN PANTALLA ---
        st.markdown("---")
        st.markdown("# 📑 INFORME EJECUTIVO DE FACTIBILIDAD FINANCIERA")
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("CAPEX Total", fmt_cop(capex_total))
        col2.metric("VPN", fmt_cop(vpn))
        col3.metric("TIR Privado", tir_text)
        col4.metric("Payback Real", payback_text)

        # Gráfica Interactiva
        st.markdown("### Comportamiento del Flujo de Caja")
        fig = go.Figure()
        colores = ['#ef4444' if val < 0 else '#22c55e' for val in flujo_inversionista]
        
        fig.add_trace(go.Bar(
            x=[f"Año {i}" for i in range(anos_contrato)], 
            y=flujo_inversionista, 
            name='Flujo Neto Anual', marker_color=colores
        ))
        
        fig.add_trace(go.Scatter(
            x=[f"Año {i}" for i in range(anos_contrato)], 
            y=flujo_acumulado, 
            name='Flujo Acumulado', mode='lines+markers', line=dict(color='#3b82f6', width=3)
        ))
        
        fig.update_layout(height=450, template="plotly_white", hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        # --- 4. DESCARGA DEL INFORME EN PDF ---
        pdf_bytes = generar_pdf(vpn, tir, payback_year, capex_total, split_ahorros, anos_contrato, wacc, flujo_inversionista, flujo_acumulado)
        
        st.download_button(
            label="📄 Descargar Informe Completo en PDF",
            data=pdf_bytes,
            file_name="Informe_Factibilidad_ESCO_EMCALI.pdf",
            mime="application/pdf",
            type="primary"
        )

    except Exception as e:
        st.error(f"Error procesando el archivo: {e}")
else:
    st.info("👈 Por favor, carga el archivo Excel en el panel lateral izquierdo para arrancar el simulador.")