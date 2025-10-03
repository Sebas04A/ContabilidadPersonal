
import plotly.graph_objects as go
def get_diferencias(df_total):
    df_diferencia = df_total.copy()

    df_diferencia["TOTAL_MADRE"] = df_diferencia["PAGOS_MENSUAL_MA"]+ df_diferencia["PAGOS_MA"]
    df_diferencia["diff_madre"] = df_diferencia["TOTAL_MADRE"].diff()

    df_diferencia["TOTAL_MADRE INTER"] = df_diferencia["PAGOS_MENSUAL_MA INTER"]+ df_diferencia["PAGOS_MA"]
    df_diferencia["diff_madre INTER"] = df_diferencia["TOTAL_MADRE INTER"].diff()

    df_diferencia['diff_days']   =df_diferencia['FECHA'].diff().dt.days
    df_diferencia["diff_total"] = df_diferencia["TOTAL"].diff()
    df_diferencia['diff_total_dias'] = df_diferencia['diff_total'] / df_diferencia['diff_days']

    df_diferencia["diff_tarjeta"] = df_diferencia["ACUMULADO_TARJETA"].diff()
    df_diferencia["diff_tarjeta_dias"] = df_diferencia["diff_tarjeta"] / df_diferencia["diff_days"]

    df_diferencia["saldo_sin_inversion"] = df_diferencia["SALDO"] - df_diferencia["INVERSION"]
    df_diferencia["diff_saldo_sin_inversion"] = df_diferencia["saldo_sin_inversion"].diff()

    # df_diferencia["saldo_real"] = df_diferencia["SALDO"] - df_diferencia["INVERSION"] + df_diferencia["PAGO_TARJETA"]
    # df_diferencia["diff_saldo_real"] = df_diferencia["saldo_real"].diff()

    df_diferencia["diff_pago_tarjeta"] = df_diferencia["PAGO_TARJETA"].diff()

    df_diferencia["diff_tarjeta_real"] = df_diferencia["TARJETA"].diff()

    # df_suavizado["SALDO"] - df_suavizado["TARJETA"] + df_suavizado["PAGO_TARJETA"]  - df_suavizado["INVERSION"] + df_suavizado["PAGO_MENSUAL INTER"] + df_suavizado["PAGO_TARJETA_MA INTER"]

    # df_diferencia["total_yo"] = df_diferencia["SALDO"] - df_diferencia["TARJETA"] + df_diferencia["PAGO_TARJETA"]  - df_diferencia["INVERSION"] + df_diferencia["NOTIONCUM"]
    # df_diferencia["diff_total_yo"] = df_diferencia["total_yo"].diff()
    # df_diferencia["diff_total_yo_dias"] = df_diferencia["diff_total_yo"] / df_diferencia['diff_days']

    df_diferencia["diff_notion"] = df_diferencia["NOTIONCUM"].diff()

    df_diferencia["diff_TOTAL"] = df_diferencia["TOTAL"].diff()
    df_diferencia["diff_TOTAL_dias"] = df_diferencia["diff_TOTAL"] / df_diferencia['diff_days']
    return df_diferencia

def graficar_diferencias(df):
    df_atipicos=df
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df_atipicos['FECHA'],
        y=df_atipicos['diff_TOTAL'],
        mode='markers',
        name='Δ TOTAL',
        line=dict(color='red'),
        hovertemplate='<b>%{x}</b><br>Valor: %{y}<br>Descripción: %{text}',
        text=df_atipicos['DESCRIPCION'] + " | " + df_atipicos["MADRE"]
    ))

    fig.add_trace(go.Bar(
        x=df_atipicos['FECHA'],
        y=-df_atipicos['diff_tarjeta'],
        name='Δ Tarjeta',
        marker_color='blue',
        text=df_atipicos['DESCRIPCION'].fillna('') + " | " + df_atipicos["MADRE"].fillna(''),
        hovertemplate='<b>%{x}</b><br>Tarjeta: %{y}<br>Descripción: %{text}',
    ))
    fig.add_trace(go.Bar(
        x=df_atipicos['FECHA'],
        y=df_atipicos["diff_saldo_sin_inversion"],
        name='Δ Saldo',
        marker_color='green',
        text=df_atipicos['DESCRIPCION'] + " | " + df_atipicos["MADRE"],
        hovertemplate='<b>%{x}</b><br>Saldo: %{y}<br>Descripción: %{text}',
    ))
    fig.add_trace(go.Bar(
        x=df_atipicos['FECHA'],
        y=-df_atipicos["diff_notion"],
        name='Δ Notion',
        marker_color='black',
        text=df_atipicos['DESCRIPCION_NOTION'].fillna('') + " | " + df_atipicos["NOTION"].fillna(0).astype(str),
    ))
    #lineas horizontales en 20 y -20
    fig.add_hline(y=10, line_width=1, line_dash="dash", line_color="green", annotation_text="Límite Superior", annotation_position="top left")
    fig.add_hline(y=-10, line_width=1, line_dash="dash", line_color="red", annotation_text="Límite Inferior", annotation_position="bottom left")
    fig.update_layout(
        title="Diferencias Diarias",
        xaxis_title="Fecha",
        yaxis_title="Diferencia",
        legend_title="Leyenda",
        template="plotly_white"
    )
    fig.show()
