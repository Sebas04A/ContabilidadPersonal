"""
Ejemplo práctico de migración de deudas.
Usa este archivo para migrar tus datos reales.
"""

import pandas as pd
from contabilidad.deudas.migrar import migrar_deudas_desde_df

def migrar_mis_deudas():
    """
    Función principal para migrar tus deudas.
    Ajusta esta función según tus datos.
    """
    
    # OPCIÓN 1: Cargar desde CSV
    # df = pd.read_csv('ruta/a/tus/datos.csv')
    
    # OPCIÓN 2: Cargar desde Excel
    # df = pd.read_excel('ruta/a/tus/datos.xlsx')
    
    # OPCIÓN 3: DataFrame en memoria (ejemplo con tus datos)
    # Incluye tanto deudas (Doy) como pagos (Debo)
    data = {
        'Tipo': ['Doy', 'Doy', 'Doy', 'Doy', 'Doy', 'Debo', 'Debo'],
        'NOTION': [210.00, 20.82, 45.00, 100.00, 7.00, 230.82, 150.00],
        'Persona': ['Madre', 'Madre', 'Madre', 'Madre', 'Ñaña', 'Madre', 'Madre'],
        'DESCRIPCION_NOTION': [
            'Pago dermatologo 30/9',
            'Medicamentos 23/10',
            'Banco Seguro',
            'Inversion',
            'Milanesa Uber',
            'Pago recibido Nov',
            'Pago recibido Dic'
        ],
        'FECHA_CREACION': [
            '2024-11-20 03:07:00',
            '2024-11-24 15:00:00',
            '2024-11-20 03:12:00',
            '2024-11-30 03:26:00',
            '2024-11-20 03:18:00',
            '2024-11-25 10:00:00',
            '2024-12-15 10:00:00'
        ],
        'FECHA_REAL': [
            '2024-09-30',
            '2024-10-23',
            '2024-11-14',
            '2024-11-18',
            '2024-11-20',
            '2024-11-25',
            '2024-12-15'
        ],
        'PERSONA_NOTION': ['Madre', 'Madre', 'Madre', 'Madre', 'Ñaña', 'Madre', 'Madre'],
        'NOTIONCUM': [210.00, 230.82, 275.82, 375.82, 382.82, 152.00, 2.00]
    }
    
    df = pd.DataFrame(data)
    
    # Convertir fechas
    df['FECHA_CREACION'] = pd.to_datetime(df['FECHA_CREACION'])
    df['FECHA_REAL'] = pd.to_datetime(df['FECHA_REAL'])
    
    print("📊 DATOS CARGADOS")
    print(f"Total filas: {len(df)}")
    print(f"\nPrimeras filas:")
    print(df.head())
    
    # PASO 1: DRY RUN (simulación)
    print("\n" + "="*60)
    print("PASO 1: SIMULACIÓN (DRY RUN)")
    print("="*60)
    
    resultado_dry = migrar_deudas_desde_df(df, dry_run=True)
    print(f"\nResultado de simulación: {resultado_dry}")
    
    # PASO 2: Confirmar antes de migrar
    print("\n" + "="*60)
    respuesta = input("\n¿Deseas ejecutar la migración REAL? (escribe 'SI' para confirmar): ")
    
    if respuesta.upper() != 'SI':
        print("❌ Migración cancelada")
        return
    
    # PASO 3: Migración real
    print("\n" + "="*60)
    print("PASO 2: MIGRACIÓN REAL")
    print("="*60)
    
    resultado_real = migrar_deudas_desde_df(df, dry_run=False)
    
    print("\n" + "="*60)
    print("RESULTADO FINAL")
    print("="*60)
    print(resultado_real)
    
    if resultado_real.get('success'):
        print("\n✅ ¡MIGRACIÓN COMPLETADA EXITOSAMENTE!")
        print(f"   Deudas insertadas: {resultado_real['deudas_insertadas']}")
        print(f"   Deudores procesados: {resultado_real['deudores_creados']}")
        
        # Verificar datos
        from contabilidad.deudas.lectura import obtener_resumen_por_deudor
        print("\n📊 RESUMEN POST-MIGRACIÓN:")
        resumen = obtener_resumen_por_deudor()
        print(resumen)
    else:
        print(f"\n❌ Error en la migración: {resultado_real.get('error')}")


if __name__ == "__main__":
    migrar_mis_deudas()
