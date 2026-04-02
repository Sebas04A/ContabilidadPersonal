# # Only Notebook
# import pandas as pd
# import plotly.graph_objects as go
# class Trace:
#     def __init__(self,tipo,name, y, x="FECHA", mode='lines+markers', line_color='blue', hovertemplate=None, text=None):
#         self.x = x
#         self.y = y
#         self.name = name
#         self.mode = mode
#         self.line_color = line_color
#         self.hovertemplate = hovertemplate
#         self.text = text
#         self.tipo = tipo
    

# class Graficos:
#     traces = []
#     highlighted_days=[]
#     fig = go.Figure()
#     max_fecha = None
#     def __init__(self, df):
#         self.df = df
#         self.max_fecha = df['FECHA'].max()
#         self.min_fecha = df['FECHA'].min()
#         self.traces = []
#         self.highlighted_days = []
#         self.fig = go.Figure()
        


#     def add_trace(self, trace: Trace):
#         self.traces.append(trace)
    
#     def delete_trace(self, trace: Trace):
#         self.traces.remove(trace)

#     def add_8_days(self):
#         fechas_8 = pd.date_range(start=self.min_fecha, end=self.max_fecha, freq='MS')
#         fechas_8 = [d + pd.DateOffset(days=5) for d in fechas_8]
#         for fecha in fechas_8:
#             if fecha <= self.df['FECHA'].max():
#                 fecha_dt = fecha.to_pydatetime()
#                 # Línea vertical
#                 self.fig.add_shape(
#                     type="line",
#                     x0=fecha_dt,
#                     x1=fecha_dt,
#                     y0=0,
#                     y1=1,
#                     xref='x',
#                     yref='paper',
#                     line=dict(color="gray", width=1, dash="dash")
#                 )

#     def add_highlighteds_day(self, fechas):
#         fechas = pd.to_datetime(fechas)
#         for fecha in fechas:
#             if fecha <= self.df['FECHA'].max():
#                 fecha_dt = pd.to_datetime(fecha).to_pydatetime()
#                 self.fig.add_vline(
#                     x=fecha_dt,
#                     line_width=2,
#                     line_dash="dash",  # Estilo: "solid", "dot", "dash"
#                     line_color="red"
#                 )

#     def show_pendiente(self, inicio=None, fin=None):
#         if inicio is None:
#             inicio = self.df['FECHA'].min()
#         if fin is None:
#             fin = self.df['FECHA'].max()

#         inicio = pd.to_datetime(inicio)
#         fin = pd.to_datetime(fin)

#         df_total_inicio = self.df[self.df['FECHA'] == inicio]
#         df_total_fin = self.df[self.df['FECHA'] == fin]
#         if df_total_inicio.empty or df_total_fin.empty:
#             print("No se encontraron datos para las fechas especificadas.")
#             print(df_total_inicio, df_total_fin)
#             return
#         total_inicio = df_total_inicio['TOTAL'].values[0]
#         total_fin = df_total_fin['TOTAL'].values[0]
#         pendiente = (total_fin - total_inicio) / (fin - inicio).days
#         print(f"Pendiente entre {inicio.strftime('%Y-%m-%d')} y {fin.strftime('%Y-%m-%d')}: {pendiente:.2f} por día")
#         print(f"Total {total_fin} - {total_inicio} = {total_fin - total_inicio}")

#         # Agregar línea de pendiente al gráfico
#         self.fig.add_shape(
#             type="line",
#             x0=inicio,
#             y0=total_inicio,
#             x1=fin,
#             y1=total_fin,
#             line=dict(color="blue", width=2, dash="dash"),
#             name="Pendiente"
#         )

#     def agregar_traces_defecto(self):
#         traces = obtener_traces(self.df)
#         for trace in traces:
#             self.add_trace(trace)


        

#     def plot(self):
#         print(self.traces)
#         print(self.df[self.df["FECHA"]>"2025-06-10"][["FECHA","TOTAL"]].head(20))
#         for trace in self.traces:
#             if trace.tipo == 'scatter':
#                 self.fig.add_trace(go.Scatter(
#                     x=self.df[trace.x],
#                     y=self.df[trace.y],
#                     mode=trace.mode,
#                     name=trace.name,
#                     line=dict(color=trace.line_color),
#                     hovertemplate=trace.hovertemplate,
#                     text=trace.text
#                 ))
#             elif trace.tipo == 'bar':
#                 self.fig.add_trace(go.Bar(
#                     x=self.df[trace.x],
#                     y=self.df[trace.y],
#                     name=trace.name,
#                     marker_color=trace.line_color,
#                     hovertemplate=trace.hovertemplate,
#                     text=trace.text
#                 ))
#         self.fig.show()



# def obtener_traces(df):
#     total = Trace(
#         tipo='scatter',
#         name='Total',
#         y='TOTAL',
#         hovertemplate='<b>%{x}</b><br>Valor: %{y}<br>Descripción: %{text}',
#         text=df['DESCRIPCION'] + " | " + df["MADRE"],
#         line_color='red'
#     )
#     total_tarjeta = Trace(
#         tipo='scatter',
#         name='Total Tarjeta',
#         y='TARJETA',
#         line_color='blue',
#         mode='lines+markers',
#         hovertemplate='<b>%{x}</b><br>Valor: %{y}<br>Descripción: %{text}',
#         text=df['DESCRIPCION'] + " | " + df["MADRE"],
#     )
#     total_cuenta = Trace(
#         tipo='scatter',
#         name='Total Cuenta (sin inversiones)',
#         y="saldo_sin_inversion",
#         line_color='green',
#         mode='lines+markers',
#         hovertemplate='<b>%{x}</b><br>Valor: %{y}<br>Descripción: %{text}',
#         text=df['DESCRIPCION'].fillna('') + " | " + df["MADRE"],
#     )

#     diff_saldo_sin_inversion = Trace(
#         tipo='bar',
#         name='Diferencia Saldo (sin inversiones)',
#         y='diff_saldo_sin_inversion',
#         line_color='green',
#         hovertemplate='<b>%{x}</b><br>Diferencia: %{y:.2f}<br>Descripción: %{text}',
#         text=df['DESCRIPCION'].fillna('') + " | " + df["MADRE"],
#     )
#     diff_tarjeta = Trace(
#         tipo='bar',
#         name='Diferencia Tarjeta',
#         y='diff_tarjeta',
#         line_color='blue',
#         hovertemplate='<b>%{x}</b><br>Diff: %{y}<br>Descripción: %{text}',
#         text=df['DESCRIPCION'].fillna('') + " | " + df["MADRE"],
#     )
#     diff_notion = Trace(
#         tipo='bar',
#         name='Diferencia Notion',
#         y='diff_notion',
#         line_color='black',
#         hovertemplate='<b>%{x}</b><br>Diff Notion: %{y}<br>Descripción: %{text}',
#         text=df['DESCRIPCION_NOTION'].fillna('')
#     )
#     # inversiones =Trace(
#     #     tipo='bar',
#     #     name='Inversiones',
#     #     y='INVERSION',
#     #     line_color='purple',
#     #     hovertemplate='<b>%{x}</b><br>Inversiones: %{y}<br>Descripción: %{text}',
#     #     text=df['descripcion'].fillna('') + " | " + df_dif_desc["madre"],
#     # )
#     total_madre = Trace(
#         tipo='scatter',
#         name='Total Madre',
#         y='TOTAL_MADRE',
#         line_color='gray',
#         mode='lines+markers',
#     )
#     interpolado_mensual = Trace(
#         tipo='scatter',
#         name='Interpolado Mensual Madre',
#         y='PAGOS_MENSUAL_MA INTER',
#         line_color='purple',
#         mode='lines+markers',
#         hovertemplate='<b>%{x}</b><br>Pago Mensual: %{y}<br>Descripción: %{text}',
#         text=df['DESCRIPCION'] + " | " + df["MADRE"],
#     )
#     notion = Trace(
#         tipo='scatter',
#         name='Notion',
#         y='NOTIONCUM',
#         line_color='black',
#         mode='lines+markers',
#         hovertemplate='<b>%{x}</b><br>Notion: %{y}<br>Descripción: %{text}',
#         text=df['DESCRIPCION_NOTION'].fillna('') + " :" + df["NOTION"].astype(str) ,
#     )

#     return total, total_tarjeta, total_cuenta, diff_saldo_sin_inversion, diff_tarjeta, diff_notion, total_madre, interpolado_mensual, notion



# #pendiente de la linea

# #FIXING INVERSIONES

# def mostrar_grafico_completo(df):
    
#     highlighted_days = [
#         '2024-06-22',
#         '2024-09-30',
#         '2025-03-22',
#         "2025-01-31",
#         "2025-07-18",
#         "2025-09-30",
#         "2025-03-16"
#     ]
#     # Crear instancia de Graficos
#     grafico = Graficos(df)
#     # Agregar trazas
#     # grafico.add_trace(total_yo)
#     grafico.add_trace(total)
#     grafico.add_trace(total_tarjeta)
#     grafico.add_trace(total_cuenta)

#     grafico.add_trace(diff_saldo_sin_inversion)
#     grafico.add_trace(diff_tarjeta)
#     grafico.add_trace(diff_notion)

#     # grafico.add_trace(total_madre)
#     grafico.add_trace(notion)

#     grafico.add_trace(interpolado_mensual)
#     # Agregar días destacados
#     grafico.add_highlighteds_day(highlighted_days)
#     # Agregar líneas de 8 días
#     grafico.add_8_days()
#     # Mostrar pendiente
#     # grafico.show_pendiente(inicio, fin)
#     # grafico.show_pendiente('2025-01-08', '2025-06-10')
#     # grafico.show_pendiente('2025-01-08', '2025-07-28')
#     # grafico.show_pendiente('2025-06-10', '2025-07-28')
#     # grafico.show_pendiente('2024-05-01', '2024-08-22')
#     # grafico.show_pendiente('2024-05-01', '2025-01-08')
#     # grafico.add_last_day_card()

#     grafico.plot()
#     return grafico
