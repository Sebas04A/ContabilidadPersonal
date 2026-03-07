import pandas as pd

from contabilidad.notion import integracionNotion
# Diccionario de meses en español
meses = {
    "enero": "01", "febrero": "02", "marzo": "03", "abril": "04", "mayo": "05", "junio": "06",
    "julio": "07", "agosto": "08", "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12"
}

def parse_fecha_notion(fecha_raw):
    if pd.isna(fecha_raw):
        return pd.NaT
    
    texto = str(fecha_raw).strip().split("\t")[0]  # Limpiar tabulaciones
    partes = texto.split()

    if len(partes) >= 6:
        dia = partes[0]
        mes_str = partes[2].lower()
        anio = partes[4]
        hora = partes[5]

        if mes_str in meses:
            mes_num = meses[mes_str]
            fecha_str = f"{anio}-{mes_num}-{dia} {hora}"
            return pd.to_datetime(fecha_str, format="%Y-%m-%d %H:%M", errors='coerce')
    return pd.NaT  # Si algo falla


def normalizar(df):
    df_notion = df.copy()

    df_notion["FECHA_CREACION"] = pd.to_datetime(df_notion['Fecha Creacion'], errors='coerce')

    df_notion["FECHA_REAL"] = pd.to_datetime(df_notion['Fecha Real'], errors='coerce')
    df_notion["FECHA_REAL"] = df_notion["FECHA_REAL"].fillna(df_notion["FECHA_CREACION"])
    df_notion["FECHA_REAL"]= df_notion["FECHA_REAL"].dt.normalize()
    df_notion.sort_values(by="FECHA_REAL", inplace=True)
    df_notion.reset_index(drop=True, inplace=True)

    df_notion["PERSONA_NOTION"] = df_notion["Persona"].apply(lambda x: x.split(" ")[0] if isinstance(x, str) else x)
    
    
    # df_notion["NOTION"] = df_notion["Valor real"].str.replace(',', '.').astype(float, errors='ignore')
    df_notion.rename(columns={"Valor real":"NOTION"},inplace=True)

    df_notion["NOTIONCUM"] = df_notion["NOTION"].cumsum()
    
    df_notion.drop(columns=["Fecha Creacion","Fecha Real","Valor"], inplace=True)
    df_notion.rename(columns={"Descripcion":"DESCRIPCION_NOTION"},inplace=True)

    
    return df_notion
def limpiar(df):

    df_notion = df.copy()
    # Corrige el nombre de la columna
    df_notion = df_notion[df_notion['Fecha Creacion'] > '2024-10-02'] 
    df_notion = df_notion[(df_notion["Valor"] != 0) & (df_notion["Descripcion"].notna())]
    return df_notion

def leer_notion():
    df_notion = integracionNotion.get_notion_data()
    df_notion = limpiar(df_notion)
    df_notion = normalizar(df_notion)

    # df_notion["NOTIONCUM"] = df_notion.groupby("Persona")["NOTION"].cumsum()
    # df_notion_madre = df_notion[df_notion["PERSONA_NOTION"] == "Madre"].copy()
    
    return df_notion