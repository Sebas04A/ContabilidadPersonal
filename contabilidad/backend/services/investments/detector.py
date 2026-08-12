"""
detector.py — Reconstruye las posiciones de plazo fijo a partir de los datos bancarios.

El banco no dice "esta cancelación corresponde a aquella apertura". Hay que emparejarlas,
y resulta que se puede hacer sin ambigüedad porque **el capital devuelto es exactamente
igual al capital depositado** (el interés viaja en filas aparte). Con eso alcanza:
emparejar por monto exacto, FIFO cuando hay varias abiertas del mismo monto.

Sobre los datos reales (`banca_unida.xlsx`, 1122 filas) esto empareja 14 aperturas con
14 cierres, sin huérfanas ni ambigüedades.

## Anatomía de una cancelación

El banco emite todas las patas de la cancelación con **la misma marca de tiempo**:

    2026-07-27 08:16:00  CANCELACION PLAZO FIJO             27000.00   ← capital
    2026-07-27 08:16:00  REGULARIZACIÓN DE TRANSACCIÓN         69.60   ← interés
    2026-07-27 08:16:00  RETENCION RENDIMIENTO FINANCIERO      -2.09   ← retención

Dos trampas que obligan a filtrar por descripción y no por "todo lo positivo del día":

1. **El interés cambió de nombre tres veces.** Hasta 2025-03 venía como una *segunda
   fila* `CANCELACION PLAZO FIJO`; entre 2025-06 y 2026-03 como `TRANSFERENCIA INTERIOR`;
   desde 2026-07 como `REGULARIZACIÓN DE TRANSACCIÓN`.

2. **Hay días sin hora.** En los extractos viejos (p.ej. 2024-09-04) todas las filas
   quedaron a medianoche, así que "misma marca de tiempo" degenera en "mismo día" y se
   cuela cualquier transferencia. El 2025-12-22, por ejemplo, hay depósitos de 110, 75 y
   45 que no tienen nada que ver con la cancelación de ese día.

De ahí que una fila solo cuente como interés si además su descripción está en la lista
blanca. Confundir esas dos cosas es el bug que hacía que 22 filas `CANCELACION PLAZO
FIJO` se reportaran como 22 inversiones cuando en realidad son 14 cancelaciones y 8
intereses.
"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import pandas as pd

from contabilidad.backend.logger import get_logger

logger = get_logger(__name__)


# ── Vocabulario del banco ────────────────────────────────────────────────────

#: Un débito con alguna de estas descripciones abre una posición.
OPENING_PATTERNS: Tuple[str, ...] = (
    "CERTIFICADO DE DEPOSITO",
    "A PLAZO FIJO",  # cubre "APERTURA DE DEPÓSTIO A PLAZO FIJO" (sic, así lo escribe el banco)
)

#: La devolución del capital al vencimiento.
CLOSING_DESCRIPTION = "CANCELACION PLAZO FIJO"

#: Las tres formas en que el banco ha rotulado el interés. `CLOSING_DESCRIPTION` está
#: en la lista a propósito: una segunda fila de cancelación que no empareja con ninguna
#: apertura es el interés de la que sí emparejó.
INTEREST_DESCRIPTIONS: Tuple[str, ...] = (
    "TRANSFERENCIA INTERIOR",
    "REGULARIZACION DE TRANSACCION",
    CLOSING_DESCRIPTION,
)

#: Cubre "RETENCION RENDIMIENTO FINANCIERO" y "RETENCION 2% RENDIMIENTO FINANCIERO".
WITHHOLDING_PATTERN = re.compile(r"RETENCION.*RENDIMIENTO")

#: Los montos del banco vienen a dos decimales; nunca hay que emparejar más fino.
AMOUNT_TOLERANCE = 0.01

DAYS_PER_YEAR = 365


# ── Normalización ────────────────────────────────────────────────────────────

def normalize_description(value: Any) -> str:
    """Mayúsculas, sin tildes y con espacios colapsados.

    El banco alterna "REGULARIZACIÓN" y "REGULARIZACION" según el extracto, así que
    comparar en crudo se rompe solo.
    """
    text = "" if value is None else str(value)
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(without_accents.upper().split())


# ── Estructuras ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class InvestmentLeg:
    """Una fila bancaria que forma parte de una posición."""

    tipo: str  # 'aporte' | 'retiro' | 'interes' | 'retencion'
    fecha: date
    monto: float  # siempre positivo; el signo lo da `tipo`
    tx_id: str
    descripcion: str


@dataclass
class DetectedPosition:
    """Una inversión reconstruida: su apertura, su cierre y las patas de ambos."""

    capital: float
    fecha_apertura: date
    tx_apertura_id: str
    fecha_cierre: Optional[date] = None
    tx_cierre_id: Optional[str] = None
    interes: float = 0.0
    retencion: float = 0.0
    movimientos: List[InvestmentLeg] = field(default_factory=list)
    #: True si las patas se agruparon por día porque las filas no traían hora.
    legs_por_dia: bool = False
    #: True si varias cancelaciones compartían marca de tiempo y hubo que prorratear.
    ambiguo: bool = False

    @property
    def estado(self) -> str:
        return "cerrada" if self.fecha_cierre else "abierta"

    @property
    def dias(self) -> Optional[int]:
        if self.fecha_cierre is None:
            return None
        return (self.fecha_cierre - self.fecha_apertura).days

    @property
    def neto(self) -> float:
        """Lo que efectivamente ganaste, ya descontada la retención."""
        return round(self.interes - self.retencion, 2)

    @property
    def total_devuelto(self) -> float:
        return round(self.capital + self.interes - self.retencion, 2)

    @property
    def tna(self) -> Optional[float]:
        """Tasa nominal anual aproximada, en porcentaje. None si sigue abierta.

        Es una *estimación*, no la tasa pactada, porque usa días calendario entre
        apertura y cancelación sobre base 365. El banco liquida sobre el plazo pactado
        con base 360, y ambos difieren: la posición 2025-11-18 → 2025-12-19 son 31 días
        calendario, pero el interés de 67,43 sobre 27.000 corresponde a 30 días al 3 %
        base 360 (67,50). Sirve para comparar posiciones entre sí; para la tasa exacta
        hace falta capturar `plazo_pactado_dias`.
        """
        dias = self.dias
        if not dias or self.capital <= 0:
            return None
        return round(self.interes / self.capital * DAYS_PER_YEAR / dias * 100, 4)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capital": round(self.capital, 2),
            "fecha_apertura": self.fecha_apertura.isoformat(),
            "fecha_cierre": self.fecha_cierre.isoformat() if self.fecha_cierre else None,
            "tx_apertura_id": self.tx_apertura_id,
            "tx_cierre_id": self.tx_cierre_id,
            "interes": round(self.interes, 2),
            "retencion": round(self.retencion, 2),
            "neto": self.neto,
            "total_devuelto": self.total_devuelto,
            "estado": self.estado,
            "dias": self.dias,
            "tna": self.tna,
            "ambiguo": self.ambiguo,
        }


@dataclass
class OrphanClosing:
    """Cancelación sin apertura: la inversión se abrió antes de que empiece el historial.

    No es un fallo del emparejamiento, es un límite de los datos. Estas hay que sembrarlas
    a mano como posiciones manuales.
    """

    fecha: date
    capital_sugerido: float
    interes_sugerido: float
    retencion: float
    tx_ids: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fecha": self.fecha.isoformat(),
            "capital_sugerido": round(self.capital_sugerido, 2),
            "interes_sugerido": round(self.interes_sugerido, 2),
            "retencion": round(self.retencion, 2),
            "tx_ids": list(self.tx_ids),
        }


@dataclass
class DetectionResult:
    posiciones: List[DetectedPosition] = field(default_factory=list)
    huerfanas: List[OrphanClosing] = field(default_factory=list)

    @property
    def cerradas(self) -> List[DetectedPosition]:
        return [p for p in self.posiciones if p.estado == "cerrada"]

    @property
    def abiertas(self) -> List[DetectedPosition]:
        return [p for p in self.posiciones if p.estado == "abierta"]

    @property
    def capital_abierto(self) -> float:
        return round(sum(p.capital for p in self.abiertas), 2)

    @property
    def interes_total(self) -> float:
        return round(sum(p.interes for p in self.cerradas), 2)

    @property
    def retencion_total(self) -> float:
        return round(sum(p.retencion for p in self.cerradas), 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "posiciones": [p.to_dict() for p in self.posiciones],
            "huerfanas": [h.to_dict() for h in self.huerfanas],
            "capital_abierto": self.capital_abierto,
            "interes_total": self.interes_total,
            "retencion_total": self.retencion_total,
        }


# ── Predicados sobre filas ───────────────────────────────────────────────────

def _is_opening(desc: str, monto: float) -> bool:
    return monto < 0 and any(p in desc for p in OPENING_PATTERNS)


def _is_closing(desc: str, monto: float) -> bool:
    return monto > 0 and desc == CLOSING_DESCRIPTION


def _is_interest_candidate(desc: str, monto: float) -> bool:
    return monto > 0 and desc in INTEREST_DESCRIPTIONS


def _is_withholding(desc: str, monto: float) -> bool:
    return monto < 0 and bool(WITHHOLDING_PATTERN.search(desc))


# ── Preparación ──────────────────────────────────────────────────────────────

def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Copia ordenada por fecha, con descripción normalizada e id garantizado."""
    required = {"FECHA", "DESCRIPCION", "MONTO"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas para detectar inversiones: {sorted(missing)}")

    out = df.copy()
    out["FECHA"] = pd.to_datetime(out["FECHA"])
    out["_desc"] = out["DESCRIPCION"].map(normalize_description)
    out["_monto"] = pd.to_numeric(out["MONTO"], errors="coerce").fillna(0.0)
    if "id" in out.columns:
        out["_tx_id"] = out["id"].astype(str)
    else:
        out["_tx_id"] = out.index.astype(str)

    # `kind='stable'` para que el orden original desempate: dentro de una misma marca de
    # tiempo, el extracto lista las patas en el orden en que ocurrieron.
    return out.sort_values("FECHA", kind="stable")


def _collect_legs(
    df: pd.DataFrame,
    timestamp: pd.Timestamp,
    principal_idx: Set[Any],
) -> Tuple[List[Tuple[Any, str, float, str]], bool]:
    """Patas de interés y retención que acompañan a una cancelación.

    Devuelve `(patas, por_dia)`, donde cada pata es `(idx, tipo, monto, descripcion)`.
    `por_dia` avisa que la ventana no discrimina por hora —porque el extracto no la
    traía— y que por lo tanto las patas se eligieron solo por descripción.

    Excluye las filas de `principal_idx`: son capital de otras cancelaciones, no interés.
    """
    same_ts = df[df["FECHA"] == timestamp]

    # Si la marca de tiempo aísla una sola fila, el extracto no traía hora útil.
    if len(same_ts) <= 1:
        same_ts = df[df["FECHA"].dt.normalize() == timestamp.normalize()]

    # Medianoche exacta = el extracto no registró horas, así que "misma marca de tiempo"
    # y "mismo día" son lo mismo y la lista blanca es lo único que filtra.
    por_dia = timestamp == timestamp.normalize()

    legs: List[Tuple[Any, str, float, str]] = []
    for idx, row in same_ts.iterrows():
        if idx in principal_idx:
            continue
        desc, monto = row["_desc"], row["_monto"]
        if _is_withholding(desc, monto):
            legs.append((idx, "retencion", abs(monto), desc))
        elif _is_interest_candidate(desc, monto):
            legs.append((idx, "interes", monto, desc))

    return legs, por_dia


def _match_open_position(
    abiertas: List[Tuple[Any, DetectedPosition]], monto: float
) -> Optional[Tuple[Any, DetectedPosition]]:
    """La posición abierta más antigua cuyo capital coincide con `monto` (FIFO)."""
    for entry in abiertas:
        if abs(entry[1].capital - monto) <= AMOUNT_TOLERANCE:
            return entry
    return None


# ── Detección ────────────────────────────────────────────────────────────────

def detect_positions(df: pd.DataFrame) -> DetectionResult:
    """Empareja aperturas y cancelaciones de plazo fijo sobre un extracto bancario.

    `df` necesita al menos `FECHA`, `DESCRIPCION` y `MONTO`; si trae `id` se usa como
    referencia de transacción. No escribe nada: es solo lectura.
    """
    data = _prepare(df)

    abiertas: List[Tuple[Any, DetectedPosition]] = []
    cerradas: List[Tuple[Any, DetectedPosition]] = []
    principal_idx: Set[Any] = set()

    # Paso 1 — emparejar por capital exacto, FIFO.
    for idx, row in data.iterrows():
        desc, monto = row["_desc"], row["_monto"]
        fecha = row["FECHA"].date()

        if _is_opening(desc, monto):
            posicion = DetectedPosition(
                capital=round(abs(monto), 2),
                fecha_apertura=fecha,
                tx_apertura_id=row["_tx_id"],
            )
            posicion.movimientos.append(
                InvestmentLeg("aporte", fecha, posicion.capital, row["_tx_id"], row["DESCRIPCION"])
            )
            abiertas.append((idx, posicion))

        elif _is_closing(desc, monto):
            match = _match_open_position(abiertas, round(monto, 2))
            if match is None:
                # O es el interés de otra cancelación, o una posición abierta antes de
                # que empiece el historial. El paso 3 decide cuál.
                continue
            abiertas.remove(match)
            _, posicion = match
            posicion.fecha_cierre = fecha
            posicion.tx_cierre_id = row["_tx_id"]
            posicion.movimientos.append(
                InvestmentLeg("retiro", fecha, posicion.capital, row["_tx_id"], row["DESCRIPCION"])
            )
            principal_idx.add(idx)
            cerradas.append((idx, posicion))

    # Paso 2 — repartir interés y retención entre las cancelaciones de cada marca de
    # tiempo. Se hace después del paso 1 porque hasta no saber qué filas son capital no
    # se puede saber cuáles son interés.
    por_timestamp: Dict[pd.Timestamp, List[DetectedPosition]] = defaultdict(list)
    for idx, posicion in cerradas:
        por_timestamp[data.at[idx, "FECHA"]].append(posicion)

    consumed_idx: Set[Any] = set()
    for timestamp, posiciones in por_timestamp.items():
        legs, por_dia = _collect_legs(data, timestamp, principal_idx)
        consumed_idx.update(idx for idx, _, _, _ in legs)

        interes_total = sum(m for _, tipo, m, _ in legs if tipo == "interes")
        retencion_total = sum(m for _, tipo, m, _ in legs if tipo == "retencion")

        # Caso normal: una sola cancelación se queda con todo.
        if len(posiciones) == 1:
            posicion = posiciones[0]
            posicion.interes = round(interes_total, 2)
            posicion.retencion = round(retencion_total, 2)
            posicion.legs_por_dia = por_dia
            for idx, tipo, monto, descripcion in legs:
                posicion.movimientos.append(
                    InvestmentLeg(
                        tipo, timestamp.date(), monto, data.at[idx, "_tx_id"], descripcion
                    )
                )
            continue

        # Varias cancelaciones a la misma hora: el banco no dice qué interés es de cuál,
        # así que se prorratea por capital y se marca para revisión manual.
        capital_total = sum(p.capital for p in posiciones) or 1.0
        logger.warning(
            "%s cancelaciones comparten marca de tiempo %s; interés prorrateado por capital",
            len(posiciones), timestamp,
        )
        for posicion in posiciones:
            peso = posicion.capital / capital_total
            posicion.interes = round(interes_total * peso, 2)
            posicion.retencion = round(retencion_total * peso, 2)
            posicion.legs_por_dia = por_dia
            posicion.ambiguo = True

    # Paso 3 — lo que quedó: cancelaciones que no son capital de nadie ni interés de nadie.
    huerfanas = _collect_orphans(data, principal_idx, consumed_idx)

    posiciones = [p for _, p in cerradas] + [p for _, p in abiertas]
    posiciones.sort(key=lambda p: (p.fecha_apertura, p.capital))

    logger.info(
        "Inversiones detectadas: %s cerradas, %s abiertas, %s cancelaciones huérfanas",
        len(cerradas), len(abiertas), len(huerfanas),
    )
    return DetectionResult(posiciones=posiciones, huerfanas=huerfanas)


def _collect_orphans(
    data: pd.DataFrame, principal_idx: Set[Any], consumed_idx: Set[Any]
) -> List[OrphanClosing]:
    """Agrupa por fecha las cancelaciones sin apertura y sugiere cuál es el capital.

    Cuando el banco emite varias filas huérfanas el mismo día (p.ej. 2024-10-25 con
    12.854,21 y 682,63), lo casi seguro es que la mayor sea el capital y el resto el
    interés. Es una *sugerencia* para la pantalla de conciliación, no un hecho.
    """
    pendientes = [
        (idx, row)
        for idx, row in data.iterrows()
        if _is_closing(row["_desc"], row["_monto"])
        and idx not in principal_idx
        and idx not in consumed_idx
    ]
    if not pendientes:
        return []

    por_dia: Dict[date, List[Tuple[Any, pd.Series]]] = defaultdict(list)
    for idx, row in pendientes:
        por_dia[row["FECHA"].date()].append((idx, row))

    huerfanas: List[OrphanClosing] = []
    for fecha, filas in sorted(por_dia.items()):
        montos = sorted((row["_monto"] for _, row in filas), reverse=True)
        del_dia = data[data["FECHA"].dt.date == fecha]

        # Ni la retención ni el interés que ya se llevó una cancelación emparejada del
        # mismo día. `_is_closing` queda fuera porque esas filas ya están en `montos`.
        sobrantes = [
            (i, r)
            for i, r in del_dia.iterrows()
            if i not in consumed_idx and i not in principal_idx
        ]
        interes_suelto = sum(
            r["_monto"]
            for i, r in sobrantes
            if _is_interest_candidate(r["_desc"], r["_monto"]) and not _is_closing(r["_desc"], r["_monto"])
        )
        retencion = sum(
            abs(r["_monto"]) for _, r in sobrantes if _is_withholding(r["_desc"], r["_monto"])
        )

        huerfanas.append(
            OrphanClosing(
                fecha=fecha,
                capital_sugerido=round(montos[0], 2),
                interes_sugerido=round(sum(montos[1:]) + interes_suelto, 2),
                retencion=round(retencion, 2),
                tx_ids=[data.at[idx, "_tx_id"] for idx, _ in filas],
            )
        )
    return huerfanas
