#!/usr/bin/env python3
"""
ver_arbol_deudas.py — Muestra el árbol de casos de deudas (fase 1) de forma visual.

Toma los datos que genera `contabilidad/debts/casos_arbol.py` y los pinta de dos formas:

  · en terminal, como árbol con guías + barra divergente del neto (debe a la derecha en
    verde, debo a la izquierda en rosa);
  · con `--html`, como diagrama nodo-enlace (posición = estructura, color = signo del
    neto, tamaño = magnitud) más la tabla completa debajo.

Así se revisa de un vistazo que cada rama hace lo que su etiqueta promete.

Uso:
    python scripts/ver_arbol_deudas.py                   # árbol completo (254 casos)
    python scripts/ver_arbol_deudas.py --nivel 3         # solo hasta nivel 3
    python scripts/ver_arbol_deudas.py --rama AN         # solo la rama que empieza en AN
    python scripts/ver_arbol_deudas.py --solo-hojas      # solo los casos terminales
    python scripts/ver_arbol_deudas.py --verificar       # contrasta contra el motor real
    python scripts/ver_arbol_deudas.py --html arbol.html # página autocontenida

`--verificar` corre cada caso por `reading._construir_flujo_cuenta` y marca ✓ / ✗ según
el neto y el ledger coincidan con lo esperado (necesita pandas + supabase instalados).
"""
import argparse
import json
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contabilidad.debts.casos_arbol import (ETIQUETAS, FECHAS,  # noqa: E402
                                            NIVEL_MAX, cruzar, generar,
                                            listas_crudas)

ANCHO_BARRA = 18   # celdas a cada lado del eje


class C:
    """Colores ANSI; se apagan solos si la salida no es una terminal."""
    activo = sys.stdout.isatty()

    RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
    VERDE, ROSA, AMBAR, AZUL, GRIS = ("\033[38;5;42m", "\033[38;5;205m",
                                      "\033[38;5;214m", "\033[38;5;75m", "\033[38;5;244m")

    @classmethod
    def p(cls, texto, *estilos):
        if not cls.activo or not estilos:
            return texto
        return "".join(estilos) + texto + cls.RESET


COLOR_ETIQUETA = {"S": C.AMBAR, "I": C.AZUL, "N": C.GRIS, "M": C.BOLD,
                  "X": C.VERDE, "Y": C.ROSA}


def _f(x):
    return f"{x:g}"


def barra(neto, escala):
    """Barra divergente: eje al centro, debe (+) a la derecha, debo (−) a la izquierda."""
    n = 0 if escala <= 0 else min(ANCHO_BARRA, round(abs(neto) / escala * ANCHO_BARRA))
    if abs(neto) > 0.005 and n == 0:
        n = 1  # que nunca desaparezca un neto distinto de cero
    if neto > 0:
        izq, der, color = " " * ANCHO_BARRA, "█" * n + " " * (ANCHO_BARRA - n), C.VERDE
    elif neto < 0:
        izq, der, color = " " * (ANCHO_BARRA - n) + "█" * n, " " * ANCHO_BARRA, C.ROSA
    else:
        return " " * ANCHO_BARRA + C.p("│", C.DIM) + " " * ANCHO_BARRA
    return C.p(izq, color) + C.p("│", C.DIM) + C.p(der, color)


def ramas(caso, por_code, ultimo_en_nivel):
    """Glifos del árbol: '│  ' donde el ancestro tiene hermanos abajo, '└─' en el último."""
    if caso.nivel == 1:
        return ""
    prefijo = "".join("   " if ultimo_en_nivel.get(caso.code[:i + 1], True) else "│  "
                      for i in range(1, caso.nivel - 1))
    return prefijo + ("└─ " if ultimo_en_nivel.get(caso.code, True) else "├─ ")


def _motor():
    """Devuelve _construir_flujo_cuenta, o None si el entorno no tiene las deps."""
    try:
        from contabilidad.debts.reading import _construir_flujo_cuenta
        return _construir_flujo_cuenta
    except Exception as e:                                   # noqa: BLE001
        print(C.p(f"⚠ No se pudo importar el motor ({e}); se omite --verificar\n", C.AMBAR))
        return None


def evaluar(caso, motor):
    """(neto_real, ledger_real, ok) según el motor de reading.py."""
    est = motor(*listas_crudas(caso, FECHAS))
    neto = est["resumen"]["neto"]
    movs = est["movimientos"]
    ledger = movs[0]["saldo_acumulado"] if movs else 0.0
    ok = abs(neto - caso.neto) < 0.011 and abs(ledger - caso.neto) < 0.011
    return neto, ledger, ok


def seleccionar(casos, nivel, rama, solo_hojas):
    sel = [c for c in casos if c.nivel <= nivel]
    if rama:
        sel = [c for c in sel if c.code.startswith(rama) or rama.startswith(c.code)]
    if solo_hojas:
        codes = {c.code for c in sel}
        sel = [c for c in sel if not any(o != c.code and o.startswith(c.code) for o in codes)]
    return sel


# ── Render de terminal ───────────────────────────────────────────────────────
def render_terminal(sel, motor, cruce=False):
    codes = {c.code for c in sel}
    # Un nodo es "último" si no tiene hermanos posteriores dentro de la selección.
    orden = {c.code: i for i, c in enumerate(sel)}
    ultimo = {}
    for c in sel:
        hermanos = [o for o in codes
                    if len(o) == len(c.code) and o[:-1] == c.code[:-1] and o in orden]
        ultimo[c.code] = orden[c.code] == max(orden[h] for h in hermanos)

    escala = max((abs(c.neto) for c in sel), default=1)

    print()
    print(C.p("  ID     nivel  árbol de casos", C.BOLD)
          + C.p(" " * 26 + "Σdebe   Σdebo", C.BOLD)
          + C.p("   ←── debo ── 0 ── debe ──→", C.BOLD)
          + C.p("       neto", C.BOLD)
          + (C.p("    cruzado  queda vivo tras el cruce", C.BOLD) if cruce else ""))
    print(C.p("  " + "─" * (172 if cruce else 132), C.DIM))

    fallos = 0
    for c in sel:
        etiqueta = "" if c.nivel == 1 else c.etiqueta
        col_et = COLOR_ETIQUETA.get(etiqueta, "")
        nueva = c.deudas[-1]
        texto = (f"{nueva.direccion} {_f(nueva.monto)}" if c.nivel == 1
                 else C.p(etiqueta, col_et, C.BOLD) + " "
                      + C.p(f"{nueva.direccion} {_f(nueva.monto)}",
                            C.VERDE if not nueva.mine else C.ROSA))
        arbol = C.p(ramas(c, codes, ultimo), C.DIM) + texto
        relleno = " " * max(0, 40 - len(_sin_color(arbol)))

        neto_txt = C.p(f"{c.neto:+9.2f}", C.VERDE if c.neto > 0 else
                       (C.ROSA if c.neto < 0 else C.DIM), C.BOLD)

        marca = ""
        if motor:
            _, _, ok = evaluar(c, motor)
            marca = C.p(" ✓", C.VERDE) if ok else C.p(" ✗", C.ROSA)
            fallos += 0 if ok else 1
        if c.hoja_por:
            marca += C.p(f"  {c.hoja_por}", C.DIM)

        cols_cruce = ""
        if cruce:
            x = cruzar(c)
            partes = []
            for d in x.restantes:
                etq = f"{d.nombre.rsplit(' ', 1)[0]} {d.restante:g}"
                partes.append(etq + C.p("*", C.AMBAR) if d.estado == "PARCIAL" else etq)
            quedan = ", ".join(partes) or C.p("nada", C.DIM)
            cols_cruce = f"  {C.p(f'{x.cruzado:9.2f}', C.AZUL)}  {quedan}"
        print(f"  {C.p(c.code.ljust(6), C.BOLD)} n{c.nivel}    {arbol}{relleno}"
              f"{c.total_debe:7.0f} {c.total_debo:7.0f}   {barra(c.neto, escala)} "
              f"{neto_txt}{marca}{cols_cruce}")

    print(C.p("  " + "─" * (172 if cruce else 132), C.DIM))
    por_nivel = {}
    for c in sel:
        por_nivel[c.nivel] = por_nivel.get(c.nivel, 0) + 1
    detalle = " · ".join(f"n{n}: {q}" for n, q in sorted(por_nivel.items()))
    print(f"  {C.p(str(len(sel)), C.BOLD)} casos   ({detalle})")
    if motor:
        estado = (C.p("todos cuadran con el motor ✓", C.VERDE, C.BOLD) if not fallos
                  else C.p(f"{fallos} casos NO cuadran ✗", C.ROSA, C.BOLD))
        print(f"  Verificación: {estado}")
    print()
    print(C.p("  Etiquetas:  ", C.DIM)
          + "  ".join(C.p(k, COLOR_ETIQUETA.get(k, ""), C.BOLD) + C.p(f" {v}", C.DIM)
                      for k, v in ETIQUETAS.items()))
    print(C.p("  La etiqueta compara la deuda nueva contra la brecha (|neto|) del padre.\n",
              C.DIM))
    return fallos


def render_cruce(caso, motor=None, sangria="  "):
    """Bloque de cierre de un caso: totales, qué se cruzó y con qué saldo queda."""
    x = cruzar(caso)
    s = sangria
    col_lado = C.VERDE if x.saldo_final > 0.005 else (C.ROSA if x.saldo_final < -0.005 else C.DIM)

    print()
    print(f"{s}{C.p(caso.code, C.BOLD)} {C.p('·', C.DIM)} {caso.titulo}")
    print(f"{s}{C.p('─' * 68, C.DIM)}")
    print(f"{s}Total debe {C.p(f'{x.total_debe:>10.2f}', C.VERDE)}"
          f"     Total debo {C.p(f'{x.total_debo:>10.2f}', C.ROSA)}")
    print(f"{s}Cruzado    {C.p(f'{x.cruzado:>10.2f}', C.AZUL, C.BOLD)}"
          f"     {C.p('(se compensa el menor de los dos totales)', C.DIM)}")

    print(f"\n{s}{C.p('Deudas que se cruzaron', C.BOLD)}")
    if not x.emparejamientos:
        print(f"{s}  {C.p('ninguna — el caso tiene deudas en una sola dirección', C.DIM)}")
    for e in x.emparejamientos:
        print(f"{s}  {C.p(e.debe, C.VERDE):<24} {C.p('×', C.DIM)} "
              f"{C.p(e.debo, C.ROSA):<24} {C.p('→', C.DIM)} "
              f"{C.p(f'{e.monto:>9.2f}', C.AZUL)}   {C.p(e.nota, C.DIM)}")

    print(f"\n{s}{C.p('Cómo queda cada deuda', C.BOLD)}")
    for d in x.deudas:
        col_estado = {"CRUZADA": C.AZUL, "PARCIAL": C.AMBAR,
                      "INTACTA": C.GRIS, "VACÍA": C.DIM}[d.estado]
        barra_d = ""
        if d.monto > 0.005:
            llenos = round(d.cruzado / d.monto * 12)
            barra_d = (C.p("█" * llenos, C.AZUL)
                       + C.p("░" * (12 - llenos), C.GRIS))
        print(f"{s}  {C.p(d.nombre, C.VERDE if d.direccion == 'debe' else C.ROSA):<26}"
              f" {barra_d}  cruzado {d.cruzado:>8.2f}   queda {d.restante:>8.2f}   "
              f"{C.p(d.estado, col_estado, C.BOLD)}")

    print(f"\n{s}{C.p('Saldo final tras el cruce', C.BOLD)}  "
          f"{C.p(f'{x.saldo_final:+.2f}', col_lado, C.BOLD)}  {C.p(x.lado, col_lado)}")
    if x.restantes:
        detalle = ", ".join(f"{d.nombre} → {d.restante:.2f}"
                            + (" (parcial)" if d.estado == "PARCIAL" else "")
                            for d in x.restantes)
        print(f"{s}{C.p('Sobreviven:', C.DIM)} {detalle}")
    else:
        print(f"{s}{C.p('No queda ninguna deuda viva.', C.DIM)}")

    if motor:
        neto, ledger, ok = evaluar(caso, motor)
        marca = C.p("✓ cuadra", C.VERDE, C.BOLD) if ok else C.p("✗ NO cuadra", C.ROSA, C.BOLD)
        print(f"{s}{C.p('Motor reading.py:', C.DIM)} neto {neto:+.2f} · "
              f"ledger {ledger:+.2f}  {marca}")
    print()
    return x


def _sin_color(s):
    out, dentro = [], False
    for ch in s:
        if ch == "\033":
            dentro = True
        elif dentro and ch == "m":
            dentro = False
        elif not dentro:
            out.append(ch)
    return "".join(out)


# ── Render HTML ──────────────────────────────────────────────────────────────
# Paleta divergente azul↔rojo con punto medio gris, validada para daltonismo en
# claro y oscuro (peor par CVD ΔE 21.6 claro / 19.2 oscuro, umbral ≥8). El verde/rosa
# que usa la app no pasa (ΔE 2.5 / 1.6 → indistinguibles en deuteranopía), y en un
# visor cuyo único trabajo es detectar signos equivocados eso no es aceptable.
COL_X, ROW_Y, MARGEN = 210, 34, 30


def _jerarquia(sel):
    """(hijos_por_code, raices) restringido a los casos seleccionados."""
    codes = {c.code for c in sel}
    hijos, raices = {c.code: [] for c in sel}, []
    for c in sel:
        if c.padre and c.padre in codes:
            hijos[c.padre].append(c)
        else:
            raices.append(c)
    return hijos, raices


def _layout(sel):
    """Posiciona el árbol: x por nivel, y por hoja (las ramas se centran en sus hijos)."""
    hijos, raices = _jerarquia(sel)
    pos, guias, fila = {}, {}, [0]

    def visitar(c, guia):
        guias[c.code] = guia
        hs = hijos[c.code]
        if not hs:
            y = MARGEN + fila[0] * ROW_Y
            fila[0] += 1
        else:
            ys = [visitar(h, guia + [i < len(hs) - 1]) for i, h in enumerate(hs)]
            y = (ys[0] + ys[-1]) / 2
        pos[c.code] = (MARGEN + (c.nivel - 1) * COL_X, y)
        return y

    for i, r in enumerate(raices):
        visitar(r, [])
    return pos, guias, hijos, raices


def _svg_arbol(sel, marcas):
    """Diagrama nodo-enlace: posición = estructura, color = signo, radio = |neto|."""
    pos, _, hijos, _ = _layout(sel)
    if not pos:
        return ""
    escala = max((abs(c.neto) for c in sel), default=1) or 1
    ancho = MARGEN + max(c.nivel for c in sel) * COL_X + 40
    alto = max(y for _, y in pos.values()) + MARGEN

    enlaces = []
    for c in sel:
        px, py = pos[c.code]
        for h in hijos[c.code]:
            hx, hy = pos[h.code]
            # El codo baja pegado al hijo: así el tramo horizontal corre entre las
            # dos líneas de texto del padre en vez de atravesarlas.
            codo = hx - 38
            enlaces.append(f'<path class="link" d="M{px} {py} H{codo} V{hy} H{hx}"/>')

    nodos = []
    for c in sel:
        x, y = pos[c.code]
        r = 4.5 + 6.5 * (abs(c.neto) / escala) ** 0.5
        lado = "pos" if c.neto > 0.005 else ("neg" if c.neto < -0.005 else "cero")
        et = "" if c.nivel == 1 else c.etiqueta
        nueva = c.deudas[-1]
        etq = f"{et} " if et else ""
        titulo = f"{etq}{nueva.direccion} {_f(nueva.monto)}"
        tip = (f"{c.code} · nivel {c.nivel}|{c.titulo}|"
               f"Σ debe {_f(c.total_debe)} · Σ debo {_f(c.total_debo)}|"
               f"neto {c.neto:+g}"
               + (f" · {c.hoja_por}" if c.hoja_por else "")
               + (" · ✓ cuadra" if marcas.get(c.code) is True else
                  (" · ✗ NO cuadra" if marcas.get(c.code) is False else "")))
        mal = ' data-mal="1"' if marcas.get(c.code) is False else ""
        nodos.append(f"""<g class="nodo {lado}" data-code="{c.code}" data-tip="{tip}"{mal}
      tabindex="0" role="button" aria-label="{c.code}: {c.titulo}, neto {c.neto:+g}">
      <circle class="halo" cx="{x}" cy="{y}" r="{r + 7:.1f}"/>
      <circle class="punto" cx="{x}" cy="{y}" r="{r:.1f}"/>
      <text class="et" x="{x + r + 7:.1f}" y="{y - 5:.1f}">{titulo}</text>
      <text class="val" x="{x + r + 7:.1f}" y="{y + 12:.1f}">{c.neto:+g}</text>
    </g>""")

    return (f'<svg class="arbol" viewBox="0 0 {ancho} {alto:.0f}" width="{ancho}" '
            f'height="{alto:.0f}" role="img" aria-label="Árbol de casos de deudas; '
            f'el detalle numérico está en la tabla de abajo">\n'
            f'  <g class="links">{"".join(enlaces)}</g>\n'
            f'  <g class="nodos">{"".join(nodos)}</g>\n</svg>')


def _datos_cruce(casos):
    """Serializa el cruce de cada caso para el panel de la página."""
    out = {}
    for c in casos:
        x = cruzar(c)
        out[c.code] = {
            "titulo": c.titulo, "nivel": c.nivel,
            "td": x.total_debe, "tdo": x.total_debo, "cruzado": x.cruzado,
            "saldo": x.saldo_final, "lado": x.lado,
            "pares": [{"debe": e.debe, "debo": e.debo, "monto": e.monto, "nota": e.nota}
                      for e in x.emparejamientos],
            "deudas": [{"nombre": d.nombre, "dir": d.direccion, "monto": d.monto,
                        "cruzado": d.cruzado, "restante": d.restante, "estado": d.estado}
                       for d in x.deudas],
        }
    return out


def _fila_tabla(c, guia, ultimo, marca):
    """Fila con guías de árbol dibujadas (│ donde el ancestro sigue, ├/└ en el nodo)."""
    cols = "".join(f'<i class="{"v" if sigue else ""}"></i>' for sigue in guia[:-1])
    if guia:
        cols += f'<i class="{"t" if not ultimo else "l"}"></i>'
    et = "" if c.nivel == 1 else c.etiqueta
    nueva = c.deudas[-1]
    chip = (f'<span class="chip et-{et}" title="{ETIQUETAS.get(et, "")}">{et}</span>'
            if et else '<span class="chip raiz">raíz</span>')
    hoja = f'<span class="hoja">{c.hoja_por}</span>' if c.hoja_por else ""
    lado = "pos" if c.neto > 0.005 else ("neg" if c.neto < -0.005 else "cero")
    chk = ("" if marca is None else
           f'<span class="chk {"ok" if marca else "bad"}">{"✓" if marca else "✗"}</span>')
    x = cruzar(c)
    quedan = " · ".join(
        f'{d.nombre.rsplit(" ", 1)[0]} {_f(d.restante)}'
        + ('<span class="parcial" title="quedó cruzada a medias">parcial</span>'
           if d.estado == "PARCIAL" else "")
        for d in x.restantes) or '<span class="nada">nada</span>'
    return f"""
      <tr data-code="{c.code}" tabindex="0">
        <td class="code">{c.code}</td>
        <td class="arbol-cel"><span class="guias">{cols}</span>{chip}
          <span class="mov">{nueva.direccion} {_f(nueva.monto)}</span>{hoja}</td>
        <td class="num">{_f(c.total_debe)}</td>
        <td class="num">{_f(c.total_debo)}</td>
        <td class="num cruzado">{_f(x.cruzado)}</td>
        <td class="queda">{quedan}</td>
        <td class="num neto {lado}"><span class="dot {lado}"></span>{c.neto:+g}</td>
        <td class="chkcol">{chk}</td>
      </tr>"""


def render_html(sel_arbol, sel_tabla, motor, titulo="Árbol de casos — Deudas"):
    marcas = {}
    if motor:
        for c in {c.code: c for c in sel_arbol + sel_tabla}.values():
            marcas[c.code] = evaluar(c, motor)[2]

    svg = _svg_arbol(sel_arbol, marcas)

    _, guias, hijos, _ = _layout(sel_tabla)
    codes = {c.code for c in sel_tabla}
    orden = {c.code: i for i, c in enumerate(sel_tabla)}
    filas = []
    for c in sel_tabla:
        hermanos = [o for o in codes if len(o) == len(c.code) and o[:-1] == c.code[:-1]]
        ultimo = orden[c.code] == max(orden[h] for h in hermanos)
        filas.append(_fila_tabla(c, guias.get(c.code, []), ultimo, marcas.get(c.code)))

    leyenda_et = " ".join(
        f'<span class="lg"><span class="chip et-{k}">{k}</span>{v}</span>'
        for k, v in ETIQUETAS.items())

    fallos = sum(1 for v in marcas.values() if v is False)
    if not marcas:
        estado = '<span class="pill neutra">sin verificar — usa --verificar</span>'
    elif fallos:
        estado = f'<span class="pill mala">{fallos} casos no cuadran con el motor</span>'
    else:
        estado = (f'<span class="pill buena">los {len(marcas)} casos cuadran '
                  f'con <code>reading.py</code></span>')

    datos = _datos_cruce({c.code: c for c in sel_arbol + sel_tabla}.values())
    inicial = (sel_tabla or sel_arbol)[-1].code

    return f"""<title>{titulo}</title>
<style>
  :root {{
    color-scheme: light;
    --plano:#f9f9f7; --sup:#fcfcfb; --tinta:#0b0b0b; --tinta2:#52514e; --mut:#898781;
    --linea:#e1e0d9; --eje:#c3c2b7; --borde:rgba(11,11,11,.10);
    --pos:#2a78d6; --neg:#e34948; --cero:#f0efec;
  }}
  @media (prefers-color-scheme: dark) {{
    :root:where(:not([data-theme="light"])) {{
      color-scheme: dark;
      --plano:#0d0d0d; --sup:#1a1a19; --tinta:#fff; --tinta2:#c3c2b7; --mut:#898781;
      --linea:#2c2c2a; --eje:#383835; --borde:rgba(255,255,255,.10);
      --pos:#3987e5; --neg:#e66767; --cero:#383835;
    }}
  }}
  :root[data-theme="dark"] {{
    color-scheme: dark;
    --plano:#0d0d0d; --sup:#1a1a19; --tinta:#fff; --tinta2:#c3c2b7; --mut:#898781;
    --linea:#2c2c2a; --eje:#383835; --borde:rgba(255,255,255,.10);
    --pos:#3987e5; --neg:#e66767; --cero:#383835;
  }}

  body {{ margin:0; background:var(--plano); color:var(--tinta); }}
  .viz {{ background:var(--plano); color:var(--tinta); min-height:100vh;
          padding:2.25rem 1.25rem 4rem;
          font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif; }}
  .viz > * {{ max-width:1180px; margin-inline:auto; }}
  h1 {{ font-size:1.55rem; margin:0 0 .4rem; letter-spacing:-.02em; }}
  h2 {{ font-size:1rem; margin:2.25rem 0 .75rem; letter-spacing:-.01em; }}
  .sub {{ color:var(--tinta2); margin:0 0 1rem; max-width:64ch; }}
  code {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.88em; }}

  .pill {{ display:inline-block; font-size:.8rem; padding:.2rem .6rem; border-radius:999px;
           border:1px solid var(--borde); }}
  .pill.buena {{ color:#006300; background:color-mix(in srgb,#0ca30c 12%,transparent); }}
  .pill.mala {{ color:var(--neg); background:color-mix(in srgb,var(--neg) 12%,transparent); }}
  .pill.neutra {{ color:var(--mut); }}

  .leyenda {{ display:flex; flex-wrap:wrap; gap:.45rem 1.15rem; align-items:center;
              color:var(--tinta2); font-size:.82rem; margin:.9rem 0 1.1rem; }}
  .lg {{ display:inline-flex; align-items:center; gap:.35rem; }}
  .chip {{ display:inline-block; min-width:1.3rem; text-align:center; padding:.05rem .28rem;
           border-radius:5px; font:700 .72rem/1.5 ui-monospace,monospace; color:var(--tinta);
           background:color-mix(in srgb,var(--mut) 22%,transparent); }}
  .chip.raiz {{ color:var(--mut); background:transparent; border:1px dashed var(--eje); }}
  .dot {{ display:inline-block; width:9px; height:9px; border-radius:50%;
          margin-right:.4rem; vertical-align:baseline; }}
  .dot.pos {{ background:var(--pos); }} .dot.neg {{ background:var(--neg); }}
  .dot.cero {{ background:var(--cero); box-shadow:inset 0 0 0 1px var(--eje); }}

  .lienzo {{ background:var(--sup); border:1px solid var(--borde); border-radius:14px;
             overflow:auto; max-height:82vh; padding:.5rem; }}
  svg.arbol {{ display:block; max-width:none; }}
  .link {{ fill:none; stroke:var(--linea); stroke-width:1.5; }}
  .nodo .halo {{ fill:transparent; }}
  .nodo .punto {{ stroke:var(--sup); stroke-width:2; }}
  .nodo.pos .punto {{ fill:var(--pos); }}
  .nodo.neg .punto {{ fill:var(--neg); }}
  .nodo.cero .punto {{ fill:var(--cero); stroke:var(--eje); }}
  .nodo[data-mal="1"] .punto {{ stroke:var(--neg); stroke-width:3; stroke-dasharray:3 2; }}
  /* El texto se recorta sobre los enlaces en vez de pelearse con ellos. */
  .nodo text {{ paint-order:stroke; stroke:var(--sup); stroke-width:3px;
                stroke-linejoin:round; }}
  .nodo .et {{ fill:var(--tinta); font-size:11.5px; }}
  .nodo .val {{ fill:var(--mut); font-size:10.5px; font-variant-numeric:tabular-nums; }}
  .nodo:hover .punto {{ stroke:var(--tinta); }}
  .nodo:hover .et {{ font-weight:700; }}

  #tip {{ position:fixed; pointer-events:none; opacity:0; transition:opacity .1s;
          background:var(--sup); color:var(--tinta); border:1px solid var(--borde);
          border-radius:9px; padding:.5rem .65rem; font-size:.78rem; line-height:1.45;
          box-shadow:0 6px 24px rgba(0,0,0,.16); z-index:9; max-width:22rem; }}
  #tip b {{ display:block; font-family:ui-monospace,monospace; font-size:.76rem;
            color:var(--mut); font-weight:600; }}

  .tabla {{ background:var(--sup); border:1px solid var(--borde); border-radius:14px;
            overflow:auto; max-height:80vh; }}
  table {{ border-collapse:collapse; width:100%; min-width:660px; }}
  th {{ position:sticky; top:0; background:var(--sup); text-align:left; font-size:.7rem;
        text-transform:uppercase; letter-spacing:.07em; color:var(--mut); font-weight:600;
        padding:.7rem .65rem; border-bottom:1px solid var(--linea); }}
  td {{ padding:.26rem .65rem; border-bottom:1px solid color-mix(in srgb,var(--linea) 50%,transparent); }}
  tr:hover td {{ background:color-mix(in srgb,var(--tinta) 4%,transparent); }}
  .code {{ font-family:ui-monospace,monospace; font-size:.78rem; color:var(--mut);
           white-space:nowrap; }}
  .arbol-cel {{ white-space:nowrap; }}
  .guias {{ display:inline-flex; vertical-align:-3px; margin-right:.35rem; }}
  .guias i {{ display:inline-block; width:16px; height:22px; position:relative; }}
  .guias i.v::before, .guias i.t::before, .guias i.l::before {{
      content:""; position:absolute; left:7px; top:-3px; width:1px; background:var(--eje); }}
  .guias i.v::before {{ bottom:-3px; }}
  .guias i.t::before {{ bottom:-3px; }}
  .guias i.l::before {{ height:14px; }}
  .guias i.t::after, .guias i.l::after {{
      content:""; position:absolute; left:7px; top:11px; width:9px; height:1px;
      background:var(--eje); }}
  .mov {{ font-size:.86rem; margin-left:.35rem; color:var(--tinta); }}
  .hoja {{ font-size:.66rem; color:var(--mut); border:1px solid var(--linea);
           border-radius:4px; padding:0 .3rem; margin-left:.45rem; }}
  .num {{ text-align:right; font-variant-numeric:tabular-nums;
          font-family:ui-monospace,monospace; font-size:.8rem; color:var(--tinta2);
          white-space:nowrap; }}
  .neto {{ font-weight:700; color:var(--tinta); }}
  .cruzado {{ color:var(--tinta); }}
  .queda {{ font-size:.78rem; color:var(--tinta2); white-space:nowrap; }}
  .queda .nada {{ color:var(--mut); }}
  .parcial {{ font-size:.62rem; text-transform:uppercase; letter-spacing:.05em;
              border:1px solid var(--eje); border-radius:4px; padding:0 .25rem;
              margin-left:.3rem; color:var(--mut); }}
  .chkcol {{ text-align:center; }}
  .chk.ok {{ color:#006300; }} .chk.bad {{ color:var(--neg); font-weight:700; }}
  tr[data-code] {{ cursor:pointer; }}
  tr[data-code].sel td {{ background:color-mix(in srgb,var(--pos) 12%,transparent); }}
  tr:focus-visible {{ outline:2px solid var(--pos); outline-offset:-2px; }}
  .nodo {{ cursor:pointer; }}
  .nodo.sel .punto {{ stroke:var(--tinta); stroke-width:3; }}

  /* ── Panel de cruce de cuentas ── */
  .panel {{ background:var(--sup); border:1px solid var(--borde); border-radius:14px;
            padding:1.1rem 1.25rem 1.35rem; margin-top:1rem; }}
  .panel-cab {{ display:flex; flex-wrap:wrap; align-items:baseline; gap:.6rem;
                border-bottom:1px solid var(--linea); padding-bottom:.7rem; }}
  .panel-cab .id {{ font:700 .9rem ui-monospace,monospace; }}
  .panel-cab .ruta {{ color:var(--tinta2); font-size:.88rem; }}
  .panel-cab .pista {{ margin-left:auto; color:var(--mut); font-size:.74rem; }}
  .tiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr));
            gap:.75rem; margin:.9rem 0 1.1rem; }}
  .tile {{ border:1px solid var(--linea); border-radius:10px; padding:.6rem .75rem; }}
  .tile .k {{ font-size:.68rem; text-transform:uppercase; letter-spacing:.07em;
              color:var(--mut); }}
  .tile .v {{ font-size:1.32rem; font-weight:700; font-variant-numeric:tabular-nums;
              margin-top:.15rem; }}
  .tile.final {{ border-width:2px; }}
  .tile.final.pos {{ border-color:var(--pos); }}
  .tile.final.neg {{ border-color:var(--neg); }}
  .tile.final.cero {{ border-color:var(--eje); }}
  .tile .lado {{ font-size:.72rem; color:var(--tinta2); }}
  .panel h3 {{ font-size:.72rem; text-transform:uppercase; letter-spacing:.08em;
               color:var(--mut); margin:1.1rem 0 .5rem; font-weight:600; }}
  .pares {{ display:flex; flex-direction:column; gap:.35rem; }}
  .par {{ display:flex; flex-wrap:wrap; align-items:baseline; gap:.5rem;
          font-size:.84rem; }}
  .par .m {{ font-family:ui-monospace,monospace; font-weight:700;
             font-variant-numeric:tabular-nums; }}
  .par .nota {{ color:var(--mut); font-size:.76rem; }}
  .par .x {{ color:var(--mut); }}
  .vacio {{ color:var(--mut); font-size:.84rem; }}
  .deudas {{ display:flex; flex-direction:column; gap:.45rem; }}
  .dfila {{ display:grid; grid-template-columns:minmax(110px,auto) 1fr auto auto;
            gap:.7rem; align-items:center; font-size:.82rem; }}
  .dfila .nom {{ font-family:ui-monospace,monospace; white-space:nowrap; }}
  .dfila .prog {{ height:8px; border-radius:2px; background:var(--cero);
                  box-shadow:inset 0 0 0 1px var(--linea); overflow:hidden; }}
  .dfila .prog i {{ display:block; height:100%; background:var(--pos); }}
  .dfila .cifra {{ font-variant-numeric:tabular-nums; color:var(--tinta2);
                   font-family:ui-monospace,monospace; white-space:nowrap; }}
  .est {{ font-size:.64rem; text-transform:uppercase; letter-spacing:.06em;
          border-radius:4px; padding:.1rem .35rem; border:1px solid var(--linea);
          color:var(--tinta2); white-space:nowrap; }}
  .est.CRUZADA {{ border-color:var(--pos); color:var(--pos); }}
  .est.PARCIAL {{ border-color:#c47d1a; color:#c47d1a; font-weight:700; }}

  @media (max-width:640px) {{
    .viz {{ padding:1.5rem .75rem 3rem; }}
    .dfila {{ grid-template-columns:1fr auto; }}
    .dfila .prog {{ grid-column:1 / -1; }}
  }}
</style>
<div class="viz">
  <h1>{titulo}</h1>
  <p class="sub">Fase 1: solo deudas, sin pagos. Cada nodo agrega <strong>una</strong> deuda
  a su padre, y su letra dice cómo se compara esa deuda nueva contra la
  <em>brecha</em> (<code>|neto|</code>) del padre. El color del punto es el signo del neto
  y el tamaño es su magnitud.</p>
  <p>{estado}</p>

  <div class="leyenda">
    <span class="lg"><span class="dot pos"></span>neto <b>+</b> · te deben</span>
    <span class="lg"><span class="dot neg"></span>neto <b>−</b> · tú debes</span>
    <span class="lg"><span class="dot cero"></span>neto 0 · al día</span>
    <span class="lg" style="color:var(--mut)">tamaño del punto = |neto|</span>
  </div>
  <div class="leyenda">{leyenda_et}</div>

  <div class="lienzo">{svg}</div>

  <div class="panel" id="panel"></div>

  <h2>Tabla de casos</h2>
  <div class="tabla">
    <table>
      <thead><tr>
        <th>ID</th><th>Caso</th><th class="num">Σ debe</th><th class="num">Σ debo</th>
        <th class="num">cruzado</th><th>queda tras el cruce</th>
        <th class="num">saldo final</th><th></th>
      </tr></thead>
      <tbody>{"".join(filas)}</tbody>
    </table>
  </div>
</div>
<div id="tip"></div>
<script>
  const CRUCES = {json.dumps(datos, ensure_ascii=False)};
  const n2 = x => x.toFixed(2);
  const panel = document.getElementById('panel');

  function pintar(code) {{
    const d = CRUCES[code];
    if (!d) return;
    const lado = d.saldo > 0.005 ? 'pos' : (d.saldo < -0.005 ? 'neg' : 'cero');

    const pares = d.pares.length ? d.pares.map(p => `
        <div class="par"><span>${{p.debe}}</span><span class="x">×</span>
          <span>${{p.debo}}</span><span class="x">→</span>
          <span class="m">${{n2(p.monto)}}</span>
          <span class="nota">${{p.nota}}</span></div>`).join('')
      : '<p class="vacio">Ninguna: el caso tiene deudas en una sola dirección, '
        + 'así que no hay nada contra qué compensar.</p>';

    const deudas = d.deudas.map(x => {{
      const pct = x.monto > 0.005 ? (x.cruzado / x.monto * 100) : 0;
      return `<div class="dfila">
          <span class="nom">${{x.nombre}}</span>
          <span class="prog"><i style="width:${{pct}}%"></i></span>
          <span class="cifra">cruzado ${{n2(x.cruzado)}} · queda ${{n2(x.restante)}}</span>
          <span class="est ${{x.estado}}">${{x.estado}}</span>
        </div>`;
    }}).join('');

    const vivas = d.deudas.filter(x => x.restante > 0.005);
    const resumen = vivas.length
      ? 'Sobreviven ' + vivas.map(x => x.nombre.replace(/ [\\d.]+$/, '') + ' con ' + n2(x.restante)
          + (x.estado === 'PARCIAL' ? ' (cruzada a medias)' : '')).join(' y ') + '.'
      : 'No queda ninguna deuda viva.';

    panel.innerHTML = `
      <div class="panel-cab">
        <span class="id">${{code}}</span><span class="ruta">${{d.titulo}}</span>
        <span class="pista">clic en cualquier nodo o fila para ver su cruce</span>
      </div>
      <div class="tiles">
        <div class="tile"><div class="k">Total debe</div><div class="v">${{n2(d.td)}}</div>
          <div class="lado">te deben</div></div>
        <div class="tile"><div class="k">Total debo</div><div class="v">${{n2(d.tdo)}}</div>
          <div class="lado">tú debes</div></div>
        <div class="tile"><div class="k">Cruzado</div><div class="v">${{n2(d.cruzado)}}</div>
          <div class="lado">el menor de los dos</div></div>
        <div class="tile final ${{lado}}"><div class="k">Saldo final tras el cruce</div>
          <div class="v">${{d.saldo > 0 ? '+' : ''}}${{n2(d.saldo)}}</div>
          <div class="lado">${{d.lado}}</div></div>
      </div>
      <h3>Deudas que se cruzaron</h3>
      <div class="pares">${{pares}}</div>
      <h3>Cómo queda cada deuda</h3>
      <div class="deudas">${{deudas}}</div>
      <p class="vacio" style="margin-top:.9rem">${{resumen}}</p>`;

    document.querySelectorAll('.sel').forEach(e => e.classList.remove('sel'));
    document.querySelectorAll(`[data-code="${{code}}"]`).forEach(e => e.classList.add('sel'));
  }}

  document.querySelectorAll('[data-code]').forEach(e => {{
    e.addEventListener('click', () => pintar(e.dataset.code));
    e.addEventListener('keydown', ev => {{
      if (ev.key === 'Enter' || ev.key === ' ') {{ ev.preventDefault(); pintar(e.dataset.code); }}
    }});
  }});

  const tip = document.getElementById('tip');
  document.querySelectorAll('.nodo').forEach(n => {{
    n.addEventListener('mouseenter', () => {{
      const [id, caso, totales, neto] = n.dataset.tip.split('|');
      const d = CRUCES[n.dataset.code];
      const extra = d ? `<br>cruzado ${{n2(d.cruzado)}} · saldo final ${{n2(d.saldo)}} (${{d.lado}})` : '';
      tip.innerHTML = `<b>${{id}}</b>${{caso}}<br>${{totales}}<br>${{neto}}${{extra}}`;
      tip.style.opacity = 1;
    }});
    n.addEventListener('mousemove', e => {{
      const r = tip.getBoundingClientRect();
      tip.style.left = Math.min(e.clientX + 14, innerWidth - r.width - 8) + 'px';
      tip.style.top = Math.min(e.clientY + 14, innerHeight - r.height - 8) + 'px';
    }});
    n.addEventListener('mouseleave', () => {{ tip.style.opacity = 0; }});
  }});

  pintar('{inicial}');
</script>
"""


# ── Render HTML · vista de flujo (espejo del modal de React) ─────────────────
# Copia la forma del `FlowLedger` de AccountStatementModal.tsx: timeline vertical,
# movimientos de presente a pasado, punto índigo para "te deben" y rosa para "tú
# debes", con el saldo acumulado bajo cada delta. Paleta = la del proyecto (zinc +
# indigo/rose/sky), no la del visor de árbol: aquí el objetivo es que se vea igual
# que en la página, no introducir un lenguaje visual nuevo.
def _tarjeta_flujo(c, marca):
    x = cruzar(c)
    lado = "pos" if c.neto > 0.005 else ("neg" if c.neto < -0.005 else "cero")
    etiqueta_neto = {"pos": "Te deben", "neg": "Tú debes", "cero": "Al día"}[lado]

    # Ledger cronológico ascendente: lo más antiguo arriba, lo más nuevo abajo, de modo
    # que el cruce de cuentas —que cierra la historia— queda al final de la tarjeta.
    apl = {a.idx: a for a in c.estado.aplicaciones}
    saldo, filas = 0.0, []
    for i, m in enumerate(c.movs):
        saldo = round(saldo + m.signo, 2)
        clase = ("pago" if m.es_pago else "deuda") + " " + (
            {"debe": "debe", "debo": "debo",
             "recibido": "recibido", "doy": "doy"}[m.direccion])
        if m.es_pago:
            titulo = ("me pagan" if m.direccion == "recibido" else "yo pago")
            icono = "←" if m.direccion == "recibido" else "→"
        else:
            titulo, icono = m.direccion, ("↑" if m.direccion == "debe" else "↓")

        # Las tres salidas de un pago: exacto (nada debajo), insuficiente (vuelven a
        # salir las deudas parciales) y en exceso (queda saldo a favor / en contra).
        cola = ""
        if m.es_pago:
            a = apl[i]
            abonos = "".join(f"""
                <li class="ab"><span class="abn">abonó a {nom}</span>
                  <span class="abm">${monto:.2f}</span></li>"""
                             for _, nom, monto in a.abonos)
            if a.salida == "exacto":
                cierre = ('<li class="ok">pago justo · no queda nada pendiente '
                          'de ese lado</li>')
            elif a.salida == "insuficiente":
                cierre = "".join(f"""
                <li class="parc"><span class="abn">{nom} sigue abierta</span>
                  <span class="abm">quedan ${rest:.2f}</span>
                  <span class="tag">{'parcial' if tocada else 'sin tocar'}</span></li>"""
                                 for _, nom, rest, tocada in a.parciales)
            else:
                quien = ("saldo a favor del deudor" if m.direccion == "recibido"
                         else "saldo a favor tuyo")
                signo = "en contra" if m.direccion == "recibido" else "a favor"
                cierre = f"""
                <li class="exc"><span class="abn">sobró del pago · {quien}</span>
                  <span class="abm">${a.sobrante:.2f}</span>
                  <span class="tag exc">{signo}</span></li>"""
            cola = f'<ul class="sub">{abonos}{cierre}</ul>'

        filas.append(f"""
        <li class="mov {clase}">
          <span class="punto"></span>
          <div class="mcard">
            <div class="mtop">
              <div class="mizq">
                <span class="mico">{icono}</span>
                <div>
                  <div class="mcon">{titulo} {_f(m.monto)}
                    {f'<span class="paso">{m.etiqueta}</span>' if m.etiqueta else
                     '<span class="paso raiz">inicio</span>'}</div>
                  <div class="mfec">n{i + 1} · {FECHAS[i]}</div>
                </div>
              </div>
              <div class="mder">
                <div class="mdelta">{'+' if m.signo >= 0 else '−'}${_f(abs(m.signo))}</div>
                <div class="msaldo">saldo {'−' if saldo < 0 else ''}${abs(saldo):.2f}</div>
              </div>
            </div>
            {cola}
          </div>
        </li>""")
    filas = "".join(filas)
    movs = c.movs

    # Detalle de lo saldado, una columna por dirección.
    def _columna(direccion):
        tocadas = [d for d in x.deudas if d.direccion == direccion and d.cruzado > 0.005]
        if not tocadas:
            return '<li class="vacio">nada</li>'
        return "".join(f"""
                <li><span class="sn">{d.nombre}</span>
                    <span class="sm">${d.cruzado:.2f}</span>
                    <span class="ss {'parc' if d.estado == 'PARCIAL' else 'tot'}">{
                      'de $' + _f(d.monto) if d.estado == 'PARCIAL' else 'saldada'}</span>
                </li>""" for d in tocadas)

    # Lo que sobrevive al cruce: vuelve a salir, marcado como parcial si ya se le abonó.
    def _nota_pend(d):
        partes = []
        if d.pagado > 0.005:
            partes.append(f"pagada ${d.pagado:.2f}")
        if d.cruzado > 0.005:
            partes.append(f"cruzada ${d.cruzado:.2f}")
        return "parcial · " + " · ".join(partes) if partes else "sin tocar"

    pendientes = "".join(f"""
            <li class="pend {'parcial' if d.estado == 'PARCIAL' else 'intacta'}">
              <span class="pn2">{d.nombre}</span>
              <span class="pbar"><i style="width:{((d.pagado + d.cruzado) / d.monto * 100) if d.monto > 0.005 else 0:.0f}%"></i></span>
              <span class="pq">quedan ${d.restante:.2f}</span>
              <span class="pe">{_nota_pend(d)}</span>
            </li>""" for d in x.restantes)
    for credito, texto in ((x.credito_deudor, "saldo a favor del deudor · se lo debes"),
                           (x.credito_owner, "saldo a favor tuyo · te lo deben")):
        if credito > 0.005:
            pendientes += f"""
            <li class="pend credito">
              <span class="pn2">crédito</span>
              <span class="pbar"><i style="width:100%"></i></span>
              <span class="pq">${credito:.2f}</span>
              <span class="pe">{texto}</span>
            </li>"""

    pares = "".join(f"""
              <li><span class="pd debe">{e.debe}</span><span class="px">×</span>
                  <span class="pd debo">{e.debo}</span><span class="px">→</span>
                  <span class="pm">${_f(e.monto)}</span></li>"""
                    for e in x.emparejamientos)

    chk = ("" if marca is None else
           f'<span class="vcheck {"ok" if marca else "bad"}">'
           f'{"✓ cuadra" if marca else "✗ no cuadra"}</span>')

    sin_cruce = x.cruzado <= 0.005

    return f"""
    <article class="caso" data-buscar="{c.code} {c.titulo}">
      <header class="chead">
        <span class="cid">{c.code}</span>
        <span class="cruta">{c.titulo}</span>
        <span class="cnivel">n{c.nivel}</span>
        <span class="cneto {lado}">{etiqueta_neto} ${_f(abs(c.neto))}</span>
        {chk}
      </header>

      <h4>Flujo <span class="cnt">{len(movs)}</span>
        <span class="orden">antiguo → nuevo</span></h4>
      <ul class="ledger">{filas}</ul>

      <h4>Cruce de cuentas <span class="orden">lo más nuevo</span></h4>
      <div class="cruce">
        <div class="hero">
          <span class="hk">Se cruzó</span>
          <span class="hv{' nulo' if sin_cruce else ''}">${x.cruzado:.2f}</span>
          <span class="hn">{'nada que cruzar: las deudas van en una sola dirección'
                            if sin_cruce else 'el menor de los dos totales'}</span>
        </div>

        <div class="sumas">
          <div class="suma debe"><span class="sk">Σ debe</span>
            <span class="sv">${_f(x.total_debe)}</span></div>
          <span class="vs">⇄</span>
          <div class="suma debo"><span class="sk">Σ debo</span>
            <span class="sv">${_f(x.total_debo)}</span></div>
        </div>

        <details class="detalle">
          <summary>Detalle de lo saldado</summary>
          <div class="cols">
            <div class="col debe"><h6>Debe · te deben</h6>
              <ul class="sald">{_columna('debe')}</ul></div>
            <div class="col debo"><h6>Debo · tú debes</h6>
              <ul class="sald">{_columna('debo')}</ul></div>
          </div>
          {f'<ul class="pares">{pares}</ul>' if pares else ''}
        </details>

        <div class="final {lado}">
          <span class="fk">Saldo después del cruce</span>
          <span class="fv">{'−' if c.neto < 0 else ''}${abs(c.neto):.2f}</span>
          <span class="fl">{x.lado}</span>
        </div>
        {f'<div class="tras"><h6>Queda por saldar</h6><ul class="pends">{pendientes}</ul></div>'
         if x.restantes else ''}
      </div>
    </article>"""


def render_html_flujo(sel, motor, titulo="Casos de deudas — vista de flujo"):
    marcas = {c.code: (evaluar(c, motor)[2] if motor else None) for c in sel}
    tarjetas = "".join(_tarjeta_flujo(c, marcas[c.code]) for c in sel)
    fallos = sum(1 for v in marcas.values() if v is False)
    if not motor:
        estado = '<span class="pill neutra">sin verificar — usa --verificar</span>'
    elif fallos:
        estado = f'<span class="pill mala">{fallos} casos no cuadran</span>'
    else:
        estado = (f'<span class="pill buena">los {len(sel)} casos cuadran '
                  f'con <code>reading.py</code></span>')

    return f"""<title>{titulo}</title>
<style>
  /* Paleta del proyecto: surface = zinc, indigo = te deben, rose = tú debes. */
  :root {{
    color-scheme: dark;
    --s950:#09090b; --s900:#18181b; --s800:#27272a; --s700:#3f3f46;
    --s500:#71717a; --s400:#a1a1aa; --s300:#d4d4d8; --s100:#f4f4f5;
    --indigo:#818cf8; --rose:#fb7185; --sky:#38bdf8; --emerald:#34d399; --amber:#fbbf24;
    --fondo:var(--s950); --panel:rgba(24,24,27,.6); --linea:rgba(255,255,255,.07);
    --tinta:var(--s100); --tinta2:var(--s400); --tinta3:var(--s500);
  }}
  :root[data-theme="light"] {{
    color-scheme: light;
    --fondo:#fafafa; --panel:#fff; --linea:rgba(9,9,11,.10);
    --tinta:#18181b; --tinta2:#52525b; --tinta3:#71717a;
    --indigo:#4f46e5; --rose:#e11d48; --sky:#0284c7; --emerald:#059669; --amber:#b45309;
  }}

  body {{ margin:0; background:var(--fondo); color:var(--tinta);
         font:13.5px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif; }}
  .wrap {{ max-width:780px; margin:0 auto; padding:1.4rem .85rem 3rem; }}
  h1 {{ font-size:1.2rem; margin:0 0 .2rem; letter-spacing:-.02em; }}
  .sub {{ color:var(--tinta2); margin:0 0 .7rem; font-size:.82rem; }}
  code {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.88em; }}
  .pill {{ display:inline-block; font-size:.78rem; padding:.2rem .6rem; border-radius:999px;
           border:1px solid var(--linea); }}
  .pill.buena {{ color:var(--emerald); background:color-mix(in srgb,var(--emerald) 12%,transparent); }}
  .pill.mala {{ color:var(--rose); background:color-mix(in srgb,var(--rose) 12%,transparent); }}
  .pill.neutra {{ color:var(--tinta3); }}

  .barra {{ position:sticky; top:0; z-index:5; background:var(--fondo);
            padding:.6rem 0; border-bottom:1px solid var(--linea); margin-bottom:.85rem;
            display:flex; gap:.6rem; align-items:center; flex-wrap:wrap; }}
  .barra input {{ flex:1; min-width:190px; background:var(--panel); color:var(--tinta);
                  border:1px solid var(--linea); border-radius:10px;
                  padding:.35rem .6rem; font-size:.82rem; }}
  .barra input:focus-visible {{ outline:2px solid var(--indigo); outline-offset:1px; }}
  .barra .conteo {{ color:var(--tinta3); font-size:.8rem; }}

  .caso {{ background:var(--panel); border:1px solid var(--linea); border-radius:12px;
           padding:.7rem .8rem .8rem; margin-bottom:.65rem; }}
  .caso[hidden] {{ display:none; }}
  .chead {{ display:flex; flex-wrap:wrap; align-items:baseline; gap:.4rem;
            padding-bottom:.5rem; border-bottom:1px solid var(--linea); }}
  .cid {{ font:800 .82rem ui-monospace,monospace; }}
  .cruta {{ color:var(--tinta2); font-size:.78rem; }}
  .cnivel, .vcheck {{ font-size:.62rem; border:1px solid var(--linea); border-radius:6px;
                      padding:.1rem .4rem; color:var(--tinta3); }}
  .vcheck {{ margin-left:auto; }}
  .vcheck.ok {{ color:var(--emerald); border-color:color-mix(in srgb,var(--emerald) 40%,transparent); }}
  .vcheck.bad {{ color:var(--rose); border-color:var(--rose); font-weight:700; }}

  .cneto {{ font:700 .72rem ui-monospace,monospace; border-radius:5px;
            padding:.08rem .38rem; }}
  .cneto.pos {{ color:var(--indigo); background:color-mix(in srgb,var(--indigo) 15%,transparent); }}
  .cneto.neg {{ color:var(--rose); background:color-mix(in srgb,var(--rose) 15%,transparent); }}
  .cneto.cero {{ color:var(--tinta2); background:var(--s800); }}

  h4 {{ font-size:.62rem; text-transform:uppercase; letter-spacing:.08em;
        color:var(--tinta3); margin:.75rem 0 .4rem; font-weight:600;
        display:flex; align-items:center; gap:.35rem; }}
  .orden {{ margin-left:auto; text-transform:none; letter-spacing:0; font-weight:400;
             font-size:.6rem; color:var(--tinta3); opacity:.75; }}
  h4 .cnt {{ background:var(--s800); border-radius:4px; padding:.02rem .25rem; }}

  .ledger {{ list-style:none; margin:0; padding:0 0 0 1.15rem; position:relative; }}
  .ledger::before {{ content:""; position:absolute; left:4px; top:.4rem; bottom:.4rem;
                     width:1px; background:var(--linea); }}
  .mov {{ position:relative; margin-bottom:.28rem; }}
  .mov .punto {{ position:absolute; left:-1.15rem; top:.72rem; width:9px; height:9px;
                 border-radius:50%; border:2px solid var(--fondo); }}
  .mov.debe .punto {{ background:var(--indigo); }}
  .mov.debo .punto {{ background:var(--rose); }}
  .mcard {{ background:color-mix(in srgb,var(--s900) 55%,transparent);
            border:1px solid var(--linea); border-radius:9px; padding:.35rem .6rem; }}
  .mtop {{ display:flex; align-items:center; justify-content:space-between; gap:.6rem; }}
  .mizq {{ display:flex; align-items:center; gap:.45rem; min-width:0; }}
  .mico {{ width:20px; height:20px; border-radius:6px; display:grid; place-items:center;
           font-size:.75rem; flex:none; }}
  .mov.debe .mico {{ background:color-mix(in srgb,var(--indigo) 16%,transparent); color:var(--indigo); }}
  .mov.debo .mico {{ background:color-mix(in srgb,var(--rose) 16%,transparent); color:var(--rose); }}
  .mcon {{ font-weight:700; font-size:.78rem; }}
  .paso {{ font:600 .55rem/1.5 ui-monospace,monospace; text-transform:uppercase;
           letter-spacing:.05em; background:var(--s800); color:var(--tinta2);
           border-radius:4px; padding:.05rem .3rem; margin-left:.35rem; }}
  .paso.raiz {{ background:transparent; border:1px dashed var(--s700); }}
  .mfec {{ font-size:.62rem; color:var(--tinta3); font-variant-numeric:tabular-nums; }}
  .mder {{ text-align:right; flex:none; }}
  .mdelta {{ font:700 .78rem ui-monospace,monospace; font-variant-numeric:tabular-nums; }}
  .mov.debe .mdelta {{ color:var(--indigo); }}
  .mov.debo .mdelta {{ color:var(--rose); }}

  /* Pagos: mismo timeline, look distinto (verde, borde punteado, sangría propia). */
  .mov.pago .punto {{ background:var(--emerald); }}
  .mov.pago .mcard {{ border-style:dashed;
                      border-color:color-mix(in srgb,var(--emerald) 35%,var(--linea));
                      background:color-mix(in srgb,var(--emerald) 6%,transparent); }}
  .mov.pago .mico {{ background:color-mix(in srgb,var(--emerald) 16%,transparent);
                     color:var(--emerald); }}
  .mov.pago .mdelta {{ color:var(--emerald); }}
  .sub {{ list-style:none; margin:.3rem 0 0; padding:0 0 0 1.65rem;
          display:flex; flex-direction:column; gap:.12rem; }}
  .sub li {{ display:flex; align-items:baseline; gap:.4rem; font-size:.63rem;
             color:var(--tinta3); }}
  .abn {{ min-width:0; }}
  .abm {{ margin-left:auto; font-family:ui-monospace,monospace;
          font-variant-numeric:tabular-nums; color:var(--tinta2); }}
  .sub .ok {{ color:var(--emerald); }}
  .sub .parc .abm, .sub .parc .abn {{ color:var(--amber); }}
  .sub .exc .abm, .sub .exc .abn {{ color:var(--sky); }}
  .tag {{ font-size:.53rem; border:1px solid currentColor; border-radius:3px;
          padding:0 .22rem; text-transform:uppercase; letter-spacing:.05em; }}
  .msaldo {{ font-size:.6rem; color:var(--tinta3); font-variant-numeric:tabular-nums; }}

  /* ── Cruce de cuentas: el valor cruzado manda, luego las sumas, luego el detalle ── */
  .cruce {{ background:color-mix(in srgb,var(--s900) 55%,transparent);
            border:1px solid var(--linea); border-radius:10px; padding:.55rem .7rem .65rem; }}
  .hero {{ display:flex; align-items:baseline; gap:.45rem; flex-wrap:wrap; }}
  .hk {{ font-size:.62rem; text-transform:uppercase; letter-spacing:.08em; color:var(--tinta3); }}
  .hv {{ font:800 1.55rem/1 ui-monospace,monospace; font-variant-numeric:tabular-nums;
         color:var(--sky); letter-spacing:-.02em; }}
  .hv.nulo {{ color:var(--tinta3); }}
  .hn {{ font-size:.62rem; color:var(--tinta3); margin-left:auto; text-align:right; }}

  .sumas {{ display:flex; align-items:stretch; gap:.35rem; margin:.45rem 0 .1rem; }}
  .suma {{ flex:1; display:flex; align-items:baseline; justify-content:space-between;
           gap:.5rem; border:1px solid var(--linea); border-radius:10px;
           padding:.28rem .5rem; }}
  .suma.debe {{ border-color:color-mix(in srgb,var(--indigo) 35%,transparent); }}
  .suma.debo {{ border-color:color-mix(in srgb,var(--rose) 35%,transparent); }}
  .sk {{ font-size:.6rem; text-transform:uppercase; letter-spacing:.06em; color:var(--tinta3); }}
  .sv {{ font:700 .88rem ui-monospace,monospace; font-variant-numeric:tabular-nums; }}
  .suma.debe .sv {{ color:var(--indigo); }}
  .suma.debo .sv {{ color:var(--rose); }}
  .vs {{ align-self:center; color:var(--tinta3); font-size:1rem; }}

  .detalle {{ margin:.45rem 0 .1rem; }}
  .detalle summary {{ cursor:pointer; font-size:.62rem; text-transform:uppercase;
                      letter-spacing:.07em; color:var(--tinta3); padding:.15rem 0;
                      list-style:none; display:flex; align-items:center; gap:.35rem; }}
  .detalle summary::-webkit-details-marker {{ display:none; }}
  .detalle summary::before {{ content:"▸"; font-size:.8rem; transition:transform .15s; }}
  .detalle[open] summary::before {{ transform:rotate(90deg); }}
  .detalle summary:hover {{ color:var(--tinta2); }}
  .detalle summary:focus-visible {{ outline:2px solid var(--indigo); outline-offset:2px;
                                    border-radius:4px; }}
  .cols {{ display:grid; grid-template-columns:1fr 1fr; gap:.35rem; margin-top:.25rem; }}
  .col {{ border:1px solid var(--linea); border-radius:8px; padding:.32rem .45rem; }}
  .col h6 {{ margin:0 0 .25rem; font-size:.58rem; text-transform:uppercase;
             letter-spacing:.07em; font-weight:600; }}
  .col.debe h6 {{ color:var(--indigo); }}
  .col.debo h6 {{ color:var(--rose); }}
  .sald {{ list-style:none; margin:0; padding:0; display:flex; flex-direction:column;
           gap:.2rem; }}
  .sald li {{ display:flex; align-items:baseline; gap:.3rem; font-size:.67rem;
              font-family:ui-monospace,monospace; font-variant-numeric:tabular-nums; }}
  .sn {{ color:var(--tinta2); white-space:nowrap; }}
  .sm {{ margin-left:auto; font-weight:700; color:var(--sky); }}
  .ss {{ font:400 .55rem/1.5 system-ui,sans-serif; border-radius:4px; padding:0 .28rem;
         white-space:nowrap; }}
  .ss.tot {{ color:var(--tinta3); border:1px solid var(--linea); }}
  .ss.parc {{ color:var(--amber); border:1px solid var(--amber); }}

  .pares {{ list-style:none; margin:.5rem 0 0; padding:0; display:flex;
            flex-direction:column; gap:.2rem; }}
  .pares li {{ display:flex; flex-wrap:wrap; gap:.3rem; align-items:baseline;
               font-size:.66rem; font-family:ui-monospace,monospace; }}
  .pd.debe {{ color:var(--indigo); }} .pd.debo {{ color:var(--rose); }}
  .px {{ color:var(--tinta3); }}
  .pm {{ color:var(--sky); font-weight:700; }}
  .vacio {{ color:var(--tinta3); font-size:.72rem; font-family:system-ui,sans-serif; }}

  .final {{ display:flex; align-items:baseline; gap:.45rem; margin-top:.5rem;
            padding-top:.45rem; border-top:1px solid var(--linea); }}
  .fk {{ font-size:.62rem; text-transform:uppercase; letter-spacing:.07em; color:var(--tinta3); }}
  .fv {{ font:800 1.1rem ui-monospace,monospace; font-variant-numeric:tabular-nums;
         margin-left:auto; }}
  .final.pos .fv {{ color:var(--indigo); }}
  .final.neg .fv {{ color:var(--rose); }}
  .final.cero .fv {{ color:var(--tinta2); }}
  .fl {{ font-size:.7rem; color:var(--tinta2); }}

  .tras {{ margin-top:.45rem; padding-top:.45rem; border-top:1px dashed var(--linea); }}
  .tras h6 {{ margin:0 0 .25rem; font-size:.58rem; text-transform:uppercase;
              letter-spacing:.07em; color:var(--tinta3); font-weight:600; }}
  .pends {{ list-style:none; margin:0; padding:0; display:flex; flex-direction:column;
            gap:.25rem; }}
  .pend {{ display:grid; grid-template-columns:minmax(86px,auto) 1fr auto auto; gap:.4rem;
           align-items:center; font-size:.67rem; }}
  .pn2 {{ font-family:ui-monospace,monospace; color:var(--tinta2); white-space:nowrap; }}
  .pbar {{ height:5px; border-radius:99px; background:var(--s800); overflow:hidden; }}
  .pbar i {{ display:block; height:100%; background:var(--sky); }}
  .pq {{ font-family:ui-monospace,monospace; font-variant-numeric:tabular-nums;
         white-space:nowrap; font-weight:700; }}
  .pend.parcial .pq {{ color:var(--amber); }}
  .pe {{ font-size:.55rem; border-radius:4px; padding:.05rem .3rem; white-space:nowrap;
         border:1px solid var(--linea); color:var(--tinta3); }}
  .pend.parcial .pe {{ color:var(--amber); border-color:var(--amber); font-weight:700; }}
  .pend.credito .pn2, .pend.credito .pq {{ color:var(--sky); }}
  .pend.credito .pbar i {{ background:var(--sky); }}
  .pend.credito .pe {{ color:var(--sky); border-color:color-mix(in srgb,var(--sky) 45%,transparent); }}

  @media (max-width:560px) {{
    .cols {{ grid-template-columns:1fr; }}
    .pend {{ grid-template-columns:1fr auto; }}
    .pbar {{ grid-column:1 / -1; }}
    .hn {{ margin-left:0; text-align:left; width:100%; }}
  }}
</style>
<div class="wrap">
  <h1>{titulo}</h1>
  <p class="sub">Cada caso como se vería en el modal <em>Estado de cuenta</em>: el flujo de
  movimientos de más reciente a más antiguo con su saldo acumulado, y al final el cruce de
  cuentas. Fase 1: solo deudas, sin pagos.</p>
  <p>{estado}</p>

  <div class="barra">
    <input id="q" type="search" placeholder="Filtrar por ID o ruta (p. ej. ANS, o «debo 60»)"
           aria-label="Filtrar casos">
    <span class="conteo" id="conteo">{len(sel)} casos</span>
  </div>

  {tarjetas}
</div>
<script>
  const q = document.getElementById('q');
  const conteo = document.getElementById('conteo');
  const casos = [...document.querySelectorAll('.caso')];
  q.addEventListener('input', () => {{
    const t = q.value.trim().toLowerCase();
    let n = 0;
    for (const c of casos) {{
      const ok = !t || c.dataset.buscar.toLowerCase().includes(t);
      c.hidden = !ok;
      if (ok) n++;
    }}
    conteo.textContent = n + (n === 1 ? ' caso' : ' casos');
  }});
</script>
"""


def main():
    ap = argparse.ArgumentParser(description="Visor del árbol de casos de deudas")
    ap.add_argument("--nivel", type=int, default=NIVEL_MAX, help=f"nivel máximo (1..{NIVEL_MAX})")
    ap.add_argument("--rama", help="prefijo de ID, p.ej. AN")
    ap.add_argument("--solo-hojas", action="store_true", help="solo los casos terminales")
    ap.add_argument("--verificar", action="store_true", help="contrastar contra reading.py")
    ap.add_argument("--cruce", action="store_true",
                    help="agrega columnas con el cruce de cuentas de cada caso")
    ap.add_argument("--detalle", nargs="?", const="*", metavar="ID",
                    help="bloque completo del cruce: un ID (--detalle ANM) o todos (--detalle)")
    ap.add_argument("--html", metavar="ARCHIVO", help="escribe una página autocontenida")
    ap.add_argument("--titulo", help="título de la página (por defecto sale del filtro)")
    ap.add_argument("--vista", choices=("arbol", "flujo"), default="arbol",
                    help="forma del --html: diagrama de árbol (defecto) o flujo tipo React")
    ap.add_argument("--abrir", action="store_true",
                    help="abre el --html en el navegador al terminar")
    ap.add_argument("--no-color", action="store_true")
    args = ap.parse_args()

    if args.no_color:
        C.activo = False

    casos = generar()
    sel = seleccionar(casos, args.nivel, args.rama, args.solo_hojas)
    if not sel:
        print("Ningún caso coincide con el filtro.")
        return 1

    motor = _motor() if args.verificar else None

    if args.html:
        # El diagrama necesita los ancestros para poder dibujar las ramas, así que
        # --solo-hojas solo recorta la tabla.
        sel_arbol = seleccionar(casos, args.nivel, args.rama, False)
        # Título propio por filtro: si no, dos páginas distintas comparten nombre.
        matices = []
        if args.nivel < NIVEL_MAX:
            matices.append(f"hasta nivel {args.nivel}")
        if args.rama:
            matices.append(f"rama {args.rama}")
        if args.solo_hojas:
            matices.append("solo hojas")
        base = ("Casos de deudas — vista de flujo" if args.vista == "flujo"
                else "Árbol de casos — Deudas")
        titulo = args.titulo or (base + (f" ({', '.join(matices)})" if matices else ""))
        if args.vista == "flujo":
            Path(args.html).write_text(render_html_flujo(sel, motor, titulo),
                                       encoding="utf-8")
            print(f"Escrito {args.html} ({len(sel)} casos en flujo).")
        else:
            Path(args.html).write_text(render_html(sel_arbol, sel, motor, titulo),
                                       encoding="utf-8")
            print(f"Escrito {args.html} ({len(sel_arbol)} nodos en el árbol, "
                  f"{len(sel)} filas en la tabla).")
        if args.abrir:
            webbrowser.open(Path(args.html).resolve().as_uri())
            print("Abriendo en el navegador…")
        return 0

    if args.detalle:
        objetivo = sel if args.detalle == "*" else [c for c in sel if c.code == args.detalle]
        if not objetivo:
            print(f"No existe el caso '{args.detalle}' dentro del filtro.")
            return 1
        for c in objetivo:
            render_cruce(c, motor)
        return 0

    return 1 if render_terminal(sel, motor, args.cruce) else 0


if __name__ == "__main__":
    sys.exit(main())
