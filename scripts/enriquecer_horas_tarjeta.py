"""
Enriquece las transacciones de tarjeta con la HORA del consumo, obtenida de los
correos "Notificación de Consumos" del Banco Pichincha que viven en el proyecto
`informacion` (dbs/correos.db).

POR QUÉ UN ARCHIVO APARTE Y NO tarjeta_unida.xlsx
-------------------------------------------------
`tarjeta_unida.xlsx` es un artefacto DERIVADO: `sources_service.py` lo reescribe
entero (`df_unido.to_excel(...)`) cada vez que se reprocesan los `.xls` crudos, y
además recorta el DataFrame a `required_cols` = [id, FECHA, DESCRIPCION, MONTO,
FUENTE, OPERACION]. Cualquier hora escrita ahí se perdería en el siguiente
reproceso, y una columna extra sería descartada aunque el archivo sobreviviera.

Por eso seguimos el patrón que el proyecto ya usa para datos añadidos por el
usuario (`data/sistema/etiquetado/etiquetas.csv`): un CSV lateral enlazado por
`source_id` + `source_type`. Sobrevive al reproceso y es auditable y reversible.

El enlace es estable: `id_utils.add_id_column` normaliza la fecha a '%Y-%m-%d'
antes de hashear, así que la hora nunca entra en el `id`. Aun así guardamos
FECHA/MONTO/DESCRIPCION en el sidecar para poder re-enlazar si un `id` cambiara.

GARANTÍAS
---------
- Solo lectura sobre correos.db (abierto con mode=ro) y sobre tarjeta_unida.xlsx.
- No toca etiquetas.csv, gastos_maestros.csv ni ningún artefacto del pipeline.
- Idempotente: dos ejecuciones seguidas producen el mismo CSV.
- Determinista: el emparejamiento no depende del orden de las filas.
- Nunca inventa una hora: si no hay correo que la respalde, no se escribe fila.
- Cada fila registra la regla y el correo que la justifican.

Uso:
    python scripts/enriquecer_horas_tarjeta.py [--dry-run] [--verbose]
"""

from __future__ import annotations

import argparse
import hashlib
import html
import os
import re
import sqlite3
import sys
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher

import pandas as pd

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from contabilidad.config import PATH_DATA, PATH_TARJETA_UNIDA  # noqa: E402

PATH_CORREOS_DB = os.environ.get(
    "PATH_CORREOS_DB", "/home/sebas/dev/projects/informacion/dbs/correos.db"
)
PATH_ENRIQUECIMIENTO_DIR = os.path.join(PATH_DATA, "sistema", "enriquecimiento")
PATH_HORAS_TARJETA = os.path.join(PATH_ENRIQUECIMIENTO_DIR, "horas_tarjeta.csv")

ASUNTO_CORREO = "Notificación de Consumos"
SOURCE_TYPE = "TARJETA"

# --- Parámetros de las reglas -------------------------------------------------
# El estado de cuenta registra el consumo el mismo día o hasta 3 días después de
# que ocurrió; nunca antes. Verificado sobre 2024-01..2026-07: ampliar la ventana
# hacia el futuro no aporta ni un match más, así que se mantiene asimétrica para
# no abrir la puerta a falsos positivos.
VENTANA_DIAS_ANTES = 3
VENTANA_DIAS_DESPUES = 0

TOLERANCIA_CENTAVOS = 0.005  # igualdad de monto

# R1 (monto exacto): monto + fecha ya son evidencia fuerte, el texto solo desempata.
SIM_MIN_MONTO_EXACTO = 0.30
# R2/R3 (monto distinto): la evidencia del monto es más débil, se exige más texto.
SIM_MIN_TARIFA = 0.55
SIM_MIN_REDONDEO = 0.75

# R2: el correo notifica el total cobrado en el punto de venta (consumo + tarifa
# de gasolinera + su IVA) mientras el estado lo desglosa en dos líneas. Solo se
# aplica si la línea de tarifa existe realmente en la misma fecha, y el delta
# debe caber en [tarifa, tarifa * (1 + IVA_MAX)] — así la regla se auto-limita y
# sigue siendo correcta si cambia el IVA o el importe de la tarifa.
PATRON_TARIFA_GASOLINERA = r"TARIFA CONSUMO GASOLINERA"
IVA_MAX = 0.15

# R3: redondeo al céntimo en gasolineras (el surtidor cobra 15.00, el estado
# liquida 14.95). Deliberadamente estrecho.
REDONDEO_MAX = 0.05

# R4: Excepción acotada temporalmente para consumos en el exterior (2026-08-20 a 2026-09-09).
# Al pagar en moneda extranjera (ej. Reales BRL en Brasil), el correo de notificación
# usa el tipo de cambio spot inmediato pero el estado de cuenta liquida días después
# con la tasa de liquidación final, produciendo una variación del ~0.45% (hasta 1.5% o $0.35).
FECHA_INICIO_EXCEPCION_EXTERIOR = "2026-08-20"
FECHA_FIN_EXCEPCION_EXTERIOR = "2026-09-09"
SIM_MIN_EXTERIOR_FX = 0.45
PCT_MAX_EXTERIOR_FX = 1.5
DELTA_MAX_EXTERIOR_FX = 0.35


# Apuntes que por naturaleza nunca generan un correo de consumo. Excluirlos no
# solo ahorra trabajo: evita que un cargo derivado coincida por monto con un
# consumo ajeno y reciba una hora que no le corresponde.
PATRON_NO_CONSUMO = (
    r"RET IVA|^IVA\b|DEV IVA|INT\. FINANCIAMIENTO|INT\. MORA|INTERESES"
    r"|PLAN DE RECOMPENSAS|PRESTACIONES EN EL EXTERIOR|SOLCA|SEGURO|COMISION"
    r"|REPOSICION TARJETA|GESTION DE COBRANZA|TARIFA CONSUMO GASOLINERA"
    r"|CONSUMOS EXTERIOR|CONS DIGITAL|NC REVERSO|N/C|^PAGO\b"
)

COLUMNAS_SALIDA = [
    "source_id",
    "source_type",
    "FECHA",
    "MONTO",
    "DESCRIPCION",
    "HORA",
    "FECHA_HORA_CONSUMO",
    "regla",
    "similitud",
    "delta_monto",
    "delta_dias",
    "id_correo",
    "establecimiento_correo",
    "monto_correo",
    "generado_en",
]


# --- Utilidades ---------------------------------------------------------------
def _normalizar_texto(s: str) -> str:
    """Mayúsculas sin acentos ni puntuación, para comparar descripciones."""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^A-Za-z0-9]", " ", s).upper().split())


def _similitud(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalizar_texto(a), _normalizar_texto(b)).ratio()


def _limpiar_sufijo_exterior(desc: str) -> str:
    """Limpia sufijos de procesamiento bancario internacional (ej. ' R CONSUMO BRA', ' S CONSUMO BRA')."""
    s = re.sub(r"\s+[A-Z]\s+CONSUMO\s+[A-Z]{3}$", "", str(desc), flags=re.IGNORECASE)
    s = re.sub(r"\s+CONSUMO\s+[A-Z]{3}$", "", s, flags=re.IGNORECASE)
    return s



def _parsear_monto(texto: str) -> float | None:
    """'1.234,56' -> 1234.56 (formato es-EC del correo)."""
    try:
        return float(texto.replace(".", "").replace(",", "."))
    except ValueError:
        return None


# --- Carga de datos -----------------------------------------------------------
def cargar_correos(path_db: str) -> pd.DataFrame:
    """Extrae monto, establecimiento, tarjeta y fecha+hora de cada notificación."""
    if not os.path.exists(path_db):
        raise FileNotFoundError(
            f"No se encontró la base de correos en {path_db}. "
            "Ajusta la variable de entorno PATH_CORREOS_DB."
        )

    uri = f"file:{path_db}?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        filas = conn.execute(
            "SELECT id, contexto FROM mensajes WHERE titulo = ?", (ASUNTO_CORREO,)
        ).fetchall()

    registros, sin_parsear = [], 0
    for id_correo, contexto in filas:
        texto = re.sub(r"[ \t\r]+", " ", html.unescape(contexto or ""))

        m_valor = re.search(r"Valor\s*\$?\s*([\d.,]+)", texto)
        m_fecha = re.search(
            r"Fecha\s*\n?\s*(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})", texto
        )
        if not (m_valor and m_fecha):
            sin_parsear += 1
            continue

        monto = _parsear_monto(m_valor.group(1))
        if monto is None:
            sin_parsear += 1
            continue

        m_est = re.search(r"Establecimiento\s*\n?\s*(.+?)\s*\n", texto)
        m_tar = re.search(r"Tarjeta usada\s*\n?\s*(\S+)", texto)

        registros.append(
            {
                "id_correo": id_correo,
                "monto": monto,
                "establecimiento": m_est.group(1).strip() if m_est else "",
                "tarjeta": m_tar.group(1).strip() if m_tar else "",
                "fecha": m_fecha.group(1),
                "hora": m_fecha.group(2),
            }
        )

    df = pd.DataFrame(registros)
    if df.empty:
        raise ValueError(f"No se pudo parsear ningún correo '{ASUNTO_CORREO}'.")
    df["fecha"] = pd.to_datetime(df["fecha"])
    df.attrs["sin_parsear"] = sin_parsear
    df.attrs["total"] = len(filas)
    return df


def cargar_transacciones(path_xlsx: str) -> pd.DataFrame:
    if not os.path.exists(path_xlsx):
        raise FileNotFoundError(f"No se encontró {path_xlsx}.")
    df = pd.read_excel(path_xlsx)
    faltantes = {"id", "FECHA", "DESCRIPCION", "MONTO"} - set(df.columns)
    if faltantes:
        raise ValueError(f"{path_xlsx} no tiene las columnas {sorted(faltantes)}.")
    df["FECHA"] = pd.to_datetime(df["FECHA"])
    return df


def es_consumo(df: pd.DataFrame) -> pd.Series:
    """Filas que pueden haber generado un correo de consumo."""
    no_consumo = df["DESCRIPCION"].astype(str).str.contains(
        PATRON_NO_CONSUMO, case=False, regex=True, na=False
    )
    return ~no_consumo & (df["MONTO"] > 0)


# --- Reglas de emparejamiento -------------------------------------------------
def _delta_tarifa_valido(delta: float, fecha, df_completo: pd.DataFrame) -> bool:
    """
    R2: ¿el delta se explica por una tarifa de gasolinera cobrada aparte?

    Exige que la línea de tarifa exista en el estado en esa misma fecha, y que el
    delta esté entre el importe de la tarifa y ese importe con IVA. No se
    hardcodea 0.23: se deriva del dato real, así la regla sigue valiendo si el
    banco cambia la tarifa o el país cambia el IVA.
    """
    tarifas = df_completo[
        (df_completo["FECHA"] == fecha)
        & df_completo["DESCRIPCION"].astype(str).str.contains(
            PATRON_TARIFA_GASOLINERA, case=False, na=False
        )
    ]
    if tarifas.empty:
        return False
    return any(
        importe - TOLERANCIA_CENTAVOS <= delta <= importe * (1 + IVA_MAX) + TOLERANCIA_CENTAVOS
        for importe in tarifas["MONTO"]
    )


def generar_candidatos(
    df_tx: pd.DataFrame, df_correos: pd.DataFrame, df_completo: pd.DataFrame
) -> list[dict]:
    """
    Todos los pares (transacción, correo) que satisfacen alguna regla.

    No decide nada todavía: solo propone. La asignación ocurre después, de forma
    global, para que el resultado no dependa del orden de las filas.
    """
    candidatos = []
    fecha_min_excep = pd.Timestamp(FECHA_INICIO_EXCEPCION_EXTERIOR)
    fecha_max_excep = pd.Timestamp(FECHA_FIN_EXCEPCION_EXTERIOR)

    for _, tx in df_tx.iterrows():
        dias = (df_correos["fecha"] - tx["FECHA"]).dt.days
        en_ventana = df_correos[
            (dias >= -VENTANA_DIAS_ANTES) & (dias <= VENTANA_DIAS_DESPUES)
        ]
        desc_limpia = _limpiar_sufijo_exterior(tx["DESCRIPCION"])

        for _, correo in en_ventana.iterrows():
            # El correo notifica el total cobrado; el estado puede liquidar menos o variar por FX.
            delta = correo["monto"] - tx["MONTO"]
            abs_delta = abs(delta)
            pct_diff = (abs_delta / tx["MONTO"]) * 100 if tx["MONTO"] > 0 else 0

            sim_orig = _similitud(tx["DESCRIPCION"], correo["establecimiento"])
            sim_clean = _similitud(desc_limpia, correo["establecimiento"])
            sim = max(sim_orig, sim_clean)

            if abs_delta < TOLERANCIA_CENTAVOS:
                regla, sim_min, prioridad = "R1_monto_exacto", SIM_MIN_MONTO_EXACTO, 4
            elif delta > 0 and _delta_tarifa_valido(delta, tx["FECHA"], df_completo):
                regla, sim_min, prioridad = "R2_tarifa_gasolinera", SIM_MIN_TARIFA, 3
            elif 0 < delta <= REDONDEO_MAX + TOLERANCIA_CENTAVOS:
                regla, sim_min, prioridad = "R3_redondeo", SIM_MIN_REDONDEO, 2
            elif (
                fecha_min_excep <= tx["FECHA"] <= fecha_max_excep
                and (pct_diff <= PCT_MAX_EXTERIOR_FX or abs_delta <= DELTA_MAX_EXTERIOR_FX)
            ):
                regla, sim_min, prioridad = "R4_exterior_fx_viaje", SIM_MIN_EXTERIOR_FX, 1
            else:
                continue

            if sim < sim_min:
                continue


            candidatos.append(
                {
                    "source_id": tx["id"],
                    "id_correo": correo["id_correo"],
                    "prioridad": prioridad,
                    "regla": regla,
                    "similitud": round(sim, 4),
                    "delta_monto": round(-delta, 2) + 0.0,  # tx - correo (+0.0 evita "-0.0")
                    "delta_dias": int((correo["fecha"] - tx["FECHA"]).days),
                    "hora": correo["hora"],
                    "fecha_consumo": correo["fecha"],
                    "establecimiento_correo": correo["establecimiento"],
                    "monto_correo": correo["monto"],
                    "FECHA": tx["FECHA"],
                    "MONTO": tx["MONTO"],
                    "DESCRIPCION": tx["DESCRIPCION"],
                }
            )
    return candidatos


def asignar(candidatos: list[dict]) -> list[dict]:
    """
    Asignación 1:1 entre transacciones y correos.

    Greedy sobre los candidatos ordenados por calidad (regla más fuerte, luego
    similitud, luego menor distancia temporal). El desempate final por los ids
    hace el resultado determinista aunque dos candidatos empaten en todo lo
    demás, de modo que reordenar el Excel no cambia la salida.
    """
    candidatos.sort(
        key=lambda c: (
            -c["prioridad"],
            -c["similitud"],
            abs(c["delta_dias"]),
            str(c["source_id"]),
            c["id_correo"],
        )
    )

    tx_usadas, correos_usados, asignados = set(), set(), []
    for c in candidatos:
        if c["source_id"] in tx_usadas or c["id_correo"] in correos_usados:
            continue
        tx_usadas.add(c["source_id"])
        correos_usados.add(c["id_correo"])
        asignados.append(c)
    return asignados


# --- Persistencia -------------------------------------------------------------
def construir_salida(asignados: list[dict]) -> pd.DataFrame:
    if not asignados:
        return pd.DataFrame(columns=COLUMNAS_SALIDA)

    ahora = datetime.now().isoformat(timespec="seconds")
    filas = []
    for c in asignados:
        fecha_hora = pd.Timestamp(f"{c['fecha_consumo'].date()} {c['hora']}")
        filas.append(
            {
                "source_id": c["source_id"],
                "source_type": SOURCE_TYPE,
                "FECHA": c["FECHA"].strftime("%Y-%m-%d"),
                "MONTO": round(float(c["MONTO"]), 2),
                "DESCRIPCION": str(c["DESCRIPCION"]).strip(),
                "HORA": c["hora"],
                "FECHA_HORA_CONSUMO": fecha_hora.strftime("%Y-%m-%d %H:%M"),
                "regla": c["regla"],
                "similitud": c["similitud"],
                "delta_monto": c["delta_monto"],
                "delta_dias": c["delta_dias"],
                "id_correo": c["id_correo"],
                "establecimiento_correo": c["establecimiento_correo"],
                "monto_correo": round(float(c["monto_correo"]), 2),
                "generado_en": ahora,
            }
        )

    df = pd.DataFrame(filas, columns=COLUMNAS_SALIDA)
    # Orden estable en disco: facilita revisar el diff entre ejecuciones.
    return df.sort_values(["FECHA", "source_id"]).reset_index(drop=True)


def guardar(df: pd.DataFrame, path: str) -> None:
    """Escritura atómica, con backup del CSV anterior si existía."""
    os.makedirs(os.path.dirname(path), exist_ok=True)

    if os.path.exists(path):
        backup = path + ".bak"
        with open(path, "rb") as origen, open(backup, "wb") as destino:
            destino.write(origen.read())

    tmp = path + ".tmp"
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)


def _huella(df: pd.DataFrame) -> str:
    """Hash del contenido ignorando `generado_en`, para comprobar idempotencia."""
    estable = df.drop(columns=["generado_en"], errors="ignore")
    return hashlib.md5(estable.to_csv(index=False).encode("utf-8")).hexdigest()


# --- Informe ------------------------------------------------------------------
def informar(
    df_tx_total: pd.DataFrame,
    df_consumos: pd.DataFrame,
    df_correos: pd.DataFrame,
    salida: pd.DataFrame,
    verbose: bool,
) -> None:
    total, consumos, con_hora = len(df_tx_total), len(df_consumos), len(salida)
    pct = (con_hora / consumos * 100) if consumos else 0.0

    print(f"\n{'=' * 62}")
    print("ENRIQUECIMIENTO DE HORAS DE TARJETA")
    print(f"{'=' * 62}")
    print(f"  correos leídos           {df_correos.attrs['total']:>6}"
          f"  (sin parsear: {df_correos.attrs['sin_parsear']})")
    print(f"  transacciones de tarjeta {total:>6}")
    print(f"  de ellas, consumos       {consumos:>6}"
          f"  ({total - consumos} apuntes sin correo posible)")
    print(f"  con hora asignada        {con_hora:>6}  ({pct:.1f}% de los consumos)")

    if con_hora:
        print("\n  por regla:")
        for regla, n in salida["regla"].value_counts().sort_index().items():
            print(f"    {regla:<24} {n:>5}")

    sin_hora = df_consumos[~df_consumos["id"].isin(salida["source_id"])]
    if len(sin_hora):
        print(f"\n  consumos sin hora: {len(sin_hora)}")
        muestra = sin_hora if verbose else sin_hora.head(10)
        for _, r in muestra.iterrows():
            print(f"    {r['FECHA'].date()} {r['MONTO']:>8.2f}  {str(r['DESCRIPCION'])[:40]}")
        if not verbose and len(sin_hora) > 10:
            print(f"    ... y {len(sin_hora) - 10} más (usa --verbose)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument(
        "--dry-run", action="store_true", help="Calcula e informa sin escribir nada."
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Lista todos los consumos sin hora."
    )
    args = parser.parse_args()

    df_correos = cargar_correos(PATH_CORREOS_DB)
    df_tx = cargar_transacciones(PATH_TARJETA_UNIDA)
    df_consumos = df_tx[es_consumo(df_tx)]

    candidatos = generar_candidatos(df_consumos, df_correos, df_tx)
    asignados = asignar(candidatos)
    salida = construir_salida(asignados)

    informar(df_tx, df_consumos, df_correos, salida, args.verbose)

    if args.dry_run:
        print(f"\n  [dry-run] no se escribió nada. Destino sería: {PATH_HORAS_TARJETA}")
    else:
        guardar(salida, PATH_HORAS_TARJETA)
        print(f"\n  guardado en {PATH_HORAS_TARJETA}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
