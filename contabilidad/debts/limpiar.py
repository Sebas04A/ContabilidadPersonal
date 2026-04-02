"""
Funciones de utilidad para limpiar la base de datos de Supabase.
"""

from supabase import create_client, Client

# Credenciales de Supabase
SUPABASE_URL = "https://rcmdzvbxerumzxvnubfo.supabase.co"
SUPABASE_KEY = "sb_publishable_CZL2FVo5YLTnUPeyAq7S-w_lfExK_yw"

# Cliente de Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def obtener_conteos():
    """Retorna un dict con el numero de filas en cada tabla."""
    return {
        'deudores': supabase.table('deudores').select('*', count='exact', head=True).execute().count,
        'deudas': supabase.table('deudas').select('*', count='exact', head=True).execute().count,
        'pagos': supabase.table('pagos').select('*', count='exact', head=True).execute().count,
        'detalle_pagos': supabase.table('detalle_pagos').select('*', count='exact', head=True).execute().count,
    }

def limpiar_base_datos():
    """
    Elimina TODOS los registros y verifica que las tablas queden vacias.
    """
    print("INICIANDO LIMPIEZA DE BASE DE DATOS...")
    
    try:
        # Conteos iniciales
        iniciales = obtener_conteos()
        print(f"   Conteos iniciales: {iniciales}")
        
        # Eliminar en orden de dependencia
        tablas = ['detalle_pagos', 'pagos', 'deudas', 'deudores']
        for tabla in tablas:
            count = iniciales.get(tabla, 0)
            if count and count > 0:
                print(f"   Eliminando {count} registros de {tabla}...")
                # El neq con un UUID inexistente es para forzar que PostgREST ejecute el delete
                supabase.table(tabla).delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
        
        # Verificacion final
        finales = obtener_conteos()
        print(f"   Conteos finales: {finales}")
        
        esta_limpio = all(v == 0 for v in finales.values())
        if esta_limpio:
            print("   CONFIRMADO: La base de datos esta completamente vacia.")
        else:
            print("   ADVERTENCIA: No se pudieron eliminar todos los registros.")
            print(f"   Tablas remanentes: {[k for k,v in finales.items() if v > 0]}")
            
        return esta_limpio
        
    except Exception as e:
        print(f"   Error durante la limpieza: {e}")
        return False

if __name__ == "__main__":
    confirm = input("Escribe 'ELIMINAR TODO' para proceder: ")
    if confirm == 'ELIMINAR TODO':
        limpiar_base_datos()
    else:
        print("Operacion cancelada.")
