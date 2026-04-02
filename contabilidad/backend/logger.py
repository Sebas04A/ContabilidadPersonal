"""
logger.py — Configuración central de logging para el backend de ContabilidadPersonal.

Uso en cada módulo:
    from contabilidad.backend.logger import get_logger
    logger = get_logger(__name__)

    logger.info("Mensaje informativo")
    logger.warning("Algo inesperado pero no fatal")
    logger.error("Error real")
    logger.debug("Info de análisis (solo visible en modo DEBUG)")
"""

import logging
import os
import sys

# ── Paleta de colores ANSI ────────────────────────────────────────────────────
RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"

GREY    = "\033[38;5;245m"
CYAN    = "\033[38;5;117m"
GREEN   = "\033[38;5;114m"
YELLOW  = "\033[38;5;221m"
RED     = "\033[38;5;203m"
MAGENTA = "\033[38;5;183m"

# ── Mapa de colores por nivel ─────────────────────────────────────────────────
LEVEL_COLORS = {
    logging.DEBUG:    DIM + GREY,
    logging.INFO:     CYAN,
    logging.WARNING:  YELLOW,
    logging.ERROR:    RED,
    logging.CRITICAL: BOLD + RED,
}

LEVEL_ICONS = {
    logging.DEBUG:    "·",
    logging.INFO:     "✓",
    logging.WARNING:  "⚠",
    logging.ERROR:    "✗",
    logging.CRITICAL: "☠",
}

# ── Mapa de módulos a colores (para distinguir visualmente cada sección) ──────
MODULE_COLORS = {
    "pipeline":     "\033[38;5;75m",    # Azul claro
    "dashboard":    "\033[38;5;141m",   # Violeta
    "transactions": "\033[38;5;215m",   # Naranja
    "sync":         "\033[38;5;120m",   # Verde claro
    "investments":  "\033[38;5;222m",   # Amarillo suave
    "sources":      "\033[38;5;153m",   # Celeste
    "variables":    "\033[38;5;210m",   # Salmón
    "supabase":     "\033[38;5;176m",   # Rosa
    "interpolated": "\033[38;5;158m",   # Menta
    "storage":      "\033[38;5;187m",   # Beige
    "budget":       "\033[38;5;173m",   # Durazno
}

def _get_module_color(name: str) -> str:
    """Devuelve el color asignado al módulo según su nombre."""
    for key, color in MODULE_COLORS.items():
        if key in name.lower():
            return color
    return MAGENTA  # Color por defecto para módulos no mapeados


# ── Formatter con color ───────────────────────────────────────────────────────
class ColorFormatter(logging.Formatter):
    """Formatter que añade colores y estructura visual clara."""

    def format(self, record: logging.LogRecord) -> str:
        level_color = LEVEL_COLORS.get(record.levelno, RESET)
        icon        = LEVEL_ICONS.get(record.levelno, " ")
        mod_color   = _get_module_color(record.name)

        # Tiempo
        time_str = self.formatTime(record, "%H:%M:%S")
        time_part = f"{DIM}{time_str}{RESET}"

        # Módulo (ajustado a 20 chars para alineación)
        module_short = record.name.split(".")[-1]          # solo el último segmento
        module_part  = f"{mod_color}{module_short:<20}{RESET}"

        # Nivel (fijo 8 chars)
        level_name = record.levelname
        level_part = f"{level_color}{icon} {level_name:<8}{RESET}"

        # Mensaje
        message = record.getMessage()
        msg_part = f"{level_color}{message}{RESET}"

        # Excepción si existe
        exc_text = ""
        if record.exc_info:
            exc_text = f"\n{DIM}{self.formatException(record.exc_info)}{RESET}"

        return f"{time_part}  {module_part}  {level_part}  {msg_part}{exc_text}"


class PlainFormatter(logging.Formatter):
    """Formatter sin colores (para redirigir a archivos)."""

    def format(self, record: logging.LogRecord) -> str:
        icon = LEVEL_ICONS.get(record.levelno, " ")
        time_str = self.formatTime(record, "%H:%M:%S")
        module_short = record.name.split(".")[-1]
        message = record.getMessage()
        exc_text = ""
        if record.exc_info:
            exc_text = f"\n{self.formatException(record.exc_info)}"
        return f"{time_str}  {module_short:<20}  {icon} {record.levelname:<8}  {message}{exc_text}"


# ── API pública ───────────────────────────────────────────────────────────────

def configure_logging(level: int | None = None) -> None:
    """
    Configura el sistema de logging global del backend.
    Llamar UNA SOLA VEZ en el startup (main.py).

    El nivel se lee de la variable de entorno LOG_LEVEL:
        LOG_LEVEL=DEBUG ./start_contabilidad.sh

    Args:
        level: Nivel de logging (e.g. logging.DEBUG). Si es None, usa LOG_LEVEL o INFO.
    """
    if level is None:
        env_level = os.environ.get("LOG_LEVEL", "INFO").upper()
        level = getattr(logging, env_level, logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Evitar duplicar handlers si se llama más de una vez
    if root_logger.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(ColorFormatter())
    root_logger.addHandler(handler)

    # Silenciar loggers ruidosos de librerías externas
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger('hpack').setLevel(logging.WARNING)
    logging.getLogger('psparser').setLevel(logging.WARNING)
    logging.getLogger('pdfplumber').setLevel(logging.WARNING)

    root_logger.info("Logging configurado — nivel: %s", logging.getLevelName(level))


def get_logger(name: str) -> logging.Logger:
    """
    Obtiene un logger para el módulo dado.
    Usar __name__ como argumento siempre.

    Ejemplo:
        logger = get_logger(__name__)
        logger.info("Pipeline inicializado")
    """
    return logging.getLogger(name)
