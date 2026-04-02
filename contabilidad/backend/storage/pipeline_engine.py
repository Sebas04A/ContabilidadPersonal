import pandas as pd
import hashlib
import json
from typing import Optional, Callable, List, Dict, Any
from contabilidad.backend.logger import get_logger
from contabilidad.backend.storage.cache import DataCache

logger = get_logger(__name__)

class TransformationPipeline:
    """
    Pipeline de transformaciones que se aplican secuencialmente a un DataFrame.
    Cada transformación puede tener caché individual.
    """
    
    def __init__(self, name: str = "default"):
        self.name = name
        self.transformations: List[Dict[str, Any]] = []
        self.cache = DataCache(ttl_seconds=600)  # 10 minutos para transformaciones
    
    def add_transformation(
        self, 
        name: str, 
        func: Callable[[pd.DataFrame], pd.DataFrame],
        cacheable: bool = True,
        dependencies: Optional[List[str]] = None
    ):
        """
        Agrega una transformación al pipeline.
        """
        self.transformations.append({
            'name': name,
            'func': func,
            'cacheable': cacheable,
            'dependencies': dependencies or []
        })
    
    def _get_transformation_hash(self, df: pd.DataFrame, transform_name: str) -> str:
        """Genera hash único para el estado del DataFrame + transformación."""
        # Usar shape + primeras/últimas filas como fingerprint
        fingerprint = {
            'shape': tuple(int(x) for x in df.shape),
            'columns': list(df.columns),
            'first_hash': str(pd.util.hash_pandas_object(df.head(5)).sum()),
            'last_hash': str(pd.util.hash_pandas_object(df.tail(5)).sum()),
            'transform': transform_name
        }
        return hashlib.md5(json.dumps(fingerprint, sort_keys=True).encode()).hexdigest()
    
    def _resolve_dependencies(self, run_only: List[str]) -> set:
        """Resuelve recursivamente las dependencias para una lista de transformaciones."""
        to_run = set(run_only)
        
        # Diccionario para rápido acceso a las dependencias registradas
        deps_map = {t['name']: t['dependencies'] for t in self.transformations}
        
        # Bucle para encontrar dependencias de dependencias recursivamente
        added_new = True
        while added_new:
            added_new = False
            current_to_run = list(to_run)
            for transform_name in current_to_run:
                deps = deps_map.get(transform_name, [])
                for dep in deps:
                    if dep not in to_run:
                        to_run.add(dep)
                        added_new = True
        
        return to_run
    
    def execute(
        self, 
        df: pd.DataFrame, 
        skip_cache: bool = False,
        run_only: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Ejecuta el pipeline completo o solo las transformaciones especificadas en run_only.
        Resuelve automáticamente las dependencias antes de ejecutar.
        """
        result = df.copy()
        
        # Resolver qué transformaciones se van a correr al final (incluyendo deps)
        resolved_run_only = None
        if run_only is not None:
            resolved_run_only = self._resolve_dependencies(run_only)
        
        for transform in self.transformations:
            transform_name = transform['name']
            
            # Saltar si se especificó run_only y esta transformación no está en la lista resuelta
            if resolved_run_only is not None and transform_name not in resolved_run_only:
                logger.debug("Skipping transform: %s (not in resolved run_only)", transform_name)
                continue
            
            # Generar key de caché única para esta transformación + estado del df
            cache_key = f"{self.name}_{transform_name}_{self._get_transformation_hash(result, transform_name)}"
            
            # Intentar obtener del caché
            if transform['cacheable'] and not skip_cache:
                cached_result = self.cache.get(cache_key)
                if cached_result is not None:
                    logger.debug("Cache hit: %s", transform_name)
                    result = cached_result
                    continue
            
            # Ejecutar transformación
            logger.debug("Executing transform: %s", transform_name)
            result = transform['func'](result)
            
            # Cachear resultado
            if transform['cacheable']:
                self.cache.set(cache_key, result)
        
        return result
    
    def invalidate_from(self, transformation_name: str):
        """Invalida caché desde una transformación en adelante."""
        # Encontrar índice de la transformación
        idx = next(
            (i for i, t in enumerate(self.transformations) if t['name'] == transformation_name),
            None
        )
        
        if idx is not None:
            # Invalidar todas las transformaciones desde ese punto
            for transform in self.transformations[idx:]:
                # Invalidar todas las entradas que contengan el nombre de la transformación
                keys_to_invalidate = [
                    key for key in self.cache.cache.keys() 
                    if transform['name'] in key
                ]
                for key in keys_to_invalidate:
                    self.cache.invalidate(key)
    
    def clear_cache(self):
        """Limpia todo el caché del pipeline."""
        self.cache.invalidate()
