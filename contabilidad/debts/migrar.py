"""
Script de migración para importar deudas existentes desde un DataFrame
a la nueva aplicación de gestión de deudas en Supabase.
"""

import pandas as pd
from datetime import datetime
from contabilidad.debts.escritura import (
    obtener_o_crear_deudor,
    crear_deudas_bulk,
    crear_deuda
)

def migrar_deudas_desde_df(df: pd.DataFrame, dry_run: bool = True):
    """
    Migra deudas desde un DataFrame al sistema de Supabase.
    
    El DataFrame debe tener las siguientes columnas:
    - Tipo: 'Doy' (deuda) o 'Debo' (pago recibido)
    - Persona o PERSONA_NOTION: Nombre del deudor
    - NOTION: Monto
    - DESCRIPCION_NOTION: Descripción
    - FECHA_REAL: Fecha del gasto/pago
    
    Args:
        df: DataFrame con los datos de deudas y pagos
        dry_run: Si True, solo muestra lo que haría sin ejecutar
        
    Returns:
        Dict con estadísticas de la migración
    """
    print("=" * 60)
    print("MIGRACIÓN DE DEUDAS Y PAGOS")
    print("=" * 60)
    
    # Validar columnas requeridas
    if 'Persona' not in df.columns and 'PERSONA_NOTION' in df.columns:
        df = df.rename(columns={'PERSONA_NOTION': 'Persona'})
    
    columnas_requeridas = ['Tipo', 'Persona', 'NOTION', 'DESCRIPCION_NOTION', 'FECHA_REAL']
    for col in columnas_requeridas:
        if col not in df.columns:
            raise ValueError(f"Columna '{col}' no encontrada en el DataFrame")
    
    # Separar deudas y pagos
    df_deudas = df[df['Tipo'] == 'Doy'].copy()
    df_pagos = df[df['Tipo'] == 'Debo'].copy()
    
    print(f"\n📊 Resumen:")
    print(f"   Total deudas (Doy): {len(df_deudas)}")
    print(f"   Total pagos (Debo): {len(df_pagos)}")
    
    # Obtener deudores únicos
    deudores_unicos = df['Persona'].unique()
    print(f"\n👥 Deudores únicos: {len(deudores_unicos)}")
    
    for nombre in deudores_unicos:
        deudas_persona = df_deudas[df_deudas['Persona'] == nombre]
        pagos_persona = df_pagos[df_pagos['Persona'] == nombre]
        total_deudas = deudas_persona['NOTION'].sum()
        # Los pagos (Debo) vienen con signo negativo, usar valor absoluto
        total_pagos = pagos_persona['NOTION'].abs().sum()
        pendiente = total_deudas - total_pagos
        
        print(f"   - {nombre}:")
        print(f"      Deudas: {len(deudas_persona)} (${total_deudas:.2f})")
        print(f"      Pagos: {len(pagos_persona)} (${total_pagos:.2f})")
        print(f"      Pendiente: ${pendiente:.2f}")
    
    if dry_run:
        print("\n DRY RUN - No se insertarán datos reales")
        print("\nPara ejecutar la migración real, llama:")
        print("migrar_deudas_desde_df(df, dry_run=False)")
        return {
            'dry_run': True,
            'total_deudas': len(df_deudas),
            'total_pagos': len(df_pagos),
            'deudores': len(deudores_unicos)
        }
    
    # PASO 0: Limpiar base de datos
    print("\n🗑️ PASO 0: Limpiando base de datos...")
    from contabilidad.debts.limpiar import limpiar_base_datos
    resultado_limpieza = limpiar_base_datos()
    if resultado_limpieza.get('error'):
        print(f"❌ Error limpiando BD: {resultado_limpieza['error']}")
        return resultado_limpieza
    
    # PASO 1: Crear/obtener deudores
    print("\n🔄 PASO 1: Creando/obteniendo deudores...")
    deudores_map = {}
    for nombre in deudores_unicos:
        try:
            deudor = obtener_o_crear_deudor(nombre)
            deudores_map[nombre] = deudor
            print(f"   ✓ {nombre} -> ID: {deudor['id']}")
        except Exception as e:
            print(f"   ✗ Error con {nombre}: {e}")
            return {'error': str(e)}
    
    # PASO 2: Insertar todas las deudas (sin marcar como pagadas aún)
    print("\n PASO 2: Insertando deudas...")
    deudas_insertadas_map = {}  # {deudor_nombre: [deudas_insertadas]}
    
    for nombre in deudores_unicos:
        deudas_persona = df_deudas[df_deudas['Persona'] == nombre].copy()
        if len(deudas_persona) == 0:
            continue
            
        deudor = deudores_map[nombre]
        deudas_para_insertar = []
        
        for idx, row in deudas_persona.iterrows():
            fecha_gasto = pd.to_datetime(row['FECHA_REAL'])
            deuda_data = {
                'titulo': str(row['DESCRIPCION_NOTION']),
                'monto': float(row['NOTION']),
                'deudor_id': deudor['id'],
                'fecha_gasto': fecha_gasto,
                'pagada': False,
            }
            deudas_para_insertar.append(deuda_data)
        
        # Insertar en batch
        try:
            count = crear_deudas_bulk(deudas_para_insertar)
            print(f"   ✓ {nombre}: {count} deudas insertadas")
            
            # Obtener las deudas recién insertadas para marcarlas después
            from contabilidad.debts.reading import obtener_deudas_por_deudor
            deudas_insertadas = obtener_deudas_por_deudor(deudor['id'], solo_pendientes=False)
            deudas_insertadas_map[nombre] = deudas_insertadas
            
        except Exception as e:
            print(f"   ✗ Error insertando deudas de {nombre}: {e}")
            return {'error': str(e)}
    
    # PASO 3: Procesar pagos y marcar deudas como pagadas
    print("\n PASO 3: Procesando pagos (marcando deudas como pagadas)...")
    
    from contabilidad.debts.escritura import marcar_deuda_como_pagada
    
    total_pagos_procesados = 0
    total_deudas_saldadas = 0
    
    for nombre in deudores_unicos:
        pagos_persona = df_pagos[df_pagos['Persona'] == nombre].copy()
        if len(pagos_persona) == 0:
            continue
        
        # Ordenar pagos por fecha
        pagos_persona = pagos_persona.sort_values('FECHA_REAL')
        
        # Obtener deudas de esta persona ordenadas por fecha (más antiguas primero)
        deudas_persona = deudas_insertadas_map.get(nombre)
        if deudas_persona is None or len(deudas_persona) == 0:
            print(f"    {nombre}: No hay deudas para saldar")
            continue
        
        # Convertir a DataFrame para facilitar el ordenamiento
        deudas_df = deudas_persona.sort_values('fecha_gasto', ascending=True).copy()
        deudas_pendientes = deudas_df[~deudas_df['pagada']].copy()
        
        print(f"\n   👤 {nombre}:")
        print(f"      Pagos a procesar: {len(pagos_persona)}")
        print(f"      Deudas pendientes: {len(deudas_pendientes)}")
        
        # Variable para acumular sobrante entre pagos
        sobrante_acumulado = 0.0
        fechas_pagadas = []  # Para rastrear el rango de fechas
        
        # Procesar cada pago
        for _, pago in pagos_persona.iterrows():
            # Los pagos (Debo) vienen con signo negativo, usar valor absoluto
            monto_pago = abs(float(pago['NOTION']))
            fecha_pago = pd.to_datetime(pago['FECHA_REAL'])
            
            # Sumar el sobrante acumulado del pago anterior
            monto_restante = monto_pago + sobrante_acumulado
            
            if sobrante_acumulado > 0:
                print(f"\n       Pago de ${monto_pago:.2f} + ${sobrante_acumulado:.2f} (sobrante) = ${monto_restante:.2f} el {fecha_pago.strftime('%Y-%m-%d')}")
            else:
                print(f"\n       Pago de ${monto_pago:.2f} el {fecha_pago.strftime('%Y-%m-%d')}")
            
            # Marcar deudas como pagadas hasta agotar el monto
            deudas_saldadas_este_pago = 0
            
            for idx, deuda in deudas_pendientes.iterrows():
                if monto_restante <= 0:
                    break
                
                monto_deuda = float(deuda['monto'])
                
                if monto_restante >= monto_deuda:
                    # Marcar como pagada completamente
                    try:
                        marcar_deuda_como_pagada(deuda['id'], fecha_pago=fecha_pago)
                        monto_restante -= monto_deuda
                        deudas_saldadas_este_pago += 1
                        total_deudas_saldadas += 1
                        fechas_pagadas.append(deuda['fecha_gasto'])  # Guardar fecha
                        print(f"         ✓ Saldada: {deuda['titulo']} (${monto_deuda:.2f})")
                        
                        # Marcar como pagada en el DataFrame local
                        deudas_pendientes = deudas_pendientes.drop(idx)
                        
                    except Exception as e:
                        print(f"         ✗ Error marcando deuda: {e}")
                else:
                    # El pago no cubre esta deuda, se agota aquí
                    print(f"          Pago insuficiente para: {deuda['titulo']} (${monto_deuda:.2f})")
                    print(f"            Sobrante del pago: ${monto_restante:.2f}")
                    break
            
            # Actualizar sobrante acumulado para el siguiente pago
            sobrante_acumulado = monto_restante
            
            if monto_restante > 0 and deudas_saldadas_este_pago > 0:
                print(f"          Sobrante para siguiente pago: ${monto_restante:.2f}")
            
            total_pagos_procesados += 1
        
        # Mostrar rango de fechas de deudas saldadas
        if len(fechas_pagadas) > 0:
            fecha_min = min(fechas_pagadas)
            fecha_max = max(fechas_pagadas)
            print(f"\n      📅 Deudas pagadas del {fecha_min.strftime('%Y-%m-%d')} al {fecha_max.strftime('%Y-%m-%d')}")
        
        # Si quedó sobrante final, mostrarlo
        if sobrante_acumulado > 0:
            print(f"\n      💰 Sobrante final no utilizado: ${sobrante_acumulado:.2f}")
    
    print(f"\n✅ MIGRACIÓN COMPLETADA")
    print(f"   Deudas insertadas: {sum(len(deudas_insertadas_map.get(n, [])) for n in deudores_unicos)}")
    print(f"   Pagos procesados: {total_pagos_procesados}")
    print(f"   Deudas saldadas: {total_deudas_saldadas}")
    print(f"   Deudores procesados: {len(deudores_map)}")
    
    # VERIFICACIÓN: Consultar BD para confirmar
    print("\n" + "="*60)
    print("VERIFICACIÓN DE DATOS EN SUPABASE")
    print("="*60)
    
    try:
        from contabilidad.debts.reading import (
            obtener_resumen_por_deudor,
            obtener_todas_deudas
        )
        
        # Obtener resumen
        print("\n📊 RESUMEN ACTUAL EN BASE DE DATOS:")
        resumen = obtener_resumen_por_deudor(solo_pendientes=True)
        
        if len(resumen) > 0:
            print(f"\n{'Deudor':<20} {'Deudas':<10} {'Total Pendiente':<15}")
            print("-" * 50)
            for _, row in resumen.iterrows():
                print(f"{row['deudor_nombre']:<20} {row['cantidad_deudas']:<10} ${row['total_deuda']:>12.2f}")
            
            total_general = resumen['total_deuda'].sum()
            print("-" * 50)
            print(f"{'TOTAL GENERAL':<20} {resumen['cantidad_deudas'].sum():<10} ${total_general:>12.2f}")
        else:
            print("   No hay deudas pendientes (todas fueron saldadas)")
        
        # Verificar deudas pagadas
        print("\n💰 DEUDAS PAGADAS:")
        todas_deudas = obtener_todas_deudas(solo_pendientes=False)
        deudas_pagadas = todas_deudas[todas_deudas['pagada'] == True]
        
        if len(deudas_pagadas) > 0:
            print(f"   Total de deudas pagadas: {len(deudas_pagadas)}")
            print(f"   Monto total pagado: ${deudas_pagadas['monto'].sum():.2f}")
            
            # Mostrar por deudor
            pagadas_por_deudor = deudas_pagadas.groupby('deudor_id').agg({
                'monto': ['count', 'sum']
            }).reset_index()
            
            # Obtener nombres de deudores
            from contabilidad.debts.reading import obtener_todos_deudores
            deudores_df = obtener_todos_deudores()
            
            print("\n   Desglose por deudor:")
            for deudor_id in pagadas_por_deudor['deudor_id']:
                deudor_nombre = deudores_df[deudores_df['id'] == deudor_id]['nombre'].iloc[0]
                deudor_pagadas = deudas_pagadas[deudas_pagadas['deudor_id'] == deudor_id]
                cantidad = len(deudor_pagadas)
                total = deudor_pagadas['monto'].sum()
                print(f"      {deudor_nombre}: {cantidad} deuda(s) - ${total:.2f}")
        else:
            print("   No hay deudas marcadas como pagadas")
        
        print("\n✅ Verificación completada")
        
    except Exception as e:
        print(f"\n⚠️ Error en verificación: {e}")
        print("   Los datos fueron migrados, pero hubo un problema al verificar")
    
    return {
        'success': True,
        'deudas_insertadas': sum(len(deudas_insertadas_map.get(n, [])) for n in deudores_unicos),
        'pagos_procesados': total_pagos_procesados,
        'deudas_saldadas': total_deudas_saldadas,
        'deudores_creados': len(deudores_map),
    }


def ejemplo_uso():
    """Ejemplo de cómo usar el script de migración"""
    
    # Crear un DataFrame de ejemplo (reemplaza esto con tu DataFrame real)
    data = {
        'Tipo': ['Doy', 'Doy', 'Doy', 'Doy', 'Doy'],
        'NOTION': [210.00, 20.82, 45.00, 100.00, 7.00],
        'Persona': ['Madre', 'Madre', 'Madre', 'Madre', 'Ñaña'],
        'DESCRIPCION_NOTION': [
            'Pago dermatologo 30/9',
            'Medicamentos 23/10',
            'Banco Seguro',
            'Inversion',
            'Milanesa Uber'
        ],
        'FECHA_CREACION': pd.to_datetime([
            '2024-11-20 03:07:00',
            '2024-11-24 15:00:00',
            '2024-11-20 03:12:00',
            '2024-11-30 03:26:00',
            '2024-11-20 03:18:00'
        ]),
        'FECHA_REAL': pd.to_datetime([
            '2024-09-30',
            '2024-10-23',
            '2024-11-14',
            '2024-11-18',
            '2024-11-20'
        ]),
    }
    
    df = pd.DataFrame(data)
    
    # Primero hacer un dry run
    print("Ejecutando DRY RUN...")
    resultado = migrar_deudas_desde_df(df, dry_run=True)
    print("\nResultado:", resultado)
    
    # Si todo se ve bien, ejecutar la migración real
    # resultado = migrar_deudas_desde_df(df, dry_run=False)


if __name__ == "__main__":
    ejemplo_uso()
