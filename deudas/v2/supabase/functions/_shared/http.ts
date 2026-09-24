// Respuestas HTTP comunes a las edge functions de deudas.

export const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

export function responder(cuerpo: unknown, status = 200): Response {
    return new Response(JSON.stringify(cuerpo), {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        status,
    })
}
