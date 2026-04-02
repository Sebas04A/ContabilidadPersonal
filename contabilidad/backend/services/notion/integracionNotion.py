# Asegúrate de que tu token de integración y el ID de la base de datos estén configurados como variables de entorno
# Se recomienda por seguridad no incrustar estos datos directamente en el código
notion_token = "ntn_P777024000043Si3MqqLwIo4AaNSUe2D75n3EKsxKwz9Mi"
id_database = "792911d5-ee6f-4eac-b079-54d7dbfa43f4"
personas_database_id = "7720cb15-9ac7-49a0-ac73-e660f41898b1"
import os
import pandas as pd
from notion_client import Client
from datetime import datetime
import json
import os
from notion_client import Client
import json


def list_accessible_databases(notion_token):
    """
    Usa la búsqueda de Notion para listar las bases de datos a las que
    la integración tiene acceso.
    """
    try:
        notion = Client(auth=notion_token)
        print("🔍 Buscando bases de datos con acceso...")
        response = notion.search(
            filter={
                "property": "object",
                "value": "database"
            }
        )

        databases = response["results"]

        if not databases:
            print("❌ No se encontraron bases de datos. Asegúrate de que tu integración tiene permisos.")
            return

        print(f"✅ Encontradas {len(databases)} bases de datos accesibles.")
        
        for db in databases:
            print(db)
            
            # print(f"  - Título: '{db_title}' (ID: {db_id})")

    except Exception as e:
        print(f"❌ Ocurrió un error: {e}")
# list_accessible_databases(notion_token)

def get_clean_users_table(notion_token, users_database_id):
    """
    Obtiene todos los registros de la base de datos de usuarios y los limpia.
    """
    notion = Client(auth=notion_token)
    all_results = []
    has_more = True
    next_cursor = None
    
    try:
        print("🔍 Obteniendo datos de la base de datos de usuarios...")
        while has_more:
            query_results = notion.databases.query(
                database_id=users_database_id,
                start_cursor=next_cursor
            )
            all_results.extend(query_results["results"])
            has_more = query_results.get("has_more")
            next_cursor = query_results.get("next_cursor")

        if not all_results:
            print("❌ Base de datos de usuarios vacía.")
            return None
        
        users_list = []
        for user_row in all_results:
            user_id = user_row["id"]
            properties = user_row["properties"]
            
            # Asume que el nombre está en la propiedad "Nombre" con tipo "title"
            title_prop = properties.get("Nombre", {})
            
            # Se extrae el texto plano de la propiedad 'title' que es una lista de objetos
            name_text = ""
            if 'title' in title_prop and isinstance(title_prop['title'], list):
                name_text = "".join([text.get("plain_text") for text in title_prop['title']])
            
            users_list.append({"id": user_id, "name": name_text})

        return pd.DataFrame(users_list)
        
    except Exception as e:
        print(f"❌ Ocurrió un error: {e}")
        return None


def get_clean_main_table(notion_token, main_database_id, users_df):

    """
    Obtiene los datos de la tabla principal y los limpia según el nombre de la columna.
    """
    notion = Client(auth=notion_token)
    all_results = []
    has_more = True
    next_cursor = None
    
   
    users_dict = dict(zip(users_df['id'], users_df['name']))
        
    

    try:
        # Lógica de paginación para obtener todos los registros
        print("🔍 Obteniendo datos de la tabla principal...")
        while has_more:
            query_results = notion.databases.query(
                database_id=main_database_id,
                start_cursor=next_cursor
            )
            all_results.extend(query_results["results"])
            has_more = query_results.get("has_more")
            next_cursor = query_results.get("next_cursor")

        if not all_results:
            print("❌ La base de datos está vacía o no se encontraron resultados.")
            return None
        
        data_list = []

        # print(all_results[0])
        
        # Procesamiento de datos por nombre de columna
        for row in all_results:
            properties = row["properties"]
            row_data = {}
            for prop_name, prop_data in properties.items():
                # print(prop_name, prop_data)
                
                # --- Lógica basada en el nombre de la columna ---
                if prop_name == "Tipo":
                    # Extrae el nombre de la propiedad 'select'
                    if prop_data.get("type") == "select":
                        select = prop_data.get("select",{})
                        # print(select)
                        row_data[prop_name] = select.get("name") if select else None
                    else:
                        row_data[prop_name] = None
                
                elif prop_name == "Valor real":
                    # Extrae el valor de la propiedad 'number'
                    # if prop_data.get("type") == "number":
                    row_data[prop_name] = prop_data.get("formula", {}).get("number")
                    # else:
                    #     row_data[prop_name] = None
                elif  prop_name == "Fecha Real":
                    if prop_data and prop_data.get("type") == "date":
                        date_obj = prop_data.get("date", {})
                        if date_obj and date_obj.get("start"):
                            dt = datetime.fromisoformat(date_obj.get("start").replace("Z", "+00:00"))
                            row_data[prop_name] = dt.strftime('%Y-%m-%d %H:%M:%S')
                        else:
                            # Handle cases where the date object is empty or malformed
                            row_data[prop_name] = None
                    else:
                        # Handle cases where the property isn't a date type or the data is missing
                        row_data[prop_name] = None
                
                elif prop_name == "Fecha Creacion":
                    # print(prop_data)
                    if prop_data and prop_data.get("type") == "created_time":
                        created_time = prop_data.get("created_time")
                        if created_time:
                            dt = datetime.fromisoformat(created_time.replace("Z", "+00:00"))
                            # print(dt)
                            row_data[prop_name] = dt.strftime('%Y-%m-%d %H:%M:%S')
                        else:
                            row_data[prop_name] = None
                    else:
                        row_data[prop_name] = None

                elif prop_name == "Persona":
                    if prop_data.get("type") == "relation":
                        related_ids = [rel.get("id") for rel in prop_data.get("relation", [])]
                        names = [users_dict.get(rid, "Nombre no encontrado") for rid in related_ids]
                        row_data[prop_name] = ", ".join(names) if names else ""
                
                # Procesa otras columnas comunes
                elif prop_name in ["Descripcion", "Valor", "Nombre de la tarea", "Fecha Creacion"]:
                    prop_type = prop_data.get("type")
                    if prop_type in ["title", "rich_text"]:
                        row_data[prop_name] = "".join([text.get("plain_text") for text in prop_data[prop_type]]) if prop_data[prop_type] else ""
                    elif prop_type == "number":
                        row_data[prop_name] = prop_data.get("number")
                    elif prop_type == "date":
                        date_obj = prop_data.get("date", {})
                        if date_obj and date_obj.get("start"):
                            row_data[prop_name] = date_obj.get("start")
                        else:
                            row_data[prop_name] = None
                    else:
                        row_data[prop_name] = str(prop_data.get(prop_type))

            data_list.append(row_data)

        return pd.DataFrame(data_list)

    except Exception as e:
        print(f"❌ Ocurrió un error: {e}")
        return None
    

def get_notion_data():
    users_df = get_clean_users_table(notion_token, personas_database_id)
    if users_df is None:
        print("❌ No se pudo obtener la tabla de usuarios.")
        return None

    main_df = get_clean_main_table(notion_token, id_database, users_df)
    if main_df is None:
        print("❌ No se pudo obtener la tabla principal.")
        return None

    return main_df