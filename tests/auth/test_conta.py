def test_conta_mostra_email(cliente_logado):
    r = cliente_logado.get("/conta")
    assert r.status_code == 200
    assert "ana@example.com" in r.text
    assert "America/Sao_Paulo" in r.text


def test_trocar_fuso(cliente_logado, post, db, usuario):
    r = post(cliente_logado, "/conta/fuso", {"fuso_horario": "America/Manaus"})
    assert r.status_code == 303
    db.refresh(usuario)
    assert usuario.fuso_horario == "America/Manaus"


def test_trocar_fuso_invalido_mostra_erro(cliente_logado, post, db, usuario):
    r = post(cliente_logado, "/conta/fuso", {"fuso_horario": "Marte/Base"})
    assert r.status_code == 400
    assert "Fuso horário inválido." in r.text
    db.refresh(usuario)
    assert usuario.fuso_horario == "America/Sao_Paulo"
