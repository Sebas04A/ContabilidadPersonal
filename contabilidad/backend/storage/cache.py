import pandas as pd
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

class DataCache:
    """
    Caché en memoria con TTL (Time To Live) y detección de cambios en archivos.
    """
    
    def __init__(self, ttl_seconds: int = 300):  # 5 minutos por defecto
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl_seconds = ttl_seconds
    
    def _get_file_hash(self, file_path: str) -> str:
        """Genera hash del archivo para detectar cambios."""
        if not os.path.exists(file_path):
            return ""
        
        # Usar timestamp de modificación + tamaño como hash rápido
        stat = os.stat(file_path)
        return f"{stat.st_mtime}_{stat.st_size}"
    
    def get(self, key: str, file_path: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        Obtiene datos del caché si están vigentes.
        """
        if key not in self.cache:
            return None
        
        entry = self.cache[key]
        
        # Verificar TTL
        if datetime.now() > entry['expires_at']:
            del self.cache[key]
            return None
        
        # Verificar si el archivo cambió
        if file_path:
            current_hash = self._get_file_hash(file_path)
            if current_hash != entry.get('file_hash', ''):
                del self.cache[key]
                return None
        
        return entry['data'].copy()  # Retornar copia para evitar mutaciones
    
    def set(self, key: str, data: pd.DataFrame, file_path: Optional[str] = None):
        """
        Guarda datos en caché.
        """
        self.cache[key] = {
            'data': data.copy(),
            'cached_at': datetime.now(),
            'expires_at': datetime.now() + timedelta(seconds=self.ttl_seconds),
            'file_hash': self._get_file_hash(file_path) if file_path else None
        }
    
    def invalidate(self, key: Optional[str] = None):
        """
        Invalida caché.
        """
        if key:
            self.cache.pop(key, None)
        else:
            self.cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estadísticas del caché."""
        return {
            'entries': len(self.cache),
            'keys': list(self.cache.keys()),
            'total_memory_mb': sum(
                entry['data'].memory_usage(deep=True).sum() / 1024 / 1024
                for entry in self.cache.values()
            )
        }
