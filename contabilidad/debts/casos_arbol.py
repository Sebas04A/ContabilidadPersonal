"""
casos_arbol.py — Generador del árbol de casos de prueba de deudas.

Cada caso es una secuencia de movimientos; cada nivel del árbol agrega UNO más.

Movimientos
-----------
Deudas (POV dueño):
    debe  →  te deben          (es_mi_deuda=False, suma al neto)
    debo  →  tú debes          (es_mi_deuda=True,  resta del neto)

Pagos (se comportan como deudas para el saldo, pero se muestran distinto):
    recibido →  te pagan       (es_mi_pago=False, resta del neto, abona el lado 'debe')
    doy      →  tú pagas       (es_mi_pago=True,  suma al neto, abona el lado 'debo')

Un pago abona las deudas pendientes de SU lado de la más antigua a la más reciente. Lo que
sobra queda como saldo a favor de quien pagó, igual que en `reading.py`:
    · sobrante de un pago recibido → crédito del deudor  → resta del neto
    · sobrante de un pago que doy  → crédito tuyo        → suma al neto

Etiquetas de cada nivel
-----------------------
Deudas, comparadas contra la **brecha** (`|neto|`) del nivel anterior:
    S  Sobrante      al lado menor, monto > brecha   → el neto cambia de signo
    I  Igual         al lado menor, monto = brecha   → neto 0
    N  Insuficiente  al lado menor, monto < brecha   → el neto conserva el signo
    M  Mayor         al lado que ya tenía más        → el neto crece en su signo
    X / Y            desde neto 0 no hay brecha: agregar un `debe` (X) o un `debo` (Y)

Pagos, comparados contra lo que queda pendiente en el lado que abonan:
    E  pago recibido exacto        F  recibido insuficiente     G  recibido en exceso
    P  pago que doy exacto         Q  el que doy insuficiente   R  el que doy en exceso

Las tres salidas de un pago son las que pidió el usuario: exacto (después no queda nada),
insuficiente (quedan deudas parciales, que se vuelven a mostrar) y en exceso (queda saldo a
favor o en contra con lo que sobró del pago). El **reordenamiento** de pagos no está
implementado todavía.

Cortes
------
1. Profundidad máxima: `NIVEL_MAX`.
2. No se expande un nodo cuya etiqueta es igual a la de su padre (dos iguales seguidos).
   El caso existe como hoja; se corta su descendencia, que repetiría lo ya cubierto.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

NIVEL_MAX = 4
MONTO_RAIZ = 100.0

ETIQUETAS = {
    "S": "deuda sobrante",
    "I": "deuda igual",
    "N": "deuda insuficiente",
    "M": "deuda al lado mayor",
    "X": "agrego un debe",
    "Y": "agrego un debo",
    "E": "me pagan justo",
    "F": "me pagan de menos",
    "G": "me pagan de más",
    "P": "pago justo",
    "Q": "pago de menos",
    "R": "pago de más",
}

# Qué etiquetas son pagos y a qué lado abonan.
PAGOS = {
    "E": ("recibido", "exacto"), "F": ("recibido", "insuficiente"), "G": ("recibido", "exceso"),
    "P": ("doy", "exacto"), "Q": ("doy", "insuficiente"), "R": ("doy", "exceso"),
}
LADO_QUE_ABONA = {"recibido": "debe", "doy": "debo"}


@dataclass(frozen=True)
class Mov:
    """Un movimiento del caso: una deuda o un pago."""
    tipo: str        # "deuda" | "pago"
    direccion: str   # deuda: "debe"|"debo"  ·  pago: "recibido"|"doy"
    monto: float
    etiqueta: str    # etiqueta del nivel en que se agregó ("" en la raíz)

    @property
    def signo(self) -> float:
        """Cuánto mueve el neto (y el ledger de reading.py)."""
        if self.tipo == "deuda":
            return self.monto if self.direccion == "debe" else -self.monto
        return -self.monto if self.direccion == "recibido" else self.monto

    @property
    def es_pago(self) -> bool:
        return self.tipo == "pago"

    @property
    def nombre_corto(self) -> str:
        return f"{self.direccion} {_f(self.monto)}"


@dataclass
class Pendiente:
    """Una deuda con lo que se le ha abonado hasta el momento."""
    idx: int          # posición (nivel) del movimiento dentro del caso
    direccion: str    # "debe" | "debo"
    monto: float
    pagado: float = 0.0

    @property
    def restante(self) -> float:
        return round(self.monto - self.pagado, 2)

    @property
    def nombre(self) -> str:
        return f"n{self.idx + 1} {self.direccion} {_f(self.monto)}"


@dataclass
class Aplicacion:
    """Cómo se repartió un pago: a qué deudas fue y cuánto sobró."""
    idx: int                       # nivel del pago
    direccion: str                 # "recibido" | "doy"
    monto: float
    abonos: list = field(default_factory=list)     # [(idx_deuda, nombre, monto)]
    # Lo que sigue abierto en ese lado después del pago:
    # [(idx_deuda, nombre, restante, ya_tenia_abonos)]
    parciales: list = field(default_factory=list)
    sobrante: float = 0.0

    @property
    def aplicado(self) -> float:
        return round(sum(m for _, _, m in self.abonos), 2)

    @property
    def salida(self) -> str:
        """Las tres salidas de un pago, medidas contra el saldo del lado que abona.

        · exacto       cubrió justo lo que había: no queda nada de ese lado
        · insuficiente no alcanzó: quedan deudas abiertas (parciales o sin tocar)
        · exceso       sobró dinero: pasa a ser saldo a favor de quien pagó
        """
        if self.sobrante > 0.005:
            return "exceso"
        return "insuficiente" if self.parciales else "exacto"


@dataclass
class Estado:
    """Situación del caso después de aplicar todos sus movimientos."""
    pendientes: list                # list[Pendiente], en orden cronológico
    credito_deudor: float           # el deudor pagó de más → se lo debes
    credito_owner: float            # pagaste de más → te lo deben
    aplicaciones: list              # list[Aplicacion], una por pago

    @property
    def pend_debe(self) -> float:
        return round(sum(p.restante for p in self.pendientes if p.direccion == "debe"), 2)

    @property
    def pend_debo(self) -> float:
        return round(sum(p.restante for p in self.pendientes if p.direccion == "debo"), 2)

    @property
    def neto(self) -> float:
        return round(self.pend_debe - self.pend_debo
                     - self.credito_deudor + self.credito_owner, 2)


def calcular_estado(movs) -> Estado:
    """Aplica los movimientos en orden y devuelve el estado resultante.

    Replica la semántica de `reading.py`: un pago abona las deudas pendientes de su lado
    (FIFO) y el sobrante queda como crédito de quien pagó; ese crédito cancela contra
    deudas futuras del mismo lado.
    """
    pendientes, aplicaciones = [], []
    credito = {"debe": 0.0, "debo": 0.0}   # crédito que cubre deudas de ese lado

    def absorber(lado):
        """El crédito acumulado cancela deudas pendientes de su mismo lado."""
        for p in pendientes:
            if credito[lado] <= 0.005:
                return
            if p.direccion != lado or p.restante <= 0.005:
                continue
            usa = round(min(p.restante, credito[lado]), 2)
            p.pagado = round(p.pagado + usa, 2)
            credito[lado] = round(credito[lado] - usa, 2)

    for i, m in enumerate(movs):
        if m.tipo == "deuda":
            pendientes.append(Pendiente(idx=i, direccion=m.direccion, monto=m.monto))
            absorber(m.direccion)
            continue

        lado = LADO_QUE_ABONA[m.direccion]
        ap = Aplicacion(idx=i, direccion=m.direccion, monto=m.monto)
        restante_pago = m.monto
        for p in pendientes:
            if restante_pago <= 0.005:
                break
            if p.direccion != lado or p.restante <= 0.005:
                continue
            usa = round(min(p.restante, restante_pago), 2)
            p.pagado = round(p.pagado + usa, 2)
            restante_pago = round(restante_pago - usa, 2)
            ap.abonos.append((p.idx, p.nombre, usa))
        ap.sobrante = round(restante_pago, 2)
        # Todo lo que sigue abierto de ese lado tras el pago: las que quedaron a medias
        # y también las que el pago nunca alcanzó a tocar.
        tocadas = {idx for idx, _, _ in ap.abonos}
        ap.parciales = [(p.idx, p.nombre, p.restante, p.idx in tocadas)
                        for p in pendientes
                        if p.direccion == lado and p.restante > 0.005]
        if ap.sobrante > 0.005:
            credito[lado] = round(credito[lado] + ap.sobrante, 2)
        aplicaciones.append(ap)

    return Estado(pendientes=pendientes,
                  credito_deudor=credito["debe"], credito_owner=credito["debo"],
                  aplicaciones=aplicaciones)


@dataclass
class Caso:
    code: str
    ruta: list           # ["debe", "N", "E", ...]
    movs: list           # list[Mov]
    padre: str = None
    hoja_por: str = ""   # "" | "repetido" | "nivel-max" | "monto-0"
    hijos: list = field(default_factory=list)

    @property
    def nivel(self) -> int:
        return len(self.movs)

    @property
    def estado(self) -> Estado:
        return calcular_estado(self.movs)

    @property
    def neto(self) -> float:
        return round(sum(m.signo for m in self.movs), 2)

    @property
    def brecha(self) -> float:
        return abs(self.neto)

    @property
    def deudas(self) -> list:
        return [m for m in self.movs if m.tipo == "deuda"]

    @property
    def pagos(self) -> list:
        return [m for m in self.movs if m.es_pago]

    @property
    def total_debe(self) -> float:
        return round(sum(m.monto for m in self.deudas if m.direccion == "debe"), 2)

    @property
    def total_debo(self) -> float:
        return round(sum(m.monto for m in self.deudas if m.direccion == "debo"), 2)

    @property
    def etiqueta(self) -> str:
        return self.ruta[-1]

    @property
    def titulo(self) -> str:
        """'debe 100 → N debo 60 → F me pagan 25'."""
        partes = [self.movs[0].nombre_corto]
        for m in self.movs[1:]:
            partes.append(f"{m.etiqueta} {m.nombre_corto}")
        return " → ".join(partes)

    @property
    def nombre(self) -> str:
        return f"{self.code} · {self.titulo}"


def _f(x: float) -> str:
    return f"{x:g}"


def _ceil5(x: float) -> float:
    return float(math.ceil(x / 5) * 5)


def _floor5(x: float) -> float:
    return float(math.floor(x / 5) * 5)


def _round5(x: float) -> float:
    return float(round(x / 5) * 5)


def _menos(B: float) -> float:
    """Un monto claramente por debajo de B (insuficiente), sin llegar a 0."""
    v = _floor5(0.6 * B)
    return v if 0 < v < B else round(0.6 * B, 2)


def _mas(B: float) -> float:
    """Un monto claramente por encima de B (sobrante / en exceso)."""
    v = _ceil5(1.5 * B)
    return v if v > B else round(1.5 * B, 2)


def _hijos_deuda(caso: Caso) -> list:
    """(etiqueta, monto, direccion) de las deudas que se pueden agregar."""
    if caso.brecha < 0.005:
        base = _round5(max(caso.total_debe, MONTO_RAIZ) / 2) or MONTO_RAIZ / 2
        return [("X", base, "debe"), ("Y", base, "debo")]

    menor = "debo" if caso.neto > 0 else "debe"
    mayor = "debe" if caso.neto > 0 else "debo"
    B = caso.brecha
    hijos = [("S", _mas(B), menor), ("I", round(B, 2), menor), ("N", _menos(B), menor)]
    # En nivel 1 solo hay un lado con monto: "M" no tiene contra qué contrastarse.
    if caso.nivel >= 2:
        hijos.append(("M", _round5(1.25 * B) or round(1.25 * B, 2), mayor))
    return hijos


def _hijos_pago(caso: Caso) -> list:
    """(etiqueta, monto, direccion) de los pagos que se pueden agregar.

    Cada dirección de pago da las tres salidas contra lo que queda pendiente en su lado.
    Si no queda nada pendiente, el único desenlace posible es el exceso.
    """
    est = caso.estado
    salidas = []
    for direccion, (exacto, insuf, exceso) in (("recibido", ("E", "F", "G")),
                                               ("doy", ("P", "Q", "R"))):
        B = est.pend_debe if direccion == "recibido" else est.pend_debo
        if B > 0.005:
            salidas += [(exacto, round(B, 2), direccion),
                        (insuf, _menos(B), direccion),
                        (exceso, _mas(B), direccion)]
        else:
            salidas.append((exceso, MONTO_RAIZ / 2, direccion))
    return salidas


def _expandir(caso: Caso, casos: list) -> None:
    if caso.nivel >= NIVEL_MAX:
        caso.hoja_por = "nivel-max"
        return
    if len(caso.ruta) >= 3 and caso.ruta[-1] == caso.ruta[-2]:
        caso.hoja_por = "repetido"
        return

    for etiqueta, monto, direccion in _hijos_deuda(caso) + _hijos_pago(caso):
        tipo = "pago" if etiqueta in PAGOS else "deuda"
        hijo = Caso(
            code=caso.code + etiqueta,
            ruta=caso.ruta + [etiqueta],
            movs=caso.movs + [Mov(tipo, direccion, monto, etiqueta)],
            padre=caso.code,
        )
        caso.hijos.append(hijo.code)
        casos.append(hijo)
        _expandir(hijo, casos)


def generar() -> list:
    """Todos los casos del árbol, en orden de recorrido (padres antes que hijos)."""
    casos: list = []
    for letra, direccion in (("A", "debe"), ("B", "debo")):
        cero = Caso(code=f"{letra}0", ruta=[direccion],
                    movs=[Mov("deuda", direccion, 0.0, "")], hoja_por="monto-0")
        casos.append(cero)

        raiz = Caso(code=letra, ruta=[direccion],
                    movs=[Mov("deuda", direccion, MONTO_RAIZ, "")])
        casos.append(raiz)
        _expandir(raiz, casos)
    return casos


# ── Cruce de cuentas ─────────────────────────────────────────────────────────
# Cierra el caso compensando lo que queda vivo de las dos direcciones: se cruza
# `min(pendiente debe, pendiente debo)` emparejando de la más antigua a la más reciente.
@dataclass
class Emparejamiento:
    debe: str
    debo: str
    monto: float
    cierra_debe: bool
    cierra_debo: bool

    @property
    def nota(self) -> str:
        if self.cierra_debe and self.cierra_debo:
            return "ambas quedan saldadas"
        if self.cierra_debo:
            return "cierra la de 'debo'; la de 'debe' queda parcial"
        if self.cierra_debe:
            return "cierra la de 'debe'; la de 'debo' queda parcial"
        return "cruce parcial de las dos"


@dataclass
class DeudaCruzada:
    nombre: str
    direccion: str
    monto: float        # monto original de la deuda
    pagado: float       # lo que ya cubrieron los pagos antes del cruce
    cruzado: float
    restante: float

    @property
    def estado(self) -> str:
        if self.monto <= 0.005:
            return "VACÍA"
        if self.restante <= 0.005:
            return "CRUZADA" if self.cruzado > 0.005 else "PAGADA"
        if self.cruzado > 0.005 or self.pagado > 0.005:
            return "PARCIAL"
        return "INTACTA"


@dataclass
class Cruce:
    total_debe: float          # pendiente del lado 'debe' al llegar al cruce
    total_debo: float
    cruzado: float
    emparejamientos: list
    deudas: list
    saldo_final: float
    credito_deudor: float = 0.0
    credito_owner: float = 0.0

    @property
    def lado(self) -> str:
        if self.saldo_final > 0.005:
            return "te deben"
        return "tú debes" if self.saldo_final < -0.005 else "al día"

    @property
    def restantes(self) -> list:
        return [d for d in self.deudas if d.restante > 0.005]


def cruzar(caso) -> Cruce:
    """Compensa lo que quedó pendiente tras los pagos y devuelve el detalle del cruce."""
    est = caso.estado
    pend = {p.nombre: p.restante for p in est.pendientes}
    lados = {"debe": [p.nombre for p in est.pendientes if p.direccion == "debe"],
             "debo": [p.nombre for p in est.pendientes if p.direccion == "debo"]}

    emparejamientos = []
    i = j = 0
    while i < len(lados["debe"]) and j < len(lados["debo"]):
        a, b = lados["debe"][i], lados["debo"][j]
        monto = round(min(pend[a], pend[b]), 2)
        if monto <= 0.005:
            i += 1 if pend[a] <= 0.005 else 0
            j += 1 if pend[b] <= 0.005 else 0
            continue
        pend[a] = round(pend[a] - monto, 2)
        pend[b] = round(pend[b] - monto, 2)
        emparejamientos.append(Emparejamiento(
            debe=a, debo=b, monto=monto,
            cierra_debe=pend[a] <= 0.005, cierra_debo=pend[b] <= 0.005))
        if pend[a] <= 0.005:
            i += 1
        if pend[b] <= 0.005:
            j += 1

    deudas = [DeudaCruzada(nombre=p.nombre, direccion=p.direccion, monto=p.monto,
                           pagado=p.pagado,
                           cruzado=round(p.restante - pend[p.nombre], 2),
                           restante=pend[p.nombre])
              for p in est.pendientes]

    return Cruce(total_debe=est.pend_debe, total_debo=est.pend_debo,
                 cruzado=round(sum(e.monto for e in emparejamientos), 2),
                 emparejamientos=emparejamientos, deudas=deudas,
                 saldo_final=caso.neto,
                 credito_deudor=est.credito_deudor, credito_owner=est.credito_owner)


FECHAS = ["2026-06-01", "2026-06-05", "2026-06-10", "2026-06-15", "2026-06-20"]


def listas_crudas(caso, fechas=None):
    """Traduce un caso a las listas que consume `reading._construir_flujo_cuenta`.

    Es el puente que permite verificar cada caso del árbol contra el motor real:
    deudas, pagos y las asignaciones pago→deuda que produjo el reparto FIFO.
    """
    fechas = fechas or FECHAS
    deudas_raw, pagos_raw, detalles = [], [], []
    for i, m in enumerate(caso.movs):
        if m.tipo == "deuda":
            deudas_raw.append({"id": f"d{i}", "titulo": m.nombre_corto, "monto": m.monto,
                               "fecha_gasto": fechas[i],
                               "es_mi_deuda": m.direccion == "debo"})
        else:
            pagos_raw.append({"id": f"p{i}", "monto_total": m.monto,
                              "fecha_pago": fechas[i],
                              "es_mi_pago": m.direccion == "doy",
                              "es_compensacion": False})
    for ap in caso.estado.aplicaciones:
        for idx, _, monto in ap.abonos:
            detalles.append({"id": f"x{ap.idx}-{idx}", "pago_id": f"p{ap.idx}",
                             "deuda_id": f"d{idx}", "monto_asignado": monto})
    return deudas_raw, pagos_raw, detalles


# ── Utilidades de reporte ────────────────────────────────────────────────────
def resumen_por_nivel(casos: list) -> dict:
    out: dict = {}
    for c in casos:
        out[c.nivel] = out.get(c.nivel, 0) + 1
    return out


def a_markdown(casos: list) -> str:
    por_nivel: dict = {}
    for c in casos:
        por_nivel.setdefault(c.nivel, []).append(c)

    L = ["# Árbol de casos — Deudas y pagos", "",
         "Generado por `contabilidad/debts/casos_arbol.py`. **No editar a mano.**", "",
         "`debe` = te deben (+) · `debo` = tú debes (−) · los pagos abonan el lado que les toca "
         "y lo que sobra queda como saldo a favor de quien pagó.", "",
         "| Etiqueta | Qué agrega ese nivel |", "|---|---|"]
    L += [f"| **{k}** | {v} |" for k, v in ETIQUETAS.items()]
    L += ["",
          f"Cortes: profundidad máxima **nivel {NIVEL_MAX}**, y una rama no se expande cuando "
          "su etiqueta repite la del padre (queda como hoja).", "",
          "Cada caso cierra con un **cruce de cuentas** sobre lo que quedó pendiente después "
          "de los pagos: se compensa `min(pendiente debe, pendiente debo)` emparejando de la "
          "más antigua a la más reciente.", ""]

    L += ["## Conteo", "", "| Nivel | Casos |", "|---|---|"]
    for n in sorted(por_nivel):
        L.append(f"| {n} | {len(por_nivel[n])} |")
    L += [f"| **Total** | **{len(casos)}** |", ""]

    for n in sorted(por_nivel):
        L += [f"## Nivel {n}", "",
              "| ID | Caso | pend. debe | pend. debo | neto | cruzado | saldo final "
              "| quedan | hoja |",
              "|---|---|---:|---:|---:|---:|---:|---|---|"]
        for c in sorted(por_nivel[n], key=lambda x: x.code):
            x = cruzar(c)
            quedan = ", ".join(
                f"{d.nombre.split(' ', 1)[0]} {_f(d.restante)}"
                + ("⅟" if d.estado == "PARCIAL" else "")
                for d in x.restantes)
            if x.credito_deudor > 0.005:
                quedan += f" · a favor deudor {_f(x.credito_deudor)}"
            if x.credito_owner > 0.005:
                quedan += f" · a favor tuyo {_f(x.credito_owner)}"
            L.append(f"| `{c.code}` | {c.titulo} | {_f(x.total_debe)} | {_f(x.total_debo)} "
                     f"| **{c.neto:+g}** | {_f(x.cruzado)} | {x.saldo_final:+g} ({x.lado}) "
                     f"| {quedan or '—'} | {c.hoja_por or ''} |")
        L.append("")

    return "\n".join(L)


if __name__ == "__main__":
    import sys

    casos = generar()
    if "--markdown" in sys.argv:
        print(a_markdown(casos))
    else:
        for c in casos:
            print(f"{c.code:14} n{c.nivel}  neto {c.neto:+8.2f}  {c.titulo}"
                  + (f"   [{c.hoja_por}]" if c.hoja_por else ""))
        print(f"\nTotal: {len(casos)} casos — por nivel: {resumen_por_nivel(casos)}")
