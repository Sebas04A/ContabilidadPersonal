import { useEffect, useRef } from 'react';
import * as echarts from 'echarts';

/**
 * Ciclo de vida de un gráfico de ECharts montado a mano: lo crea una vez sobre `ref`,
 * lo ajusta cuando cambia el tamaño de su contenedor (no solo de la ventana) y lo
 * libera al desmontar. `chart.current` ya existe en los efectos que el componente
 * declare después de llamar al hook.
 */
export function useEChart() {
  const ref = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const instancia = echarts.init(ref.current);
    chart.current = instancia;
    const observer = new ResizeObserver(() => instancia.resize());
    observer.observe(ref.current);
    return () => {
      observer.disconnect();
      instancia.dispose();
      chart.current = null;
    };
  }, []);

  return { ref, chart };
}
