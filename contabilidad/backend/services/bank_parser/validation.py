
from collections import Counter
from contabilidad.config import CUENTAS_COLUMNAS
import numpy as np
import pandas as pd
import os

def imprimir_cambios(df_nuevo,
                     path_datos_anteriores,
                     columnas_base=CUENTAS_COLUMNAS):
    """
    only notebook
    Imprime:
      1) Filas nuevas/eliminadas por fecha.
      2) Para fechas comunes, compara multiconjuntos de filas
         (sin importar el orden) y para cada diferencia:
           - Si es un cambio (un viejo - un nuevo), muestra
             columna por columna el valor antiguo y el nuevo.
           - Si una fila entera falta o sobra, la marca como
             "ELIMINADA" o "NUEVA".
    """
    # 1) Prepara columnas
    cols = [c for c in columnas_base if c != "DESCRIPCION"]
    compare_cols = [c for c in cols if c != "FECHA"]

    # 2) Normaliza df_nuevo
    df_n = (
        df_nuevo[cols].copy()
        .assign(FECHA=lambda d: pd.to_datetime(d["FECHA"], errors="coerce").dt.normalize())
        .dropna(subset=["FECHA"])
        .round(6)
    )

    # 3) Carga CSV antiguo
    if not os.path.exists(path_datos_anteriores):
        raise FileNotFoundError(f"No existe: {path_datos_anteriores}")
    print("Cargando datos anteriores de:", path_datos_anteriores)
    df_a = (
        pd.read_excel(path_datos_anteriores, usecols=cols, parse_dates=["FECHA"])
        .assign(FECHA=lambda d: d["FECHA"].dt.normalize())
        .dropna(subset=["FECHA"])
        .round(6)
    )
    if(df_n["FECHA"].min() < df_a["FECHA"].min() or
       df_a["FECHA"].max() > df_n["FECHA"].max()):
        print(f"Advertencia: EL RANGO DE FECHAS ESTA MAL\n"
                f"  Nuevo:   {df_n['FECHA'].min().date()} → {df_n['FECHA'].max().date()}\n"
                f"  Anterior:{df_a['FECHA'].min().date()} → {df_a['FECHA'].max().date()}")
        print("Asegúrate de que el rango de fechas es correcto.")
        raise ValueError("El rango de fechas de nuevos y antiguso esta mal")
        
       
    # 4) Rango común de fechas
    inicio = max(df_n["FECHA"].min(), df_a["FECHA"].min())
    fin    = min(df_n["FECHA"].max(), df_a["FECHA"].max())
    if inicio > fin:
        print(f"No hay rango común:\n"
              f"  Nuevo:   {df_n['FECHA'].min().date()} → {df_n['FECHA'].max().date()}\n"
              f"  Anterior:{df_a['FECHA'].min().date()} → {df_a['FECHA'].max().date()}")
        return
    print(f"Rango común de fechas: {inicio.date()} → {fin.date()}")

    #Mostar saldos iniciales y finales
    saldo_inicial_nuevo = df_n[df_n["FECHA"] == inicio]["SALDO"].values
    saldo_inicial_anterior = df_a[df_a["FECHA"] == inicio]["SALDO"].values
    saldo_final_nuevo = df_n[df_n["FECHA"] == fin]["SALDO"].values
    saldo_final_anterior = df_a[df_a["FECHA"] == fin]["SALDO"].values
    print(f"SALDO INICIAL: Nuevo {saldo_inicial_nuevo} Anterior {saldo_inicial_anterior}")
    print(f"SALDO FINAL: Nuevo {saldo_final_nuevo} Anterior {saldo_final_anterior}")

    # 5) Filtra al rango
    df_n_r = df_n[df_n["FECHA"].between(inicio, fin)].reset_index(drop=True)
    df_a_r = df_a[df_a["FECHA"].between(inicio, fin)].reset_index(drop=True)
    # print("DF ANTIGUIO")
    # display(df_a_r)  # Mostrar las primeras 20 filas del DataFrame anterior
    # print(f"DF NUEVO")
    # display(df_n_r)  # Mostrar las primeras 20 filas del DataFrame nuevo

    # 6) Identificar fechas
    fechas_n = set(df_n_r["FECHA"])
    fechas_a = set(df_a_r["FECHA"])
    comunes    = sorted(fechas_n & fechas_a)
    nuevas     = sorted(fechas_n - fechas_a)
    eliminadas = sorted(fechas_a - fechas_n)

    # 7) Imprimir filas nuevas
    if nuevas:
        print("\n=== Filas NUEVAS ===")
        for fecha in nuevas:
            sub = df_n_r[df_n_r["FECHA"] == fecha]
            for _, row in sub.iterrows():
                print(f"NUEVA (fecha {fecha.date()}): {row.to_dict()}")
    else:
        print("\nNo hay fechas nuevas.")

    # 8) Imprimir filas eliminadas
    if eliminadas:
        print("\n=== Filas ELIMINADAS ===")
        for fecha in eliminadas:
            sub = df_a_r[df_a_r["FECHA"] == fecha]
            for _, row in sub.iterrows():
                print(f"ELIMINADA (fecha {fecha.date()}): {row.to_dict()}")
    else:
        print("\nNo hay fechas eliminadas.")

    # 9) Comparaciones en fechas comunes (sin importar orden)
    if comunes:
        print(f"\n=== Cambios en fechas comunes ({inicio.date()} → {fin.date()}) ===")
        for fecha in comunes:
            sub_n = df_n_r[df_n_r["FECHA"] == fecha][compare_cols]
            sub_a = df_a_r[df_a_r["FECHA"] == fecha][compare_cols]

            # print(f"\nFecha: {fecha.date()}")
            # print("NUEVO:")
            # print(sub_n.head(20))
            # print("ANTIGUO:")
            # print(sub_a.head(20))

            # Multiconjuntos de tuplas de valores
            cnt_n = Counter(map(tuple, sub_n.values))
            cnt_a = Counter(map(tuple, sub_a.values))

            # Identificar y quitar filas idénticas
            iguales = cnt_n & cnt_a
            for tpl, cnt in iguales.items():
                cnt_n[tpl] -= cnt
                cnt_a[tpl] -= cnt
                if cnt_n[tpl] == 0: del cnt_n[tpl]
                if cnt_a.get(tpl,0) == 0 and tpl in cnt_a: del cnt_a[tpl]

            # Ahora cnt_n = filas "nuevas" o modificadas,
            #     cnt_a = filas "eliminadas" o modificadas
            # Intentar emparejar por posición en la lista resultante
            nuevos_list    = list(cnt_n.elements())
            eliminados_list = list(cnt_a.elements())
            pares = min(len(nuevos_list), len(eliminados_list))

            # 9.a) Mostrar cambios célula a célula para cada par
            for i in range(pares):
                old = eliminados_list[i]
                new = nuevos_list[i]
                for j, col in enumerate(compare_cols):
                    if old[j] != new[j]:
                        print(f"FECHA {fecha.date()} – Columna '{col}': antiguo={old[j]}, nuevo={new[j]}")

            # 9.b) Filas extra sin pareja => puros añadidos o eliminados
            for tpl in nuevos_list[pares:]:
                print(f"FECHA {fecha.date()} – FILA EXTRA NUEVA: {dict(zip(compare_cols, tpl))}")
            for tpl in eliminados_list[pares:]:
                print(f"FECHA {fecha.date()} – FILA EXTRA ELIMINADA: {dict(zip(compare_cols, tpl))}")
    else:
        print("\nNo hay fechas comunes para comparar.")


def test_balance_validity(df, diferencia_permitida=1):
    print("Probando validez de saldos... con diferencia permitida de ", diferencia_permitida)
    saldo_anterior = df.iloc[0]['SALDO']
    for i in range(1, len(df)):
        saldo_actual = df.iloc[i]['SALDO']
        saldo_calculado = saldo_anterior + df.iloc[i]['MONTO']
        if not np.isclose(saldo_actual, saldo_calculado, atol=diferencia_permitida):
            print(f"Saldo incorrecto en {df.iloc[i]['FECHA']}: esperado {saldo_calculado}, encontrado {saldo_actual}")
            print(f"Saldo Ant {saldo_anterior}, Saldo Act {saldo_actual}, MONTO {df.iloc[i]['MONTO']}")
            print(f"DIFERENCIA {saldo_actual - saldo_calculado}")
            print("\n")
         
            
        saldo_anterior = saldo_actual
        