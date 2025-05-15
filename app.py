# ✅ PIAT v1.5 - Con prioridad respetada y flujo en vez de PUSH (con Stock Restante en Asignación)
import streamlit as st
import pandas as pd
import numpy as np
import io
import matplotlib.pyplot as plt
import seaborn as sns
 
st.set_page_config(page_title="PIAT - Asignación de Stock", layout="centered")
st.title("📦 IST - Asignación de Stock por Cliente y Mes (v1.5 Prioridad Fix + Flujo continuo)")
 
st.markdown("""
### ✅ ¿Qué hace este módulo?
 
- Asigna productos considerando **mínimos requeridos por cliente y mes**
- Utiliza el **stock restante como flujo acumulado entre meses**
- Prioriza clientes por nivel definido (1 es mayor prioridad)
- El stock sobrante **se arrastra como flujo**, no se manda a `PUSH`
- Exporta un archivo Excel con todas las vistas necesarias (incluyendo Stock Restante)
 
---
📥 ¿No tienes un archivo?  
👉 [Descargar archivo de prueba](https://github.com/sebasalinas27/IST-Modulo-Asignacion/raw/main/Template_Pruebas_PIAT.xlsx)
""")
 
uploaded_file = st.file_uploader("Sube tu archivo Excel", type=["xlsx"])
 
if uploaded_file:
    st.subheader("📊 Resumen del archivo cargado")
    df_stock_preview = pd.read_excel(uploaded_file, sheet_name="Stock Disponible")
    df_prioridad_preview = pd.read_excel(uploaded_file, sheet_name="Prioridad Clientes")
    df_minimos_preview = pd.read_excel(uploaded_file, sheet_name="Mínimos de Asignación")
 
    st.write(f"- **Productos**: {df_stock_preview['Codigo'].nunique()}")
    st.write(f"- **Clientes**: {df_prioridad_preview.shape[0]}")
    st.write(f"- **Meses**: {df_stock_preview['MES'].nunique()}")
    st.write(f"- **Celdas con mínimo asignado**: {(df_minimos_preview['Minimo'] > 0).sum()}")
 
    if st.button("🔁 Ejecutar Asignación"):
        try:
            # Lectura de datos
            df_stock = pd.read_excel(uploaded_file, sheet_name="Stock Disponible")
            df_prioridad = pd.read_excel(uploaded_file, sheet_name="Prioridad Clientes", index_col=0)
            df_minimos = pd.read_excel(uploaded_file, sheet_name="Mínimos de Asignación", index_col=[0,1,2])
 
            # Preprocesamiento mínimos
            df_minimos = df_minimos.groupby(level=[0,1,2]).sum().sort_index()
            df_minimos['Pendiente'] = df_minimos['Minimo']
 
            # Prioridades
            prioridad_clientes = pd.to_numeric(df_prioridad.iloc[:,0], errors='coerce').fillna(5)
            clientes_ordenados = prioridad_clientes.sort_values().index.tolist()
 
            # Filtrar stock
            df_stock = df_stock[df_stock['Stock Disponible']>0].copy()
            df_stock = df_stock.set_index(['MES','Codigo']).sort_index()
            df_stock['Stock Restante'] = df_stock['Stock Disponible']
 
            # Filtrar códigos relevantes
            validos = set(df_stock.index.get_level_values(1)) & set(df_minimos.index.get_level_values(1))
            df_stock = df_stock[df_stock.index.get_level_values(1).isin(validos)]
            df_minimos = df_minimos[df_minimos.index.get_level_values(1).isin(validos)]
 
            meses = sorted(df_stock.index.get_level_values(0).unique())
            df_asignacion = pd.DataFrame(0,
                                         index=df_minimos.index.droplevel(2).unique(),
                                         columns=clientes_ordenados)
 
            # Flujo acumulado
            stock_flujo = {}
            for mes in meses:
                # Sumar stock disponible a flujo
                for codigo in df_stock.index.get_level_values(1).unique():
                    if (mes,codigo) in df_stock.index:
                        stock_flujo[codigo] = stock_flujo.get(codigo,0) + df_stock.at[(mes,codigo),'Stock Restante']
 
                # Asignar por prioridad
                pendientes = df_minimos[(df_minimos.index.get_level_values(0)==mes)]
                pendientes = pendientes[pendientes['Pendiente']>0].reset_index()
                pendientes['Prioridad'] = pendientes['Cliente'].map(prioridad_clientes)
                pendientes = pendientes.sort_values('Prioridad')
                for _,fila in pendientes.iterrows():
                    m,codigo,cliente = fila['MES'],fila['Codigo'],fila['Cliente']
                    pend = df_minimos.at[(m,codigo,cliente),'Pendiente']
                    disp = stock_flujo.get(codigo,0)
                    if pend>0 and disp>0:
                        asign = min(pend,disp)
                        if (m,codigo) not in df_asignacion.index:
                            df_asignacion.loc[(m,codigo),:] = 0
                        df_asignacion.at[(m,codigo),cliente] += asign
                        df_minimos.at[(m,codigo,cliente),'Pendiente'] -= asign
                        stock_flujo[codigo] -= asign
 
            # Cálculos finales
            df_minimos['Asignado'] = df_minimos.index.map(lambda x: df_asignacion.at[(x[0],x[1]),x[2]] if (x[0],x[1]) in df_asignacion.index else 0)
            df_minimos['Cumple'] = df_minimos['Asignado']>=df_minimos['Minimo']
            df_minimos['Pendiente Final'] = df_minimos['Minimo']-df_minimos['Asignado']
 
                        # Asegurar que el índice de df_asignacion sea MultiIndex para hacer join correctamente
            df_asignacion.index = pd.MultiIndex.from_tuples(df_asignacion.index, names=['MES','Codigo'])
            # Incorporar Stock Restante en Asignación
            df_asign_out = df_asignacion.join(df_stock['Stock Restante'])

            # Generar Excel
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_asign_out.to_excel(writer, sheet_name='Asignación Flujo', index=True)
                df_stock.reset_index().to_excel(writer, sheet_name='Stock Disponible', index=False)
                df_prioridad.to_excel(writer, sheet_name='Prioridad Clientes')
                df_minimos.reset_index().to_excel(writer, sheet_name='Mínimos de Asignación', index=False)
            output.seek(0)
 
            st.success('✅ Optimización completada.')
 
            # Gráficos
            st.subheader('📊 Total asignado por cliente')
            total = df_asignacion.sum().sort_values(ascending=False)
            fig1,ax1=plt.subplots(figsize=(10,4))
            sns.barplot(x=total.index,y=total.values,ax=ax1)
            ax1.set(title='Total Asignado por Cliente',ylabel='Unidades')
            ax1.tick_params(axis='x',rotation=45)
            st.pyplot(fig1)
            st.subheader('📈 Evolución mensual por cliente')
            df_plot = df_asignacion.reset_index().melt(id_vars=['MES','Codigo'],var_name='Cliente',value_name='Asignado')
            df_grp = df_plot.groupby(['MES','Cliente'])['Asignado'].sum().reset_index()
            fig2,ax2=plt.subplots(figsize=(10,5))
            sns.lineplot(data=df_grp,x='MES',y='Asignado',hue='Cliente',marker='o',ax=ax2)
            ax2.set_title('Evolución mensual de asignación')
            ax2.legend(bbox_to_anchor=(1.05,1),loc='upper left')
            st.pyplot(fig2)
            st.subheader('📦 Stock asignado vs restante por mes')
            df_tot = df_stock.reset_index().groupby('MES')[['Stock Disponible','Stock Restante']].sum()
            df_tot['Asignado']=df_tot['Stock Disponible']-df_tot['Stock Restante']
            df_melt=df_tot.reset_index().melt(id_vars='MES',var_name='Tipo',value_name='Unidades')
            fig3,ax3=plt.subplots(figsize=(8,4))
            sns.barplot(data=df_melt,x='MES',y='Unidades',hue='Tipo',ax=ax3)
            ax3.set(title='Distribución de stock por mes')
            st.pyplot(fig3)
 
            st.download_button(label='📥 Descargar archivo Excel',data=output.getvalue(),file_name='asignacion_resultados_PIAT_v1_5.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
 
        except Exception as e:
            st.error(f"❌ Error al procesar el archivo: {e}")
