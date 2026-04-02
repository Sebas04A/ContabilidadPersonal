from contabilidad.models import Payment
import pandas as pd
from contabilidad.backend.logger import get_logger

logger = get_logger(__name__)

# pagos_tarjetas_cancelado = ["2025-04-28","2024-08-23","2024-09-23"]
MANDATORY_PAYMENT_DESC = "PAGO TARJETA" #Los que tienen esta descripcion son pagos obligatorios de 20 dolares en general. El minimo
CORRECTION_NOT_MANDATORY="PAGO TARJETA DE CREDITO"

INTERBANK_PAYMENT_DESC = "INTERBANCARIA" #Pagos a otras tarjetas
MASTERCARD_PAYMENT_DESC = "MASTE" #Pagos que nos aseguramos que sea mastercard
MY_CARD_NUMBER_DESC = "223067" #Numero de mi tarjeta principal

#EJEMPLO NUEVO
# PAGO TARJETA DE CREDITO MASTERCARD BANCO PICHINCHA  22306700007562


def get_credit_card_payments(df, canceled_payments=[]):
    df=df.copy()
    is_canceled_payment = df["FECHA"].astype(str).isin(canceled_payments)
    is_mandatory_payment = df['DESCRIPCION'].str.contains(MANDATORY_PAYMENT_DESC, na=False) & ~df['DESCRIPCION'].str.contains(CORRECTION_NOT_MANDATORY, na=False)
    is_not_discover = ~df['DESCRIPCION'].str.contains(INTERBANK_PAYMENT_DESC, na=False)

    # pago_obligatorio = df[is_mandatory_payment& is_not_discover]
    is_mastercard_payment = df['DESCRIPCION'].str.contains(MASTERCARD_PAYMENT_DESC, na=False) & ~is_canceled_payment
    is_my_card = df['DESCRIPCION'].str.contains(MY_CARD_NUMBER_DESC, na=False) & is_mastercard_payment
        

    payments = df[(is_mandatory_payment & is_not_discover) | (is_my_card)].copy()
    payment_classes =[]
    logger.debug('payments: %s', payments.to_string())

    for payment_idx in payments.index:
        payment_classes.append(
            Payment(
                amount=df.loc[payment_idx, "DEBITO"],
                start_date=df.loc[payment_idx, "FECHA"].strftime('%Y-%m-%d')
            )
        )
    
    return payment_classes

    
def view_investments(df):
    ''' only notebook '''
    
    STARTED_INVESTMENT_DESC = ["CERTIFICADO DE DEPOSITO","A PLAZO FIJO"]
    FINISHED_INVESTMENT_DESC = "CANCELACION PLAZO FIJO"

    finished_investment = df[df['DESCRIPCION'] == FINISHED_INVESTMENT_DESC ]
    started_investment =df[df["DESCRIPCION"].str.contains("|".join(STARTED_INVESTMENT_DESC), na=False)]
    print(started_investment[["FECHA","DESCRIPCION","MONTO"]], end="\n\n")

    investments_view_df  = pd.concat([finished_investment, started_investment], ignore_index=True)
    investments_view_df = investments_view_df.sort_values(by='FECHA')
    print("------INVESTMENTS")
    print(investments_view_df[["FECHA","DESCRIPCION","MONTO"]], end="\n\n")

    print("------FINISHED INVESTMENTS")
    for investment_date in finished_investment["FECHA"]:
        investment_rows = df[df["FECHA"] == investment_date]
        print(f"Investment Date: {investment_date}")
        fixed_term = investment_rows[investment_rows["DESCRIPCION"] == FINISHED_INVESTMENT_DESC]["MONTO"].values[0]
        # interest = investment_rows[investment_rows["DESCRIPCION"] == "TRANSFERENCIA INTERIOR"]["CREDITO"].values[0]
        filtered_interestt = investment_rows[investment_rows["DESCRIPCION"] == "TRANSFERENCIA INTERIOR"]
        if not filtered_interestt.empty:
            interest = filtered_interestt["CREDITO"].values[0]
        else:
            interest = investment_rows[investment_rows["DESCRIPCION"] == FINISHED_INVESTMENT_DESC]["MONTO"].values[1]
        
        # Verificar si existe la fila de tax antes de acceder
        if not investment_rows[investment_rows["DESCRIPCION"] == "RETENCION RENDIMIENTO FINANCIERO"].empty:
            tax = investment_rows[investment_rows["DESCRIPCION"] == "RETENCION RENDIMIENTO FINANCIERO"]["DEBITO"].values[0]
        else:
            tax = 0.0
    #     print(f'Fecha {fecha}')
    #     print(f'Fixed Term {fixed_term}')
    #     print(f'Interest {interest}')
    #     print(f'Tax {tax}')
        print(f'Fixed Term {fixed_term:,.2f} | Interest {interest:,.2f} | Tax {tax:,.2f}')
        total_amount = fixed_term + interest - tax
        
        print(f'Total {total_amount:,}',end="\n\n")

    print("------STARTED INVESTMENTS")
    print(started_investment[["FECHA","DESCRIPCION","MONTO"]],end="\n\n")


def add_missing_dates(df: pd.DataFrame, dates: list) -> pd.DataFrame:
    """
    Asegura que las fechas indicadas existan en el DataFrame. 
    Si no existen, las inyecta como filas vacías (NaN) y reordena cronológicamente.
    """
    df = df.copy()
    if not dates:
        return df
    
    needed_dates = set(pd.to_datetime(dates))
    existing_dates = set(pd.to_datetime(df['FECHA']))
    missing_dates = list(needed_dates - existing_dates)
    
    if missing_dates:
        df_missing = pd.DataFrame({'FECHA': missing_dates})
        df = pd.concat([df, df_missing], ignore_index=True)
        df['FECHA'] = pd.to_datetime(df['FECHA'])
        df = df.sort_values('FECHA').reset_index(drop=True)
        
    return df


def mark_fixed_payments(df, payments: list[Payment], column_name, include_last=False):
    """ Marks fixed payments from the DataFrame in a new column. """
    df = df.copy()
    df[column_name] = 0.0
    
    for payment in payments:
        end = None
        start = None
        if getattr(payment, 'end_date', None):
            end = df["FECHA"]<=pd.to_datetime(payment.end_date) if include_last else df["FECHA"]< pd.to_datetime(payment.end_date)
        else:
            end = pd.Series(True, index=df.index)
        start = df["FECHA"]>=pd.to_datetime(payment.start_date) if payment.start_date else pd.Series(True, index=df.index)

        # print(f"Pago: {payment.amount} desde {payment.start_date} hasta {payment.end_date}")
        mask  = start & end
        df.loc[mask, column_name] += payment.amount
    return df