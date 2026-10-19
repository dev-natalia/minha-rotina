from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.contadores import service
from app.contadores.models import Lancamento
from app.contadores.service import DadosContador
from app.erros import ErroValidacao, NaoEncontrado


def cigarros(**extra) -> DadosContador:
    return DadosContador(nome="Cigarros", unidade="unidade", **extra)


def test_criar_contador_basico(db, usuario):
    c = service.criar_contador(db, usuario.id, cigarros())
    assert (c.nome, c.unidade, c.passo, c.ativo, c.posicao) == ("Cigarros", "unidade", 1, True, 1)
    agua = service.criar_contador(db, usuario.id, DadosContador("Água", "copo"))
    assert agua.posicao == 2


def test_posicao_e_por_usuario(db, usuario, outro_usuario):
    service.criar_contador(db, outro_usuario.id, cigarros())
    assert service.criar_contador(db, usuario.id, cigarros()).posicao == 1


def test_criar_normaliza_textos(db, usuario):
    c = service.criar_contador(db, usuario.id, DadosContador("  Estudo  ", "  minuto ", passo=15))
    assert (c.nome, c.unidade, c.passo) == ("Estudo", "minuto", 15)


def test_valor_inicial_vira_ajuste(db, usuario):
    quando = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    c = service.criar_contador(db, usuario.id, DadosContador("Treinos", "sessão"), valor_inicial=40, valor_inicial_em=quando)
    [ajuste] = db.scalars(select(Lancamento).where(Lancamento.contador_id == c.id)).all()
    assert (ajuste.tipo, ajuste.quantidade, ajuste.ocorrido_em, ajuste.usuario_id) == ("ajuste", 40, quando, usuario.id)


def test_meta_completa(db, usuario):
    c = service.criar_contador(db, usuario.id, cigarros(meta_valor=5, meta_periodo="dia", meta_sentido="maximo"))
    assert (c.meta_valor, c.meta_periodo, c.meta_sentido) == (5, "dia", "maximo")


def test_meta_incompleta_erro(db, usuario):
    with pytest.raises(ErroValidacao, match="Para definir uma meta, preencha valor, período e sentido."):
        service.criar_contador(db, usuario.id, cigarros(meta_valor=5))


def test_meta_com_periodo_invalido_erro(db, usuario):
    with pytest.raises(ErroValidacao):
        service.criar_contador(db, usuario.id, cigarros(meta_valor=5, meta_periodo="semana", meta_sentido="maximo"))


def test_nome_e_unidade_obrigatorios(db, usuario):
    with pytest.raises(ErroValidacao, match="Informe um nome."):
        service.criar_contador(db, usuario.id, DadosContador("  ", "copo"))
    with pytest.raises(ErroValidacao, match="Informe a unidade."):
        service.criar_contador(db, usuario.id, DadosContador("Água", ""))


def test_passo_zero_erro(db, usuario):
    with pytest.raises(ErroValidacao):
        service.criar_contador(db, usuario.id, cigarros(passo=0))


def test_atualizar_contador(db, usuario):
    c = service.criar_contador(db, usuario.id, cigarros())
    service.atualizar_contador(db, usuario.id, c.id, DadosContador("Cigarros", "unidade", passo=2, meta_valor=3, meta_periodo="dia", meta_sentido="maximo"))
    db.refresh(c)
    assert (c.passo, c.meta_valor) == (2, 3)


def test_desativar_some_da_lista_ativa_mas_aparece_em_todos(db, usuario):
    c = service.criar_contador(db, usuario.id, cigarros())
    service.criar_contador(db, usuario.id, DadosContador("Água", "copo"))
    service.definir_ativo(db, usuario.id, c.id, False)
    assert [x.nome for x in service.listar_contadores(db, usuario.id)] == ["Água"]
    assert [x.nome for x in service.listar_contadores(db, usuario.id, ativos=False)] == ["Cigarros"]
    assert [x.nome for x in service.listar_contadores(db, usuario.id, ativos=None)] == ["Cigarros", "Água"]


def test_contador_de_outro_usuario_nao_encontrado(db, usuario, outro_usuario):
    dela = service.criar_contador(db, outro_usuario.id, cigarros())
    with pytest.raises(NaoEncontrado):
        service.obter_contador(db, usuario.id, dela.id)
    with pytest.raises(NaoEncontrado):
        service.atualizar_contador(db, usuario.id, dela.id, DadosContador("Hack", "x"))
    with pytest.raises(NaoEncontrado):
        service.definir_ativo(db, usuario.id, dela.id, False)
    assert service.listar_contadores(db, usuario.id, ativos=None) == []


def test_banco_rejeita_lancamento_com_usuario_inconsistente(db, usuario, outro_usuario):
    dela = service.criar_contador(db, outro_usuario.id, cigarros())
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(Lancamento(contador_id=dela.id, usuario_id=usuario.id, quantidade=1,
                              ocorrido_em=datetime.now(timezone.utc), tipo="normal"))
            db.flush()


def test_banco_rejeita_quantidade_zero(db, usuario):
    c = service.criar_contador(db, usuario.id, cigarros())
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(Lancamento(contador_id=c.id, usuario_id=usuario.id, quantidade=0,
                              ocorrido_em=datetime.now(timezone.utc), tipo="normal"))
            db.flush()


@pytest.mark.parametrize("valor", ["abc", "0", "-3", "99999999999", "", "1.5"])
def test_ler_inteiro_rejeita(valor):
    with pytest.raises(ErroValidacao, match="Quantidade: informe um número inteiro entre 1 e 1000000."):
        service.ler_inteiro(valor, "Quantidade")


def test_ler_inteiro_aceita():
    assert service.ler_inteiro(" 30 ", "Quantidade") == 30
    assert service.ler_inteiro("0", "Valor inicial", minimo=0) == 0
