# #only notebook
# from plotly.subplots import make_subplots
# import plotly.graph_objects as go
# from contabilidad.backend.services.credit_card.models import MAPEO_COLUMNAS

# def visualizar_tarjeta_pago(df,datos_tarjetas,pagos_tarjeta):
#     df = df.copy()

#     # Lista de fechas donde quieres dibujar las líneas verticales.
#     # Puedes modificar, agregar o eliminar fechas de esta lista.


#     # Convierte las fechas de string a objetos Timestamp de Pandas para consistencia.


#     # --- 2. CREACIÓN DEL GRÁFICO BASE ---
#     # Inicializa un objeto Figure. Este será tu lienzo para el gráfico.
#     fig = go.Figure()


#     # --- 2. AÑADIR ÁREAS SOMBREADAS CON ALTURA ESPECÍFICA (AL FONDO) ---
#     # Itera sobre tu DataFrame de áreas y dibuja un rectángulo para cada una.
#     for index, row in datos_tarjetas.iterrows():
#         # Elige el color basado en si el valor es positivo o negativo
#         color = "green" if row[MAPEO_COLUMNAS["TOTAL_A_PAGAR"]] >= 0 else "red"
#         hover_text = f"Total: {row[MAPEO_COLUMNAS['TOTAL_A_PAGAR']]}. Consumos : {row[MAPEO_COLUMNAS["TOTAL_CONSUMO"]]}" # Tooltip personalizado
#         fig.add_trace(go.Scatter(
#             # Coordenadas para formar un rectángulo
#             x=[row[MAPEO_COLUMNAS["FECHA_EMISION"]], row[MAPEO_COLUMNAS["FECHA_MAX_PAGO"]], row[MAPEO_COLUMNAS["FECHA_MAX_PAGO"]], row[MAPEO_COLUMNAS["FECHA_EMISION"]], row[MAPEO_COLUMNAS["FECHA_EMISION"]]],
#             y=[0, 0, row[MAPEO_COLUMNAS["TOTAL_A_PAGAR"]], row[MAPEO_COLUMNAS["TOTAL_A_PAGAR"]], 0],
#             fill="toself",
#             fillcolor=color,
#             opacity=0.2, # Controla la transparencia
#             mode='lines',
#             line=dict(width=0), # Sin borde para el área
#             showlegend=False, # Ocultar de la leyenda para no saturarla
#             text=hover_text,
#             hoverinfo='text'

#         ))


#     # --- 3. AÑADIR TRAZAS (DATOS) ---
#     # Agrega una traza (trace) de ejemplo para visualizar los datos del DataFrame.
#     # Puedes agregar más trazas (líneas, barras, etc.) usando fig.add_trace().
#     fig.add_trace(go.Scatter(
#         x=df['FECHA'],
#         y=df['TARJETA'],
#         mode='lines',
#         name='Mi Serie de Datos',
#         line=dict(color='blue', width=2)

#     ))


#     # 2. Preparar los datos para Plotly
#     fechas_pagos = [p.inicio for p in pagos_tarjeta]
#     montos_pagos = [p.monto for p in pagos_tarjeta]

#     # 3. Añadir la traza de barras al gráfico `fig`
#     # El ancho se especifica en milisegundos para que sea consistente en el eje de fechas.
#     # 1 día = 24*60*60*1000 = 86,400,000 milisegundos.
#     # Usaremos un ancho de 3 días para que las barras sean gruesas y visibles.
#     ancho_barra_ms = 3 * 86400000

#     fig.add_trace(go.Bar(
#         x=fechas_pagos,
#         y=montos_pagos,
#         name='Pagos Realizados',
#         width=ancho_barra_ms,
#         marker_color='orange', # Un color que se distinga
#         opacity=0.8
#     ))
#     # --- 4. AÑADIR LÍNEAS VERTICALES ---
#     # Itera sobre tu lista de fechas importantes y agrega una línea vertical por cada una.

#     # 1. Definir los nombres de las columnas que vas a usar
#     fecha_col = MAPEO_COLUMNAS["MAX_FECHA_MOVIMIENTO"]
#     valor_col = "TOTAL_A_PAGAR"

#     # 2. Filtrar el DataFrame para obtener solo las filas con fechas válidas
#     puntos_a_marcar = datos_tarjetas.dropna(subset=[fecha_col]).copy()

#     # 3. Agregar todos los puntos rojos en una sola operación
#     fig.add_trace(go.Scatter(
#         x=puntos_a_marcar[fecha_col],
#         y=puntos_a_marcar[valor_col],
#         mode='markers',
#         marker=dict(color='red', size=10),
#         name='Fecha Límite de Pago'
#     ))

#     # 4. Agregar las líneas verticales para cada punto
#     # 4. Agregar las líneas verticales y anotaciones manualmente
#     for fecha in puntos_a_marcar[fecha_col]:
        
#         # Dibuja la línea vertical usando add_shape
#         fig.add_shape(
#             type="line",
#             x0=fecha, y0=0, # Punto de inicio (x, y)
#             x1=fecha, y1=1, # Punto final (x, y)
#             yref="paper",   # Hace que la línea ocupe toda la altura del gráfico (de 0 a 100%)
#             line=dict(
#                 color="red",
#                 width=2,
#                 dash="dash",
#             )
#         )

#         # Añade el texto de la fecha por separado usando add_annotation
#         fig.add_annotation(
#             x=fecha,
#             y=1,            # Posición Y en la parte superior
#             yref="paper",   # Referencia a la altura total del gráfico
#             text=fecha.strftime('%d-%b'),
#             showarrow=False,
#             font=dict(
#                 color="red",
#                 size=10
#             ),
#             xanchor="left", # Ancla el texto a la izquierda de la fecha
#             xshift=4        # Un pequeño desplazamiento a la derecha para que no se pegue a la línea
#         )

#     # --- 5. PERSONALIZACIÓN DEL DISEÑO ---
#     # Actualiza el layout del gráfico para añadir títulos, etiquetas y mejorar la apariencia.
#     fig.update_layout(
#         title_text="Análisis de Datos con Eventos Marcados",
#         xaxis_title="Fecha",
#         yaxis_title="Valor / Métrica",
#         template="plotly_white", # Un tema limpio. Otros pueden ser "plotly_dark", "ggplot2", etc.
#         legend_title_text='Leyenda',
#         font=dict(
#             family="Arial, sans-serif",
#             size=12,
#             color="black"
#         )
#     )

#     # --- 6. MOSTRAR EL GRÁFICO ---
#     # Abre una ventana del navegador para mostrar el gráfico interactivo.
#     fig.show()