import sys
import os

project_root = "/home/sebas/dev/projects/ContabilidadPersonal"

from contabilidad.backend.services.investment_service import InvestmentService
try:
    service = InvestmentService()
    # print("Testing get_investments_from_accounts...")
    # accounts = service.get_investments_from_accounts()
    # print(f"Iniciadas: {len(accounts.iniciadas)}")
    # print(f"Finalizadas: {len(accounts.finalizadas)}")

    print("\nTesting get_investment_chart_data...")
    chart_data = service.get_investment_chart_data()
    print("Keys:", chart_data.keys())
    print("Periods count:", len(chart_data['investment_periods']))
    if chart_data['investment_periods']:
        print("First period:", chart_data['investment_periods'][0])
except Exception as e:
    import traceback
    traceback.print_exc()
