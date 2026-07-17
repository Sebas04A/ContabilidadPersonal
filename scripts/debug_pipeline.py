import os
import sys

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Enable mock mode explicitly for debug
os.environ["MOCK_MODE"] = "true"

from contabilidad.backend.storage.data_pipeline import get_pipeline

pipeline = get_pipeline()
meta = pipeline.get_credit_card_metadata()
print("Metadata loaded, empty?", meta.empty, "shape:", meta.shape if meta is not None else "None")

cons = pipeline.get_raw_data('tarjeta')
print("Consumos loaded, empty?", cons.empty if cons is not None else True, "shape:", cons.shape if cons is not None else "None")

banca = pipeline.get_raw_data('cuenta')
print("Banca loaded, empty?", banca.empty if banca is not None else True, "shape:", banca.shape if banca is not None else "None")

from contabilidad.backend.storage.transformations.credit_cards import transform_credit_cards
# Let's try running the transformation
print("Testing transform_credit_cards...")
df_result = transform_credit_cards(banca)
print("Finished. PAGO_TARJETA in df?", "PAGO_TARJETA" in df_result.columns)
