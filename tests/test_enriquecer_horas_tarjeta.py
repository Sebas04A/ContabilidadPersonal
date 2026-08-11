import sys, os
sys.path.insert(0,'/home/sebas/dev/projects/ContabilidadPersonal/scripts')
sys.path.insert(0,'/home/sebas/dev/projects/ContabilidadPersonal')
import enriquecer_horas_tarjeta as E
import pandas as pd

co=E.cargar_correos(E.PATH_CORREOS_DB)
tx=E.cargar_transacciones(E.PATH_TARJETA_UNIDA)
cons=tx[E.es_consumo(tx)]

def run(df_tx, df_full, df_co):
    return E.construir_salida(E.asignar(E.generar_candidatos(df_tx, df_co, df_full)))

base=run(cons,tx,co); h0=E._huella(base)
print("baseline filas:",len(base),"huella:",h0[:12])

# 1. determinismo frente al orden de las transacciones
s1=cons.sample(frac=1,random_state=7)
r1=run(s1,tx,co)
print("1. orden tx barajado      ->", "OK" if E._huella(r1)==h0 else "FALLA")

# 2. determinismo frente al orden de los correos
s2=co.sample(frac=1,random_state=13)
r2=run(cons,tx,s2)
print("2. orden correos barajado ->", "OK" if E._huella(r2)==h0 else "FALLA")

# 3. unicidad 1:1
d1=base.source_id.duplicated().sum(); d2=base.id_correo.duplicated().sum()
print(f"3. 1:1 sin duplicados     -> {'OK' if d1==0 and d2==0 else 'FALLA'} (tx dup={d1}, correo dup={d2})")

# 4. toda hora asignada procede de un correo real y la fecha es coherente
c=co.set_index('id_correo')
bad=0
for _,r in base.iterrows():
    e=c.loc[r.id_correo]
    if e.hora!=r.HORA: bad+=1
print("4. hora == hora del correo ->", "OK" if bad==0 else f"FALLA ({bad})")

# 5. ventana asimetrica respetada: el correo nunca es posterior al estado
print(f"5. delta_dias en [-3,0]    -> {'OK' if base.delta_dias.between(-3,0).all() else 'FALLA'} (min={base.delta_dias.min()}, max={base.delta_dias.max()})")

# 6. las reglas laxas no se disparan solas
print("6. reglas:", base.regla.value_counts().to_dict())
lax=base[base.regla!='R1_monto_exacto']
print(f"   similitud minima en reglas laxas: {lax.similitud.min():.2f} (umbral R2={E.SIM_MIN_TARIFA}, R3={E.SIM_MIN_REDONDEO})")

# 7. ningun apunte no-consumo recibio hora
noc=tx[~tx.index.isin(cons.index)]
solap=set(base.source_id)&set(noc.id)
print("7. no-consumos sin hora    ->", "OK" if not solap else f"FALLA ({len(solap)})")

# 8. los ids del sidecar existen en tarjeta_unida
print("8. ids enlazan con el xlsx ->", "OK" if set(base.source_id)<=set(tx.id) else "FALLA")

# 9. R2 solo donde existe la linea de tarifa
r2c=base[base.regla=='R2_tarifa_gasolinera']
ok=all(len(tx[(tx.FECHA==pd.Timestamp(f))&(tx.DESCRIPCION.str.contains('TARIFA CONSUMO GASOLINERA',na=False))])>0
       for f in r2c.FECHA)
print("9. R2 exige linea tarifa   ->", "OK" if ok else "FALLA")
