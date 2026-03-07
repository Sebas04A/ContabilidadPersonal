const SUPABASE_URL = 'https://rcmdzvbxerumzxvnubfo.supabase.co';
const SUPABASE_ANON_KEY = 'sb_publishable_CZL2FVo5YLTnUPeyAq7S-w_lfExK_yw';
const DEUDOR_ID = 'c3526465-22e4-4ed1-a729-02200cf28b5b'; // Madre

async function testFunction() {
    console.log(`Testing Edge Function for Deudor ID: ${DEUDOR_ID}...`);
    
    try {
        const response = await fetch(`${SUPABASE_URL}/functions/v1/get_historial`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${SUPABASE_ANON_KEY}`,
                'apikey': SUPABASE_ANON_KEY
            },
            body: JSON.stringify({ deudor_id: DEUDOR_ID, pov: 'owner' })
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error('Error Response:', errorText);
            return;
        }

        const data = await response.json();
        console.log('\n================================================');
        console.log(`HISTORIAL COMPLETO - Grupos: ${data.length}`);
        console.log('================================================');
        // console.log(data[0].pagos)
        
        data.forEach((group, i) => {
            console.log(`\n--- GRUPO #${i + 1} ---`);
            console.log(`Saldo Anterior:  $${group.saldoAnterior.toFixed(2)}`);
            console.log(`Deudas del Grupo: $${group.totalDeudas.toFixed(2)}`);
            console.log(`Pagos del Grupo:  $${group.totalPagos.toFixed(2)}`);
            console.log(`Saldo Posterior: $${group.saldoPosterior.toFixed(2)}`);
            console.log('------------------------------------------------');

            console.log('  PAGOS:');
            if (group.pagos.length === 0) console.log('    (Sin pagos)');
            group.pagos.forEach(p => {
                const cruceStr = p.linkedCruceAmount ? ` [Cruce: $${p.linkedCruceAmount}]` : '';
                console.log(`    [${p.type.toUpperCase()}] ${p.date.split('T')[0]} | ${p.title.padEnd(25)} | $${p.amount.toFixed(2)}${cruceStr}`);
            });

            console.log('  DEUDAS:');
            if (group.deudas.length === 0) console.log('    (Sin deudas con abonos)');
            group.deudas.forEach(d => {
                const parcial = d.montoPagado < d.amount ? ` (Abonado: $${d.montoPagado})` : ' (Pagada)';
                console.log(`    [DEUDA] ${d.date.split('T')[0]} | ${d.title.padEnd(25)} | $${d.amount.toFixed(2)}${parcial} | Saldo: $${d.balance.toFixed(2)}`);
            });
        });
        console.log('\n================================================\n');
    } catch (err) {
        console.error('Fetch error:', err);
    }
}

testFunction();
