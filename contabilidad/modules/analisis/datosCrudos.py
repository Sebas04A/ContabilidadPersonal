# Only Notebook
# Archivo: visualizador_financiero.py
# -*- coding: utf-8 -*-
"""
Módulo que contiene la clase VisualizadorFinanciero para la exploración
interactiva de DataFrames de pandas en un entorno de notebook (Jupyter/Colab).
Versión 2.4 con lógica mejorada para la creación de la fuente 'Todas'.
"""

import pandas as pd
import ipywidgets as widgets
from IPython.display import display, clear_output

class VisualizadorFinanciero:
    """
    Clase para gestionar y visualizar datos financieros de forma interactiva.
    """
    def __init__(self, **kwargs):
        """
        Inicializa con uno o más DataFrames.
        Ej: VisualizadorFinanciero(cuenta=df_cuenta, tarjeta=df_tarjeta)
        """
        self.dataframes = {nombre: df.copy() for nombre, df in kwargs.items() if isinstance(df, pd.DataFrame)}
        self.config = {}
        if not self.dataframes:
            raise ValueError("Debes proporcionar al menos un DataFrame de pandas válido.")

    def configurar_fuente(self, nombre_df: str, col_fecha: str, col_valor: str = None, col_descripcion: str = None, columnas_default: list = None):
        """
        Configura las columnas clave para un DataFrame específico.

        Args:
            nombre_df (str): Nombre clave del DataFrame (ej. 'cuenta').
            col_fecha (str): Nombre de la columna de fecha.
            col_valor (str, optional): Nombre de la columna de valor numérico.
            col_descripcion (str, optional): Nombre de la columna de descripción.
            columnas_default (list, optional): Lista de columnas a mostrar por defecto para esta fuente.
        """
        if nombre_df not in self.dataframes:
            raise ValueError(f"El DataFrame '{nombre_df}' no fue encontrado.")
        
        df = self.dataframes[nombre_df]
        for col in [col_fecha, col_valor, col_descripcion]:
            if col and col not in df.columns:
                raise ValueError(f"La columna '{col}' no existe en el DataFrame '{nombre_df}'.")
        
        df[col_fecha] = pd.to_datetime(df[col_fecha])
        self.dataframes[nombre_df] = df.sort_values(by=col_fecha).reset_index(drop=True)
        
        self.config[nombre_df] = {
            'fecha': col_fecha, 'valor': col_valor, 
            'descripcion': col_descripcion, 'columnas_default': columnas_default
        }
        print(f"(OK) Fuente '{nombre_df}' configurada.")

    def obtener_vista(self, nombre_df: str, fecha_objetivo, num_filas: int = 8, justo: bool = False, columnas_mostrar: list = None):
        """
        Obtiene una vista filtrada de un DataFrame alrededor de una fecha específica.
        """
        if nombre_df not in self.config:
            raise ValueError(f"Configuración para '{nombre_df}' no encontrada. Usa 'configurar_fuente' primero.")

        config = self.config[nombre_df]
        df = self.dataframes[nombre_df]
        col_fecha = config['fecha']
        
        fecha_objetivo = pd.to_datetime(fecha_objetivo)
        
        if justo:
            fecha_inicio = fecha_objetivo.normalize()
            fecha_fin = fecha_inicio + pd.Timedelta(days=1, seconds=-1)
            df_filtrado = df[(df[col_fecha] >= fecha_inicio) & (df[col_fecha] <= fecha_fin)]
        else:
            indice = df[col_fecha].searchsorted(fecha_objetivo, side='left')
            inicio = max(0, indice - num_filas)
            fin = min(len(df), indice + num_filas)
            df_filtrado = df.iloc[inicio:fin]
        
        total = 0
        if config.get('valor') and config['valor'] in df_filtrado.columns:
            total = df_filtrado[config['valor']].sum()
        
        if columnas_mostrar and all(c in df_filtrado.columns for c in columnas_mostrar):
            df_final = df_filtrado[columnas_mostrar]
        else:
            df_final = df_filtrado

        return df_final, total

    def _generar_fuente_combinada(self):
        """
        Método interno para crear el DataFrame 'Todas' unificado.
        Es más robusto: solo necesita 'col_fecha' y 'col_valor' para incluir una fuente.
        """
        if len(self.config) < 2:
            return

        dfs_combinados = []
        for nombre, conf in self.config.items():
            if nombre == 'Todas': continue
            
            # Lógica mejorada: solo se requiere fecha y valor. La descripción es opcional.
            if not all([conf.get('fecha'), conf.get('valor')]):
                print(f"(AVISO) Advertencia: La fuente '{nombre}' no se incluirá en 'Todas' por falta de configuración de 'col_fecha' o 'col_valor'.")
                continue

            df_temp = self.dataframes[nombre].copy()
            df_temp['FUENTE'] = nombre
            
            # Construir el mapa de renombre dinámicamente
            rename_map = {
                conf['fecha']: 'FECHA',
                conf['valor']: 'VALOR',
            }
            if conf.get('descripcion'):
                rename_map[conf['descripcion']] = 'DESCRIPCION'

            df_temp = df_temp.rename(columns=rename_map)
            
            # Añadir una descripción por defecto si no existe
            if 'DESCRIPCION' not in df_temp.columns:
                df_temp['DESCRIPCION'] = "Sin descripción"
            
            columnas_estandar = ['FECHA', 'VALOR', 'DESCRIPCION', 'FUENTE']
            columnas_a_incluir = [c for c in columnas_estandar if c in df_temp.columns]
            dfs_combinados.append(df_temp[columnas_a_incluir])

        if len(dfs_combinados) < 2:
            return

        df_todo = pd.concat(dfs_combinados, ignore_index=True).sort_values(by='FECHA').reset_index(drop=True)
        self.dataframes['Todas'] = df_todo
        self.config['Todas'] = {
            'fecha': 'FECHA', 'valor': 'VALOR', 'descripcion': 'DESCRIPCION',
            'columnas_default': ['FECHA', 'VALOR', 'DESCRIPCION', 'FUENTE']
        }
        print("(INFO) Fuente combinada 'Todas' generada exitosamente.")

    def mostrar_gui(self):
        """
        Renderiza y muestra la interfaz gráfica con un layout vertical (filtros arriba).
        """
        if not self.config:
            print("(ERROR) Error: Ninguna fuente de datos ha sido configurada. Usa 'configurar_fuente' primero.")
            return
        
        self._generar_fuente_combinada()

        df_selector = widgets.Dropdown(options=list(self.dataframes.keys()), description='Fuente:')
        date_picker = widgets.DatePicker(description='Fecha:', value=pd.to_datetime('today').date())
        filas_slider = widgets.IntSlider(value=8, min=1, max=30, step=1, description='Contexto:')
        justo_checkbox = widgets.Checkbox(value=False, description='Solo día exacto', indent=False)
        columnas_selector = widgets.SelectMultiple(description='Columnas:', rows=10)
        boton_mostrar = widgets.Button(description="Generar Vista", button_style='primary', icon='search')
        
        total_display = widgets.HTML(value="<div style='padding: 10px;'>Selecciona filtros y genera una vista.</div>")
        salida_df = widgets.Output()

        def actualizar_opciones_columnas(change):
            df_seleccionado = change['new']
            if df_seleccionado:
                columnas = self.dataframes[df_seleccionado].columns.tolist()
                columnas_selector.options = columnas
                defaults = self.config[df_seleccionado].get('columnas_default')
                columnas_selector.value = defaults if defaults else columnas
        
        df_selector.observe(actualizar_opciones_columnas, names='value')

        def on_button_clicked(b):
            with salida_df:
                clear_output(wait=True)
                try:
                    df_vista, total = self.obtener_vista(
                        nombre_df=df_selector.value, fecha_objetivo=date_picker.value,
                        num_filas=filas_slider.value, justo=justo_checkbox.value,
                        columnas_mostrar=list(columnas_selector.value)
                    )
                    
                    total_html = f"""
                    <div style='background-color: #f0f8ff; border: 1px solid #b0c4de; padding: 15px; border-radius: 8px; text-align: center;'>
                        <p style='font-size: 16px; margin: 0; color: #4682b4;'>Suma Total de la Vista</p>
                        <p style='font-size: 28px; font-weight: bold; margin: 5px 0 0 0; color: #005a9e;'>
                            Total: {total:,.2f}
                        </p>
                    </div>
                    """
                    total_display.value = total_html
                    
                    if df_vista.empty:
                        print("\nNo se encontraron datos para la selección actual.")
                    else:
                        display(df_vista.style.set_properties(**{'text-align': 'left'}).set_table_styles([dict(selector='th', props=[('text-align', 'left')])]))

                except Exception as e:
                    print(f"(ERROR) Error: {e}")

        boton_mostrar.on_click(on_button_clicked)
        actualizar_opciones_columnas({'new': df_selector.value})
        
        # --- NUEVO DISEÑO DE LAYOUT ---
        acordeon_columnas = widgets.Accordion(children=[columnas_selector], titles=['Personalizar Columnas'])
        
        # Agrupar controles principales horizontalmente
        controles_principales = widgets.HBox([
            df_selector, date_picker, filas_slider, justo_checkbox
        ], layout=widgets.Layout(flex_flow='row wrap', justify_content='space-between', align_items='center'))

        # Panel de filtros superior
        panel_filtros = widgets.VBox([
            widgets.HTML("<h3>Filtros de Búsqueda</h3>"),
            controles_principales,
            acordeon_columnas,
            widgets.HTML("<hr>"),
            boton_mostrar
        ], layout=widgets.Layout(width='99%', border='1px solid #e0e0e0', padding='15px', border_radius='5px', margin='0 0 20px 0'))

        # Panel de resultados inferior
        panel_resultados = widgets.VBox([
            total_display, salida_df
        ], layout=widgets.Layout(width='99%'))

        # Layout principal vertical que apila los paneles
        app_layout = widgets.VBox([panel_filtros, panel_resultados])
        display(app_layout)



def configurar_cuenta(visualizador: VisualizadorFinanciero):
    return visualizador.configurar_fuente(
        nombre_df='movimientos_cuenta',
        col_fecha='FECHA',
        col_valor='MONTO'
    )
def configurar_tarjeta(visualizador: VisualizadorFinanciero):
    return visualizador.configurar_fuente(
        nombre_df='movimientos_tarjeta',
        col_fecha='FECHA',
        col_valor='VALOR'
    )
def confgurar_completo(visualizador: VisualizadorFinanciero):
    return visualizador.configurar_fuente(
        nombre_df='movimientos_completo',
        col_fecha='FECHA',
        col_valor='TOTAL',
        col_descripcion="DESCRIPCION",
        columnas_default=['FECHA',"TOTAL", 'SALDO', 'TARJETA',"INVERSION","NOTIONCUM","PAGOS_MENSUAL_MA INTER","DESCRIPCION","MADRE"]
    )
def configurar_completo_diff(visualizador: VisualizadorFinanciero):
    return visualizador.configurar_fuente(
        nombre_df='movimientos_completo_diff',
        col_fecha='FECHA',
        col_valor='diff_TOTAL',
        col_descripcion="DESCRIPCION",
        columnas_default=['FECHA',"diff_TOTAL", 'diff_saldo_sin_inversion', 'diff_tarjeta', 'diff_notion',"diff_madre INTER" ,'DESCRIPCION','MADRE']
    )


def visualizar_cuenta(df_cuenta):
    visualizador_cuenta = VisualizadorFinanciero(
        movimientos_cuenta= df_cuenta
    )
    configurar_cuenta(visualizador_cuenta)
    visualizador_cuenta.mostrar_gui()

def visualizar_tarjeta(df_tarjeta):
    visualizador_tarjeta = VisualizadorFinanciero(
        movimientos_tarjeta= df_tarjeta
    )
    configurar_tarjeta(visualizador_tarjeta)
    visualizador_tarjeta.mostrar_gui()

def visualizar_todo(df_cuenta, df_tarjetas,df_completo):
    visualizador = VisualizadorFinanciero(
        movimientos_cuenta= df_cuenta,
        movimientos_tarjeta= df_tarjetas,
        movimientos_completo= df_completo,
        movimientos_completo_diff= df_completo
    )
    configurar_cuenta(visualizador)
    configurar_tarjeta(visualizador)
    confgurar_completo(visualizador)
    configurar_completo_diff(visualizador)
    visualizador.mostrar_gui()