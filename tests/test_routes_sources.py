from fastapi.testclient import TestClient
from contabilidad.backend.main import app

client = TestClient(app)

def test_get_sources_summary_endpoint():
    response = client.get("/api/sources/summary")
    assert response.status_code == 200
    data = response.json()
    assert "bank_sources" in data
    assert "card_sources" in data
    assert isinstance(data["bank_sources"], list)
    assert isinstance(data["card_sources"], list)
    
    if len(data["bank_sources"]) > 0:
        source = data["bank_sources"][0]
        assert "file_name" in source
        assert "min_date" in source
        assert "max_date" in source
        assert "chart_data" in source
        assert "total_rows" in source
        if len(source["chart_data"]) > 0:
            assert "date" in source["chart_data"][0]
            assert source["chart_data"][0]["date"] is not None

    if len(data["card_sources"]) > 0:
        source = data["card_sources"][0]
        assert "file_name" in source
        assert "min_date" in source
        assert "max_date" in source
        assert "chart_data" in source
        assert "total_rows" in source
        if len(source["chart_data"]) > 0:
            assert "date" in source["chart_data"][0]
            assert source["chart_data"][0]["date"] is not None

