from sqlalchemy import text


def test_healthz(cliente):
    r = cliente.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_healthz_toca_o_banco(db):
    assert db.execute(text("select 1")).scalar() == 1
