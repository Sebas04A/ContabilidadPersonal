const SUPABASE_URL = 'https://rcmdzvbxerumzxvnubfo.supabase.co';
const SUPABASE_ANON_KEY = 'sb_publishable_CZL2FVo5YLTnUPeyAq7S-w_lfExK_yw';
const DEUDOR_ID = 'c3526465-22e4-4ed1-a729-02200cf28b5b'; // Prueba

async function testFunction() {
    console.log(`Testing Edge Function ESTADO CUENTA...`);
    
    try {
        const response = await fetch(`${SUPABASE_URL}/functions/v1/get_estado_cuenta`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${SUPABASE_ANON_KEY}`,
                'apikey': SUPABASE_ANON_KEY
            },
            body: JSON.stringify({ deudor_id: DEUDOR_ID, pov: 'debtor' })
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error('Error Response:', errorText);
            return;
        }

        const data = await response.json();
        console.log(data);
        console.log('\n================================================');
        console.log(`RESUMEN (POV WEB VISOR - DEBTOR)`);
        console.log('================================================');
        console.log(`Deuda Total (Perspectiva): $${data.resumen.total_deuda.toFixed(2)}`);
        console.log(`Monto a cruzar ideal:    $${data.resumen.monto_ideal_a_cruzar.toFixed(2)}`);
        console.log(`Saldo a favor POV:       $${data.resumen.saldo_favor.toFixed(2)}`);
        console.log('------------------------------------------------');

        console.log('\n  DEUDAS PENDIENTES:');
        data.deudas_pendientes.forEach(d => {
            console.log(`    ${d.fecha_gasto.split('T')[0]} | ${d.titulo.padEnd(20)} | Pendiente: $${d.saldo_pendiente.toFixed(2)} | Cruce sugerido: $${d.cruce_sugerido.toFixed(2)} | EsTuDeuda (Para POV): ${d.es_tu_deuda}`);
        });

        console.log('\n================================================\n');

        // Test with owner POV
        console.log(`\nTesting Edge Function ESTADO CUENTA (POV FLUTTER APP - OWNER)...`);
        const responseOwner = await fetch(`${SUPABASE_URL}/functions/v1/get_estado_cuenta`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${SUPABASE_ANON_KEY}`,
                'apikey': SUPABASE_ANON_KEY
            },
            body: JSON.stringify({ deudor_id: DEUDOR_ID, pov: 'owner' })
        });
        const dataOwner = await responseOwner.json();
        console.log(`RESUMEN (POV OWNER)`);
        console.log(`Deuda Total (Perspectiva): $${dataOwner.resumen.total_deuda.toFixed(2)}`);
        console.log(`Monto a cruzar ideal:      $${dataOwner.resumen.monto_ideal_a_cruzar.toFixed(2)}`);
        console.log(`Saldo a favor POV:         $${dataOwner.resumen.saldo_favor.toFixed(2)}`);
    } catch (err) {
        console.error('Fetch error:', err);
    }
}

testFunction();
