/**
 * Las categorías de gasto, en un solo sitio.
 *
 * La misma lista estaba escrita a mano en EditModal, MonthlyBudget,
 * DashboardFilterBar y ExplorerExclusionsModal. Lo nuevo usa esta; los cuatro
 * sitios viejos siguen con su copia hasta que alguien los migre a propósito.
 */
export const CATEGORIAS = [
  'Alimentación', 'Transporte', 'Ocio', 'Salud', 'Subscripciones', 'Mensual',
  'Inversion', 'Regalo', 'Mujeres', 'Aseo', 'Deudas', 'Tarjeta', 'Ropa',
  'Viajes', 'Otro',
];

/** Con el hueco al principio, para un select donde "sin categoría" es una opción. */
export const CATEGORIAS_CON_VACIO = ['---', ...CATEGORIAS];
