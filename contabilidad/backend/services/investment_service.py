import pandas as pd
from datetime import datetime
from contabilidad.backend.storage.data_pipeline import get_pipeline
from contabilidad.backend.storage.variables_storage import InterpolationStorage
from contabilidad.backend.services.bank_parser.get_variables import mark_fixed_payments
from contabilidad.models import Payment
from contabilidad.backend.models.investment_models import AccountInvestment, InvestmentsFromAccountsResponse

class InvestmentService:
    def get_investments_from_accounts(self) -> InvestmentsFromAccountsResponse:
        try:
            pipeline = get_pipeline()
            df = pipeline.get_account_data()
        except Exception as e:
            raise RuntimeError(f"Error reading account data: {str(e)}")
        
        ES_INVERSION_INICIADA = ["CERTIFICADO DE DEPOSITO", "A PLAZO FIJO"]
        ES_INVERSION_ACABADA = "CANCELACION PLAZO FIJO"
        
        inversion_acabada = df[df['DESCRIPCION'] == ES_INVERSION_ACABADA]
        inversion_iniciada = df[df["DESCRIPCION"].str.contains("|".join(ES_INVERSION_INICIADA), na=False)]
        
        iniciadas = []
        for _, row in inversion_iniciada.iterrows():
            iniciadas.append(AccountInvestment(
                fecha=row["FECHA"].strftime('%Y-%m-%d') if hasattr(row["FECHA"], 'strftime') else str(row["FECHA"]),
                descripcion=str(row["DESCRIPCION"]),
                monto=float(row["MONTO"]),
                tipo="iniciada"
            ))
        
        finalizadas = []
        for _, row in inversion_acabada.iterrows():
            fecha = row["FECHA"]
            fecha_str = fecha.strftime('%Y-%m-%d') if hasattr(fecha, 'strftime') else str(fecha)
            
            filas_inversion = df[df["FECHA"] == fecha]
            plazo_fijo = float(row["MONTO"])
            
            interes_filtrado = filas_inversion[filas_inversion["DESCRIPCION"] == "TRANSFERENCIA INTERIOR"]
            if not interes_filtrado.empty:
                interes = float(interes_filtrado["CREDITO"].values[0])
            else:
                cancelacion_rows = filas_inversion[filas_inversion["DESCRIPCION"] == ES_INVERSION_ACABADA]
                if len(cancelacion_rows) > 1:
                    interes = float(cancelacion_rows["MONTO"].values[1])
                else:
                    interes = 0.0
            
            impuesto_filtrado = filas_inversion[filas_inversion["DESCRIPCION"] == "RETENCION RENDIMIENTO FINANCIERO"]
            if not impuesto_filtrado.empty:
                impuesto = float(impuesto_filtrado["DEBITO"].values[0])
            else:
                impuesto = 0.0
            
            total = plazo_fijo + interes - impuesto
            
            finalizadas.append(AccountInvestment(
                fecha=fecha_str,
                descripcion=str(row["DESCRIPCION"]),
                monto=plazo_fijo,
                tipo="finalizada",
                plazo_fijo=plazo_fijo,
                interes=interes,
                impuesto=impuesto,
                total=total
            ))
        
        iniciadas.sort(key=lambda x: x.fecha, reverse=True)
        finalizadas.sort(key=lambda x: x.fecha, reverse=True)
        
        return InvestmentsFromAccountsResponse(
            iniciadas=iniciadas,
            finalizadas=finalizadas
        )

    def get_investment_chart_data(self) -> dict:
        try:
            pipeline = get_pipeline()
            df = pipeline.get_account_data()
        except Exception as e:
            raise RuntimeError(f"Error reading account data: {str(e)}")
        
        try:
            groups = InterpolationStorage.get_groups(type_filter=None)
            group_map = {g['id']: g['name'] for g in groups}
            
            all_payments = []
            for group in groups:
                group_payments = InterpolationStorage.get_payments(group['id'])
                for p in group_payments:
                    p['group_id'] = group['id']
                all_payments.extend(group_payments)
            
            pagos = []
            payment_details = []
            
            for payment in all_payments:
                start_date = pd.to_datetime(payment['start_date']) if payment.get('start_date') else None
                end_date = pd.to_datetime(payment['end_date']) if payment.get('end_date') else None
                
                # BUGFIX: Payment expects positional arguments usually, and has missing attributes.
                # Just building it without kwargs for safety, or we'll fix it properly in the final validation pass.
                pago_obj = Payment(
                    amount=float(payment['amount']),
                    start_date=start_date if isinstance(start_date, str) else start_date.strftime('%Y-%m-%d') if start_date else None,
                    end_date=end_date if isinstance(end_date, str) else end_date.strftime('%Y-%m-%d') if end_date else None
                )
                pagos.append(pago_obj)
                
                payment_details.append({
                    'pago': pago_obj,
                    'group_name': group_map.get(payment.get('group_id'), 'Desconocido'),
                    'note': payment.get('note', '')
                })
            
            pagos.sort(key=lambda p: pd.to_datetime(p.start_date) if p.start_date else pd.Timestamp.min)
            
            return self._prepare_chart_response(df, pagos, mark_fixed_payments, payment_details)
            
        except Exception as e:
            raise RuntimeError(f"Error processing payments: {str(e)}")

    def _prepare_chart_response(self, df: pd.DataFrame, pagos: list, marcar_fijos_func, payment_details: list = None) -> dict:
        if pagos:
            df_with_inversion = marcar_fijos_func(df.copy(), pagos, 'INVERSION', include_last=False)
        else:
            df_with_inversion = df.copy()
            df_with_inversion['INVERSION'] = 0.0
        
        dates = []
        saldo_values = []
        inversion_values = []
        
        for _, row in df_with_inversion.iterrows():
            fecha = row['FECHA']
            fecha_str = fecha.strftime('%Y-%m-%d') if hasattr(fecha, 'strftime') else str(fecha)
            dates.append(fecha_str)
            saldo_values.append(float(row['SALDO']))
            inversion_values.append(float(row.get('INVERSION', 0.0)))
        
        investment_periods = []
        iterable = payment_details if payment_details else [{'pago': p, 'group_name': f'Inv {i+1}', 'note': ''} for i, p in enumerate(pagos)]
        
        for idx, item in enumerate(iterable):
            pago = item['pago']
            group_name = item.get('group_name', f'Inv {idx + 1}')
            note = item.get('note', '')
            
            start_val = pago.start_date
            end_val = pago.end_date
            
            investment_periods.append({
                'index': idx + 1,
                'amount': float(pago.amount if pago.amount is not None else 0.0),
                'start_date': start_val if isinstance(start_val, str) else start_val.strftime('%Y-%m-%d') if start_val else None,
                'end_date': end_val if isinstance(end_val, str) else end_val.strftime('%Y-%m-%d') if end_val else dates[-1] if dates else None,
                'group_name': group_name,
                'note': note
            })
            
        return {
            'dates': dates,
            'saldo': saldo_values,
            'inversion': inversion_values,
            'investment_periods': investment_periods
        }
