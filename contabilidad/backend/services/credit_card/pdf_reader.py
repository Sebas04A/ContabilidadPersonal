import os
import re
import pandas as pd
import pdfplumber


def get_credit_card_data_from_pdf(file_path: str) -> tuple[pd.DataFrame, DATOS_TARJETA_COMPLETA]:
    """
    Procesa un archivo .pdf de estado de cuenta de tarjeta y retorna:
      - df: DataFrame de movimientos con columnas estandarizadas
            (FECHA, DESCRIPCION, MONTO, OPERACION, ...)
      - metadata: objeto DATOS_TARJETA_COMPLETA con los metadatos del estado de cuenta.

    El DataFrame devuelto DEBE tener al menos las columnas:
        - FECHA       : datetime
        - DESCRIPCION : str
        - MONTO / VALOR : float  (se renombra a MONTO en sources_service)
        - OPERACION   : str (opcional, si el PDF lo trae)

    TODO: Implementar la lógica de extracción desde prueba_pdf.ipynb
    """
    file_name = os.path.basename(file_path)
    
    movimientos = []
    # Expresión regular para: Fecha (00/00) + Referencia (opcional) + El resto
    patron_fila = re.compile(r'^(\d{2}/\d{2})\s+(?:(\d+)\s+)?(.*)\s+([\d,.]+-?)$')
    inicio_patron="ARCENTALES"
    fin_patron="SUBTOTAL :"
    
    with pdfplumber.open(file_path) as pdf:
        # Extraemos el texto completo para el parsing de metadata
        texto_completo = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        
        # --- 1. FUNCIÓN INTERNA DE LIMPIEZA ---
        def limpiar_monto(texto):
            if not texto: return 0.0
            # Normalización: 1.234,56 -> 1234.56
            num = texto.replace('.', '').replace(',', '.')
            if num.endswith('-'):
                num = '-' + num.replace('-', '')
            try:
                return float(num)
            except ValueError:
                return 0.0

        from contabilidad.backend.services.credit_card.utils import try_parse_date_es

        # Definimos un patrón específico para el formato de fecha del banco: DD MMM YYYY
        patron_fecha_banco = r'(\d{2}\s+[A-Z]{3}\s+\d{4})'

        meta_raw = {
            'EMPRESA':          "BANCO PICHINCHA",
            'NUM_TARJETA':      re.search(r'(\d{4}X+5647)', texto_completo).group(1) if re.search(r'(\d{4}X+5647)', texto_completo) else "N/A",
            
            # Usamos el patrón específico para detener la captura exactamente en el año
            'FECHA_EMISION':    try_parse_date_es(re.search(fr'FECHA(?: DE)?\s+EMISIÓN:\s+{patron_fecha_banco}', texto_completo, re.IGNORECASE).group(1)) if re.search(fr'FECHA(?: DE)?\s+EMISIÓN:\s+{patron_fecha_banco}', texto_completo, re.IGNORECASE) else None,
            
            'FECHA_MAX_PAGO':   try_parse_date_es(re.search(fr'FECHA MÁXIMA DE PAGO SIN RECARGOS\s+{patron_fecha_banco}', texto_completo, re.IGNORECASE).group(1)) if re.search(fr'FECHA MÁXIMA DE PAGO SIN RECARGOS\s+{patron_fecha_banco}', texto_completo, re.IGNORECASE) else None,
            
            'SALDO_ANTERIOR':   limpiar_monto(re.search(r'SALDO ANTERIOR\s+([\d,.]+)', texto_completo).group(1)) if re.search(r'SALDO ANTERIOR\s+([\d,.]+)', texto_completo) else 0.0,
            'SUBTOTAL_PAGADO':  limpiar_monto(re.search(r'SUBTOTAL PAGOS\s+([\d,.]+)', texto_completo).group(1)) if re.search(r'SUBTOTAL PAGOS\s+([\d,.]+)', texto_completo) else 0.0,
            'TOTAL_A_PAGAR':    limpiar_monto(re.search(r'TOTAL A PAGAR\s+([\d,.]+)', texto_completo).group(1)) if re.search(r'TOTAL A PAGAR\s+([\d,.]+)', texto_completo) else 0.0,
            'MINIMO_A_PAGAR':   limpiar_monto(re.search(r'MINIMO A PAGAR\s+([\d,.]+)', texto_completo).group(1)) if re.search(r'MINIMO A PAGAR\s+([\d,.]+)', texto_completo) else 0.0,
            'TOTAL_CONSUMO':    limpiar_monto(re.search(r'TOTAL CONSUMOS MES\s+([\d,.]+)', texto_completo).group(1)) if re.search(r'TOTAL CONSUMOS MES\s+([\d,.]+)', texto_completo) else 0.0,
        }

        # Recorremos todas las líneas del texto completo para atrapar todos los movimientos,
        # incluyendo los que estén en secciones previas (ej. "SUBTOTAL PAGOS")
        for linea in texto_completo.split("\n"):
            linea_limpia = linea.strip()
            match = patron_fila.match(linea_limpia)
            if match:
                fecha_str, ref, desc, valor = match.groups()
                
                # Ignorar filas de metadata que se parecen a movimientos (ej: pagos)
                desc_upper = desc.upper()
                if "PAGO" in desc_upper and "GRACIAS" in desc_upper:
                    continue
                if "SU PAGO" in desc_upper:
                    continue
                    
                ref = ref if ref else "" # Puede ser None
                
                # Arreglar el formato del número (Pichincha style)
                valor = valor.replace('.', '').replace(',', '.')
                if valor.endswith('-'):
                    valor = '-' + valor.replace('-', '')
                
                movimientos.append([fecha_str, ref, desc, float(valor)])

        # --- 3. EXTRACCIÓN DE MOVIMIENTOS ---
       

        df = pd.DataFrame(movimientos, columns=["FECHA","CODIGO","DESCRIPCION","MONTO"])

        # --- 4. TRANSFORMACIONES Y DICCIONARIO FINAL ---
        if not df.empty:
            df.rename(columns={'VALOR': 'MONTO'}, inplace=True)
            
            statement_date = meta_raw['FECHA_EMISION'] if meta_raw['FECHA_EMISION'] else pd.Timestamp.now()
            stmt_year = statement_date.year
            stmt_month = statement_date.month
            
            def parse_mov_date(f_str):
                try:
                    dia, mes = map(int, f_str.split('/'))
                    y = stmt_year
                    if mes > stmt_month:
                        y -= 1
                    return pd.Timestamp(year=y, month=mes, day=dia)
                except:
                    return pd.NaT
            
            df['FECHA'] = df['FECHA'].apply(parse_mov_date)

        flat_meta = {
            'EMPRESA':             meta_raw['EMPRESA'],
            'NUM_TARJETA':         meta_raw['NUM_TARJETA'],
            'FECHA_EMISION':       meta_raw['FECHA_EMISION'],
            'FECHA_MAX_PAGO':      meta_raw['FECHA_MAX_PAGO'],
            'saldo_anterior':      meta_raw['SALDO_ANTERIOR'],
            'subtotal_pagado':     meta_raw['SUBTOTAL_PAGADO'],
            'total_a_pagar':       meta_raw['TOTAL_A_PAGAR'],
            'minimo_a_pagar':      meta_raw['MINIMO_A_PAGAR'],
            'total_consumo':       meta_raw['TOTAL_CONSUMO'],
            'num_transacciones':   len(df),
            'fecha_min':           df['FECHA'].min() if not df.empty else None,
            'fecha_max':           df['FECHA'].max() if not df.empty else None,
            'total_mes':           df['MONTO'].sum() if not df.empty else 0,
            'total_a_pagar_despues': meta_raw['TOTAL_A_PAGAR'] + (df['MONTO'].sum() if not df.empty else 0),
            'source_file':         file_name,
        }

        return df, flat_meta