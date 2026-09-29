import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf
import plotly.graph_objects as go
from fpdf import FPDF

# Configuración de página
st.set_page_config(page_title="Simulador ESCO EMCALI", layout="wide")

# Función para formatear moneda estilo Colombia (puntos para miles)
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

# --- FUNCIONES DE APOYO (GENERADOR PDF) ---
def generar_pdf(vpn, tir, payback, capex_total, split, anos, wacc, estado):
    pdf = FPDF()
    pdf.add_page()
    
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, txt="INFORME DE FACTIBILIDAD FINANCIERA", ln=True, align='C')
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, txt="Modelo ESCO - Modernizacion PTAP EMCALI", ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, txt="1. Metodologia Aplicada", ln=True)
    pdf.set_font("Arial", '', 11)
    texto_metodologia = (
        "El presente modelo evalua la viabilidad de modernizar los sistemas electromecanicos "
        "de las plantas Puerto Mallarino y Rio Cauca bajo un esquema ESCO. "
        "EMCALI no compromete recursos de capital (CAPEX) en la etapa constructiva "
        "ni afecta la tarifa del usuario final (POIR excluido). Un inversionista privado asume "
        f"el 100% de la inversion requerida, cuantificada en ${capex_total:,.0f} COP."
    )
    pdf.multi_cell(0, 6, txt=texto_metodologia)
    pdf.ln(5)
    
    texto_repago = (
        f"El repago del inversionista se estructura pignorando exclusivamente el {split*100:.0f}% de los "
        f"ahorros energeticos y operativos comprobados generados por los equipos, durante un horizonte "
        f"contractual de {anos} anos."
    )
    pdf.multi_cell(0, 6, txt=texto_repago)
    pdf.ln(10)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, txt="2. Resultados de la Simulacion Financiera", ln=True)
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 6, txt=f"- Tasa de Descuento (WACC): {wacc*100:.1f}%", ln=True)
    pdf.cell(0, 6, txt=f"- Valor Presente Neto (VPN): ${vpn:,.0f} COP", ln=True)
    tir_text = f"{tir:.2f}%" if not np.isnan(tir) else "No calculable"
    pdf.cell(0, 6, txt=f"- Tasa Interna de Retorno (TIR): {tir_text}", ln=True)
    pdf.cell(0, 6, txt=f"- Periodo de Recuperacion Real (Payback): Anio {payback}", ln=True)
    pdf.ln(10)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, txt="3. Conclusion Estrategica", ln=True)
    pdf.set_font("Arial", '', 11)
    
    if vpn > 0:
        texto_conclusion = (
            f"VIABLE. Las condiciones iteradas arrojan rentabilidad positiva para el inversionista. "
            f"El flujo de ahorros cedidos es suficiente para cubrir la inversion inicial, el costo de "
            f"capital del {wacc*100:.1f}%, y generar excedente. El punto de equilibrio se alcanza en el Anio {payback}."
        )
    else:
        texto_conclusion = (
            "NO VIABLE. Los flujos de ahorro cedidos no alcanzan a compensar las inyecciones "
            "de capital ni el costo de oportunidad del privado. Se requiere aumentar "
            "el porcentaje cedido o extender el horizonte del contrato para lograr viabilidad."
        )
    
    pdf.multi_cell(0, 6, txt=texto_conclusion)
    
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

        # Cálculos Financieros Oficiales
        capex_total = sum(capex_base)
        vpn = npf.npv(wacc, flujo_inversionista)
        tir = npf.irr(flujo_inversionista) * 100
        estado_proyecto = "VIABLE" if vpn > 0 else "NO VIABLE"

        # Lógica Corregida del Payback
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

        # --- 3. GENERACIÓN DEL INFORME EJECUTIVO EN PANTALLA ---
        st.markdown("---")
        st.markdown("# 📑 INFORME EJECUTIVO DE FACTIBILIDAD FINANCIERA")
        st.markdown("**Proyecto:** Mejoramiento de los Sistemas Electromecánicos de las Unidades Operacionales Conectadas al Anillo 34,5KV y Planta Río Cali Fase I")
        st.markdown(f"**Metodología Evaluada:** Modelo ESCO - {split_ahorros*100:.0f}% Ahorros")
        
        st.markdown("### 1. Contexto y Metodología Aplicada")
        st.markdown(f"""
        El presente modelo evalúa la viabilidad de modernizar los sistemas electromecánicos de las plantas de EMCALI bajo un esquema ESCO. En este escenario, **EMCALI no compromete recursos de capital (CAPEX) en la etapa constructiva ni afecta la tarifa del usuario final** (ingresos POIR excluidos). 

        En su lugar, un inversionista privado asume el **100% de la inversión requerida**, que asciende a **{fmt_cop(capex_total)} COP**. El repago de esta inversión se estructura pignorando exclusivamente el **{split_ahorros*100:.0f}% de los ahorros energéticos y operativos** comprobados que generarán los nuevos equipos, durante un horizonte contractual de {anos_contrato} años.
        """)

        st.markdown("### 2. Resultados de la Simulación Financiera")
        st.markdown("Basado en las cifras extraídas del presupuesto y flujo de caja base, el proyecto bajo modelo ESCO presenta los siguientes indicadores desde la perspectiva del inversionista privado:")
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("CAPEX Total", fmt_cop(capex_total))
        col2.metric("VPN", fmt_cop(vpn), estado_proyecto)
        col3.metric("TIR Privado", tir_text)
        col4.metric("Payback Real", payback_text)

        st.markdown("### 3. Comportamiento del Flujo de Caja")
        st.markdown(f"La siguiente gráfica ilustra la evolución financiera del contrato. La curva azul (Flujo Acumulado) demuestra cómo el proyecto evoluciona desde el déficit inicial de la inversión hasta cruzar a terreno positivo en el **{payback_text}**.")
        
        fig = go.Figure()
        colores = ['#ef4444' if val < 0 else '#22c55e' for val in flujo_inversionista]
        
        fig.add_trace(go.Bar(
            x=[f"Año {i}" for i in range(anos_contrato)], 
            y=flujo_inversionista, 
            name='Flujo Neto Anual', 
            marker_color=colores
        ))
        
        fig.add_trace(go.Scatter(
            x=[f"Año {i}" for i in range(anos_contrato)], 
            y=flujo_acumulado, 
            name='Flujo Acumulado', 
            mode='lines+markers',
            line=dict(color='#3b82f6', width=3)
        ))
        
        fig.update_layout(height=450, template="plotly_white", hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("### 4. Conclusión Estratégica")
        if vpn > 0:
            st.success(f"""
            **🟢 VIABLE.**  
            Bajo las condiciones iteradas ({anos_contrato} años cediendo el {split_ahorros*100:.0f}% del ahorro), el proyecto es financieramente atractivo para el sector privado. El flujo de ahorros es robusto y suficiente para cubrir la inversión inicial de {fmt_cop(capex_total)} COP, absorber el costo de capital del {wacc*100:.1f}%, y generar un excedente (VPN) superior a {fmt_cop(vpn)} COP. 

            Al recuperar la inversión en el **{payback_text}**, existe viabilidad para ejecutar el proyecto bajo este esquema. Se sugiere evaluar variaciones en el porcentaje de pignoración para permitir a EMCALI capturar flujo de caja libre antes de la finalización del contrato.
            """)
        else:
            st.error(f"""
            **🔴 NO VIABLE.**  
            Bajo las condiciones iteradas ({anos_contrato} años cediendo el {split_ahorros*100:.0f}% del ahorro), el proyecto destruye valor para el inversionista. Los flujos pignorados no alcanzan a compensar la inversión de {fmt_cop(capex_total)} COP frente al costo de oportunidad del capital ({wacc*100:.1f}%). 

            Se requiere aumentar el porcentaje de ahorros cedido al privado o extender el horizonte del contrato para alcanzar el punto de equilibrio financiero.
            """)

        st.markdown("---")

        # --- 4. DESCARGA DEL INFORME EN PDF ---
        pdf_bytes = generar_pdf(vpn, tir, payback_year, capex_total, split_ahorros, anos_contrato, wacc, estado_proyecto)
        
        st.download_button(
            label="📄 Descargar este Informe en PDF",
            data=pdf_bytes,
            file_name="Informe_Factibilidad_ESCO_EMCALI.pdf",
            mime="application/pdf",
            type="primary"
        )

    except Exception as e:
        st.error(f"Error procesando el archivo: {e}")
else:
    st.info("👈 Por favor, carga el archivo Excel en el panel lateral izquierdo para arrancar el simulador.")