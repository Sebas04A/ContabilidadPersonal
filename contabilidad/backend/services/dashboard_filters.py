"""
dashboard_filters.py — Filtro a nivel transacción para el dashboard
===================================================================

El presupuesto filtra transacciones en el navegador porque las tiene todas a
mano. El dashboard no: recibe series diarias ya agregadas, así que el filtro
tiene que aplicarse acá, antes de agrupar por día.

Los predicados replican uno a uno los de `MonthlyBudget.tsx`. Si cambia uno,
tiene que cambiar el otro — son la misma pregunta hecha en dos lenguajes.

Cómo se aplica a las series (`_reconstruir_saldo` en dashboard_service):

    SALDO_filtrado(d) = SALDO_real(d) − Σ(MONTO de lo excluido hasta d)

Se resta lo excluido en vez de reconstruir el saldo desde cero sumando lo que
queda. Da el mismo resultado en aritmética limpia, pero no lo es: el SALDO del
extracto y la suma de MONTO difieren hoy en ~$12.67 acumulados (cinco desfases
de 2024). Reconstruyendo, esa deriva contaminaría toda serie filtrada;
restando, el saldo real queda de ancla y con el filtro abierto la salida es
idéntica al bit a la de hoy.
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional
import unicodedata

import pandas as pd

from contabilidad.backend.logger import get_logger

logger = get_logger(__name__)

# Etiquetas que el frontend usa para "esta transacción no tiene el campo".
SIN_CATEGORIA = 'Sin Categoría'
SIN_ETIQUETA = 'Sin Etiqueta'


def _norm(s: Any) -> str:
    """Minúsculas sin tildes, igual que `normalize()` en matchFund.ts."""
    if s is None:
        return ''
    txt = str(s)
    if txt.strip().lower() == 'nan':
        return ''
    txt = unicodedata.normalize('NFD', txt)
    txt = ''.join(c for c in txt if unicodedata.category(c) != 'Mn')
    return txt.strip().lower()


def _tags_de(valor: Any) -> List[str]:
    """Los tags de una fila, ya troceados y sin vacíos."""
    if valor is None:
        return []
    txt = str(valor)
    if txt.strip().lower() == 'nan':
        return []
    return [t.strip() for t in txt.split(',') if t.strip()]


def _categoria_de(valor: Any) -> str:
    """La categoría de una fila, con el mismo default que usa el presupuesto."""
    txt = '' if valor is None else str(valor)
    if not txt.strip() or txt.strip() == '---' or txt.strip().lower() == 'nan':
        return SIN_CATEGORIA
    return txt.strip()


def _es_verdadero(valor: Any) -> bool:
    """Un booleano de etiquetas.csv, que puede venir como bool, NaN o texto."""
    if valor is None:
        return False
    if isinstance(valor, str):
        return valor.strip().lower() in ('true', '1', 'yes', 'si', 'sí')
    try:
        if pd.isna(valor):
            return False
    except (TypeError, ValueError):
        pass
    return bool(valor)


@dataclass
class TxFilter:
    """Qué transacciones entran al dashboard.

    Todos los campos por defecto dejan pasar todo: un `TxFilter()` recién creado
    es inerte y `activo()` da False, así que el dashboard toma el camino de
    siempre sin recalcular nada.
    """

    categorias_excluidas: List[str] = field(default_factory=list)
    tags_excluidos: List[str] = field(default_factory=list)
    # 'all' | 'labeled' | 'unlabeled'
    etiquetado: str = 'all'
    # 'all' | 'included' | 'excluded'
    reembolsable: str = 'all'
    # 'all' | 'needs' | 'wants' | 'rated'
    prioridad: str = 'all'
    # None = todos los fondos. Una lista = solo esos IDs. La lista vacía es
    # significativa: "solo lo que no pertenece a ningún fondo".
    fondos: Optional[List[str]] = None

    def activo(self) -> bool:
        return bool(
            self.categorias_excluidas
            or self.tags_excluidos
            or self.etiquetado != 'all'
            or self.reembolsable != 'all'
            or self.prioridad != 'all'
            or self.fondos is not None
        )

    def firma(self) -> str:
        """Identidad estable del filtro, para cachés y logs."""
        return repr((
            sorted(self.categorias_excluidas),
            sorted(self.tags_excluidos),
            self.etiquetado,
            self.reembolsable,
            self.prioridad,
            None if self.fondos is None else sorted(self.fondos),
        ))

    # ── Predicados ───────────────────────────────────────────────────────────
    # Uno por filtro, cada uno espejo del suyo en MonthlyBudget.tsx.

    def _pasa_prioridad(self, fila: Any, monto: float) -> bool:
        # Solo aplica a gastos: los ingresos no se clasifican como
        # Necesidad/Deseo y tienen que seguir contando (MonthlyBudget.tsx:95).
        if self.prioridad == 'all' or monto >= 0:
            return True
        p = str(fila.get('prioridad') or '').strip()
        if self.prioridad == 'needs':
            return p == 'Necesidad'
        if self.prioridad == 'wants':
            return p == 'Deseo'
        return p in ('Necesidad', 'Deseo')

    def _pasa_reembolsable(self, fila: Any) -> bool:
        if self.reembolsable == 'all':
            return True
        es = _es_verdadero(fila.get('es_reembolsable'))
        return es if self.reembolsable == 'included' else not es

    def _pasa_etiquetado(self, fila: Any) -> bool:
        if self.etiquetado == 'all':
            return True
        revisado = _es_verdadero(fila.get('revisado'))
        return revisado if self.etiquetado == 'labeled' else not revisado

    def _pasa_categoria(self, fila: Any) -> bool:
        if not self.categorias_excluidas:
            return True
        return _categoria_de(fila.get('categoria')) not in self.categorias_excluidas

    def _pasa_tags(self, fila: Any) -> bool:
        if not self.tags_excluidos:
            return True
        tags = _tags_de(fila.get('tags'))
        if not tags:
            return SIN_ETIQUETA not in self.tags_excluidos
        return not any(t in self.tags_excluidos for t in tags)

    def _pasa_fondo(self, fila: Any, fondos_catalogo: List[dict]) -> bool:
        if self.fondos is None:
            return True
        fondo = _fondo_de(fila, fondos_catalogo)
        # Lo que no pertenece a ningún fondo siempre se muestra
        # (matchesFund en MonthlyBudget.tsx:82).
        if fondo is None:
            return True
        return fondo in self.fondos

    def aplicar(self, df: pd.DataFrame) -> pd.DataFrame:
        """Las filas de `df` que pasan el filtro.

        `df` es lo que devuelve `transaction_service.load_data()`: transacciones
        con sus etiquetas y con los splits ya resueltos en MONTO.
        """
        if df.empty or not self.activo():
            return df

        fondos_catalogo = _catalogo_de_fondos() if self.fondos is not None else []

        def pasa(fila) -> bool:
            monto = float(fila.get('MONTO') or 0.0)
            return (
                self._pasa_prioridad(fila, monto)
                and self._pasa_reembolsable(fila)
                and self._pasa_etiquetado(fila)
                and self._pasa_categoria(fila)
                and self._pasa_tags(fila)
                and self._pasa_fondo(fila, fondos_catalogo)
            )

        mask = df.apply(pasa, axis=1)
        return df[mask]


def _fondo_de(fila: Any, fondos_catalogo: List[dict]) -> Optional[str]:
    """El ID del fondo al que pertenece una transacción, o None.

    Espejo de `matchFund()` en el frontend: gana la asignación manual
    (`fondo_id`), y si no, el tag vinculado del fondo.
    """
    if not fondos_catalogo:
        return None

    fondo_id = fila.get('fondo_id')
    fondo_id = '' if fondo_id is None or pd.isna(fondo_id) else str(fondo_id).strip()
    tags = [_norm(t) for t in _tags_de(fila.get('tags'))]

    for f in fondos_catalogo:
        if fondo_id and fondo_id == str(f.get('id')):
            return str(f['id'])
        vinculado = _norm(f.get('tag_vinculado'))
        if vinculado and vinculado in tags:
            return str(f['id'])
    return None


def _catalogo_de_fondos() -> List[dict]:
    """id + tag_vinculado de cada fondo. Lo mínimo para resolver pertenencia.

    Va directo a `InterpolationStorage` y no a `fund_service.get_all_funds()`:
    ese último calcula saldos y sparklines de cada fondo, que acá no se usan.
    """
    try:
        from contabilidad.backend.storage.variables_storage import InterpolationStorage
        grupos = InterpolationStorage.get_groups(type_filter=None, fund_only=True)
        return [
            {'id': str(g['id']), 'tag_vinculado': g.get('tag_vinculado')}
            for g in grupos
        ]
    except Exception as e:
        logger.error("No se pudo leer el catálogo de fondos: %s", e, exc_info=True)
        return []


def filtro_desde_query(
    categorias_excluidas: Optional[str] = None,
    tags_excluidos: Optional[str] = None,
    etiquetado: str = 'all',
    reembolsable: str = 'all',
    prioridad: str = 'all',
    fondos: Optional[str] = None,
) -> TxFilter:
    """Arma un TxFilter desde los query params de la petición.

    Las listas viajan separadas por coma. `fondos` distingue tres casos: ausente
    es None ("todos"), y la cadena vacía es la lista vacía ("ninguno"), que no
    es lo mismo.
    """
    def lista(valor: Optional[str]) -> List[str]:
        if not valor:
            return []
        return [x.strip() for x in valor.split(',') if x.strip()]

    return TxFilter(
        categorias_excluidas=lista(categorias_excluidas),
        tags_excluidos=lista(tags_excluidos),
        etiquetado=etiquetado,
        reembolsable=reembolsable,
        prioridad=prioridad,
        fondos=None if fondos is None else lista(fondos),
    )
