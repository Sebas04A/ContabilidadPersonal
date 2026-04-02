# Resumen Funcional del Proyecto: Sistema Integral de Contabilidad Personal

## 1. Visión General
Este proyecto consiste en un ecosistema de software diseñado para otorgar un control absoluto, detallado y analítico sobre las finanzas personales. A diferencia de las aplicaciones comerciales estándar que ofrecen resúmenes limitados o requieren carga manual tediosa, este sistema está construido para procesar los movimientos financieros reales del usuario de forma masiva, consolidando información de múltiples fuentes (cuentas bancarias, tarjetas de crédito, deudas e inversiones) en una única plataforma de inteligencia financiera.

El objetivo central es convertir los datos crudos e incomprensibles de los bancos en información estructurada que permita evaluar el comportamiento financiero, la capacidad de ahorro y el patrimonio real de una persona.

---

## 2. ¿Qué HACE el sistema? (Casos de Uso Principales)
El sistema cubre varias áreas críticas de la economía personal:

*   **Interpretación y Unificación de Estados de Cuenta:** El sistema cuenta con "lectores" que toman los estados de cuenta bancarios y los resúmenes de las tarjetas de crédito (usualmente planillas complejas que otorga el banco) y los convierte en un solo flujo de dinero lógico, alineando los gastos de la tarjeta con el dinero real disponible.
*   **Etiquetado Automatizado e Inteligente:** Cada movimiento puede ser clasificado al detalle (ej. categoría, prioridad, etiquetas extra y hasta un "índice de felicidad" de compra). Para evitar un trabajo manual constante, el sistema aprende de clasificaciones anteriores y clasifica automáticamente gastos futuros similares (ej: si detecta "NETFLIX", sabe etiquetarlo como "Suscripciones").
*   **Cuadros de Mando (Dashboards) Duales:** La interfaz visual ofrece dos perspectivas analíticas mayores: un visor de *Evolución* (para auditar el crecimiento del patrimonio neto a largo plazo) y un visor de *Variaciones Diarias* (diseñado para auditar la volatilidad del flujo de caja y aislar picos de gasto de un día específico). Además, cuenta con un módulo de análisis exclusivo para comprender el endeudamiento rotativo de **Tarjetas de Crédito**.
*   **Ciclo de Vida de Inversiones:** A diferencia de un simple registro, el sistema modela el ciclo completo de un activo. Separa inversiones "Iniciadas" de "Finalizadas", calculando matemáticamente el interés real ganado, deduciendo cargas impositivas (impuestos) y graficando la eficiencia del capital inmovilizado en el tiempo.
*   **Gestión de Presupuestos por Etiquetas (Micro-presupuestos):** Superando las limitaciones de los presupuestos estrictamente categóricos, el sistema permite definir y monitorear límites de gasto sobre *etiquetas transversales personalizadas* (ej. presupuestar un "Viaje a Europa" o "Remodelación"), evaluando constantemente su grado de ejecución.
*   **Auditoría de Salud Financiera (Regla 50/30/20):** Mide automáticamente el porcentaje exacto de los ingresos que están consumiendo los gastos esenciales (Necesidades) frente a los no esenciales (Deseos). Advierte si se rompen los límites de riesgo recomendados (ej. necesidades > 50% del ingreso, o deseos > 30%), e identifica los lujos impulsivos que más capital drena.
*   **Módulo de Analíticas Avanzadas (Insights Tesis):** Un set de herramientas analíticas predictivas orientadas a la evaluación futura y el impacto del comportamiento financiero:
    * **Simulador de Día de Libertad (Survival Rate):** Analiza el capital acumulado líquido y el gasto mensual promedio para calcular exactamente cuántos "días de vida financiera" tiene el usuario si sus ingresos se detuvieran hoy.
    * **Punto de Equilibrio de Supervivencia:** Calcula el "Burn Rate" o ingreso mínimo vital requerido para cubrir únicamente los elementos esenciales, definiendo la línea roja de supervivencia mes a mes.
    * **Auditor de "Lifestyle Creep":** Detecta automáticamente la inflación del estilo de vida, cruzando la tasa de crecimiento de los ingresos contra el crecimiento de los gastos en "Deseos". Emite alertas si el aumento de sueldo se está traduciendo en lujos en lugar de ahorro, mostrando el capital perdido a largo plazo.
    * **Optimizador de ROI Emocional y Costo de Oportunidad:** Añade una dimensión psicológica (1-10 de felicidad) a los gastos. El sistema aísla los gastos "ineficientes" (alto costo, baja felicidad) y proyecta con interés compuesto el asombroso costo de oportunidad de ese dinero drenado a 10, 20 o 30 años.
    * **Mapa de Eficiencia por Categorías:** Un gráfico de dispersión que ubica todas las categorías del usuario en un mapa cartesiano, cruzando el "gasto mensual" versus el "ROI emocional", permitiendo identificar de un vistazo las fugas de capital altamente insatisfactorias frente a aquellas que brindan máxima calidad de vida.
    * **Optimizador Fiscal (SRI Ecuador):** Un simulador en tiempo real que modela las normativas tributarias vigentes (ej. Rebaja de Impuesto a la Renta basada en cargas familiares y la Canasta Familiar Básica), proyectando cuánto dinero puede deducir o recuperar de su pago anual de impuestos.
*   **Análisis Comparativo Aislado:** Funcionalidad avanzada que le otorga al usuario el poder de seleccionar a conveniencia múltiples categorías (o etiquetas) para visualizarlas en aislamiento estadístico, descubriendo ineficiencias y fugas de capital de forma comparativa sin el ruido del presupuesto total mensual.
*   **Asistente de Pagos y Conciliación:** Incluye un motor para detectar y vincular pagos cruzados automáticamente (por ejemplo, cuando un ingreso a la cuenta es en realidad la devolución de un préstamo, o el pago de una tarjeta) asegurando que el flujo neto (ingreso - gasto) se mantenga exacto sin duplicar la contabilidad.
*   **Agrupación y División de Transacciones (Splitting):** Ofrece herramientas contables detalladas para consolidar facturas pequeñas en "Grupos" o tomar un consumo grande (ej. la cuenta de un gran restaurante) y dividirlo matemáticamente en partes si diferentes porciones corresponden a distintas personas o categorías, vinculándolo directamente con el sistema de deudas.
*   **Ecosistema Social de Deudas ("Quién me debe y a quién le debo"):** Cuenta con un módulo independiente diseñado para los préstamos informales entre familiares o amigos. 
    * Posee lógica financiera avanzada, como la "compensación cruzada": si Juan le debe $50 a Pedro, y Pedro le debe $30 a Juan, el sistema deduce y ajusta automáticamente que Juan solo debe $20, "matando" la diferencia sin mover dinero real.
    * Genera un visor web transparente para que las personas que le deben dinero al usuario puedan consultar su propio estado de cuenta por internet sin tener que preguntar.

---

## 3. ¿Qué NO hace el sistema? (Límites del Proyecto)
Es fundamental definir los límites del software para mantener su alcance acotado y seguro:

*   **No se conecta a los bancos (Sin Open Banking):** Por cuestiones estrictas de seguridad de la información y privacidad, el sistema no solicita credenciales bancarias, ni extrae datos directamente de internet desde los bancos. Funciona procesando los archivos que el propio usuario descarga y le entrega al sistema de forma local.
*   **No mueve dinero real:** Es una herramienta analítica (de diagnóstico) y no transaccional. No tiene capacidad para aprobar pagos, hacer transferencias ni descontar fondos reales; su única responsabilidad es calcular e informar.
*   **No es un sofware contable-corporativo:** No gestiona facturación, ni calcula cargas impositivas, ni gestiona inventarios. Está minuciosamente optimizado para el control del bolsillo del ciudadano común y cómo gasta su salario.

---

## 4. ¿Cómo lo hace? (El Flujo de Uso Diario)
Sin entrar en detalles de código o servidores, la dinámica de uso es la siguiente:

1.  **Recolección de Información:** A finalizar la semana o el mes, el usuario ingresa a sus portales bancarios y descarga sus movimientos en los archivos provistos por el banco.
2.  **Carga al Sistema:** El usuario simplemente "suelta" esos archivos en el sistema. Éste se encarga de leerlos, limpiarlos de ruido (cabeceras inútiles, formatos extraños) y fusiona la tarjeta de crédito con el dinero de la caja de ahorro.
3.  **Auditoría y Corrección:** El usuario abre la plataforma web desde su computadora. Ve listados todos sus movimientos; el sistema ya habrá adivinado la categoría de casi todo con su función de auto-aprendizaje. El usuario únicamente valida o ajusta lo que sea nuevo.
4.  **Decisiones Presupuestarias:** Una vez validado, los gráficos se actualizan. El usuario revisa en un panel de control si gastó más de lo presupuestado en un rubro específico y cómo impactó ese consumo en su saldo general histórico.
5.  **Gestión Social Móvil:** De forma paralela, desde su propio teléfono móvil, el usuario puede registrar durante el día en una app si le pagó el almuerzo a un colega (generando una deuda a favor). El sistema sincroniza esa deuda y el colega puede luego ver su balance actualizado desde su propio celular a través de un link.

---

## 5. Justificación como Tema de Tesis Universitaria
Este proyecto posee la escala y complejidad ideal para presentarse como tesis o proyecto final universitario, debido a que demuestra competencias integrales en Ingeniería de Software:

*   **Solución a un Problema Cotidiano Real:** Ofrece un valor funcional inmediato para un problema común, combinando áreas de las Finanzas Personales con la Informática.
*   **Procesamiento de Datos Complejos:** Incluye rutinas de Extracción, Transformación y Carga (ETL) para leer, interpretar y normalizar planillas financieras sucias y dispares.
*   **Implementación de Analítica Predictiva y Ciencia de Datos:** Eleva el proyecto más allá de un simple registro contable al incorporar modelos matemáticos y predictivos (como el cálculo del "Survival Rate", la evaluación del costo de oportunidad con interés compuesto, y la detección algorítmica de "Lifestyle Creep"). Integrando visualizaciones complejas y multidimensionales en variables no convencionales (como la correlación Precio vs Felicidad).
*   **Reglas de Negocio Robustas:** Implementación de lógica matemática no trivial: manejo de fechas y periodos de corte de tarjetas de crédito, interpolación de variables diarias, y cálculos de balances financieros con "compensación de deudas" en redes de personas (así como simulaciones fiscales bajo normativas SRI del Ecuador).
*   **Arquitectura de Sistemas Distribuidos:** El ecosistema no es una simple pieza monolítica. Está estructurado como una solución completa que abarca un motor procesador de datos (Backend), una aplicación visual analítica (Web Frontend) y una aplicación móvil persistente, todos sincronizándose e interactuando entre sí para ofrecer un servicio continuo al usuario.
