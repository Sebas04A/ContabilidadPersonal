import streamlit as st
import pandas as pd
import os
from datetime import datetime
import uuid
import rules_handler as rules_module
import sincronizacion

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Control Financiero PRO", layout="wide")

# --- DEFINICIÓN DE COLUMNAS ---
COLUMNAS_EXTRA = {
    'nombre_limpio': '',
    'categoria': '---',
    'tags': '',
    'prioridad': '---',
    'es_fijo': False,
    'pertenece_a': '---',
    'es_reembolsable': False,
    'deudor': '',
    'felicidad': 0,
    'revisado': False,
    'nota': '',
    'split_group_id': ''
}

# --- FUNCIÓN DE CARGA ---
def cargar_datos():
    raise NotImplementedError("Esta función ya no esta en funcionamiento. Hay que actualizar los paths")
    archivo_maestro = '../data/etiquetado/gastos_maestros.csv'
    archivo_input = '../data/etiquetado/transacciones_input.csv'
    
    if os.path.exists(archivo_maestro):
        df = pd.read_csv(archivo_maestro)
    elif os.path.exists(archivo_input):
        df = pd.read_csv(archivo_input)
        for col, default in COLUMNAS_EXTRA.items():
            df[col] = default
        df.to_csv(archivo_maestro, index=False)
    else:
        st.error("⚠️ Faltan archivos de datos.")
        return pd.DataFrame()
    
    df['FECHA'] = pd.to_datetime(df['FECHA'])
    
    # --- AUTO-APLICAR REGLAS ---
    if not df.empty and 'revisado' in df.columns:
        df = rules_module.apply_rules_to_df(df)
    
    return df




# --- HELPER TAGS ---
def obtener_tags_unicos(df):
    if 'tags' not in df.columns:
        return []
    tags_sucios = df['tags'].dropna().astype(str).tolist()
    todos_tags = []
    for t in tags_sucios:
        # Se asume que los tags están separados por coma
        if t.strip():
            todos_tags.extend([tag.strip() for tag in t.split(',') if tag.strip()])
    return sorted(list(set(todos_tags)))

# --- HELPER UI ---
def render_form_fields(key_prefix, default_data, all_tags):
    """
    Renderiza los campos comunes de edición (Categoría, Tags, Prioridad, etc.)
    Retorna un diccionario con los valores actuales.
    """
    # --- SECCIÓN 1: CLASIFICACIÓN ---
    with st.container(border=True):
        st.markdown("##### 📍 Identificación y Clasificación")
        c1, c2 = st.columns(2)
        
        with c1:
            # Nombre Limpio
            val_nombre = default_data.get('nombre_limpio', '')
            nombre_limpio = st.text_input("Nombre Comercial", value=val_nombre, help="Nombre legible del establecimiento", key=f"{key_prefix}_nom")
            
        with c2:
            # Categoría
            opciones_cat = ["---", "Alimentación", "Transporte", "Ocio", "Salud", "Subscripciones", "Mensual","Inversion","Regalo" , "Mujeres","Aseo","Deudas","Tarjeta","Ropa" ,"Viajes","Otro"]
            cat_actual = default_data.get('categoria', '---')
            # Fallback si llega vacío o none
            if not cat_actual or cat_actual == "Sin Categoría": cat_actual = "---"
            
            idx_cat = opciones_cat.index(cat_actual) if cat_actual in opciones_cat else 0
            nueva_cat = st.selectbox("Categoría", opciones_cat, index=idx_cat, key=f"{key_prefix}_cat")

        st.divider()
        
        # Tags
        current_tags = default_data.get('tags', [])
        
        ct1, ct2 = st.columns([2, 1])
        with ct1:
            sel_tags = st.multiselect("Tags existentes", options=all_tags, default=[t for t in current_tags if t in all_tags] + [t for t in current_tags if t not in all_tags], key=f"{key_prefix}_tags")
        with ct2:
            nuevo_tag = st.text_input("Nuevo Tag", placeholder="ej: regalo_navidad", key=f"{key_prefix}_newtag")

    # --- SECCIÓN 2: CONTEXTO Y EXPERIENCIA ---
    with st.container(border=True):
        st.markdown("##### ✨ Experiencia y Contexto")
        ce1, ce2, ce3 = st.columns([1, 1.5, 1])
        
        with ce1:
            prioridad_val = default_data.get('prioridad', '---')
            if not prioridad_val: prioridad_val = '---'
            opciones_prio = ["---", "Necesidad", "Deseo"]
            idx_prio = opciones_prio.index(prioridad_val) if prioridad_val in opciones_prio else 0
            
            # Usar selectbox en vez de radio para ahorrar espacio visual con la opcion extra
            prioridad = st.selectbox("Prioridad", opciones_prio, index=idx_prio, key=f"{key_prefix}_prio")
        
        with ce2:
            # Felicidad 0 para "No aplica"
            try:
                felicidad_val = int(default_data.get('felicidad', 0))
            except:
                felicidad_val = 0
                
            felicidad = st.select_slider("Felicidad / Valor", options=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], value=felicidad_val if 0 <= felicidad_val <= 9 else 0, help="0: Sin calificar", format_func=lambda x: "---" if x==0 else str(x), key=f"{key_prefix}_happy")
            if felicidad > 0:
                st.caption("1: Arrepentimiento | 5: Neutro | 9: Increíble")
            else:
                st.caption("Sin calificación")
            
        with ce3:
            st.write("")
            es_fijo = st.checkbox("📌 Gasto Fijo", value=bool(default_data.get('es_fijo', False)), help="Marcado para gastos que ocurren cada mes", key=f"{key_prefix}_fijo")

    # --- SECCIÓN 3: CUENTAS Y DEUDAS ---
    with st.container(border=True):
        st.markdown("##### 🤝 Cuentas y Deudas")
        cd1, cd2, cd3 = st.columns(3)
        
        with cd1:
            opciones_personas = ["---", "Yo", "Mamá", "Hermana", "Familia", "Amigo", "Trabajo", "Otro"]
            pert_val = default_data.get('pertenece_a', '---')
            if not pert_val: pert_val = '---'
            
            idx_pert = opciones_personas.index(pert_val) if pert_val in opciones_personas else 0
            pertenece_a = st.selectbox("¿A quién pertenece?", opciones_personas, index=idx_pert, key=f"{key_prefix}_pert")

        with cd2:
            st.write("")
            es_reembolsable = st.checkbox("🔄 Es Reembolsable", value=bool(default_data.get('es_reembolsable', False)), key=f"{key_prefix}_reemb")
            if pertenece_a != "Yo" and pertenece_a != "---" and not es_reembolsable:
                st.caption(f"💡 ¿{pertenece_a} te lo debe?")

        with cd3:
            # Opciones para deudor (incluyendo vacío)
            opciones_deudor = ["", "Yo", "Mamá", "Hermana", "Familia", "Amigo", "Trabajo", "Otro"]
            
            valor_actual_deudor = default_data.get('deudor', '')
            
            # Sugerencia automática si está vacío
            if valor_actual_deudor == "" and pertenece_a not in ["Yo", "---"]:
                valor_actual_deudor = pertenece_a
            
            idx_deudor = opciones_deudor.index(valor_actual_deudor) if valor_actual_deudor in opciones_deudor else 0
            
            deudor_final = st.selectbox("¿Quién debe pagar?", opciones_deudor, index=idx_deudor, key=f"{key_prefix}_deudor")

            # Reset logic for deudor if not applicable
            if not es_reembolsable and not deudor_final:
                deudor_final = ""

    st.write("")
    
    # --- SECCIÓN 4: NOTAS ---
    nota_val = default_data.get('nota', '')
    nota = st.text_area("Notas / Descripción Adicional", value=nota_val, placeholder="Detalles extra del gasto...", height=68, key=f"{key_prefix}_nota")
    
    # PROCESAR OUTPUT
    lista_final_tags = sel_tags.copy()
    if nuevo_tag.strip():
        lista_final_tags.append(nuevo_tag.strip())
    tags_str_final = ", ".join(sorted(list(set(lista_final_tags))))

    return {
        'nombre_limpio': nombre_limpio,
        'categoria': nueva_cat if nueva_cat != "---" else "",
        'tags': tags_str_final,
        'prioridad': prioridad if prioridad != "---" else "",
        'es_fijo': es_fijo,
        'pertenece_a': pertenece_a if pertenece_a != "---" else "Yo", # Default a Yo para logica interna? O vacio? Mejor Yo para evitar bugs viejos
        'es_reembolsable': es_reembolsable,
        'deudor': deudor_final,
        'felicidad': felicidad, # 0 = '---'
        'nota': nota
    }

# --- MODAL DE EDICIÓN ---
@st.dialog("✏️ Editar Transacción", width="large")
def modal_edicion(index_real, row):
    # --- HEADER INFO ---
    col_title, col_stat = st.columns([3, 1])
    with col_title:
        st.markdown(f"### {row['DESCRIPCION']}")
        st.caption(f"📅 {row['FECHA'].strftime('%d %b %Y, %H:%M')}")
    with col_stat:
        st.markdown(f"<div style='text-align: right; font-size: 24px; font-weight: bold; color: #1E88E5;'>${row['MONTO']:.2f}</div>", unsafe_allow_html=True)
    
    st.write("")
    
    # --- MODO DIVISIÓN ---
    if 'split_mode' not in st.session_state:
        st.session_state.split_mode = False
    
    # Toggle para activar split
    do_split = st.checkbox("🔪 Dividir Transacción", value=st.session_state.split_mode, key="split_toggle")
    st.session_state.split_mode = do_split

    all_tags = obtener_tags_unicos(st.session_state.df)

    if not do_split:
        # ==============================================================================
        # MODO EDICIÓN SIMPLE (ORIGINAL)
        # ==============================================================================
        with st.form("form_edicion", border=False):
            # Preparar datos iniciales
            current_tags_str = str(row['tags']) if pd.notna(row['tags']) else ""
            current_tags = [t.strip() for t in current_tags_str.split(',') if t.strip()]
            
            current_cl = str(row['nombre_limpio']).strip()
            val_nombre = current_cl if current_cl else str(row['DESCRIPCION']).title()

            default_data = {
                'nombre_limpio': val_nombre,
                'categoria': row['categoria'],
                'tags': current_tags,
                'prioridad': row['prioridad'],
                'felicidad': row['felicidad'],
                'es_fijo': row['es_fijo'],
                'pertenece_a': row['pertenece_a'],
                'es_reembolsable': row['es_reembolsable'],
                'deudor': str(row['deudor']).strip() if pd.notna(row['deudor']) else "",
                'nota': str(row['nota']) if pd.notna(row['nota']) else ""
            }

            form_results = render_form_fields("simple", default_data, all_tags)
            
            st.write("")
            guardar_regla = st.checkbox("🤖 Guardar como regla automática (para el futuro)", value=False, help="Si se marca, el sistema recordará este nombre, categoría y tags para transacciones similares.")
            
            if st.form_submit_button("🚀 GUARDAR CAMBIOS", use_container_width=True, type="primary"):
                # Actualizar Dataframe
                for k, v in form_results.items():
                    st.session_state.df.at[index_real, k] = v
                
                st.session_state.df.at[index_real, 'revisado'] = True
                
                # Aprender
                try:
                    attrs_to_learn = None
                    if guardar_regla:
                        attrs_to_learn = {k: v for k, v in form_results.items() if k in ['categoria', 'tags', 'prioridad', 'es_fijo', 'felicidad', 'nota']}
                    
                    rules_module.learn_from_transaction(row['DESCRIPCION'], form_results['nombre_limpio'], attrs_to_learn)
                except Exception as e:
                    print(f"Error aprendiendo reglas: {e}")
                
                st.session_state.df.to_csv("../data/etiquetado/gastos_maestros.csv", index=False)
                st.session_state.data_key += 1
                if 'split_mode' in st.session_state: del st.session_state.split_mode
                st.rerun()

    else:
        # ==============================================================================
        # MODO DIVISIÓN
        # ==============================================================================
        st.info("💡 Divide la transacción. El sistema calculará automáticamente los montos restantes.")
        
        col_controls, col_info = st.columns([1, 1])
        with col_controls:
            num_splits = st.number_input("Número de partes", min_value=2, max_value=10, value=2, step=1)
        
        splits_data = []
        # TRABAJAR CON MAGNITUDES POSITIVAS PARA LA UI
        original_sign = 1 if row['MONTO'] >= 0 else -1
        total_original_abs = abs(row['MONTO'])
        total_asignado_acum_abs = 0.0
        
        # Iterar para generar inputs
        for i in range(int(num_splits)):
            st.markdown(f"**Parte {i+1}**")
            
            # --- Auto-Cálculo del Monto (Magnitud) ---
            default_monto = 0.0
            
            # Key para este monto
            key_monto = f"split_monto_{i}"
            
            remanente_actual_abs = total_original_abs - total_asignado_acum_abs
            
            if i == int(num_splits) - 1:
                # Forzar el value del último input para que sea el remanente exacto
                val_to_render = max(0.0, round(remanente_actual_abs, 2))
            else:
                 # Recuperar valor si existe, o 0.0
                 val_to_render = st.session_state.get(key_monto, 0.0)

            # Input siempre positivo (magnitud)
            monto_val_abs = st.number_input(f"Monto #{i+1} (Magnitud)", min_value=0.0, step=0.01, value=float(val_to_render), key=key_monto)
            total_asignado_acum_abs += monto_val_abs

            # --- Formulario Completo Reutilizado ---
            with st.expander(f"Detalles de Parte {i+1}", expanded=True):
                 current_cl = str(row['nombre_limpio']).strip()
                 val_nombre = current_cl if current_cl else str(row['DESCRIPCION']).title()
                 
                 default_split = {
                    'nombre_limpio': f"{val_nombre} ({i+1})",
                    'categoria': row['categoria'],
                    'tags': [t.strip() for t in str(row['tags']).split(',') if t.strip()] if pd.notna(row['tags']) else [],
                    'prioridad': row['prioridad'],
                    'felicidad': row['felicidad'],
                    'es_fijo': row['es_fijo'],
                    'pertenece_a': row['pertenece_a'],
                    'es_reembolsable': row['es_reembolsable'],
                    'deudor': str(row['deudor']).strip() if pd.notna(row['deudor']) else "",
                    'nota': str(row['nota']) if pd.notna(row['nota']) else ""
                }
                 # Render form
                 split_res = render_form_fields(f"split_{i}", default_split, all_tags)
                 
                 # Agregar el monto con el SIGNO CORRECTO
                 split_res['MONTO'] = monto_val_abs * original_sign
                 # Mantener otros campos vitales
                 split_res['DESCRIPCION'] = row['DESCRIPCION']
                 split_res['FECHA'] = row['FECHA']
                 split_res['TIPO'] = row['TIPO']
                 
                 splits_data.append(split_res)
        
        # Validación de Suma (Magnitudes)
        diff = abs(total_original_abs - total_asignado_acum_abs)
        is_valid = diff < 0.01
        
        st.divider()
        col_res, col_action = st.columns([2, 1])
        
        with col_res:
             st.markdown(f"**Total Original (Abs):** ${total_original_abs:.2f}")
             st.markdown(f"**Total Asignado (Abs):** ${total_asignado_acum_abs:.2f}")
             
             if not is_valid:
                 st.markdown(f"<span style='color:red; font-weight:bold'>⚠️ Diferencia: ${diff:.2f}</span>", unsafe_allow_html=True)
             else:
                 st.markdown("<span style='color:green; font-weight:bold'>✅ Montos cuadran perfectamente</span>", unsafe_allow_html=True)

        with col_action:
            if st.button("💾 GUARDAR DIVISIÓN", type="primary", disabled=not is_valid, use_container_width=True):
                # GENERAR UUID GRUPO
                group_id = str(uuid.uuid4())
                
                nuevas_filas = []
                for s in splits_data:
                    # Copiar datos base de la fila original
                    nueva_fila = row.copy()
                    
                    # Sobrescribir con datos del split
                    for k, v in s.items():
                        nueva_fila[k] = v
                    
                    # Comunes
                    nueva_fila['split_group_id'] = group_id
                    nueva_fila['revisado'] = True
                    
                    nuevas_filas.append(nueva_fila)
                
                # 1. Eliminar fila original del DF
                st.session_state.df = st.session_state.df.drop(index_real)
                
                # 2. Agregar nuevas
                df_nuevas = pd.DataFrame(nuevas_filas)
                st.session_state.df = pd.concat([st.session_state.df, df_nuevas], ignore_index=True)
                
                # 3. Guardar
                st.session_state.df.to_csv("../data/etiquetado/gastos_maestros.csv", index=False)
                
                st.success("Transacción dividida con éxito!")
                st.session_state.data_key += 1
                if 'split_mode' in st.session_state: del st.session_state.split_mode
                st.rerun()

def render_sync_ui():
    """Renderiza la sección de sincronización en el sidebar."""
    with st.sidebar.expander("🔄 Sincronización de Datos", expanded=False):
        st.write("Carga nuevos movimientos desde cuentas y tarjetas.")
        
        # Default date logic
        default_date = datetime.now().date()
        if 'df' in st.session_state and not st.session_state.df.empty:
             val_max = st.session_state.df['FECHA'].max()
             if pd.notna(val_max):
                 default_date = val_max.date()
        
        fecha_corte = st.date_input("Fecha Inicio Nuevos Datos", value=default_date, key="sync_date_input")
        
        overwrite = st.checkbox("⚠️ Sobrescribir desde esta fecha", value=False, help="Si se activa, BORRA todo lo existente desde esa fecha y lo reemplaza con lo nuevo.")
        
        if st.button("Ejecutar Sincronización", type="primary"):
            try:
                with st.spinner("Procesando fuentes de datos..."):
                    # Llamada al módulo de lógica
                    # Nota: Pasamos fecha_corte tal cual (objeto date)
                    added, msg = sincronizacion.sincronizar_db(fecha_corte, overwrite=overwrite)
                
                if msg:
                    st.warning(msg)
                
                if added > 0:
                    st.success(f"✅ Se agregaron {added} registros nuevos.")
                else:
                    st.info("No se encontraron registros nuevos para agregar con los criterios seleccionados.")
                
                # Recargar datos en la app
                st.session_state.df = cargar_datos()
                st.session_state.data_key += 1
                if 'fecha_input' in st.session_state: del st.session_state.fecha_input
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Error en sincronización: {e}")


# --- MAIN ---
def main():
    if 'df' not in st.session_state:
        st.session_state.df = cargar_datos()
    
    # Inicializar key para tabla
    if 'data_key' not in st.session_state:
        st.session_state.data_key = 0

    df = st.session_state.df
    if df.empty: return

    # Filtros Sidebar
    st.sidebar.header("📅 Navegación")
    
    # Insertar Sync UI aquí
    render_sync_ui()
    st.sidebar.divider()

    fechas = sorted(df['FECHA'].dt.date.unique())
    if not fechas:
        st.warning("No hay fechas.")
        return
        
    # Lógica de navegación segura con session_state
    if 'fecha_input' not in st.session_state:
        st.session_state.fecha_input = fechas[-1] # Default última fecha

    # Callback para actualizar fecha
    def actualizar_fecha():
        st.session_state.fecha_input = st.session_state.fecha_widget

    # Calendario vinculado
    fecha_sel = st.sidebar.date_input(
        "Selecciona una fecha", 
        value=st.session_state.fecha_input, 
        min_value=fechas[0], 
        max_value=fechas[-1], 
        format="YYYY-MM-DD",
        key="fecha_widget",
        on_change=actualizar_fecha
    )
    
    # Asegurar sync si cambia externa (aunque date_input con key maneja mucho)
    if fecha_sel != st.session_state.fecha_input:
         st.session_state.fecha_input = fecha_sel

    # Validar existencia de datos
    if st.session_state.fecha_input not in fechas:
        fechas_menores = [f for f in fechas if f <= st.session_state.fecha_input]
        st.session_state.fecha_input = fechas_menores[-1] if fechas_menores else fechas[0]
        st.rerun()

    current_date = st.session_state.fecha_input

    # Botón para ir al siguiente día con datos
    idx_actual = fechas.index(current_date) if current_date in fechas else 0
    
    if idx_actual < len(fechas) - 1:
        def next_day():
            st.session_state.fecha_input = fechas[idx_actual + 1]
            # No necesitamos rerun explícito, el cambio de estado gatilla rerun al salir del callback
            
        st.sidebar.button("➡️ Siguiente día con datos", on_click=next_day)

    # Vista Data
    mask = df['FECHA'].dt.date == current_date
    df_view = df.loc[mask].copy()

    pendientes = len(df_view[df_view['revisado']==False])
    st.sidebar.metric("Pendientes", pendientes)

    # Tabla Display
    df_display = df_view[['FECHA', 'DESCRIPCION', 'MONTO', 'categoria', 'nombre_limpio', 'revisado', 'nota', 'es_reembolsable', 'tags']].copy()
    df_display['Hora'] = df_display['FECHA'].dt.strftime('%H:%M')
    df_display['Estado'] = df_display['revisado'].apply(lambda x: "✅" if x else "📝")
    df_display = df_display[['Estado', 'Hora', 'MONTO', 'nombre_limpio', 'categoria',"tags","nota","es_reembolsable"]]

    # Calculo Totales
    total_dia = df_view['MONTO'].sum()
    
    # Header con metricas
    c_head1, c_head2 = st.columns([3, 1])
    with c_head1:
        st.subheader(f"Transacciones del {current_date.strftime('%d-%m-%Y')}")
    with c_head2:
        st.markdown(f"<div style='text-align: right; font-size: 20px; font-weight: bold; color: {'green' if total_dia >= 0 else 'red'};'>Total: ${total_dia:,.2f}</div>", unsafe_allow_html=True)

    event = st.dataframe(
        df_display,
        on_select="rerun",
        selection_mode="single-row",
        use_container_width=True,
        hide_index=True,
        height=500,
        key=f"data_table_{st.session_state.data_key}" # Key dinámica para resetear selección
    )

    if event.selection.rows:
        idx_visual = event.selection.rows[0]
        idx_real = df_view.index[idx_visual]
        row_real = df.loc[idx_real]
        modal_edicion(idx_real, row_real)

if __name__ == "__main__":
    main()