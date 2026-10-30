from datetime import date, time

import pytest

from app.erros import ErroValidacao, NaoEncontrado
from app.rotina import service
from app.rotina.service import DadosAtividade

SEMANA = date(2026, 10, 19)  # segunda-feira
SEMANA_ANTERIOR = date(2026, 10, 12)


def dados(titulo="Trabalho", inicio=(8, 0), fim=(12, 0), **extra) -> DadosAtividade:
    return DadosAtividade(titulo=titulo, hora_inicio=time(*inicio), hora_fim=time(*fim), **extra)


def test_criar_para_varios_dias_compartilha_grupo(db, usuario):
    criadas = service.criar_atividades(db, usuario.id, date(2026, 10, 21), [0, 1, 2, 3, 4], dados())
    assert [a.data for a in criadas] == [date(2026, 10, d) for d in range(19, 24)]
    grupos = {a.grupo_id for a in criadas}
    assert len(grupos) == 1 and None not in grupos


def test_criar_um_dia_sem_grupo(db, usuario):
    [atividade] = service.criar_atividades(db, usuario.id, SEMANA, [6], dados())
    assert atividade.data == date(2026, 10, 25)
    assert atividade.grupo_id is None


def test_criar_normaliza_campos(db, usuario):
    [a] = service.criar_atividades(db, usuario.id, SEMANA, [0], dados(titulo="  Estudos  ", descricao="   ", cor="azul"))
    assert a.titulo == "Estudos"
    assert a.descricao is None
    assert a.cor == "azul"


def test_fim_antes_do_inicio_erro(db, usuario):
    with pytest.raises(ErroValidacao, match="O horário de fim deve ser depois do início."):
        service.criar_atividades(db, usuario.id, SEMANA, [0], dados(inicio=(10, 0), fim=(10, 0)))


def test_titulo_vazio_erro(db, usuario):
    with pytest.raises(ErroValidacao, match="Informe um título."):
        service.criar_atividades(db, usuario.id, SEMANA, [0], dados(titulo="   "))


def test_titulo_longo_erro(db, usuario):
    with pytest.raises(ErroValidacao):
        service.criar_atividades(db, usuario.id, SEMANA, [0], dados(titulo="x" * 121))


def test_sem_dias_erro(db, usuario):
    with pytest.raises(ErroValidacao, match="Escolha pelo menos um dia."):
        service.criar_atividades(db, usuario.id, SEMANA, [], dados())


def test_dia_invalido_erro(db, usuario):
    with pytest.raises(ErroValidacao):
        service.criar_atividades(db, usuario.id, SEMANA, [7], dados())


def test_cor_invalida_erro(db, usuario):
    with pytest.raises(ErroValidacao, match="Cor inválida."):
        service.criar_atividades(db, usuario.id, SEMANA, [0], dados(cor="roxo-neon"))


def test_listar_semana_ordena(db, usuario):
    service.criar_atividades(db, usuario.id, SEMANA, [1], dados("Estudos", (19, 0), (21, 0)))
    service.criar_atividades(db, usuario.id, SEMANA, [1], dados("Almoço", (12, 0), (13, 0)))
    service.criar_atividades(db, usuario.id, SEMANA, [0], dados("Trabalho"))
    service.criar_atividades(db, usuario.id, SEMANA_ANTERIOR, [0], dados("Antiga"))
    titulos = [a.titulo for a in service.listar_semana(db, usuario.id, date(2026, 10, 22))]
    assert titulos == ["Trabalho", "Almoço", "Estudos"]


def test_listar_dia(db, usuario):
    service.criar_atividades(db, usuario.id, SEMANA, [0, 1], dados())
    assert len(service.listar_dia(db, usuario.id, date(2026, 10, 20))) == 1


def _grupo_seg_a_sex(db, usuario):
    return service.criar_atividades(db, usuario.id, SEMANA, [0, 1, 2, 3, 4], dados())


def test_editar_so_este_dia_tira_do_grupo(db, usuario):
    criadas = _grupo_seg_a_sex(db, usuario)
    quarta = criadas[2]
    service.atualizar_atividade(db, usuario.id, quarta.id, dados(inicio=(9, 0), fim=(12, 0)), "dia")
    db.refresh(quarta)
    assert quarta.hora_inicio == time(9, 0)
    assert quarta.grupo_id is None
    outras = [a for a in service.listar_semana(db, usuario.id, SEMANA) if a.id != quarta.id]
    assert all(a.hora_inicio == time(8, 0) and a.grupo_id == criadas[0].grupo_id for a in outras)


def test_editar_todos_os_dias_do_grupo(db, usuario):
    criadas = _grupo_seg_a_sex(db, usuario)
    service.atualizar_atividade(db, usuario.id, criadas[2].id, dados(titulo="Avulsa"), "dia")
    service.atualizar_atividade(db, usuario.id, criadas[0].id, dados(titulo="Escritório", cor="areia"), "grupo")
    semana = {a.data.day: a for a in service.listar_semana(db, usuario.id, SEMANA)}
    assert [semana[d].titulo for d in (19, 20, 22, 23)] == ["Escritório"] * 4
    assert all(semana[d].cor == "areia" for d in (19, 20, 22, 23))
    assert semana[21].titulo == "Avulsa"


def test_editar_grupo_nao_muda_datas(db, usuario):
    criadas = _grupo_seg_a_sex(db, usuario)
    service.atualizar_atividade(db, usuario.id, criadas[0].id, dados(titulo="X"), "grupo")
    assert [a.data.day for a in service.listar_semana(db, usuario.id, SEMANA)] == [19, 20, 21, 22, 23]


def test_editar_com_dados_invalidos_nao_altera(db, usuario):
    [a] = service.criar_atividades(db, usuario.id, SEMANA, [0], dados())
    with pytest.raises(ErroValidacao):
        service.atualizar_atividade(db, usuario.id, a.id, dados(inicio=(13, 0), fim=(12, 0)), "dia")
    db.refresh(a)
    assert a.hora_inicio == time(8, 0)


def test_excluir_grupo(db, usuario):
    criadas = _grupo_seg_a_sex(db, usuario)
    service.criar_atividades(db, usuario.id, SEMANA, [0], dados("Outra"))
    service.excluir_atividade(db, usuario.id, criadas[1].id, "grupo")
    assert [a.titulo for a in service.listar_semana(db, usuario.id, SEMANA)] == ["Outra"]


def test_excluir_so_um_dia(db, usuario):
    criadas = _grupo_seg_a_sex(db, usuario)
    service.excluir_atividade(db, usuario.id, criadas[1].id, "dia")
    assert [a.data.day for a in service.listar_semana(db, usuario.id, SEMANA)] == [19, 21, 22, 23]


def test_copiar_semana_anterior(db, usuario):
    trabalho = service.criar_atividades(db, usuario.id, SEMANA_ANTERIOR, [0, 1], dados(descricao="foco", cor="verde"))
    almoco = service.criar_atividades(db, usuario.id, SEMANA_ANTERIOR, [0, 1], dados("Almoço", (12, 0), (13, 0)))
    service.criar_atividades(db, usuario.id, SEMANA_ANTERIOR, [4], dados("Feira", (10, 0), (11, 0)))

    assert service.copiar_semana_anterior(db, usuario.id, date(2026, 10, 21)) == 5

    copiadas = service.listar_semana(db, usuario.id, SEMANA)
    assert sorted((a.data.day, a.titulo) for a in copiadas) == [
        (19, "Almoço"), (19, "Trabalho"), (20, "Almoço"), (20, "Trabalho"), (23, "Feira"),
    ]
    trabalho_novo = [a for a in copiadas if a.titulo == "Trabalho"]
    almoco_novo = [a for a in copiadas if a.titulo == "Almoço"]
    assert trabalho_novo[0].descricao == "foco" and trabalho_novo[0].cor == "verde"
    assert len({a.grupo_id for a in trabalho_novo}) == 1
    assert len({a.grupo_id for a in almoco_novo}) == 1
    assert trabalho_novo[0].grupo_id != almoco_novo[0].grupo_id
    assert trabalho_novo[0].grupo_id not in {trabalho[0].grupo_id, almoco[0].grupo_id}
    assert [a for a in copiadas if a.titulo == "Feira"][0].grupo_id is None
    # A semana de origem continua intacta.
    assert len(service.listar_semana(db, usuario.id, SEMANA_ANTERIOR)) == 5


def test_copiar_substitui_semana_atual(db, usuario):
    service.criar_atividades(db, usuario.id, SEMANA_ANTERIOR, [0], dados())
    service.criar_atividades(db, usuario.id, SEMANA, [2], dados("Avulsa"))
    service.copiar_semana_anterior(db, usuario.id, SEMANA)
    assert [a.titulo for a in service.listar_semana(db, usuario.id, SEMANA)] == ["Trabalho"]


def test_copiar_semana_anterior_vazia_erro(db, usuario):
    service.criar_atividades(db, usuario.id, SEMANA, [2], dados("Avulsa"))
    with pytest.raises(ErroValidacao, match="A semana anterior não tem atividades."):
        service.copiar_semana_anterior(db, usuario.id, SEMANA)
    assert len(service.listar_semana(db, usuario.id, SEMANA)) == 1


def test_copiar_nao_mexe_em_outro_usuario(db, usuario, outro_usuario):
    service.criar_atividades(db, outro_usuario.id, SEMANA_ANTERIOR, [0], dados("Dela"))
    service.criar_atividades(db, outro_usuario.id, SEMANA, [3], dados("Dela hoje"))
    service.criar_atividades(db, usuario.id, SEMANA_ANTERIOR, [0], dados("Minha"))
    service.copiar_semana_anterior(db, usuario.id, SEMANA)
    assert [a.titulo for a in service.listar_semana(db, outro_usuario.id, SEMANA)] == ["Dela hoje"]
    assert [a.titulo for a in service.listar_semana(db, usuario.id, SEMANA)] == ["Minha"]


def test_nao_acessa_atividade_de_outro_usuario(db, usuario, outro_usuario):
    [dela] = service.criar_atividades(db, outro_usuario.id, SEMANA, [0], dados("Dela"))
    with pytest.raises(NaoEncontrado):
        service.obter_atividade(db, usuario.id, dela.id)
    with pytest.raises(NaoEncontrado):
        service.atualizar_atividade(db, usuario.id, dela.id, dados("Hack"), "dia")
    with pytest.raises(NaoEncontrado):
        service.excluir_atividade(db, usuario.id, dela.id, "grupo")
    assert service.listar_semana(db, usuario.id, SEMANA) == []
    db.refresh(dela)
    assert dela.titulo == "Dela"
