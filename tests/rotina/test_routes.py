from datetime import date, time

from app.rotina import service
from app.rotina.service import DadosAtividade

SEMANA = "2026-10-19"


def nova(post, cliente, **campos):
    dados = {"semana": SEMANA, "titulo": "Pilates", "hora_inicio": "08:00", "hora_fim": "09:00", "dias": ["0"]}
    dados.update(campos)
    return post(cliente, "/rotina/atividades", dados)


def criar_direto(db, usuario, dias=(0,), titulo="Trabalho"):
    return service.criar_atividades(
        db, usuario.id, date(2026, 10, 19), list(dias), DadosAtividade(titulo, time(8), time(12))
    )


def test_rotina_exige_login(cliente):
    assert cliente.get("/rotina", follow_redirects=False).status_code == 303


def test_semana_vazia_mostra_copiar(cliente_logado):
    html = cliente_logado.get(f"/rotina?semana={SEMANA}").text
    assert "Semana sem rotina" in html
    assert "Copiar semana anterior" in html


def test_cabecalho_da_semana_e_navegacao(cliente_logado):
    html = cliente_logado.get(f"/rotina?semana=2026-10-21").text
    assert "19 a 25 de outubro" in html
    assert "semana=2026-10-12" in html and "semana=2026-10-26" in html


def test_criar_atividade_redireciona_e_aparece(cliente_logado, post):
    r = nova(post, cliente_logado, dias=["0", "2"])
    assert r.status_code == 303
    assert r.headers["location"].startswith(f"/rotina?semana={SEMANA}")
    html = cliente_logado.get(f"/rotina?semana={SEMANA}&vista=lista").text
    assert html.count("Pilates") == 2


def test_criar_atividade_fim_antes_do_inicio_mostra_erro(cliente_logado, post, db, usuario):
    r = nova(post, cliente_logado, titulo="Yoga", hora_inicio="10:00", hora_fim="09:00")
    assert r.status_code == 400
    assert "O horário de fim deve ser depois do início." in r.text
    assert 'value="Yoga"' in r.text
    assert service.listar_semana(db, usuario.id, date(2026, 10, 19)) == []


def test_criar_atividade_hora_invalida_mostra_erro(cliente_logado, post):
    r = nova(post, cliente_logado, hora_inicio="25:99")
    assert r.status_code == 400
    assert "Informe horários válidos." in r.text


def test_criar_sem_dias_mostra_erro(cliente_logado, post):
    r = nova(post, cliente_logado, dias=[])
    assert r.status_code == 400
    assert "Escolha pelo menos um dia." in r.text


def test_vista_fica_no_cookie(cliente_logado, db, usuario):
    criar_direto(db, usuario)
    r = cliente_logado.get(f"/rotina?semana={SEMANA}&vista=lista")
    assert r.cookies.get("vista_rotina") == "lista" or "vista_rotina=lista" in r.headers.get("set-cookie", "")
    html = cliente_logado.get(f"/rotina?semana={SEMANA}").text
    assert 'data-vista="lista"' in html


def test_vista_invalida_usa_dia(cliente_logado):
    html = cliente_logado.get(f"/rotina?semana={SEMANA}&vista=xyz").text
    assert 'data-vista="dia"' in html


def test_as_tres_vistas_mostram_a_atividade(cliente_logado, db, usuario):
    criar_direto(db, usuario, dias=(0,), titulo="Trabalho")
    for vista in ("grade", "dia", "lista"):
        html = cliente_logado.get(f"/rotina?semana={SEMANA}&vista={vista}&dia={SEMANA}").text
        assert "Trabalho" in html, vista


def test_grade_tem_rotulo_acessivel(cliente_logado, db, usuario):
    criar_direto(db, usuario)
    html = cliente_logado.get(f"/rotina?semana={SEMANA}&vista=grade").text
    assert 'aria-label="Trabalho, segunda, 08:00 às 12:00"' in html


def test_form_de_edicao_de_grupo_pergunta_escopo(cliente_logado, db, usuario):
    [a, _] = criar_direto(db, usuario, dias=(0, 1))
    html = cliente_logado.get(f"/rotina/atividades/{a.id}/editar").text
    assert "Só este dia" in html and "Todos os dias desta semana" in html


def test_editar_todos_os_dias(cliente_logado, post, db, usuario):
    [a, b] = criar_direto(db, usuario, dias=(0, 1))
    r = post(cliente_logado, f"/rotina/atividades/{a.id}", {
        "titulo": "Escritório", "hora_inicio": "09:00", "hora_fim": "12:00", "escopo": "grupo",
    })
    assert r.status_code == 303
    db.refresh(b)
    assert b.titulo == "Escritório" and b.hora_inicio == time(9)


def test_excluir_so_este_dia(cliente_logado, post, db, usuario):
    [a, b] = criar_direto(db, usuario, dias=(0, 1))
    assert post(cliente_logado, f"/rotina/atividades/{a.id}/excluir", {"escopo": "dia"}).status_code == 303
    assert [x.id for x in service.listar_semana(db, usuario.id, date(2026, 10, 19))] == [b.id]


def test_editar_atividade_de_outro_usuario_404(cliente_logado, post, db, outro_usuario):
    [dela] = criar_direto(db, outro_usuario, titulo="Dela")
    assert cliente_logado.get(f"/rotina/atividades/{dela.id}/editar").status_code == 404
    r = post(cliente_logado, f"/rotina/atividades/{dela.id}", {
        "titulo": "Hack", "hora_inicio": "08:00", "hora_fim": "09:00", "escopo": "dia",
    })
    assert r.status_code == 404
    assert post(cliente_logado, f"/rotina/atividades/{dela.id}/excluir", {"escopo": "grupo"}).status_code == 404
    db.refresh(dela)
    assert dela.titulo == "Dela"


def test_copiar_semana_vazia_mostra_erro(cliente_logado, post):
    r = post(cliente_logado, "/rotina/copiar-semana", {"semana": SEMANA})
    assert r.status_code == 400
    assert "A semana anterior não tem atividades." in r.text


def test_copiar_semana_copia(cliente_logado, post, db, usuario):
    service.criar_atividades(db, usuario.id, date(2026, 10, 12), [0], DadosAtividade("Antiga", time(8), time(9)))
    r = post(cliente_logado, "/rotina/copiar-semana", {"semana": SEMANA})
    assert r.status_code == 303
    assert [a.titulo for a in service.listar_semana(db, usuario.id, date(2026, 10, 19))] == ["Antiga"]


def test_copiar_semana_pede_confirmacao_quando_ha_atividades(cliente_logado, post, db, usuario):
    service.criar_atividades(db, usuario.id, date(2026, 10, 12), [0], DadosAtividade("Antiga", time(8), time(9)))
    criar_direto(db, usuario, titulo="Atual")
    r = post(cliente_logado, "/rotina/copiar-semana", {"semana": SEMANA})
    assert r.status_code == 200
    assert "Isso vai substituir as atividades desta semana. Continuar?" in r.text
    assert [a.titulo for a in service.listar_semana(db, usuario.id, date(2026, 10, 19))] == ["Atual"]
    r = post(cliente_logado, "/rotina/copiar-semana", {"semana": SEMANA, "confirmar": "sim"})
    assert r.status_code == 303
    assert [a.titulo for a in service.listar_semana(db, usuario.id, date(2026, 10, 19))] == ["Antiga"]


def test_post_sem_csrf_403(cliente_logado):
    r = cliente_logado.post("/rotina/atividades", data={"titulo": "x"}, follow_redirects=False)
    assert r.status_code == 403
