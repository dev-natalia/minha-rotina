from datetime import timedelta

from app import tempo
from app.auth import service
from tests.conftest import SENHA_TESTE


def _login(cliente, email, senha):
    return cliente.post("/login", data={"email": email, "senha": senha}, follow_redirects=False)


def test_pagina_de_login_publica(cliente):
    r = cliente.get("/login")
    assert r.status_code == 200
    assert 'name="email"' in r.text and 'name="senha"' in r.text


def test_login_correto_redireciona_e_define_cookie(cliente, usuario):
    r = _login(cliente, "ana@example.com", SENHA_TESTE)
    assert r.status_code == 303
    assert r.headers["location"] == "/"
    cookie = r.headers["set-cookie"]
    assert cookie.startswith("sessao=")
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie


def test_login_aceita_email_com_maiusculas(cliente, usuario):
    assert _login(cliente, " ANA@example.com ", SENHA_TESTE).status_code == 303


def test_login_senha_errada(cliente, usuario):
    r = _login(cliente, "ana@example.com", "errada-123")
    assert r.status_code == 400
    assert "Email ou senha incorretos." in r.text
    assert 'value="ana@example.com"' in r.text
    assert "set-cookie" not in r.headers


def test_login_usuario_inativo_falha(cliente, usuario, db):
    service.desativar_usuario(db, "ana@example.com")
    assert _login(cliente, "ana@example.com", SENHA_TESTE).status_code == 400


def test_bloqueio_apos_5_falhas(cliente, usuario):
    for _ in range(5):
        assert _login(cliente, "ana@example.com", "errada-123").status_code == 400
    r = _login(cliente, "ana@example.com", SENHA_TESTE)
    assert r.status_code == 429
    assert "Muitas tentativas. Tente de novo em alguns minutos." in r.text


def test_bloqueio_expira_depois_de_15_minutos(cliente, usuario, monkeypatch):
    for _ in range(5):
        _login(cliente, "ana@example.com", "errada-123")
    depois = tempo.agora_utc() + timedelta(minutes=16)
    monkeypatch.setattr(tempo, "agora_utc", lambda: depois)
    assert _login(cliente, "ana@example.com", SENHA_TESTE).status_code == 303


def test_rota_protegida_sem_sessao_redireciona(cliente):
    r = cliente.get("/conta", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_htmx_sem_sessao_recebe_hx_redirect(cliente):
    r = cliente.get("/conta", headers={"HX-Request": "true"}, follow_redirects=False)
    assert r.headers["HX-Redirect"] == "/login"
    assert "senha" not in r.text


def test_sessao_expirada_redireciona(cliente_logado, monkeypatch):
    depois = tempo.agora_utc() + timedelta(days=91)
    monkeypatch.setattr(tempo, "agora_utc", lambda: depois)
    assert cliente_logado.get("/conta", follow_redirects=False).status_code == 303


def test_sessao_e_renovada_com_uso(cliente_logado, monkeypatch):
    # Usada no dia 80, a sessão ganha mais 90 dias e ainda vale no dia 120.
    inicio = tempo.agora_utc()
    monkeypatch.setattr(tempo, "agora_utc", lambda: inicio + timedelta(days=80))
    assert cliente_logado.get("/conta", follow_redirects=False).status_code == 200
    monkeypatch.setattr(tempo, "agora_utc", lambda: inicio + timedelta(days=120))
    assert cliente_logado.get("/conta", follow_redirects=False).status_code == 200


def test_usuario_desativado_perde_a_sessao(cliente_logado, db):
    service.desativar_usuario(db, "ana@example.com")
    assert cliente_logado.get("/conta", follow_redirects=False).status_code == 303


def test_post_sem_csrf_403(cliente_logado):
    r = cliente_logado.post("/sair", follow_redirects=False)
    assert r.status_code == 403


def test_post_com_csrf_errado_403(cliente_logado):
    r = cliente_logado.post("/sair", data={"csrf_token": "falso"}, follow_redirects=False)
    assert r.status_code == 403


def test_csrf_pelo_header_htmx(cliente_logado):
    r = cliente_logado.post("/sair", headers={"X-CSRF-Token": cliente_logado.csrf}, follow_redirects=False)
    assert r.status_code == 303


def test_sair_encerra_sessao(cliente_logado, post):
    r = post(cliente_logado, "/sair")
    assert r.status_code == 303
    assert r.headers["location"] == "/login"
    assert cliente_logado.get("/conta", follow_redirects=False).status_code == 303


def test_layout_tem_navegacao(cliente_logado):
    html = cliente_logado.get("/conta").text
    assert '<html lang="pt-BR">' in html
    for item in ("Início", "Rotina", "Contadores", "Histórico"):
        assert item in html
    assert 'id="anuncio"' in html and 'aria-live="polite"' in html
