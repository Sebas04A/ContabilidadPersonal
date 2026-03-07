# Clase de configuración para la limpieza de datos
from dataclasses import dataclass,field
import os

@dataclass
class FileProcessingConfig:
    # 🔸 Obligatorios
    path: str = None

    # 🔹 Opcionales con valores por defecto
    fecha_col: str = "Fecha"
    saldo_col: str = "Saldo"
    descripcion_col: str = "Concepto"
    fecha_format: str = "%Y-%m-%d, %I:%M %p"
    tiene_monto: bool = True
    descripcion_a_eliminar: list = field(default_factory=lambda: [])
    print("PATH ACTUAL:", os.getcwd())

    def __post_init__(self):
        # Validar que el path existe y es un archivo válido
        if self.path is not None:
            if not isinstance(self.path, str):
                raise TypeError("El 'path' debe ser una cadena o None.")
            if not os.path.exists(self.path):
                raise FileNotFoundError(f"Archivo no encontrado: {self.path}")
            if not self.path.endswith(('.csv', '.xlsx')):
                raise ValueError("El 'path' debe tener extensión .csv o .xlsx.")
            
        
        # Validar que los nombres de columna sean cadenas no vacías
        for field_name in ['fecha_col', 'saldo_col', 'descripcion_col']:
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"'{field_name}' debe ser una cadena no vacía.")
        
        # Validar formato de fecha
        if not isinstance(self.fecha_format, str) or not "%" in self.fecha_format:
            raise ValueError("El formato de fecha debe ser una cadena válida como '%d/%m/%Y'.")