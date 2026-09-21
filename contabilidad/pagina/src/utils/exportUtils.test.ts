import { describe, it, expect } from 'vitest';
import {
  prepareTransactionsForExport,
  calculateExportSummary,
  generateExportData,
  ExportOptions,
} from './exportUtils';
import { Transaction } from '../services/api';

const mockTransactions: Transaction[] = [
  {
    id: 'tx-1',
    FECHA: '2026-05-10',
    HORA: '14:30',
    TIPO: 'BANCA',
    DESCRIPCION: 'PAGO SUELDO EMPRESA XYZ',
    nombre_limpio: 'Sueldo Mayo',
    categoria: 'Sueldo',
    tags: 'ingreso, nomina',
    MONTO: 3500.5,
    prioridad: 'Needs',
    es_fijo: true,
    pertenece_a: 'sebas',
    es_reembolsable: false,
    deudor: '',
    felicidad: 5,
    revisado: true,
    nota: 'Depósito puntual',
    split_group_id: '',
  },
  {
    id: 'tx-2',
    FECHA: '2026-05-11',
    HORA: '19:15',
    TIPO: 'TARJETA',
    DESCRIPCION: 'SUPERMERCADO JUMBO',
    nombre_limpio: 'Jumbo',
    categoria: 'Alimentación',
    tags: 'mercado',
    MONTO: -120.0,
    prioridad: 'Needs',
    es_fijo: false,
    pertenece_a: 'sebas',
    es_reembolsable: false,
    deudor: '',
    felicidad: 4,
    revisado: false,
    nota: '',
    split_group_id: '',
  },
  {
    id: 'tx-split',
    FECHA: '2026-05-12',
    HORA: '20:00',
    TIPO: 'TARJETA',
    DESCRIPCION: 'CENA CON AMIGOS RESTAURANTE',
    nombre_limpio: 'Restaurante Don Julio',
    categoria: 'Ocio',
    tags: 'salida',
    MONTO: -200.0,
    prioridad: 'Wants',
    es_fijo: false,
    pertenece_a: 'sebas',
    es_reembolsable: true,
    deudor: 'Carlos',
    felicidad: 5,
    revisado: true,
    nota: 'Total cuenta',
    split_group_id: 'grp-1',
    subTransactions: [
      {
        id: 'sub-1',
        FECHA: '2026-05-12',
        HORA: '20:00',
        TIPO: 'TARJETA',
        DESCRIPCION: 'CENA CON AMIGOS RESTAURANTE',
        nombre_limpio: 'Restaurante Don Julio - Mi parte',
        categoria: 'Alimentación',
        tags: 'cena',
        MONTO: -80.0,
        prioridad: 'Wants',
        es_fijo: false,
        pertenece_a: 'sebas',
        es_reembolsable: false,
        deudor: '',
        felicidad: 5,
        revisado: true,
        nota: 'Lo que yo comí',
        split_group_id: 'grp-1',
      },
      {
        id: 'sub-2',
        FECHA: '2026-05-12',
        HORA: '20:00',
        TIPO: 'TARJETA',
        DESCRIPCION: 'CENA CON AMIGOS RESTAURANTE',
        nombre_limpio: 'Restaurante Don Julio - Parte Carlos',
        categoria: 'Deudas',
        tags: 'amigos',
        MONTO: -120.0,
        prioridad: 'Wants',
        es_fijo: false,
        pertenece_a: 'sebas',
        es_reembolsable: true,
        deudor: 'Carlos',
        felicidad: 5,
        revisado: true,
        nota: 'Carlos me devuelve luego',
        split_group_id: 'grp-1',
      },
    ],
  },
];

describe('exportUtils', () => {
  it('prepareTransactionsForExport desglosa splits cuando flattenSplits es true', () => {
    const flattened = prepareTransactionsForExport(mockTransactions, true);
    expect(flattened.length).toBe(4); // 1 + 1 + 2 subtransacciones
    expect(flattened[2].nombre_limpio).toBe('Restaurante Don Julio - Mi parte');
    expect(flattened[2].MONTO).toBe(-80.0);
    expect(flattened[3].nombre_limpio).toBe('Restaurante Don Julio - Parte Carlos');
    expect(flattened[3].MONTO).toBe(-120.0);
  });

  it('prepareTransactionsForExport mantiene padre cuando flattenSplits es false', () => {
    const unflattened = prepareTransactionsForExport(mockTransactions, false);
    expect(unflattened.length).toBe(3);
    expect(unflattened[2].MONTO).toBe(-200.0);
  });

  it('calculateExportSummary calcula totales correctamente', () => {
    const summary = calculateExportSummary(mockTransactions);
    expect(summary.count).toBe(3);
    expect(summary.income).toBe(3500.5);
    expect(summary.expenses).toBe(-320.0);
    expect(summary.net).toBe(3180.5);
  });

  it('genera formato Excel (TSV con HTML)', () => {
    const options: ExportOptions = {
      format: 'excel',
      selectedColumnIds: ['fecha', 'concepto', 'categoria', 'monto'],
      flattenSplits: false,
      includeHeaders: true,
      includeSummary: true,
      numberFormat: 'raw',
    };
    const res = generateExportData(mockTransactions, options, {});
    expect(res.mimeType).toBe('text/tab-separated-values');
    expect(res.filename).toContain('.tsv');
    expect(res.text).toContain('Fecha\tConcepto\tCategoría\tMonto');
    expect(res.text).toContain('2026-05-10\tPAGO SUELDO EMPRESA XYZ\tSueldo\t3500.5');
    expect(res.html).toBeDefined();
    expect(res.html).toContain('<table');
    expect(res.html).toContain('PAGO SUELDO EMPRESA XYZ');
  });

  it('genera formato CSV con comas y comillas de escape', () => {
    const options: ExportOptions = {
      format: 'csv_comma',
      selectedColumnIds: ['fecha', 'nombre_limpio', 'tags', 'monto'],
      flattenSplits: false,
      includeHeaders: true,
      includeSummary: false,
      numberFormat: 'raw',
    };
    const res = generateExportData(mockTransactions, options, {});
    expect(res.mimeType).toContain('text/csv');
    expect(res.filename).toContain('.csv');
    // BOM UTF-8 present
    expect(res.text.charCodeAt(0)).toBe(0xfeff);
    // Tags contains comma, so must be quoted: "ingreso, nomina"
    expect(res.text).toContain('"ingreso, nomina"');
  });

  it('genera formato CSV con punto y coma', () => {
    const options: ExportOptions = {
      format: 'csv_semicolon',
      selectedColumnIds: ['fecha', 'nombre_limpio', 'monto'],
      flattenSplits: false,
      includeHeaders: true,
      includeSummary: false,
      numberFormat: 'raw',
    };
    const res = generateExportData(mockTransactions, options, {});
    expect(res.text).toContain('Fecha;Nombre Limpio / Comercio;Monto');
    expect(res.text).toContain('2026-05-10;Sueldo Mayo;3500.5');
  });

  it('genera formato Markdown', () => {
    const options: ExportOptions = {
      format: 'markdown',
      selectedColumnIds: ['fecha', 'nombre_limpio', 'monto'],
      flattenSplits: false,
      includeHeaders: true,
      includeSummary: true,
      numberFormat: 'raw',
    };
    const res = generateExportData(mockTransactions, options, {});
    expect(res.mimeType).toBe('text/markdown');
    expect(res.filename).toContain('.md');
    expect(res.text).toContain('| Fecha | Nombre Limpio / Comercio | Monto |');
    expect(res.text).toContain('| 2026-05-10 | Sueldo Mayo | 3500.5 |');
    expect(res.text).toContain('> **Resumen**: 3 transacciones');
  });

  it('genera lista de texto legible', () => {
    const options: ExportOptions = {
      format: 'text_list',
      selectedColumnIds: ['fecha', 'nombre_limpio', 'monto'],
      flattenSplits: false,
      includeHeaders: false,
      includeSummary: true,
      numberFormat: 'formatted',
    };
    const res = generateExportData(mockTransactions, options, {});
    expect(res.mimeType).toBe('text/plain');
    expect(res.filename).toContain('.txt');
    expect(res.text).toContain('• 2026-05-10 | Sueldo Mayo: $3,500.50 [Sueldo] (ingreso, nomina) // Depósito puntual');
    expect(res.text).toContain('=== RESUMEN');
  });

  it('genera JSON válido', () => {
    const options: ExportOptions = {
      format: 'json',
      selectedColumnIds: ['fecha', 'nombre_limpio', 'monto'],
      flattenSplits: false,
      includeHeaders: false,
      includeSummary: true,
      numberFormat: 'raw',
    };
    const res = generateExportData(mockTransactions, options, {});
    expect(res.mimeType).toBe('application/json');
    expect(res.filename).toContain('.json');
    const parsed = JSON.parse(res.text);
    expect(parsed.resumen.count).toBe(3);
    expect(parsed.transacciones.length).toBe(3);
    expect(parsed.transacciones[0].nombre_limpio).toBe('Sueldo Mayo');
  });
});
