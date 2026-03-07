import pandas as pd

m = pd.read_csv('data/etiquetado/gastos_maestros.csv')
b = pd.read_excel('data/procesada/banca/banca_unida.xlsx')
t = pd.read_excel('data/procesada/tarjeta/tarjeta_unida.xlsx')
m['FECHA'] = pd.to_datetime(m['FECHA'])
b['FECHA'] = pd.to_datetime(b['FECHA'])
t['FECHA'] = pd.to_datetime(t['FECHA'])

results = []
results.append('Maestros: {} to {}'.format(m['FECHA'].min().date(), m['FECHA'].max().date()))
results.append('Banca: {} to {}'.format(b['FECHA'].min().date(), b['FECHA'].max().date()))
results.append('Tarjeta: {} to {}'.format(t['FECHA'].min().date(), t['FECHA'].max().date()))

in_range = m[m['FECHA'] >= b['FECHA'].min()]
results.append('Maestros in banca range: {} of {}'.format(len(in_range), len(m)))

out_range = m[m['FECHA'] < b['FECHA'].min()]
results.append('Maestros BEFORE banca range: {}'.format(len(out_range)))

results.append('TIPO values: {}'.format(m['TIPO'].unique().tolist()))

# Check if maestros has only CUENTA type (no TARJETA)
tipo_counts = m['TIPO'].value_counts().to_dict()
results.append('TIPO counts: {}'.format(tipo_counts))

with open('scripts/check.txt', 'w') as f:
    f.write('\n'.join(results))

print('DONE')
