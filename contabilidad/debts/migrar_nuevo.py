"""
Script de migracion OPTIMIZADO para el nuevo sistema Supabase (Deudas + Pagos + Detalles).
Este script:
1. Lee un DataFrame.
2. Crea deudores si no existen.
3. Inserta TODAS las deudas ('Doy') como pendientes.
4. Inserta TODOS los pagos ('Debo').
5. Distribuye automaticamente los fondos de los pagos a las deudas mas antiguas (FIFO) del mismo deudor.
"""

import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
from contabilidad.debts.escritura import (
    obtener_o_crear_deudor,
    crear_deudas_bulk,
    supabase # Cliente directo por si acaso
)

def migrar_deudas_desde_df(df: pd.DataFrame, dry_run: bool = True):
    """
    Migra deudas desde un DataFrame al sistema de Supabase con logica de PAGOS REALES.
    
    El DataFrame debe tener las siguientes columnas:
    - Tipo: 'Doy' (deuda) o 'Debo' (pago recibido)
    - Persona o PERSONA_NOTION: Nombre del deudor
    - NOTION: Monto
    - DESCRIPCION_NOTION: Descripcion
    - FECHA_REAL: Fecha del gasto/pago
    
    Args:
        df: DataFrame con los datos de deudas y pagos
        dry_run: Si True, solo muestra lo que haria sin ejecutar
        
    Returns:
        Dict con estadisticas de la migracion
    """
    print("=" * 60)
    print("MIGRACION V3 - SISTEMA DE PAGOS INTELIGENTE")
    print("=" * 60)
    
    # ---------------------------------------------------------
    # 0. Preparacion y Validacion
    # ---------------------------------------------------------
    if 'Persona' not in df.columns and 'PERSONA_NOTION' in df.columns:
        df = df.rename(columns={'PERSONA_NOTION': 'Persona'})
    
    required_cols = ['Tipo', 'Persona', 'NOTION', 'DESCRIPCION_NOTION', 'FECHA_REAL']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Falta columna: {col}")

    # Separar
    df_deudas = df[df['Tipo'] == 'Doy'].copy()
    df_pagos = df[df['Tipo'] == 'Debo'].copy()
    
    deudores_uniques = df['Persona'].unique()
    
    print(f"Deudas encontradas: {len(df_deudas)}")
    print(f"Pagos encontrados: {len(df_pagos)}")
    print(f"Deudores unicos: {len(df['Persona'].unique())}")

    # ---------------------------------------------------------
    # 0.5 Previsualizacion de Saldos (Teorico)
    # ---------------------------------------------------------
    print("\n" + "-"*40)
    print("PREVISUALIZACION DE SALDOS (TEORICO)")
    print("-" * 40)
    print(f"{'DEUDOR':<20} | {'DOY':>10} | {'DEBO':>10} | {'NETO':>10}")
    print("-" * 55)
    
    for nombre in sorted(df['Persona'].unique()):
        tot_doy = df_deudas[df_deudas['Persona'] == nombre]['NOTION'].sum()
        # Los 'Debo' usualmente ya vienen negativos o positivos dependiendo del origen,
        # pero en la logica de migracion original se tomaba el abs().
        tot_debo = abs(df_pagos[df_pagos['Persona'] == nombre]['NOTION'].sum())
        neto = tot_doy - tot_debo
        print(f"{nombre:<20} | {tot_doy:>10.2f} | {tot_debo:>10.2f} | {neto:>10.2f}")
    print("-" * 55)

    if dry_run:
        print("\n[DRY RUN] No se realizaran cambios. Ejecuta con dry_run=False para aplicar.")
        return {'status': 'dry_run'}

    # ---------------------------------------------------------
    # 0.7 Limpiar Base de Datos
    # ---------------------------------------------------------
    from contabilidad.debts.limpiar import limpiar_base_datos
    if not limpiar_base_datos():
        print("\nERROR: No se pudo limpiar la base de datos. Deteniendo migracion por seguridad.")
        return {'status': 'error', 'message': 'Limpieza fallida'}
    
    print("\nDATABASE LIMPIA - Iniciando carga de datos...")

    # ---------------------------------------------------------
    # 1. Gestion de Deudores
    # ---------------------------------------------------------
    print("\n1. Sincronizando Deudores...")
    mapa_deudores = {} # Nombre -> ID
    
    for nombre in deudores_uniques:
        try:
            d = obtener_o_crear_deudor(nombre)
            mapa_deudores[nombre] = d['id']
            print(f"   v {nombre} (ID: {d['id'][:8]}...)")
        except Exception as e:
            print(f"   x Error con {nombre}: {e}")
            return {'error': str(e)}

    # ---------------------------------------------------------
    # 2. Insertar Deudas (Todas nacen PENDIENTES)
    # ---------------------------------------------------------
    print("\n2. Insertando Deudas...")
    # Agrupamos todas las deudas para insert bulk optimizado o por persona
    
    # Trackeamos IDs de deudas insertadas para luego asignar pagos
    # Estructura: deudas_por_persona[deudor_id] = [ {id, monto_original, saldo, fecha} ]
    deudas_activas_por_id = {} 

    for nombre, deudor_id in mapa_deudores.items():
        subset = df_deudas[df_deudas['Persona'] == nombre]
        if subset.empty: continue
        
        payloads = []
        for _, row in subset.iterrows():
            payloads.append({
                'titulo': str(row['DESCRIPCION_NOTION']),
                'monto': float(row['NOTION']),
                'deudor_id': deudor_id,
                'fecha_gasto': pd.to_datetime(row['FECHA_REAL'])
            })
            
        # Insertar
        try:
            count = crear_deudas_bulk(payloads)
            print(f"   v {nombre}: {count} deudas creadas")
        except Exception as e:
            print(f"   x Error insertando deudas de {nombre}: {e}")

    # ---------------------------------------------------------
    # 2.5 Recuperar Deudas Frescas (con IDs generados)
    # ---------------------------------------------------------
    # Fetch de TODO lo insertado (o pendiente) para hacer el macheo en memoria
    # Es mas seguro leer de la BD para tener los IDs reales
    print("\nRecargando deudas desde BD para procesar pagos...")
    
    from contabilidad.debts.reading import obtener_todas_deudas
    all_deudas_db = obtener_todas_deudas(solo_pendientes=True) # Trae DF
    
    # ---------------------------------------------------------
    # 3. Procesar Pagos y Distribucion (FIFO)
    # ---------------------------------------------------------
    print("\n3. Procesando Pagos y Asignaciones...")
    
    stats_pagos = 0
    stats_asig = 0
    
    for nombre, deudor_id in mapa_deudores.items():
        # Pagos de este deudor
        subset_pagos = df_pagos[df_pagos['Persona'] == nombre].sort_values('FECHA_REAL')
        if subset_pagos.empty: continue
        
        # Deudas de este deudor (del DF recargado)
        mis_deudas = all_deudas_db[all_deudas_db['deudor_id'] == deudor_id].sort_values('fecha_gasto').to_dict('records')
        
        total_debo_deudor = abs(subset_pagos['NOTION'].sum())
        running_debo = 0
        running_asignado = 0 # Acumulativo de lo que realmente se ha bajado de la deuda
        
        print(f"\n--- Detalle de pagos para {nombre} (Total a registrar: ${total_debo_deudor:.2f}) ---")
        
        for _, row_pago in subset_pagos.iterrows():
            monto_pago = abs(float(row_pago['NOTION']))
            fecha_pago_dt = pd.to_datetime(row_pago['FECHA_REAL'])
            fecha_pago_str = fecha_pago_dt.strftime('%Y-%m-%d')
            
            # Calcular saldo pendiente ACTUAL (antes de este pago)
            saldo_pendiente_antes = sum(deuda.get('saldo_vivo', float(deuda['saldo_pendiente'])) for deuda in mis_deudas)
            
            running_debo += monto_pago
            debo_restante = total_debo_deudor - running_debo
            
            print(f"   -> Pago de ${monto_pago:<8} | Pendiente: ${saldo_pendiente_antes:<9.2f} | Falta registrar: ${debo_restante:<9.2f} ({fecha_pago_str})")
            
            # A. Insertar el Pago en BD
            res_pago = supabase.table('pagos').insert({
                'deudor_id': deudor_id,
                'monto_total': monto_pago,
                'fecha_pago': fecha_pago_str
            }).execute()
            
            if not res_pago.data:
                print("      x Error creando pago")
                continue
                
            pago_id = res_pago.data[0]['id']
            stats_pagos += 1
            
            # B. Distribuir dinero entre deudas (Logica in Memory -> Writes)
            remanente_pago = monto_pago
            
            for deuda in mis_deudas:
                if remanente_pago <= 0.001: break
                
                saldo_actual = deuda.get('saldo_vivo', float(deuda['saldo_pendiente'])) 
                if saldo_actual <= 0.001: continue 
                
                match_amount = min(remanente_pago, saldo_actual)
                
                # Crear Detalle
                supabase.table('detalle_pagos').insert({
                    'pago_id': pago_id,
                    'deuda_id': deuda['id'],
                    'monto_asignado': match_amount
                }).execute()
                
                # Update locals
                remanente_pago -= match_amount
                deuda['saldo_vivo'] = saldo_actual - match_amount
                running_asignado += match_amount
                stats_asig += 1
                
                print(f"      - Asignado ${match_amount:.2f} a '{deuda['titulo']}' (Cumu. Asignado: ${running_asignado:.2f})")

            # C. Consultar TOTAL REAL en BD tras el pago
            try:
                res_v = supabase.table('vista_estado_deudas').select('saldo_pendiente').eq('deudor_id', deudor_id).execute()
                total_db = sum(float(x['saldo_pendiente']) for x in res_v.data)
                print(f"      => TOTAL REAL BD para {nombre}: ${total_db:.2f}")
            except Exception as e:
                print(f"      x Error consultando total BD: {e}")

    # ---------------------------------------------------------
    # 4. Resumen Final
    # ---------------------------------------------------------
    print("\n" + "="*60)
    print("RESUMEN FINAL DE ESTADO DE CUENTA")
    print("="*60)
    
    # Recargar estado final desde la vista
    from contabilidad.debts.reading import obtener_resumen_por_deudor
    
    try:
        resumen = obtener_resumen_por_deudor(solo_pendientes=True)
        
        if not resumen.empty:
            print(f"\n{'DEUDOR':<20} | {'DEUDAS PEND':<12} | {'SALDO PENDIENTE':<15}")
            print("-" * 55)
            for _, row in resumen.iterrows():
                print(f"{row['deudor_nombre']:<20} | {row['cantidad_deudas']:<12} | ${row['total_deuda']:>12.2f}")
            print("-" * 55)
            print(f"{'TOTAL':<20} | {resumen['cantidad_deudas'].sum():<12} | ${resumen['total_deuda'].sum():>12.2f}")
        else:
            print("\nTodo esta saldado! No hay deudas pendientes.")
            
    except Exception as e:
        print(f"Error generando resumen: {e}")

    print("\nMIGRACION COMPLETADA EXITOSAMENTE")
    return {'status': 'success', 'pagos_creados': stats_pagos, 'asignaciones': stats_asig}

if __name__ == "__main__":
    print("Script listo. Importar y usar migrar_deudas_desde_df(df).")
