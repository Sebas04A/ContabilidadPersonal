import pandas as pd
import os
import uuid
import shutil
from typing import List, Dict, Any, Optional
from datetime import date, datetime

from contabilidad.backend.logger import get_logger

logger = get_logger(__name__)

# Define paths
from contabilidad.config import PATH_DATA
BASE_DATA_PATH = os.path.join(PATH_DATA, 'sistema', 'interpolaciones')

GROUPS_FILE = os.path.join(BASE_DATA_PATH, 'grupos.csv')
PAYMENTS_FILE = os.path.join(BASE_DATA_PATH, 'pagos.csv')

# Full schema for groups. New columns are appended automatically by read_csv for
# backward compatibility with older grupos.csv files.
# `fondo_origen` links a generated payments group back to the fund (fund id) it was
# materialized from, so re-generating can find and replace it idempotently.
# `es_inversion` marks a group as an investment portfolio (positions in
# `inversiones/posiciones.csv` point at it), the same way `es_fondo` marks a fund.
# `es_custodia` marks a portfolio holding somebody else's money: it lives in the user's
# bank account, so it must be tracked, but it never counts towards their net worth.
GROUP_COLUMNS = ['id', 'name', 'description', 'type', 'es_fondo', 'fecha_inicio', 'saldo_inicial', 'tag_vinculado', 'fondo_origen', 'es_inversion', 'es_custodia']


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ('true', '1', 'yes', 'si', 'sí')
    if value is None:
        return False
    try:
        if pd.isna(value):
            return False
    except (TypeError, ValueError):
        pass
    return bool(value)


def _texto_plano(value: Any) -> str:
    """El valor tal cual, como texto, sin que un NaN se cuele como 'nan'."""
    if value is None:
        return ''
    try:
        if pd.isna(value):
            return ''
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _normalize_group(row: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce a raw group record into clean, JSON-friendly types."""
    es_fondo_bool = _as_bool(row.get('es_fondo'))

    # `saldo_inicial` vacío y `saldo_inicial = 0` **no son lo mismo**: el primero es «esto
    # no se ha configurado, dedúcelo», el segundo es «el usuario afirma que arranca en
    # cero». `saldo_inicial` sigue valiendo 0.0 cuando falta —hay consumidores que suman
    # con él y no deben ver un None—, y quien necesite distinguir mira
    # `saldo_inicial_configurado`.
    saldo = row.get('saldo_inicial')
    configurado = True
    try:
        if saldo is None or (isinstance(saldo, float) and pd.isna(saldo)) or str(saldo).strip() == '':
            saldo_val = 0.0
            configurado = False
        else:
            saldo_val = float(saldo)
            if pd.isna(saldo_val):
                saldo_val = 0.0
                configurado = False
    except (ValueError, TypeError):
        saldo_val = 0.0
        configurado = False

    def _clean_str(value, default=''):
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return default
        s = str(value).strip()
        return default if s == '' or s.lower() == 'nan' else s

    fecha_raw = _clean_str(row.get('fecha_inicio'), '')
    fecha_val = fecha_raw[:10] if fecha_raw else None

    return {
        'id': row.get('id'),
        'name': _clean_str(row.get('name')),
        'description': _clean_str(row.get('description')),
        'type': _clean_str(row.get('type'), 'interpolated'),
        'es_fondo': es_fondo_bool,
        'fecha_inicio': fecha_val,
        'saldo_inicial': saldo_val,
        'saldo_inicial_configurado': configurado,
        'tag_vinculado': _clean_str(row.get('tag_vinculado')) or None,
        'fondo_origen': _clean_str(row.get('fondo_origen')) or None,
        'es_inversion': _as_bool(row.get('es_inversion')),
        'es_custodia': _as_bool(row.get('es_custodia')),
        'origen': _origen(row),
    }


def _origen(row: Dict[str, Any]) -> str:
    """Quién manda sobre este grupo, deducido de lo que ya está en el CSV.

    `type` **no dice qué es un grupo, dice cómo se ejecuta**: `VirtualItemsProcessor`
    aplica al patrimonio exactamente `fixed` e `interpolated`, así que todo el que quiera
    contar —un pago fijo a mano, un fondo, un portafolio de inversión o una serie que
    generó una máquina— acaba marcado `fixed`. Filtrar por `type` mezcla cinco especies
    distintas, y por eso la pantalla de Pagos fijos enseñaba quince grupos cuando pagos
    fijos del usuario hay tres.

    Esto no cambia el modelo, solo lo lee: es una etiqueta derivada, sin columna nueva ni
    migración. El orden de las ramas importa — un grupo generado desde un fondo lleva
    `fondo_origen` *y* podría llevar otras banderas, y lo que manda sobre él es su
    generador.
    """
    if _texto_plano(row.get('fondo_origen')):
        return 'generado'
    if _as_bool(row.get('es_fondo')):
        return 'fondo'
    if _as_bool(row.get('es_inversion')):
        return 'inversion'
    return 'manual'

def ensure_data_dir():
    if not os.path.exists(BASE_DATA_PATH):
        os.makedirs(BASE_DATA_PATH)

def read_csv(file_path: str, columns: List[str]) -> pd.DataFrame:
    ensure_data_dir()
    if not os.path.exists(file_path):
        return pd.DataFrame(columns=columns)
    try:
        df = pd.read_csv(file_path)
        # Ensure all columns exist
        for col in columns:
            if col not in df.columns:
                df[col] = None
        
        # Replace NaN with None for JSON/Pydantic compatibility.
        #
        # Hay que pasar por `object` a la fuerza. Un `df[col] = df[col].apply(...)` no
        # basta: en una columna que pandas infirió `float64` o `str` —cualquier columna de
        # texto enteramente vacía lo es— asignar de vuelta una serie de `None` la
        # re-infiere y el NaN reaparece intacto. Y `nan` es *truthy*, así que río abajo un
        # `campo or ''` no lo atrapa y FastAPI revienta al serializar con "Out of range
        # float values are not JSON compliant".
        #
        # Solo se convierten las columnas que de verdad tienen huecos: una columna llena
        # conserva su dtype nativo y su aritmética.
        for col in df.columns:
            faltantes = df[col].isna()
            if not faltantes.any():
                continue
            columna = df[col].astype(object)
            columna[faltantes] = None
            df[col] = columna

        return df
    except Exception as e:
        logger.error("Error leyendo %s: %s", file_path, e)
        return pd.DataFrame(columns=columns)

PAYMENT_COLUMNS = ['id', 'group_id', 'amount', 'start_date', 'end_date', 'note']

# Campos sin los cuales una fila de pago no significa nada.
#
# Las fechas **no** están aquí, y es deliberado: un pago fijo sin inicio vale «desde
# siempre» y sin fin vale «para siempre», que son dos cosas que el usuario necesita poder
# decir. Antes había que escribir una fecha centinela (`3000-01-01` en el corte,
# `2030-01-01` a mano) para expresar «hasta siempre», y una fila a la que le faltara una
# fecha desaparecía a la vez del dashboard y de la pantalla de Variables.
#
# Un grupo `interpolated` **sí** necesita las dos, porque sin ellas no hay tramo que
# repartir. Eso se valida donde se sabe el tipo del grupo, no aquí.
PAYMENT_REQUIRED = ['id', 'group_id', 'amount']


def _indices_de(df: pd.DataFrame, columna: str, valor: Any) -> List[Any]:
    """Los índices de fila cuyo `columna` vale `valor`.

    Existe porque los ids **no están garantizados como únicos**: `pagos.csv` llegó a tener
    el mismo id en dos filas distintas. Un `df[df['id'] != x]` borra las dos de golpe, así
    que toda escritura por id pasa por aquí y actúa sobre **una sola fila**.
    """
    return df.index[df[columna].astype(str) == str(valor)].tolist()


def _id_unico(df: pd.DataFrame) -> str:
    """Un uuid4 que no colisione con los que ya están en el archivo."""
    existentes = set(df['id'].astype(str)) if 'id' in df.columns else set()
    while True:
        candidato = str(uuid.uuid4())
        if candidato not in existentes:
            return candidato


def save_csv(df: pd.DataFrame, file_path: str):
    ensure_data_dir()
    if os.path.exists(file_path):
        try:
            shutil.copy2(file_path, file_path + ".bak")
        except Exception:
            pass
    df.to_csv(file_path, index=False)

class InterpolationStorage:
    @staticmethod
    def get_groups(
        type_filter: str = 'interpolated',
        fund_only: bool = False,
        origen: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        df = read_csv(GROUPS_FILE, GROUP_COLUMNS)
        # Backward compatibility: treat None/NaN type as 'interpolated'
        if 'type' in df.columns:
            df['type'] = df['type'].fillna('interpolated')

        if type_filter:
            df = df[df['type'] == type_filter]

        groups = [_normalize_group(r) for r in df.to_dict('records')]
        if fund_only:
            groups = [g for g in groups if g['es_fondo']]
        if origen:
            groups = [g for g in groups if g['origen'] == origen]
        return groups

    @staticmethod
    def get_groups_by_fondo_origen(fund_id: str) -> List[Dict[str, Any]]:
        """Every group generated (materialized) from the given fund."""
        df = read_csv(GROUPS_FILE, GROUP_COLUMNS)
        if 'fondo_origen' not in df.columns:
            return []
        df = df[df['fondo_origen'].fillna('').astype(str) == str(fund_id)]
        return [_normalize_group(r) for r in df.to_dict('records')]

    @staticmethod
    def get_group(group_id: str) -> Optional[Dict[str, Any]]:
        df = read_csv(GROUPS_FILE, GROUP_COLUMNS)
        group = df[df['id'] == group_id]
        if group.empty:
            return None
        return _normalize_group(group.iloc[0].to_dict())

    @staticmethod
    def create_group(name: str, description: str = None, group_type: str = 'interpolated',
                     es_fondo: bool = False, fecha_inicio: Optional[str] = None,
                     saldo_inicial: Optional[float] = None,
                     tag_vinculado: Optional[str] = None,
                     fondo_origen: Optional[str] = None,
                     es_inversion: bool = False,
                     es_custodia: bool = False) -> Dict[str, Any]:
        ensure_data_dir()
        # Read existing (to guarantee full/consistent columns) then append.
        df = read_csv(GROUPS_FILE, GROUP_COLUMNS)
        new_id = _id_unico(df)  # mismo motivo que en create_payment
        new_row = {
            'id': new_id, 'name': name, 'description': description, 'type': group_type,
            'es_fondo': bool(es_fondo),
            'fecha_inicio': str(fecha_inicio)[:10] if fecha_inicio else None,
            # Vacío, no 0: un grupo recién creado no tiene saldo inicial *configurado*, y
            # escribir un cero sería afirmar que arranca vacío. `_normalize_group` lo sigue
            # leyendo como 0.0 para quien solo quiera sumar.
            'saldo_inicial': saldo_inicial,
            'tag_vinculado': tag_vinculado or None,
            'fondo_origen': fondo_origen or None,
            'es_inversion': bool(es_inversion),
            'es_custodia': bool(es_custodia),
        }

        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        save_csv(df[GROUP_COLUMNS], GROUPS_FILE)
        return _normalize_group(new_row)

    @staticmethod
    def update_group(group_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        df = read_csv(GROUPS_FILE, GROUP_COLUMNS)
        indices = _indices_de(df, 'id', group_id)
        if not indices:
            return None
        fila = indices[0]

        for key, value in updates.items():
            if key in GROUP_COLUMNS and key != 'id':
                if isinstance(value, (date, datetime)):
                    value = value.isoformat()[:10]
                if value is None or (isinstance(value, str) and value.strip() == ''):
                    # Vaciar una celda es una operación legítima —es lo que distingue
                    # «sin configurar» de «configurado en cero»— pero pandas 3 se niega a
                    # meter un hueco en una columna `float64`. La columna pasa a `object`
                    # para admitirlo; al releer, `read_csv` lo devuelve como None.
                    df[key] = df[key].astype(object)
                    value = None
                df.at[fila, key] = value

        save_csv(df[GROUP_COLUMNS], GROUPS_FILE)
        return _normalize_group(df.loc[fila].to_dict())

    @staticmethod
    def delete_group(group_id: str) -> bool:
        df = read_csv(GROUPS_FILE, GROUP_COLUMNS)
        indices = _indices_de(df, 'id', group_id)
        if not indices:
            return False

        # Remove group — solo una fila, por si el id estuviera repetido.
        df = df.drop(index=indices[0])
        save_csv(df, GROUPS_FILE)

        # Remove associated payments (aquí sí van todos: son muchos por grupo)
        payments_df = read_csv(PAYMENTS_FILE, PAYMENT_COLUMNS)
        payments_df = payments_df[payments_df['group_id'] != group_id]
        save_csv(payments_df, PAYMENTS_FILE)
        
        return True

    @staticmethod
    def get_payments(group_id: str = None) -> List[Dict[str, Any]]:
        df = read_csv(PAYMENTS_FILE, PAYMENT_COLUMNS)

        # Coerce types to handle invalid data
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
        # Convert dates and handle errors
        df['start_date'] = pd.to_datetime(df['start_date'], errors='coerce').dt.date
        df['end_date'] = pd.to_datetime(df['end_date'], errors='coerce').dt.date

        # Filter invalid rows (ensure required fields are present).
        # Lo que se cae aquí no desaparece: `get_invalid_payments()` lo lista.
        df = df.dropna(subset=PAYMENT_REQUIRED)

        if group_id:
            df = df[df['group_id'] == group_id]

        df["note"] = df["note"].fillna("")  # Ensure note is never None

        # `NaT` es el hueco de pandas y no sobrevive a JSON ni a un `if fecha`. Las fechas
        # ausentes salen como `None`, que es lo que significan: «desde siempre» / «para
        # siempre».
        registros = df.to_dict('records')
        for registro in registros:
            for campo in ('start_date', 'end_date'):
                if pd.isna(registro[campo]):
                    registro[campo] = None
        return registros

    @staticmethod
    def get_invalid_payments(group_id: str = None) -> List[Dict[str, Any]]:
        """Las filas de `pagos.csv` que `get_payments()` descarta, con el motivo.

        Sin esto son fantasmas: no las aplica el dashboard y no las lista la pantalla de
        Variables, así que el usuario no puede borrar lo que no puede ver. Llegó a haber 4.

        Se devuelven **en crudo y como texto**, porque justamente lo que les pasa es que
        algún campo no se deja convertir. `delete_payment()` sí sabe borrarlas: opera sobre
        el CSV sin filtrar.

        Una fecha ausente **no** hace inválida a una fila de un grupo `fixed`: ahí significa
        «desde siempre» o «para siempre». En un grupo `interpolated` sí, porque sin las dos
        puntas no hay tramo que repartir y el pago no haría nada.
        """
        df = read_csv(PAYMENTS_FILE, PAYMENT_COLUMNS)

        amount = pd.to_numeric(df['amount'], errors='coerce')
        inicio = pd.to_datetime(df['start_date'], errors='coerce')
        fin = pd.to_datetime(df['end_date'], errors='coerce')
        tipos = {g['id']: g['type'] for g in InterpolationStorage.get_groups(type_filter=None)}

        invalidas = []
        for pos, (_, fila) in enumerate(df.iterrows()):
            faltan = []
            grupo = str(fila.get('group_id') or '').strip()
            if not str(fila.get('id') or '').strip():
                faltan.append('id')
            if not grupo:
                faltan.append('grupo')
            elif grupo not in tipos:
                faltan.append('un grupo que exista')
            if pd.isna(amount.iloc[pos]):
                faltan.append('monto')
            if tipos.get(grupo) == 'interpolated':
                if pd.isna(inicio.iloc[pos]):
                    faltan.append('fecha de inicio (obligatoria al interpolar)')
                if pd.isna(fin.iloc[pos]):
                    faltan.append('fecha de fin (obligatoria al interpolar)')
            if not faltan:
                continue
            if group_id and str(fila.get('group_id') or '') != str(group_id):
                continue
            invalidas.append({
                'id': _texto_plano(fila.get('id')),
                'group_id': _texto_plano(fila.get('group_id')),
                'amount': _texto_plano(fila.get('amount')),
                'start_date': _texto_plano(fila.get('start_date')),
                'end_date': _texto_plano(fila.get('end_date')),
                'note': _texto_plano(fila.get('note')),
                'fila': pos + 2,  # +1 por el encabezado, +1 porque los humanos cuentan desde 1
                'motivo': 'Le falta: ' + ', '.join(faltan),
            })
        return invalidas

    @staticmethod
    def get_payment(payment_id: str) -> Optional[Dict[str, Any]]:
        df = read_csv(PAYMENTS_FILE, PAYMENT_COLUMNS)

        # Coerce types to handle invalid data
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
        df['start_date'] = pd.to_datetime(df['start_date'], errors='coerce').dt.date
        df['end_date'] = pd.to_datetime(df['end_date'], errors='coerce').dt.date

        # Filter invalid rows first
        df = df.dropna(subset=PAYMENT_REQUIRED)

        payment = df[df['id'] == payment_id]
        if payment.empty:
            return None
            
        return payment.iloc[0].to_dict()

    @staticmethod
    def create_payment(group_id: str, amount: float, start_date: date, end_date: date, note: str = None) -> Dict[str, Any]:
        ensure_data_dir()
        # El id se comprueba contra los que ya están: un uuid4 no colisiona por azar, pero
        # `pagos.csv` sí llegó a tener ids repetidos (sembrados a mano) y desde entonces
        # toda escritura por id es ambigua. Aquí se corta el problema en el origen.
        new_id = _id_unico(read_csv(PAYMENTS_FILE, PAYMENT_COLUMNS))
        new_row = {
            'id': new_id, 
            'group_id': group_id, 
            'amount': amount, 
            'start_date': start_date, 
            'end_date': end_date, 
            'note': note
        }
        df_new = pd.DataFrame([new_row])
        
        if os.path.exists(PAYMENTS_FILE) and os.path.getsize(PAYMENTS_FILE) > 0:
            try:
                shutil.copy2(PAYMENTS_FILE, PAYMENTS_FILE + ".bak")
            except Exception:
                pass
            df_new.to_csv(PAYMENTS_FILE, mode='a', header=False, index=False)
        else:
            df_new.to_csv(PAYMENTS_FILE, index=False)
        return new_row

    @staticmethod
    def update_payment(payment_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        df = read_csv(PAYMENTS_FILE, PAYMENT_COLUMNS)

        indices = _indices_de(df, 'id', payment_id)
        if not indices:
            return None
        if len(indices) > 1:
            logger.warning("pagos.csv tiene el id %s en %d filas; se edita solo la primera "
                           "(filas %s)", payment_id, len(indices), [i + 2 for i in indices])
        fila = indices[0]

        if pd.isna(df.at[fila, 'note']):
            df.at[fila, 'note'] = ""  # Ensure note is not NaN for the update process
        for key, value in updates.items():
            if key in df.columns:
                if isinstance(value, (date, datetime)):
                    value = value.isoformat()
                df.at[fila, key] = value
        save_csv(df, PAYMENTS_FILE)

        return df.loc[fila].to_dict()

    @staticmethod
    def delete_payment(payment_id: str) -> bool:
        df = read_csv(PAYMENTS_FILE, PAYMENT_COLUMNS)

        indices = _indices_de(df, 'id', payment_id)
        if not indices:
            return False
        if len(indices) > 1:
            logger.warning("pagos.csv tiene el id %s en %d filas; se borra solo la primera "
                           "(filas %s)", payment_id, len(indices), [i + 2 for i in indices])

        df = df.drop(index=indices[0])
        save_csv(df, PAYMENTS_FILE)
        return True

    @staticmethod
    def delete_payment_row(fila: int) -> bool:
        """Borra por número de fila del CSV (1 = encabezado), no por id.

        Es la única forma de quitar una fila inválida: puede no tener id, o tener uno
        repetido. `get_invalid_payments()` devuelve ese número en `fila`.
        """
        df = read_csv(PAYMENTS_FILE, PAYMENT_COLUMNS)
        indice = fila - 2  # deshacer el encabezado y el conteo desde 1
        if indice < 0 or indice >= len(df):
            return False
        df = df.drop(index=df.index[indice])
        save_csv(df, PAYMENTS_FILE)
        return True
