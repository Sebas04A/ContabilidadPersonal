import os
import pandas as pd
from datetime import datetime, timedelta
import random
import uuid
import argparse

# --- Constantes y Configuración ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MOCK_DATA_DIR = os.path.join(PROJECT_ROOT, "data_mock")

class GeneratorConfig:
    def __init__(self, start_date=None, end_date=None, modules=None):
        self.start_date = start_date or datetime(2024, 1, 1)
        self.end_date = end_date or datetime(2024, 4, 30)
        self.modules = modules or ["banca", "tarjeta", "deudas", "virtuales", "etiquetado"]
        
        # Parámetros internos
        self.initial_saldo = 2500.00
        self.card_cut_day = 6
        self.card_payment_delay = 15 # Días después del corte

class BaseGenerator:
    def __init__(self, config: GeneratorConfig):
        self.config = config
        self._ensure_dirs()

    def _ensure_dirs(self):
        dirs = [
            os.path.join(MOCK_DATA_DIR, "nuevos", "banca"),
            os.path.join(MOCK_DATA_DIR, "nuevos", "tarjeta"),
            os.path.join(MOCK_DATA_DIR, "sistema", "procesada", "banca"),
            os.path.join(MOCK_DATA_DIR, "sistema", "procesada", "tarjeta"),
            os.path.join(MOCK_DATA_DIR, "sistema", "etiquetado"),
            os.path.join(MOCK_DATA_DIR, "sistema", "interpolaciones"),
            os.path.join(MOCK_DATA_DIR, "sistema", "deudas"),
        ]
        for d in dirs:
            if not os.path.exists(d):
                os.makedirs(d)

    def generate_id(self):
        return uuid.uuid4().hex

class FinancialDataGenerator(BaseGenerator):
    def __init__(self, config: GeneratorConfig):
        super().__init__(config)
        self.banca_rows = []
        self.tarjeta_consumos = []
        self.tarjeta_metadata = []
        self.planned_debts = []
        self.current_card_consumos = 0
        self.current_card_txs = 0
        self.last_cut_date = self.config.start_date - timedelta(days=30)

    def generate(self):
        current_date = self.config.start_date
        print(f"Generando datos financieros desde {current_date.date()} hasta {self.config.end_date.date()}...")

        while current_date <= self.config.end_date:
            self._generate_daily_bank(current_date)
            self._generate_daily_card(current_date)
            
            # Corte de tarjeta
            if current_date.day == self.config.card_cut_day:
                self._process_card_cut(current_date)
                
            current_date += timedelta(days=1)

        self._finalize_banca()
        self._save_to_files()

    def _generate_daily_bank(self, date):
        # Sueldo
        if date.day in [15, 30]:
            self.banca_rows.append({
                "id": self.generate_id(), "FECHA": date, 
                "DESCRIPCION": "TRANSFERENCIA RECIBIDA NOMINA MOCK", "MONTO": 1350.00, "FUENTE": "BANCO"
            })
        
        # Arriendo
        if date.day == 1:
            self.banca_rows.append({
                "id": self.generate_id(), "FECHA": date, 
                "DESCRIPCION": "TRANSFERENCIA ENVIADA ARRIENDO", "MONTO": -450.00, "FUENTE": "BANCO"
            })

        # Definición de reglas presupuestarias determinísticas suavizadas (50/30/20)
        # Ingreso mensual estimado = 2700
        budget_rules = [
            {"desc": "TRANSFERENCIA ENVIADA ARRIENDO", "freq": "monthly", "day": 1, "target": 400.0, "fuente": "BANCO"},
            {"desc": "PAGO SERVICIOS AGUA LUZ", "freq": "monthly", "day": 5, "target": 100.0, "fuente": "BANCO"},
            {"desc": "PAGO INTERNET", "freq": "monthly", "day": 10, "target": 50.0, "fuente": "TARJETA"},
            {"desc": "SEGURO MEDICO", "freq": "monthly", "day": 15, "target": 150.0, "fuente": "TARJETA"},
            {"desc": "SUPERMERCADO CASH", "freq": "weekly", "weekday": 6, "target": 100.0, "fuente": "TARJETA"}, # Necesidad: 100 semanales = 400
            {"desc": "PAGO GASOLINERA", "freq": "biweekly", "day1": 2, "day2": 16, "target": 50.0, "fuente": "TARJETA"}, # Necesidad: 100 mensuales
            {"desc": "COMIDA PARA MASCOTA", "freq": "monthly", "day": 20, "target": 50.0, "fuente": "TARJETA"}, # Necesidad
            {"desc": "FERRETERIA LOCAL", "freq": "random", "prob": 0.05, "target": 25.0, "fuente": "TARJETA"}, # Necesidad
            {"desc": "FARMACIA SANA", "freq": "random", "prob": 0.05, "target": 15.0, "fuente": "TARJETA"}, # Necesidad
            {"desc": "CAFETERIA", "freq": "daily", "prob": 0.6, "target": 3.0, "fuente": "TARJETA"}, # Deseo: ~60 al mes
            {"desc": "RESTAURANTE LOCAL", "freq": "weekly", "weekday": 5, "target": 50.0, "fuente": "TARJETA"}, # Deseo: vieres = 200 al mes
            {"desc": "UBER EATS MOCK", "freq": "weekly", "weekday": 2, "target": 30.0, "fuente": "TARJETA"}, # Deseo: martes = 120 al mes
            {"desc": "NETFLIX", "freq": "monthly", "day": 12, "target": 15.0, "fuente": "TARJETA"}, # Deseo
            {"desc": "SPOTIFY", "freq": "monthly", "day": 13, "target": 15.0, "fuente": "TARJETA"}, # Deseo
            {"desc": "CINE MOCK", "freq": "biweekly", "day1": 7, "day2": 21, "target": 25.0, "fuente": "TARJETA"}, # Deseo: 50 al mes
            {"desc": "ZARA MOCK", "freq": "random", "prob": 0.05, "target": 60.0, "fuente": "TARJETA"}, # Deseo: ropa
            {"desc": "AMAZON MOCK", "freq": "random", "prob": 0.05, "target": 60.0, "fuente": "TARJETA"}, # Deseo: gadgets
            {"desc": "GAME STORE", "freq": "random", "prob": 0.02, "target": 30.0, "fuente": "TARJETA"}, # Deseo
            {"desc": "AGENCIA DE VIAJES RESERVA", "freq": "random", "prob": 0.02, "target": 100.0, "fuente": "TARJETA"}, # Deseo
            {"desc": "CURSO UDEMY", "freq": "random", "prob": 0.03, "target": 20.0, "fuente": "TARJETA"}, # Necesidad educativa
            {"desc": "CLINICA ESTETICA", "freq": "random", "prob": 0.005, "target": 500.0, "fuente": "BANCO"} # Deseo grande atipico
        ]

        # Evaluación diaria de reglas para garantizar que los pagos suceden
        for rule in budget_rules:
            trigger = False
            rfry = rule["freq"]
            if rfry == "monthly" and date.day == rule.get("day"): trigger = True
            elif rfry == "weekly" and date.weekday() == rule.get("weekday"): trigger = True
            elif rfry == "biweekly" and date.day in [rule.get("day1"), rule.get("day2")]: trigger = True
            elif rfry == "daily" and random.random() < rule.get("prob", 1.0): trigger = True
            elif rfry == "random" and random.random() < rule.get("prob", 0.1): trigger = True
                
            if trigger:
                # Randomismo de +/- 10% para hacerlo realista
                real_amount = round(rule["target"] * random.uniform(0.9, 1.1), 2)
                
                if rule["fuente"] == "TARJETA":
                    self.tarjeta_consumos.append({
                        "id": self.generate_id(), "FECHA": date, "DESCRIPCION": rule["desc"], 
                        "MONTO": real_amount, "FUENTE": "TARJETA", "OPERACION": "CONSUMO"
                    })
                    self.current_card_consumos += real_amount
                    self.current_card_txs += 1
                else:
                    self.banca_rows.append({
                        "id": self.generate_id(), "FECHA": date, "DESCRIPCION": rule["desc"], 
                        "MONTO": -real_amount, "FUENTE": "BANCO"
                    })

        # --- Flujo de Inversiones (Pagos Fijos) ---
        # El dinero sale de inversion (entra a banco) en el dia 5 de cada trimestre
        if date.month in [1, 4, 7, 10] and date.day == 5:
            self.banca_rows.append({
                "id": self.generate_id(), "FECHA": date, 
                "DESCRIPCION": "CANCELACION PLAZO FIJO MOCK", "MONTO": 5000.00, "FUENTE": "INVERSION"
            })
            self.banca_rows.append({
                "id": self.generate_id(), "FECHA": date, 
                "DESCRIPCION": "TRANSFERENCIA INTERIOR (INTERESES)", "MONTO": 45.00, "FUENTE": "INVERSION"
            })

        # El dinero vuelve a inversion (sale de banco) en el dia 25 del mismo mes, este es el pago fijo real
        if date.month in [1, 4, 7, 10] and date.day == 25:
            self.banca_rows.append({
                "id": self.generate_id(), "FECHA": date, 
                "DESCRIPCION": "CERTIFICADO DE DEPOSITO MOCK", "MONTO": -5000.00, "FUENTE": "INVERSION"
            })

        # --- Sueldo Quincenal ---
        if date.day in [15, 28]: # 28 as safe end of month
            self.banca_rows.append({
                "id": self.generate_id(), "FECHA": date, 
                "DESCRIPCION": "TRANSFERENCIA RECIBIDA NOMINA MOCK", "MONTO": 1350.00, "FUENTE": "BANCO"
            })

        # --- Flujo de Anticipos (Interpolados) Mensuales Antiguo Reemplazado por Nomina ---
        # Removido el "anticipo" viejo de 400.

        # --- Flujo Determinístico Frecuente de Deudas ---
        mes_actual = date.month
        # 1. Préstamo a inicios de mes (Día 5)
        if date.day == 5:
            self.banca_rows.append({"id": f"tx_d1_{mes_actual}", "FECHA": date, "DESCRIPCION": "TRANSFERENCIA ENVIADA PAGO PRESTAMO ANA", "MONTO": -100.00, "FUENTE": "BANCO"})
            self.planned_debts.append({
                "id": f"deuda_1_{mes_actual}", "titulo": f"Prestamo Ana Mes {mes_actual}", "monto_original": 100.0, "deudor_id": "d2", "deudor_nombre": "Ana Mock", 
                "fecha_gasto": date, "estado": "PAGADA", "pagos": [
                    {"fecha_pago": date + timedelta(days=20), "monto": 100.0}
                ]
            })
            
        if date.day == 25:
             # Pago correspondiente a deuda de dia 5
             self.banca_rows.append({"id": self.generate_id(), "FECHA": date, "DESCRIPCION": "TRANSFERENCIA RECIBIDA PAGO ANA", "MONTO": 100.00, "FUENTE": "BANCO"})

        # 2. Gasto compartido quincenal (Día 12)
        if date.day == 12:
            self.banca_rows.append({"id": f"tx_d2_{mes_actual}", "FECHA": date, "DESCRIPCION": "PAGO GASTO COMPARTIDO CENA", "MONTO": -60.00, "FUENTE": "BANCO"})
            self.planned_debts.append({
                "id": f"deuda_2_{mes_actual}", "titulo": f"Cena Carlos {mes_actual}", "monto_original": 60.0, "deudor_id": "d1", "deudor_nombre": "Carlos Mock", 
                "fecha_gasto": date, "estado": "PAGADA", "pagos": [
                    {"fecha_pago": date + timedelta(days=6), "monto": 60.0}
                ]
            })

        if date.day == 18:
             # Pago de Carlos (ocurre 6 días después del 12)
             self.banca_rows.append({"id": self.generate_id(), "FECHA": date, "DESCRIPCION": "TRANSFERENCIA RECIBIDA PAGO CARLOS", "MONTO": 60.00, "FUENTE": "BANCO"})

        # 3. Deuda inter-mensual o parcial (Día 22)
        if date.day == 22:
            self.banca_rows.append({"id": f"tx_d3_{mes_actual}", "FECHA": date, "DESCRIPCION": "TRANSFERENCIA ENVIADA PAGO PRESTAMO MIGUEL", "MONTO": -150.00, "FUENTE": "BANCO"})
            
            # Solo paga si no es el último mes del rango, o pagará despues
            fecha_pago3 = date + timedelta(days=15)
            # Para el mock, la pondremos completa siempre que caiga dentro del end_date aprox
            if mes_actual < 6:
                estado_deuda = "PAGADA"
                pagos_mig = [{"fecha_pago": fecha_pago3, "monto": 150.0}]
            else:
                estado_deuda = "PENDIENTE"
                pagos_mig = []
                
            self.planned_debts.append({
                "id": f"deuda_3_{mes_actual}", "titulo": f"Emergencia Miguel {mes_actual}", "monto_original": 150.0, "deudor_id": "d3", "deudor_nombre": "Miguel Mock", 
                "fecha_gasto": date, "estado": estado_deuda, "pagos": pagos_mig
            })

        # Pago de Miguel cae en el dia 7 del siguiente mes (22+15 = ~7)
        if date.day == 7 and mes_actual > 1:
             self.banca_rows.append({"id": self.generate_id(), "FECHA": date, "DESCRIPCION": "TRANSFERENCIA RECIBIDA PAGO MIGUEL", "MONTO": 150.00, "FUENTE": "BANCO"})

    def _generate_daily_card(self, date):
        pass # La lógica de generación ahora está cubierta en _generate_daily_bank mediante los templates

    def _process_card_cut(self, date):
        max_payment_date = date + timedelta(days=self.config.card_payment_delay)
        total_a_pagar = round(self.current_card_consumos, 2)
        
        metadata = {
            "EMPRESA": "MOCK USER SERVICES",
            "NUM_TARJETA": "XXXX-XXXX-XXXX-1234",
            "FECHA_EMISION": date,
            "FECHA_MAX_PAGO": max_payment_date,
            "saldo_anterior": 0.0,
            "subtotal_pagado": 0.0,
            "total_a_pagar": total_a_pagar,
            "minimo_a_pagar": round(total_a_pagar * 0.1, 2),
            "total_consumo": total_a_pagar,
            "num_transacciones": self.current_card_txs,
            "fecha_min": self.last_cut_date,
            "fecha_max": date,
            "total_mes": total_a_pagar,
            "total_a_pagar_despues": total_a_pagar,
            "source_file": f"MockCard_{date.strftime('%Y-%m')}.xlsx",
            "verificacion_monto_ok": True,
            "verificacion_transacciones_ok": True
        }
        self.tarjeta_metadata.append(metadata)

        # Pago en el banco
        if max_payment_date <= self.config.end_date:
            self.banca_rows.append({
                "id": self.generate_id(), "FECHA": max_payment_date, 
                "DESCRIPCION": f"PAGO TARJETA DE CREDITO MASTERCARD BANCO PICHINCHA  223067XXXX-MOCK-{date.strftime('%Y-%m')}", 
                "MONTO": -total_a_pagar, "FUENTE": "BANCO"
            })

        self.last_cut_date = date
        self.current_card_consumos = 0
        self.current_card_txs = 0

    def _finalize_banca(self):
        self.banca_rows.sort(key=lambda x: x["FECHA"])
        saldo = self.config.initial_saldo
        for row in self.banca_rows:
            saldo += row["MONTO"]
            row["SALDO"] = round(saldo, 2)

    def _save_to_files(self):
        # 1. Banca
        df_b = pd.DataFrame(self.banca_rows)
        df_b.to_excel(os.path.join(MOCK_DATA_DIR, "sistema", "procesada", "banca", "banca_unida.xlsx"), index=False)

        # 2. Tarjeta Consolidada
        df_t = pd.DataFrame(self.tarjeta_consumos)
        df_t.to_excel(os.path.join(MOCK_DATA_DIR, "sistema", "procesada", "tarjeta", "tarjeta_unida.xlsx"), index=False)

        # 3. Metadata y Archivos Mensuales
        df_m = pd.DataFrame(self.tarjeta_metadata)
        df_m.to_excel(os.path.join(MOCK_DATA_DIR, "sistema", "procesada", "tarjeta", "tarjeta_metadata_unida.xlsx"), index=False)

        for _, meta in df_m.iterrows():
            period_str = meta["FECHA_EMISION"].strftime("%Y-%m")
            f_min, f_max = meta["fecha_min"], meta["fecha_max"]
            df_period = df_t[(df_t["FECHA"] > f_min) & (df_t["FECHA"] <= f_max)]
            
            file_path = os.path.join(MOCK_DATA_DIR, "sistema", "procesada", "tarjeta", f"{period_str}.xlsx")
            with pd.ExcelWriter(file_path) as writer:
                pd.DataFrame([meta]).to_excel(writer, sheet_name='Resumen', index=False)
                df_period.to_excel(writer, sheet_name='Movimientos', index=False)

        print(f"Archivos financieros guardados en {MOCK_DATA_DIR}")

class DebtDataGenerator(BaseGenerator):
    def __init__(self, config: GeneratorConfig, fin_gen: FinancialDataGenerator = None):
        super().__init__(config)
        self.fin_gen = fin_gen

    def generate(self):
        print("Generando datos de deudas estáticamente sincronizadas...")
        deudas = []
        pagos = []
        
        if not self.fin_gen or not self.fin_gen.planned_debts:
            print("No hay deudas planificadas en fin_gen.")
            pd.DataFrame(columns=["id", "titulo", "monto_original", "deudor_id", "fecha_gasto", "estado", "deudor_nombre", "deudor_token"]).to_csv(os.path.join(MOCK_DATA_DIR, "sistema", "deudas", "deudas.csv"), index=False)
            pd.DataFrame(columns=["id", "fecha_pago", "monto_total", "deudor_id", "deudor_nombre"]).to_csv(os.path.join(MOCK_DATA_DIR, "sistema", "deudas", "pagos_deudas.csv"), index=False)
            return

        for PD in self.fin_gen.planned_debts:
            deudas.append({
                "id": PD["id"], 
                "titulo": PD["titulo"], 
                "monto_original": PD["monto_original"],
                "deudor_id": PD["deudor_id"], 
                "fecha_gasto": PD["fecha_gasto"].strftime("%Y-%m-%d"),
                "estado": PD["estado"], 
                "deudor_nombre": PD["deudor_nombre"], 
                "deudor_token": "token_" + PD["deudor_id"]
            })
            
            for pgo in PD["pagos"]:
                pagos.append({
                    "id": self.generate_id(), 
                    "fecha_pago": pgo["fecha_pago"].strftime("%Y-%m-%d"),
                    "monto_total": pgo["monto"], 
                    "deudor_id": PD["deudor_id"], 
                    "deudor_nombre": PD["deudor_nombre"]
                })

        pd.DataFrame(deudas).to_csv(os.path.join(MOCK_DATA_DIR, "sistema", "deudas", "deudas.csv"), index=False)
        pd.DataFrame(pagos).to_csv(os.path.join(MOCK_DATA_DIR, "sistema", "deudas", "pagos_deudas.csv"), index=False)
             
        print(f"Archivos de deudas guardados sincronizados: {len(deudas)} deudas, {len(pagos)} pagos.")

class VirtualDataGenerator(BaseGenerator):
    def generate(self):
        print("Generando datos de ítems virtuales (Fijos/Interpolados)...")
        
        # 1. Grupos
        groups = [
            {"id": "g_fixed_1", "name": "Fondo Rotativo Plazo Fijo", "description": "Dinero en cuenta pero reservado para reinversion", "type": "fixed"},
            {"id": "g_interp_nomina", "name": "Nomina Prorrateada", "description": "Sueldo recibido dividido gradualmente para net worth", "type": "interpolated"}
        ]
        
        # 2. Pagos
        payments = []
        
        # Generar pagos fijos (En cada trimestre, del dia 5 al 25)
        for month in [1, 4]: # Enero y Abril (dentro del rango 2024-01 a 2024-06)
            payments.append({
                "id": f"p_fix_{month}", "group_id": "g_fixed_1", "amount": 5000.0, 
                "start_date": datetime(2024, month, 5).date(), 
                "end_date": datetime(2024, month, 25).date(), 
                "note": f"Reserva Inversion {month}/2024"
            })
            
        # Generar Sueldo interpolado quincenalmente
        # Asumiendo ingresos el 15 y 28 de $1350 cada uno
        for month in range(1, 7): # De Enero a Junio
            # Quincena 1 (asumimos que cobre la quincena pasada o arranca en 0)
            st1 = datetime(2024, month, 1).date()
            ed1 = datetime(2024, month, 15).date()
            payments.append({
                "id": f"p_nomina_{month}_1", "group_id": "g_interp_nomina", "amount": 1350.0, 
                "start_date": st1, "end_date": ed1, "note": f"Nomina Q1 {month}/2024"
            })
            
            st2 = datetime(2024, month, 16).date()
            ed2 = datetime(2024, month, 28).date()
            payments.append({
                "id": f"p_nomina_{month}_2", "group_id": "g_interp_nomina", "amount": 1350.0, 
                "start_date": st2, "end_date": ed2, "note": f"Nomina Q2 {month}/2024"
            })
        
        pd.DataFrame(groups).to_csv(os.path.join(MOCK_DATA_DIR, "sistema", "interpolaciones", "grupos.csv"), index=False)
        pd.DataFrame(payments).to_csv(os.path.join(MOCK_DATA_DIR, "sistema", "interpolaciones", "pagos.csv"), index=False)
        print(f"Archivos de ítems virtuales guardados: {len(payments)} registros.")

class LabelDataGenerator(BaseGenerator):
    def __init__(self, config: GeneratorConfig, fin_gen: FinancialDataGenerator):
        super().__init__(config)
        self.fin_gen = fin_gen
        
        # 10 Categorias Completas con 20 Tags + Extras
        self.LABEL_RULES = {
            "TRANSFERENCIA ENVIADA ARRIENDO": {"categoria": "Vivienda", "tags": "Arriendo", "prioridad": "Necesidad", "felicidad": 4, "es_fijo": True},
            "PAGO SERVICIOS AGUA LUZ": {"categoria": "Servicios Basicos", "tags": "Recibos_Luz_Agua", "prioridad": "Necesidad", "felicidad": 3, "es_fijo": True},
            "PAGO INTERNET": {"categoria": "Servicios Basicos", "tags": "Internet_Telefono", "prioridad": "Necesidad", "felicidad": 5, "es_fijo": True},
            "SEGURO MEDICO": {"categoria": "Salud", "tags": "Seguro_Medico", "prioridad": "Necesidad", "felicidad": 5, "es_fijo": True},
            "SUPERMERCADO CASH": {"categoria": "Alimentacion", "tags": "Groceries_Mensual", "prioridad": "Necesidad", "felicidad": 6, "es_fijo": True},
            "PAGO GASOLINERA": {"categoria": "Transporte", "tags": "Gasolina", "prioridad": "Necesidad", "felicidad": 4, "es_fijo": True},
            "COMIDA PARA MASCOTA": {"categoria": "Mascotas", "tags": "Mascotas_Comida", "prioridad": "Necesidad", "felicidad": 6, "es_fijo": True},
            "FERRETERIA LOCAL": {"categoria": "Vivienda", "tags": "Mantenimiento_Casa", "prioridad": "Necesidad", "felicidad": 3, "es_fijo": False},
            "FARMACIA SANA": {"categoria": "Salud", "tags": "Medicamentos", "prioridad": "Necesidad", "felicidad": 2, "es_fijo": False},
            "CAFETERIA": {"categoria": "Alimentacion", "tags": "Cafe_Diario", "prioridad": "Deseo", "felicidad": 8, "es_fijo": False},
            "RESTAURANTE LOCAL": {"categoria": "Alimentacion", "tags": "Salida_FinSemana", "prioridad": "Deseo", "felicidad": 9, "es_fijo": False},
            "UBER EATS MOCK": {"categoria": "Alimentacion", "tags": "Comida_Rapida", "prioridad": "Deseo", "felicidad": 7, "es_fijo": False},
            "NETFLIX": {"categoria": "Entretenimiento", "tags": "Streaming_Mensual", "prioridad": "Deseo", "felicidad": 6, "es_fijo": True},
            "SPOTIFY": {"categoria": "Entretenimiento", "tags": "Streaming_Mensual", "prioridad": "Deseo", "felicidad": 7, "es_fijo": True},
            "CINE MOCK": {"categoria": "Entretenimiento", "tags": "Peliculas_Teatro", "prioridad": "Deseo", "felicidad": 8, "es_fijo": False},
            "ZARA MOCK": {"categoria": "Compras Personales", "tags": "Ropa_Trabajo", "prioridad": "Deseo", "felicidad": 7, "es_fijo": False},
            "AMAZON MOCK": {"categoria": "Compras Personales", "tags": "Gadget_Tech", "prioridad": "Deseo", "felicidad": 9, "es_fijo": False},
            "GAME STORE": {"categoria": "Entretenimiento", "tags": "Juegos_Video", "prioridad": "Deseo", "felicidad": 8, "es_fijo": False},
            "AGENCIA DE VIAJES RESERVA": {"categoria": "Viajes", "tags": "Viaje_Relax", "prioridad": "Deseo", "felicidad": 9, "es_fijo": False},
            "CURSO UDEMY": {"categoria": "Educacion", "tags": "Curso_Desarrollo", "prioridad": "Necesidad", "felicidad": 7, "es_fijo": False},
            "CLINICA ESTETICA": {"categoria": "Salud", "tags": "Operacion_Nariz", "prioridad": "Deseo", "felicidad": 6, "es_fijo": False},
            
            # --- Extras Financieros que no afectan presupuesto UI base ---
            "TRANSFERENCIA RECIBIDA NOMINA MOCK": {"categoria": "Ingresos Principales", "tags": "Nomina", "prioridad": "Ingreso", "felicidad": 9, "es_fijo": True},
            "PAGO TARJETA DE CREDITO": {"categoria": "Tarjetas", "tags": "Pago_Tarjeta", "prioridad": "Pago Financiero", "felicidad": 4, "es_fijo": True},
            "CERTIFICADO DE DEPOSITO MOCK": {"categoria": "Inversiones", "tags": "Inversion_LargoPlazo", "prioridad": "Financiero", "felicidad": 8, "es_fijo": True},
            "CANCELACION PLAZO FIJO MOCK": {"categoria": "Inversiones", "tags": "Inversion_Liquida", "prioridad": "Financiero", "felicidad": 8, "es_fijo": True},
            "TRANSFERENCIA INTERIOR (INTERESES)": {"categoria": "Inversiones", "tags": "Rendimientos", "prioridad": "Ingreso Extra", "felicidad": 9, "es_fijo": False},
            
            # --- Etiquetas de Deudas ---
            "TRANSFERENCIA ENVIADA PAGO PRESTAMO": {"categoria": "Deudas", "tags": "Prestamo", "prioridad": "Financiero", "felicidad": 3, "es_fijo": False},
            "TRANSFERENCIA RECIBIDA PAGO ANA": {"categoria": "Deudas", "tags": "Cobro", "prioridad": "Deuda", "felicidad": 6, "es_fijo": False},
            "TRANSFERENCIA RECIBIDA PAGO CARLOS": {"categoria": "Deudas", "tags": "Cobro", "prioridad": "Deuda", "felicidad": 6, "es_fijo": False},
            "TRANSFERENCIA RECIBIDA PAGO MIGUEL": {"categoria": "Deudas", "tags": "Cobro", "prioridad": "Deuda", "felicidad": 6, "es_fijo": False},
            "PAGO GASTO COMPARTIDO CENA": {"categoria": "Deudas", "tags": "Gasto_Compartido", "prioridad": "Deseo", "felicidad": 7, "es_fijo": False},
        }

    def generate(self):
        if not self.fin_gen:
            print("No hay datos financieros para etiquetar.")
            return

        print("Generando datos de etiquetado realista (etiquetas.csv)...")
        etiquetas = []
        
        # Unificar transacciones para etiquetar
        todas_transacciones = []
        for b in self.fin_gen.banca_rows:
            todas_transacciones.append({"id": b["id"], "desc": b["DESCRIPCION"], "mon": b["MONTO"], "tipo": "BANCA"})
        for t in self.fin_gen.tarjeta_consumos:
            todas_transacciones.append({"id": t["id"], "desc": t["DESCRIPCION"], "mon": t["MONTO"], "tipo": "TARJETA"})
            
        for tx in todas_transacciones:
            # Buscar coincidencia
            matched_rule = None
            for key, rule in self.LABEL_RULES.items():
                if key in tx["desc"]:
                    matched_rule = rule
                    break
                    
            if not matched_rule:
                if 'Deuda' in tx["desc"] or 'Prestamo' in tx["desc"]:
                    matched_rule = {"categoria": "Deudas", "tags": "Prestamo", "prioridad": "Financiero", "felicidad": 3, "es_fijo": False}
                elif tx["mon"] > 0 and tx["tipo"] == "BANCA": # Solo los ingresos en banca son positivos reales
                    matched_rule = {"categoria": "Ingresos Varios", "tags": "Ingreso_Extra", "prioridad": "Ingreso", "felicidad": 7, "es_fijo": False}
                else:
                    matched_rule = {"categoria": "Varios", "tags": "Otros", "prioridad": "Necesidad", "felicidad": 5, "es_fijo": False}
                    
            # Insertar ruido ocasional en la felicidad o prioridad para más realismo
            felicidad = matched_rule["felicidad"]
            if random.random() < 0.2:
                felicidad = min(9, max(1, felicidad + random.choice([-2, -1, 1, 2])))
                
            prioridad = matched_rule["prioridad"]
            if prioridad == "Necesidad" and random.random() < 0.1:
                prioridad = "Deseo"
                
            tags = matched_rule["tags"]
            # Alto valor: si sale mucha plata de la cuenta o si se gasta mucho en la tarjeta
            if (tx['tipo'] == 'BANCA' and tx['mon'] < -300) or (tx['tipo'] == 'TARJETA' and tx['mon'] > 300): 
                tags += ",alto_valor"
                
            etiquetas.append({
                "source_id": tx["id"],
                "source_type": tx["tipo"],
                "nombre_limpio": tx["desc"],
                "categoria": matched_rule["categoria"],
                "tags": tags,
                "prioridad": prioridad,
                "es_fijo": matched_rule["es_fijo"],
                "pertenece_a": "",
                "es_reembolsable": False,
                "deudor": "",
                "felicidad": felicidad,
                "revisado": True,
                "nota": "",
                "split_group_id": "",
                "group_id": "",
                "monto_asignado": ""
            })

        pd.DataFrame(etiquetas).to_csv(os.path.join(MOCK_DATA_DIR, "sistema", "etiquetado", "etiquetas.csv"), index=False)
        print(f"Archivo de etiquetas guardado: {len(etiquetas)} registros.")

def main():
    parser = argparse.ArgumentParser(description="Generador Modular de Datos Mock")
    parser.add_argument("--start", type=str, help="Fecha inicio (YYYY-MM-DD)", default="2024-01-01")
    parser.add_argument("--end", type=str, help="Fecha fin (YYYY-MM-DD)", default="2024-06-30")
    parser.add_argument("--skip-deudas", action="store_true", help="No generar deudas")
    parser.add_argument("--skip-finanzas", action="store_true", help="No generar banca/tarjeta")
    parser.add_argument("--skip-virtuales", action="store_true", help="No generar items virtuales")
    parser.add_argument("--skip-etiquetado", action="store_true", help="No etiquetar generacion")
    
    args = parser.parse_args()
    
    config = GeneratorConfig(
        start_date=datetime.strptime(args.start, "%Y-%m-%d"),
        end_date=datetime.strptime(args.end, "%Y-%m-%d")
    )
    
    fin_gen = None
    if not args.skip_finanzas:
        fin_gen = FinancialDataGenerator(config)
        fin_gen.generate()
    
    if not args.skip_deudas:
        DebtDataGenerator(config, fin_gen).generate()

    if not args.skip_virtuales:
        VirtualDataGenerator(config).generate()
        
    if not args.skip_etiquetado and fin_gen:
        LabelDataGenerator(config, fin_gen).generate()

if __name__ == "__main__":
    main()
