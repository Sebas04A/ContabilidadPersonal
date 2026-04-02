import pandas as pd
from contabilidad.backend.logger import get_logger

logger = get_logger(__name__)

def transform_investments(df: pd.DataFrame) -> pd.DataFrame:
    try:
        from contabilidad.backend.storage.variables_storage import InterpolationStorage
        from contabilidad.backend.services.bank_parser.get_variables import mark_fixed_payments
        from contabilidad.models import Payment
        
        groups = InterpolationStorage.get_groups(type_filter=None)
        all_payments = []
        for group in groups:
            group_payments = InterpolationStorage.get_payments(group['id'])
            all_payments.extend(group_payments)
        
        pagos = []
        for payment in all_payments:
            start_date = pd.to_datetime(payment['start_date']) if payment['start_date'] else None
            end_date = pd.to_datetime(payment['end_date']) if payment['end_date'] else None
            
            pago_obj = Payment(
                amount=float(payment['amount']),
                start_date=start_date,
                end_date=end_date
            )
            pagos.append(pago_obj)
        
        if pagos:
            df = mark_fixed_payments(df, pagos, 'INVERSION', include_last=False)
        else:
            df['INVERSION'] = 0.0
            
        return df
    except Exception as e:
        logger.warning("Error en transform_investments: %s", e)
        if 'INVERSION' not in df.columns:
            df['INVERSION'] = 0.0
        return df
