# -*- coding: utf-8 -*-

from contabilidad.cuenta.lectura  .FileProcessingConfig import FileProcessingConfig 
from contabilidad.cuenta.lectura import cuenta as LecturaCuenta
from contabilidad.config import PATH_DATA,NOMBRE_COMPLETO,NOMBRE_BANCA,PATH_CUENTAS_ACTUAL,PATH_COMPLETOS_VALIDACION,PATH_COMPLETOS,NOMBRE_BANCA,COLUMNAS_GUARDAR_COMPLETO,COLUMNAS_GUARDAR_CUENTAS,PATH_DATA_ACTUAL
from contabilidad.Modelos import DataCambiosGuardadoCuenta,DataCambiosGuardado,EnhancedJSONEncoder
import json

from contabilidad.guardar import verificacion_cambios
from contabilidad.descripciones.leer import guardar_descripciones
import os
from datetime import datetime





def verificar_completo_anterior(df_completo):
    return True
    

def crear_data_cuenta_guardado(df_cuentas,path_carpeta,nueva_cuenta_config:FileProcessingConfig):
    nueva_cuenta=LecturaCuenta.leer_cuenta_nuevo(nueva_cuenta_config)
    


def crear_data_guardado(df_completo,df_cuentas,nueva_cuenta_config:FileProcessingConfig):
    pass




def guardar_atipicos(df):
    df.to_excel(PATH_ATIPICOS_ACTUAL, index=False)
    df.to_excel(PATH_CUENTAS_ACTUAL, index=False)
    



def guardar_nuevos_datos(df_completo,df_cuentas,nueva_cuenta_config:FileProcessingConfig):
   pass

    





def obtener_data_guardado_cuenta(df_cuenta,nueva_cuenta_config:FileProcessingConfig)->DataCambiosGuardadoCuenta:
    df_nuevo = LecturaCuenta.leer_cuenta_nuevo(nueva_cuenta_config)
    fecha_inicio = df_cuenta["FECHA"].min()
    fecha_fin = df_nuevo["FECHA"].max() 
    saldo_inicio = df_cuenta[df_cuenta["FECHA"] == fecha_inicio]["SALDO"].iloc[0]
    saldo_fin = df_nuevo[df_nuevo["FECHA"] == fecha_fin]["SALDO"].iloc[-1]
    from contabilidad.guardar import verificacion_cambios
    cambios = verificacion_cambios.verificar_nuevas_cuentas(df_cuenta,df_nuevo)
    cambios =""
    return DataCambiosGuardadoCuenta(fecha_inicio=fecha_inicio,fecha_fin=fecha_fin,saldo_inicio=saldo_inicio,saldo_fin=saldo_fin,path_nuevos_datos=nueva_cuenta_config.path,cambios=cambios)




    
def obtener_nombre_carpeta():
    """
    Genera un nombre de carpeta basado en la fecha actual.
    Si la carpeta ya existe, añade un sufijo numérico para evitar sobrescribir.
    """
    base_nombre = datetime.now().strftime("%Y-%m-%d")
    nombre_carpeta = base_nombre
    contador = 1
    while os.path.exists(os.path.join(PATH_COMPLETOS, nombre_carpeta)):
        nombre_carpeta = f"{base_nombre}_{contador}"
        contador += 1
    return nombre_carpeta

def crear_carpeta_de_guardado(path):
    if not os.path.exists(path):
        os.makedirs(path)
    return path

def obtener_cambios_df_completo(df_completo):
    from contabilidad.guardar import verificacion_cambios


def guardar_archivo_completo(df_completo,path_carpeta):
    df_completo = df_completo[COLUMNAS_GUARDAR_COMPLETO].copy()
    path = path_carpeta + "/" + NOMBRE_COMPLETO
    df_completo.to_excel(path, index=False)
    print("Datos Completos Guardado en:", path)
    return path

def guardar_cuenta(df_cuentas,path_carpeta):
    df_cuentas = df_cuentas[COLUMNAS_GUARDAR_CUENTAS].copy()
    path = path_carpeta + "/" + NOMBRE_BANCA
    df_cuentas.to_excel(path, index=False)
    print("Cuentas Guardado en:", path)
    return path


def guardar_metadata(datos: DataCambiosGuardado, path_carpeta: str):
   
    path = path_carpeta + "/metadata.json"
    try:
        with open(path, 'w', encoding='utf-8') as f:
            
            
            json.dump(datos, f, cls=EnhancedJSONEncoder, indent=4, ensure_ascii=False)
        print(f" Datos guardados exitosamente en '{path}'")
    except Exception as e:
        print(f" Error al guardar los datos: {e}")


def guardar_toda_carpeta(df_completo,df_cuentas,path_carpeta,datos_guardado:DataCambiosGuardado):
    path_carpeta=crear_carpeta_de_guardado(path_carpeta)
    print("Guardando en:", path_carpeta)
    path_completo = guardar_archivo_completo(df_completo,path_carpeta)
    path_cuenta = guardar_cuenta(df_cuentas,path_carpeta)
    path_metadata = guardar_metadata(datos_guardado,path_carpeta)
    path_descripciones = guardar_descripciones(df_completo,path_carpeta)

    # Guardar el objeto DataCambiosGuardado como JSON
    

    
    
def guardar_prueba_nuevos_datos(df_completo,df_cuentas,nueva_cuenta_config:FileProcessingConfig,nombre_carpeta=None):
    
    if not nombre_carpeta:
        nombre_carpeta = obtener_nombre_carpeta()
    path_carpeta = PATH_COMPLETOS_VALIDACION + "/" + nombre_carpeta
    # path_carpeta=crear_carpeta_de_guardado(path_carpeta)
    # print("Guardando nuevos datos en:", path_carpeta)
    datos_guardado_cuenta= obtener_data_guardado_cuenta(df_cuenta=df_cuentas,nueva_cuenta_config=nueva_cuenta_config)
    
    cambios_datos_completo = obtener_cambios_df_completo(df_completo)
    datos_guardado = DataCambiosGuardado(
        fecha=datetime.now(),
        path_carpeta_anterior= PATH_DATA_ACTUAL,
        cambios=cambios_datos_completo, 
        cambiosCuenta=datos_guardado_cuenta
    )
    # return datos_guardado
    guardar_toda_carpeta(df_completo=df_completo,df_cuentas=df_cuentas,datos_guardado=datos_guardado,path_carpeta=path_carpeta)
    # guardar_cuenta()

    # crear_data_cuenta_guardado(df_cuentas,path_carpeta,nueva_cuenta_config)


def guardar_nuevos_datos_finales(df_completo,df_cuentas,nueva_cuenta_config:FileProcessingConfig):
    nombre_carpeta = obtener_nombre_carpeta()
    path_carpeta = PATH_COMPLETOS + "/" + nombre_carpeta
    # path_carpeta=crear_carpeta_de_guardado(path_carpeta)
    # print("Guardando nuevos datos en:", path_carpeta)
    datos_guardado_cuenta= obtener_data_guardado_cuenta(df_cuenta=df_cuentas,nueva_cuenta_config=nueva_cuenta_config)
    
    cambios_datos_completo = obtener_cambios_df_completo(df_completo)
    datos_guardado = DataCambiosGuardado(
        fecha=datetime.now(),
        path_carpeta_anterior=PATH_DATA_ACTUAL,
        cambios=cambios_datos_completo, 
        cambiosCuenta=datos_guardado_cuenta
    )
    # return datos_guardado
    guardar_toda_carpeta(df_completo=df_completo,df_cuentas=df_cuentas,datos_guardado=datos_guardado,path_carpeta=path_carpeta)
    cambiar_json_archivo_actual(nombre_carpeta)


def cambiar_json_archivo_actual(nombre_carpeta):
    raise NotImplementedError("Hay que actualizar los paths para volver a correr esta función")
    ruta_json = PATH_DATA + "/config.json"
    try:
        with open(ruta_json, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        config['path_actual'] = nombre_carpeta
        
        with open(ruta_json, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        
        print(f"Archivo JSON actualizado correctamente en '{ruta_json}'")
    except Exception as e:
        print(f"Error al actualizar el archivo JSON: {e}")