from contabilidad.backend.services.credit_card.models import DATOS_TARJETA_TOTALES, DATOS_TARJETA_INFO_MOVIMIENTOS
from contabilidad.backend.services.credit_card.utils import to_float

def extraer_valores_nulos(totales: list[list[str]]) -> list:
    """Extrae solo los valores no nulos de las listas interiores."""
    ret = []
    for fila in totales:
        f = []
        for x in fila:
            if x != '':
                f.append(x)
        ret.append(f)
    return ret

def get_info_totales(totales_info: list[list[str]]) -> tuple[DATOS_TARJETA_TOTALES, float]:
    """Extrae totales de las filas de totales."""
    totales_validos = extraer_valores_nulos(totales_info)
    import re
    def pick_total(pattern: str) -> float:
        import numpy as np
        for row in totales_validos:
            for cell in row:
                if re.search(pattern, cell, re.IGNORECASE):
                    # El valor suele estar en la última columna o penúltima
                    try:
                        f = to_float(row[-1])
                        if not np.isnan(f): return f
                        if len(row) > 1:
                            f2 = to_float(row[-2])
                            if not np.isnan(f2): return f2
                    except Exception:
                        pass
        return np.nan

    minimo_pagar = pick_total("M I N I M O   A   P A G A R")
    return DATOS_TARJETA_TOTALES(
        TOTAL_A_PAGAR=pick_total("T O T A L   N U E V O   S A L D O"),
        TOTAL_CONSUMO=pick_total("T O T A L   C O N S U M O S/A V A N C E S|T O T A L   A V A N C E S"),
        MINIMO_A_PAGAR=minimo_pagar,
    ), minimo_pagar
