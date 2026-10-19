# minha-rotina v1 — Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar a v1 do minha-rotina: um app web/PWA com vários usuários isolados, rotina semanal por semana, contadores com lançamentos individuais, histórico corrigível e painel inicial.

**Architecture:** Monólito FastAPI que renderiza HTML no servidor (Jinja2), com HTMX para atualizações parciais (contadores) e CSS escrito à mão. Cada área (auth, rotina, contadores, histórico, painel) é um pacote com `models.py` / `service.py` / `routes.py`; a lógica de negócio fica nos services (testados direto contra PostgreSQL), as rotas só validam forms, chamam services e renderizam. Totais são sempre consultas SQL sobre `lancamentos`.

**Tech Stack:** Python 3.14, uv, FastAPI, Jinja2, HTMX 2.0.4 (arquivo local), SQLAlchemy 2 (síncrono) + psycopg 3, Alembic, argon2-cffi, pydantic-settings, pytest + httpx (TestClient), PostgreSQL 17 (Neon em produção, Docker local), Fly.io, Cloudflare R2.

**Spec:** `docs/superpowers/specs/2026-10-19-minha-rotina-v1-design.md` — leia antes de qualquer tarefa. Decisões citadas como "spec §N" estão lá.

## Global Constraints

- Toda a interface em **português do Brasil**. Identificadores de domínio em português, como no spec (`usuarios`, `atividades_planejadas`, `contadores`, `lancamentos`).
- Sem framework JS, sem bundler, sem Node. JS só em `app/static/js/app.js` (vanilla) e `app/static/vendor/htmx.min.js` (htmx.org **2.0.4**, baixado do cdnjs e versionado no repo).
- Instantes gravados como `timestamptz` em UTC; dia/mês/ano calculados no `fuso_horario` do usuário; **dia vira à meia-noite**; **semana começa na segunda**. Troca de fuso recalcula tudo no fuso atual (spec §5).
- **Isolamento**: toda query filtra por `usuario_id` do usuário logado; id de outro usuário → **404**.
- Toda rota que altera dados é `POST` e exige CSRF (header `X-CSRF-Token` ou campo `csrf_token`), senão **403**.
- Forms são lidos como `str` e validados nos services; erro de validação re-renderiza o form com mensagem em português e os valores digitados (nunca JSON 422 para o usuário).
- Quantidades e passos são **inteiros ≥ 1**. Totais vêm de `SUM(quantidade)` dos lançamentos não cancelados — nunca de um campo acumulado.
- Lançamentos nunca são apagados (`DELETE` proibido em `lancamentos`); cancelar = `cancelado_em`; corrigir = cancelar + novo com `substitui_id`.
- Visual "Calmo" (spec §10): fundo `#f6f3ee`, texto `#2b2a27`, acento `#4f7d55`/`#3f6b45`, bordas `#e6e0d6`, títulos em serifa (Georgia), contraste AA, alvos de toque ≥ 44px.
- Acessibilidade (spec §11) faz parte do "pronto" de toda tarefa com template: rótulos acessíveis, foco visível, teclado, `aria-live` para totais, `prefers-reduced-motion`.
- Sem offline: service worker só faz cache de estáticos e da página `/offline`.
- Fora de escopo (não implementar): hábitos, tarefas, IA, gráficos, semana/total-geral no seletor de contadores, modo escuro, cadastro pela UI.

## Review Focus

1. **Toque duplo / rede lenta no `+`** — o mesmo toque enviado duas vezes deve gerar um único lançamento (Task 9: `test_registrar_mesmo_token_nao_duplica`; Task 10: `test_mais_com_mesmo_token_duas_vezes`).
2. **Lançamentos perto da meia-noite** — 23:30 em São Paulo é 02:30 UTC do dia seguinte; deve contar no dia local (Task 2: `test_limites_dia_em_sao_paulo`; Task 9: `test_total_dia_respeita_fuso`).
3. **URL com id de outro usuário** — qualquer rota com id alheio responde 404 e não altera nada (Task 7: `test_editar_atividade_de_outro_usuario_404`; Task 10: `test_mais_em_contador_de_outro_usuario_404`; Task 11: `test_cancelar_lancamento_de_outro_usuario_404`).
4. **Sessão expirada durante um clique HTMX** — a página toda deve ir para `/login`, não injetar o form de login dentro do card (Task 4: `test_htmx_sem_sessao_recebe_hx_redirect`).
5. **Entrada inválida em forms** (quantidade `0`, `-3`, `abc`, `99999999999`; fim ≤ início; título vazio) — mensagem em português com os valores preservados, status 400, nada gravado (Task 7: `test_criar_atividade_fim_antes_do_inicio_mostra_erro`; Task 10: `test_quantidade_invalida_nao_registra`).

---

## Estrutura de arquivos

```
pyproject.toml, uv.lock, .python-version (3.14), .gitignore, .env.example
docker-compose.yml            # Postgres 17 local (dev + testes)
alembic.ini, alembic/env.py, alembic/versions/
Dockerfile, fly.toml, Dockerfile.backup, scripts/backup.sh
docs/operacao.md              # deploy, criar usuário, backup e restauração
app/
  main.py        # create_app(): rotas, estáticos, handlers de erro
  config.py      # Settings + get_settings()
  db.py          # Base, engine, SessionLocal, get_db()
  tempo.py       # agora_utc, limites de período, semana, formatação pt-BR
  erros.py       # ErroValidacao, NaoEncontrado
  web.py         # templates, render(), csrf
  cli.py         # python -m app.cli ...
  auth/      models.py service.py seguranca.py deps.py routes.py
  rotina/    models.py service.py layout.py routes.py
  contadores/ models.py service.py lancamentos.py routes.py
  historico/ routes.py
  painel/    routes.py
  pwa/       routes.py          # /manifest.webmanifest, /sw.js, /offline
  templates/ base.html, _nav.html, auth/, conta/, rotina/, contadores/, historico/, painel/, offline.html
  static/    css/app.css, js/app.js, vendor/htmx.min.js, icons/
tests/
  conftest.py, test_tempo.py, auth/, rotina/, contadores/, historico/, painel/, pwa/
```

---

### Task 1: Esqueleto do projeto, banco e harness de testes

**Files:**
- Create: `pyproject.toml`, `.python-version`, `.gitignore`, `.env.example`, `docker-compose.yml`, `alembic.ini`, `alembic/env.py`, `app/__init__.py`, `app/config.py`, `app/db.py`, `app/erros.py`, `app/main.py`, `tests/conftest.py`, `tests/test_saude.py`

**Interfaces:**
- Produces:
  - `app.config.Settings` (pydantic-settings, lê `.env`): `database_url: str`, `cookie_secure: bool = True`, `dias_sessao: int = 90`, `ambiente: str = "dev"`; `get_settings() -> Settings` (cacheado).
  - `app.db.Base(DeclarativeBase)`, `app.db.engine`, `app.db.SessionLocal`, `app.db.get_db() -> Iterator[Session]`.
  - `app.erros.ErroValidacao(Exception)` com atributo `mensagem: str`; `app.erros.NaoEncontrado(Exception)`.
  - `app.main.create_app() -> FastAPI`; `app.main.app = create_app()`. Handler de `NaoEncontrado` → 404 HTML simples.
  - Fixtures em `tests/conftest.py`: `db` (Session dentro de transação revertida ao fim de cada teste, `join_transaction_mode="create_savepoint"`), `cliente` (`TestClient` com `get_db` sobrescrito para usar a mesma Session). Banco de teste em `TEST_DATABASE_URL`; schema criado uma vez por sessão via `alembic upgrade head`.

- [ ] **Step 1:** `git init`; `.gitignore` com `.venv/`, `__pycache__/`, `.env`, `.superpowers/`, `*.dump`. `uv init --app` ajustado; dependências: `fastapi`, `uvicorn[standard]`, `jinja2`, `python-multipart`, `sqlalchemy>=2`, `psycopg[binary]>=3`, `alembic`, `argon2-cffi`, `pydantic-settings`; dev: `pytest`, `httpx`. `docker-compose.yml` com `postgres:17`, porta 5432, bancos `rotina` e `rotina_test` (script de init). `.env.example` com `DATABASE_URL=postgresql+psycopg://rotina:rotina@localhost:5432/rotina` e `TEST_DATABASE_URL=...rotina_test`, `COOKIE_SECURE=false`.
- [ ] **Step 2: Write the failing test** `tests/test_saude.py`:

```python
def test_healthz(cliente):
    r = cliente.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}

def test_healthz_toca_o_banco(db):
    from sqlalchemy import text
    assert db.execute(text("select 1")).scalar() == 1
```

- [ ] **Step 3:** Run `docker compose up -d` then `uv run pytest tests/test_saude.py -v` → FAIL (`/healthz` 404 ou import error).
- [ ] **Step 4:** Implementar `config.py`, `db.py`, `erros.py`, `main.py` (`GET /healthz` executa `select 1` e retorna `{"ok": True}`), `alembic/env.py` lendo `get_settings().database_url` e `Base.metadata` (importando todos os `models` dos pacotes — manter a lista em `app/models.py` que importa cada módulo de models; criar esse arquivo agora, vazio de imports).
- [ ] **Step 5:** Run `uv run pytest -v` → PASS.
- [ ] **Step 6: Commit** — inclua `docs/` (spec e este plano).

```bash
git add -A
git commit -m "chore: esqueleto FastAPI, banco e harness de testes"
```

---

### Task 2: Tempo e fuso

**Files:**
- Create: `app/tempo.py`, `tests/test_tempo.py`

**Interfaces:**
- Produces (todas puras, exceto `agora_utc`):
  - `Periodo = Literal["dia", "mes", "ano"]`
  - `agora_utc() -> datetime` — único ponto de "agora" do app; testes fazem `monkeypatch.setattr("app.tempo.agora_utc", ...)`. Código sempre chama `tempo.agora_utc()` (via módulo) para o patch funcionar.
  - `local(instante: datetime, fuso: str) -> datetime`
  - `hoje_local(fuso: str, agora: datetime) -> date`
  - `limites_periodo(periodo: Periodo, agora: datetime, fuso: str) -> tuple[datetime, datetime]` — `[inicio, fim)` em UTC do dia/mês/ano local que contém `agora`.
  - `limites_datas(de: date, ate: date, fuso: str) -> tuple[datetime, datetime]` — `[de 00:00 local, (ate+1) 00:00 local)` em UTC.
  - `inicio_semana(d: date) -> date` — segunda-feira da semana de `d`.
  - `fuso_valido(fuso: str) -> bool` — via `zoneinfo.available_timezones()`.
  - `data_por_extenso(d: date) -> str` — ex.: `"Segunda-feira, 19 de outubro"` (nomes fixos em pt-BR, sem depender de locale).
  - `NOMES_DIAS_CURTOS = ("S", "T", "Q", "Q", "S", "S", "D")`, `NOMES_DIAS = ("Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo")`.

- [ ] **Step 1: Write the failing tests**

```python
from datetime import date, datetime, timezone as tz
from app import tempo

SP = "America/Sao_Paulo"

def test_limites_dia_em_sao_paulo():
    agora = datetime(2026, 10, 20, 2, 30, tzinfo=tz.utc)  # 23:30 do dia 19 em SP
    ini, fim = tempo.limites_periodo("dia", agora, SP)
    assert ini == datetime(2026, 10, 19, 3, 0, tzinfo=tz.utc)
    assert fim == datetime(2026, 10, 20, 3, 0, tzinfo=tz.utc)

def test_limites_mes_e_ano():
    agora = datetime(2026, 10, 19, 15, 0, tzinfo=tz.utc)
    assert tempo.limites_periodo("mes", agora, SP) == (
        datetime(2026, 10, 1, 3, tzinfo=tz.utc), datetime(2026, 11, 1, 3, tzinfo=tz.utc))
    assert tempo.limites_periodo("ano", agora, SP) == (
        datetime(2026, 1, 1, 3, tzinfo=tz.utc), datetime(2027, 1, 1, 3, tzinfo=tz.utc))

def test_inicio_semana_e_segunda():
    assert tempo.inicio_semana(date(2026, 10, 25)) == date(2026, 10, 19)  # domingo
    assert tempo.inicio_semana(date(2026, 10, 19)) == date(2026, 10, 19)

def test_limites_datas_inclui_o_ultimo_dia():
    ini, fim = tempo.limites_datas(date(2026, 10, 1), date(2026, 10, 31), SP)
    assert fim == datetime(2026, 11, 1, 3, tzinfo=tz.utc)

def test_data_por_extenso():
    assert tempo.data_por_extenso(date(2026, 10, 19)) == "Segunda-feira, 19 de outubro"

def test_fuso_valido():
    assert tempo.fuso_valido(SP) and not tempo.fuso_valido("Marte/Base")
```

- [ ] **Step 2:** Run `uv run pytest tests/test_tempo.py -v` → FAIL (módulo ausente).
- [ ] **Step 3:** Implementar `app/tempo.py` com `zoneinfo`.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5: Commit** `feat: utilitários de tempo e fuso`

---

### Task 3: Usuários, senha e CLI

**Files:**
- Create: `app/auth/__init__.py`, `app/auth/models.py`, `app/auth/seguranca.py`, `app/auth/service.py`, `app/cli.py`, migração Alembic `usuarios`, `tests/auth/test_usuarios.py`, `tests/auth/test_cli.py`
- Modify: `app/models.py` (importar `app.auth.models`), `tests/conftest.py` (fixtures `usuario`, `outro_usuario`)

**Interfaces:**
- Produces:
  - Model `Usuario` (`usuarios`): `id: int`, `email: str` (único, gravado em minúsculas), `nome: str`, `senha_hash: str`, `fuso_horario: str = "America/Sao_Paulo"`, `ativo: bool = True`, `criado_em: datetime`.
  - `seguranca.hash_senha(senha: str) -> str`, `seguranca.verificar_senha(hash: str, senha: str) -> bool` (argon2-cffi `PasswordHasher`).
  - `service.criar_usuario(db, email: str, nome: str, senha: str) -> Usuario` — normaliza email (strip + lower); `ErroValidacao` se email sem `@`, nome vazio, senha < 8 caracteres ou email já existe (`"Já existe um usuário com este email."`).
  - `service.redefinir_senha(db, email: str, senha: str) -> None`, `service.desativar_usuario(db, email: str) -> None` (ambos `NaoEncontrado` se email não existe).
  - `service.atualizar_fuso(db, usuario: Usuario, fuso: str) -> None` (`ErroValidacao("Fuso horário inválido.")`).
  - CLI: `uv run python -m app.cli criar-usuario --email X --nome Y` (senha via `getpass`, digitada duas vezes), `redefinir-senha --email X`, `desativar-usuario --email X`. argparse; imprime mensagem em pt-BR; exit code 1 em erro.
  - Fixtures: `usuario` (`ana@example.com`, nome "Ana", senha `"senha-segura-1"`), `outro_usuario` (`bia@example.com`).

- [ ] **Step 1: Write the failing tests** (`test_usuarios.py`): `test_criar_usuario_normaliza_email` (`" Ana@Example.COM "` → `"ana@example.com"`, `senha_hash != senha`, `verificar_senha` True); `test_email_duplicado_erro` (mesmo email com outra caixa → `ErroValidacao`); `test_senha_curta_erro` (`"1234567"`); `test_redefinir_senha` (nova senha verifica, antiga não); `test_desativar_usuario` (`ativo is False`); `test_atualizar_fuso_invalido`. (`test_cli.py`): `test_cli_criar_usuario` chamando `app.cli.main(["criar-usuario", "--email", "c@x.com", "--nome", "C"])` com `getpass` monkeypatched para `"senha-segura-1"` e o `SessionLocal` do CLI apontando para a Session `db` do teste → usuário existe; `test_cli_senhas_diferentes_falha` → retorna 1, nada criado.
- [ ] **Step 2:** Run `uv run pytest tests/auth -v` → FAIL.
- [ ] **Step 3:** Implementar models + migração (`alembic revision --autogenerate -m "usuarios"`, revisar), seguranca, service, cli (`main(argv: list[str] | None = None) -> int`; usa `app.cli.abrir_sessao()` que os testes podem substituir).
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5: Commit** `feat: usuários, hash de senha e CLI de contas`

---

### Task 4: Login, sessão, CSRF e layout base

**Files:**
- Create: `app/auth/deps.py`, `app/auth/routes.py`, `app/web.py`, `app/templates/base.html`, `app/templates/_nav.html`, `app/templates/auth/login.html`, `app/templates/conta/conta.html`, `app/static/css/app.css`, `app/static/js/app.js`, `app/static/vendor/htmx.min.js`, migração `sessoes` e `tentativas_login`, `tests/auth/test_login.py`, `tests/auth/test_conta.py`
- Modify: `app/auth/models.py`, `app/auth/service.py`, `app/main.py`, `tests/conftest.py`

**Interfaces:**
- Consumes: Task 3 (`Usuario`, `verificar_senha`, `atualizar_fuso`), Task 2 (`agora_utc`).
- Produces:
  - Models `Sessao` (`sessoes`): `id`, `token_hash: str` (sha256 hex, único), `usuario_id`, `csrf_token: str`, `criado_em`, `expira_em`. `TentativaLogin` (`tentativas_login`): `id`, `email`, `ip`, `criado_em`.
  - `service.autenticar(db, email: str, senha: str, ip: str) -> Usuario | None` — falha registra tentativa; com ≥ 5 falhas para o email **ou** ≥ 20 para o IP nos últimos 15 minutos, levanta `MuitasTentativas` sem verificar senha. Usuário inativo → `None`.
  - `service.criar_sessao(db, usuario) -> tuple[str, Sessao]` (token = `secrets.token_urlsafe(32)`; guarda só o hash; expira em `dias_sessao`).
  - `service.obter_sessao(db, token: str) -> Sessao | None` — `None` se expirada ou usuário inativo; se `expira_em` foi renovada há mais de 1 dia, renova para `agora + dias_sessao`.
  - `service.encerrar_sessao(db, token: str) -> None`.
  - `deps.usuario_atual(request, db) -> Usuario` — lê cookie `sessao`; sem sessão levanta `NaoAutenticado`. Handler: request com header `HX-Request` → 200 vazio com header `HX-Redirect: /login`; senão 303 para `/login`. Guarda a `Sessao` em `request.state.sessao`.
  - `deps.exigir_csrf(request) -> None` — dependency para todo POST autenticado; compara header `X-CSRF-Token` ou campo de form `csrf_token` com `request.state.sessao.csrf_token` via `secrets.compare_digest`; diferente → 403.
  - `web.templates` (Jinja2Templates em `app/templates`), `web.render(request, nome: str, contexto: dict, status: int = 200) -> HTMLResponse` — injeta `usuario` e `csrf_token` (se houver sessão) e `request`.
  - Rotas: `GET /login`, `POST /login` (campos `email`, `senha`; sucesso → cookie `sessao` HttpOnly, `SameSite=Lax`, `Secure=settings.cookie_secure`, `max_age=dias_sessao*86400`, redirect 303 `/`; erro → 400 com `"Email ou senha incorretos."` e email preservado; `MuitasTentativas` → 429 com `"Muitas tentativas. Tente de novo em alguns minutos."`), `POST /sair` (CSRF; apaga sessão e cookie), `GET /conta`, `POST /conta/fuso`.
  - `base.html`: `<html lang="pt-BR">`, `<body hx-headers='{"X-CSRF-Token": "{{ csrf_token }}"}'>`, link para manifest, região `<div id="anuncio" aria-live="polite" class="sr-only">`, `{% block conteudo %}`, inclui `_nav.html` com Início · Rotina · Contadores · Histórico (`aria-current="page"` na atual) e ícone de conta no cabeçalho. Barra inferior < 900px, lateral ≥ 900px.
  - `app.css`: variáveis CSS do estilo Calmo (Global Constraints), `.sr-only`, foco visível (`:focus-visible` com contorno verde 3px), botões ≥ 44px, `@media (prefers-reduced-motion: reduce)` desliga transições.
  - Fixtures: `cliente_logado` (TestClient logado como `usuario`, com atributo `csrf: str`), `post(cliente, url, dados: dict, htmx: bool = False)` helper que injeta `csrf_token`.

- [ ] **Step 1: Write the failing tests** — `test_login.py`:
  - `test_login_correto_redireciona_e_define_cookie` (303 para `/`, cookie `sessao` presente)
  - `test_login_senha_errada` (400, texto `"Email ou senha incorretos."`, valor do email no HTML)
  - `test_login_usuario_inativo_falha`
  - `test_bloqueio_apos_5_falhas` (5 erradas → 6ª com senha certa → 429)
  - `test_rota_protegida_sem_sessao_redireciona` (`GET /conta` → 303 `/login`)
  - `test_htmx_sem_sessao_recebe_hx_redirect` (`GET /conta` com `HX-Request: true` → header `HX-Redirect == "/login"`)
  - `test_sessao_expirada_redireciona` (monkeypatch `agora_utc` 91 dias à frente)
  - `test_post_sem_csrf_403` (`POST /sair` sem token)
  - `test_sair_encerra_sessao` (depois `GET /conta` → 303)
  — `test_conta.py`: `test_conta_mostra_email`, `test_trocar_fuso` (`America/Manaus` gravado), `test_trocar_fuso_invalido_mostra_erro` (400, `"Fuso horário inválido."`).
- [ ] **Step 2:** Run `uv run pytest tests/auth -v` → FAIL.
- [ ] **Step 3:** Implementar models + migração, service, deps, web, rotas, templates, CSS base. Baixar `htmx.min.js` 2.0.4 de `https://cdnjs.cloudflare.com/ajax/libs/htmx/2.0.4/htmx.min.js` para `app/static/vendor/`. Registrar `RequestValidationError` → 400 HTML genérico (`"Dados inválidos."`) como rede de proteção.
- [ ] **Step 4:** Run `uv run pytest -v` → PASS.
- [ ] **Step 5:** Verificação manual: `uv run uvicorn app.main:app --reload`, criar usuário pelo CLI, logar, ver nav em 375px e 1280px, navegar só com Tab.
- [ ] **Step 6: Commit** `feat: login, sessão, CSRF e layout base`

---

### Task 5: PWA (manifest, service worker, offline)

**Files:**
- Create: `app/pwa/__init__.py`, `app/pwa/routes.py`, `app/static/manifest.webmanifest`, `app/static/sw.js`, `app/templates/offline.html`, `app/static/icons/icon-192.png`, `icon-512.png`, `icon-maskable-512.png`, `tests/pwa/test_pwa.py`
- Modify: `app/main.py`, `app/templates/base.html`, `app/static/js/app.js`

**Interfaces:**
- Produces: `GET /manifest.webmanifest` (`application/manifest+json`), `GET /sw.js` (`application/javascript`, header `Service-Worker-Allowed: /`, `Cache-Control: no-cache`), `GET /offline` (público). `app.js` registra o service worker.
- Manifest: `name: "minha-rotina"`, `short_name: "Rotina"`, `start_url: "/"`, `scope: "/"`, `display: "standalone"`, `background_color: "#f6f3ee"`, `theme_color: "#4f7d55"`, `lang: "pt-BR"`, ícones 192/512 + maskable.
- `sw.js`: no `install` faz cache de `/offline`, `app.css`, `app.js`, `htmx.min.js`, ícones (nome do cache versionado `rotina-v1`); `fetch` de navegação: rede primeiro, e só em falha de rede responde `/offline`; estáticos: cache primeiro; **nunca** cacheia respostas HTML de dados.

- [ ] **Step 1: Write the failing tests:** `test_manifest` (status 200, content-type, `display == "standalone"`, `start_url == "/"`), `test_sw_servido_na_raiz` (header `Service-Worker-Allowed == "/"`), `test_offline_publico` (200 sem login, contém `"Sem conexão"`).
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implementar (ícones simples provisórios: quadrado `#4f7d55` com "R" branco em serifa). **Step 4:** Run → PASS.
- [ ] **Step 5:** Verificação: Chrome DevTools → Application → Manifest sem erros de instalabilidade (em `localhost`).
- [ ] **Step 6: Commit** `feat: base PWA`

---

### Task 6: Rotina — modelo e service

**Files:**
- Create: `app/rotina/__init__.py`, `app/rotina/models.py`, `app/rotina/service.py`, migração `atividades_planejadas`, `tests/rotina/test_service.py`
- Modify: `app/models.py`

**Interfaces:**
- Consumes: `ErroValidacao`, `NaoEncontrado`, `tempo.inicio_semana`.
- Produces:
  - Model `AtividadePlanejada` (`atividades_planejadas`): `id`, `usuario_id` (FK, `ON DELETE CASCADE`), `data: date`, `hora_inicio: time`, `hora_fim: time`, `titulo: str` (≤ 120), `descricao: str | None`, `cor: str | None`, `grupo_id: UUID | None`, `criado_em`, `atualizado_em`. `CHECK (hora_fim > hora_inicio)`. Índice `(usuario_id, data)`.
  - `CORES = ("verde", "areia", "lavanda", "azul", "rosa")`.
  - `@dataclass DadosAtividade(titulo: str, hora_inicio: time, hora_fim: time, descricao: str | None = None, cor: str | None = None)`.
  - `validar_dados(dados) -> DadosAtividade` (strip; título vazio → `"Informe um título."`; fim ≤ início → `"O horário de fim deve ser depois do início."`; cor fora de `CORES` → `"Cor inválida."`; descrição vazia → `None`).
  - `criar_atividades(db, usuario_id: int, semana: date, dias: list[int], dados: DadosAtividade) -> list[AtividadePlanejada]` — `dias` são 0–6 (segunda=0); vazio → `"Escolha pelo menos um dia."`; `semana` normalizada com `inicio_semana`; mais de um dia → mesmo `grupo_id` novo.
  - `listar_semana(db, usuario_id, semana: date) -> list[AtividadePlanejada]` (ordem `data, hora_inicio, titulo`).
  - `listar_dia(db, usuario_id, dia: date) -> list[AtividadePlanejada]`.
  - `obter_atividade(db, usuario_id, atividade_id: int) -> AtividadePlanejada` (`NaoEncontrado` se não existe ou é de outro usuário).
  - `Escopo = Literal["dia", "grupo"]`.
  - `atualizar_atividade(db, usuario_id, atividade_id, dados, escopo: Escopo) -> None` — `"dia"`: atualiza só ela e zera `grupo_id`; `"grupo"`: aplica título/horários/descrição/cor a todas do mesmo `grupo_id` (sem grupo, igual a `"dia"`). Nunca muda `data`.
  - `excluir_atividade(db, usuario_id, atividade_id, escopo: Escopo) -> None`.
  - `copiar_semana_anterior(db, usuario_id, semana: date) -> int` — semana anterior vazia → `ErroValidacao("A semana anterior não tem atividades.")`; senão, numa transação, apaga a semana atual e copia cada atividade com `data + 7 dias`, gerando um `grupo_id` novo por grupo de origem (mapeamento antigo→novo); retorna quantas copiou.

- [ ] **Step 1: Write the failing tests:**
  - `test_criar_para_varios_dias_compartilha_grupo` (dias `[0,1,2,3,4]`, semana `2026-10-21` → 5 atividades de `2026-10-19` a `2026-10-23`, mesmo `grupo_id` não nulo)
  - `test_criar_um_dia_sem_grupo`
  - `test_fim_antes_do_inicio_erro`, `test_titulo_vazio_erro`, `test_sem_dias_erro`
  - `test_editar_so_este_dia_tira_do_grupo` (horário muda só nela; `grupo_id is None`; as outras intactas)
  - `test_editar_todos_os_dias_do_grupo` (as 5 com novo título; a que saiu do grupo antes não muda)
  - `test_excluir_grupo` e `test_excluir_so_um_dia`
  - `test_copiar_semana_anterior` (2 grupos na semana 12/10 → copiados para 19/10 com datas +7 e dois `grupo_id` novos distintos dos originais)
  - `test_copiar_substitui_semana_atual` (atividade avulsa existente em 19/10 some)
  - `test_copiar_semana_anterior_vazia_erro`
  - `test_nao_acessa_atividade_de_outro_usuario` (`obter_atividade` com id do `outro_usuario` → `NaoEncontrado`; `listar_semana` não inclui)
- [ ] **Step 2:** Run `uv run pytest tests/rotina -v` → FAIL.
- [ ] **Step 3:** Implementar models, migração e service.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5: Commit** `feat: modelo e regras da rotina semanal`

---

### Task 7: Rotina — telas (Grade · Dia · Lista) e formulários

**Files:**
- Create: `app/rotina/layout.py`, `app/rotina/routes.py`, `app/templates/rotina/semana.html`, `_grade.html`, `_dia.html`, `_lista.html`, `form.html`, `tests/rotina/test_layout.py`, `tests/rotina/test_routes.py`
- Modify: `app/main.py`, `app/static/css/app.css`, `app/static/js/app.js`

**Interfaces:**
- Consumes: Task 6 service; `usuario_atual`, `exigir_csrf`, `render`; `tempo`.
- Produces:
  - `layout.BlocoLayout` (dataclass): `atividade`, `faixa: int`, `total_faixas: int`.
  - `layout.distribuir_faixas(atividades: list[AtividadePlanejada]) -> list[BlocoLayout]` — para as atividades de **um dia**: grupos de sobreposição transitiva; dentro de cada grupo, guloso por `hora_inicio` atribuindo a menor faixa livre; `total_faixas` = faixas usadas no grupo.
  - `layout.faixa_horaria(atividades) -> tuple[int, int]` — horas inteiras `(min(6, menor início), max(23, maior fim arredondado para cima))`.
  - Rotas (todas com `usuario_atual`; POSTs com `exigir_csrf`):
    - `GET /rotina?semana=AAAA-MM-DD&vista=grade|dia|lista&dia=AAAA-MM-DD` — padrões: semana atual, `vista` do cookie `vista_rotina` (senão `dia`), `dia` = hoje se estiver na semana, senão segunda. `vista` explícita grava o cookie (1 ano). Setas ‹ › (`semana ± 7`) e "Hoje". Semana vazia: texto `"Semana sem rotina"` e botão **Copiar semana anterior**.
    - `POST /rotina/copiar-semana` (`semana`, `confirmar`) — se a semana tem atividades e `confirmar != "sim"`, renderiza confirmação `"Isso vai substituir as atividades desta semana. Continuar?"`; senão copia e redireciona 303 para `/rotina?semana=...`. Erro de semana anterior vazia → mensagem na própria tela.
    - `GET /rotina/atividades/nova?semana=&dia=` → `form.html` (título, início, fim `type="time"`, dias como checkboxes estilizados S T Q Q S S D com `aria-label` do nome completo, já marcando `dia`; descrição; cor como radios com nome acessível).
    - `POST /rotina/atividades` → cria; erro → 400 com form preenchido.
    - `GET /rotina/atividades/{id}/editar` → form sem os dias; se a atividade tem grupo, radios `"Só este dia"` / `"Todos os dias desta semana"` (padrão "Só este dia").
    - `POST /rotina/atividades/{id}` (campos + `escopo`), `POST /rotina/atividades/{id}/excluir` (`escopo`).
  - `app.js`: na página `/rotina` sem cookie `vista_rotina`, se `matchMedia("(min-width: 900px)")` casar, `location.replace` com `vista=grade` (assim o padrão é Dia no celular e Grade no computador); swipe horizontal na vista Dia troca de dia (pointer events, limiar 50px).
  - Grade: 7 colunas, linha por hora em `faixa_horaria`, blocos posicionados por minuto (`top`/`height` em %) e `left/width` por faixa; abreviações no celular. Cada bloco é um link para editar com `aria-label="Trabalho, segunda, 08:00 às 12:00"`.

- [ ] **Step 1: Write the failing tests** — `test_layout.py`: `test_sem_sobreposicao_uma_faixa`; `test_duas_sobrepostas_duas_faixas` (8–10 e 9–11 → faixas 0 e 1, total 2); `test_cadeia_transitiva` (8–10, 9–11, 10:30–12 → total 2, a terceira na faixa 0); `test_faixa_horaria_padrao_e_estendida` (sem atividades → (6, 23); atividade 05:30–07:00 → início 5). — `test_routes.py`:
  - `test_semana_vazia_mostra_copiar` (texto `"Semana sem rotina"`)
  - `test_criar_atividade_redireciona_e_aparece` (POST com dias `0` e `2` → GET da semana contém o título duas vezes na vista lista)
  - `test_criar_atividade_fim_antes_do_inicio_mostra_erro` (400, mensagem, título digitado presente, nada gravado)
  - `test_vista_fica_no_cookie` (GET `?vista=lista` → cookie `vista_rotina=lista`; GET sem vista renderiza lista)
  - `test_editar_atividade_de_outro_usuario_404` (GET editar e POST editar/excluir → 404; atividade inalterada)
  - `test_copiar_semana_pede_confirmacao_quando_ha_atividades`
  - `test_post_sem_csrf_403`
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implementar. **Step 4:** Run → PASS.
- [ ] **Step 5:** Verificação manual em 375px e 1280px: as três vistas, criar Trabalho seg–sex, editar "só este dia", copiar para a semana seguinte, navegar tudo por teclado.
- [ ] **Step 6: Commit** `feat: telas da rotina semanal`

---

### Task 8: Contadores — modelo e configuração

**Files:**
- Create: `app/contadores/__init__.py`, `app/contadores/models.py`, `app/contadores/service.py`, migração `contadores` e `lancamentos`, `tests/contadores/test_service.py`
- Modify: `app/models.py`

**Interfaces:**
- Produces:
  - Model `Contador` (`contadores`): `id`, `usuario_id` (FK cascade), `nome` (≤ 60), `unidade` (≤ 30), `passo: int` (CHECK ≥ 1), `meta_valor: int | None` (CHECK ≥ 1), `meta_periodo: str | None` (`dia|mes|ano`), `meta_sentido: str | None` (`maximo|minimo`), `ativo: bool = True`, `posicao: int`, `criado_em`, `atualizado_em`. CHECK: os três campos de meta todos nulos ou todos preenchidos. `UNIQUE (id, usuario_id)`.
  - Model `Lancamento` (`lancamentos`): `id: int` (bigint), `contador_id`, `usuario_id`, `quantidade: int` (CHECK > 0), `ocorrido_em: timestamptz`, `criado_em: timestamptz` (default now), `tipo: str` (`normal|ajuste`), `cancelado_em: timestamptz | None`, `substitui_id: int | None` (FK `lancamentos.id`), `token_cliente: UUID | None` (UNIQUE). FK composta `(contador_id, usuario_id) → contadores(id, usuario_id)`. Índice `(contador_id, ocorrido_em)`.
  - `@dataclass DadosContador(nome: str, unidade: str, passo: int = 1, meta_valor: int | None = None, meta_periodo: str | None = None, meta_sentido: str | None = None)`.
  - `ler_inteiro(valor: str, campo: str, minimo: int = 1, maximo: int = 1_000_000) -> int` — usado também pelas rotas; erro `ErroValidacao(f"{campo}: informe um número inteiro entre {minimo} e {maximo}.")`.
  - `criar_contador(db, usuario_id, dados, valor_inicial: int | None = None, valor_inicial_em: datetime | None = None) -> Contador` — `posicao` = máximo + 1; `valor_inicial` cria um `Lancamento` tipo `ajuste` em `valor_inicial_em` (padrão `agora_utc()`).
  - `atualizar_contador(db, usuario_id, contador_id, dados) -> None`, `definir_ativo(db, usuario_id, contador_id, ativo: bool) -> None`.
  - `listar_contadores(db, usuario_id, ativos: bool | None = True) -> list[Contador]` (ordem `posicao`), `obter_contador(db, usuario_id, contador_id) -> Contador` (`NaoEncontrado`).
  - Validação: nome e unidade obrigatórios (`"Informe um nome."`, `"Informe a unidade."`); meta parcial → `"Para definir uma meta, preencha valor, período e sentido."`.

- [ ] **Step 1: Write the failing tests:** `test_criar_contador_basico` (passo 1, ativo, posição 1, segundo recebe 2); `test_valor_inicial_vira_ajuste` (1 lançamento `tipo == "ajuste"`, `quantidade == 40`); `test_meta_incompleta_erro`; `test_passo_zero_erro`; `test_desativar_some_da_lista_ativa_mas_aparece_em_todos`; `test_contador_de_outro_usuario_nao_encontrado`; `test_banco_rejeita_lancamento_com_usuario_inconsistente` (inserir `Lancamento` com `usuario_id` do outro usuário para contador alheio → `IntegrityError`); `test_ler_inteiro` (`"abc"`, `"0"`, `"-3"`, `"99999999999"` → erro; `" 30 "` → 30).
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implementar. **Step 4:** Run → PASS.
- [ ] **Step 5: Commit** `feat: modelo de contadores e lançamentos`

---

### Task 9: Lançamentos e totais (service)

**Files:**
- Create: `app/contadores/lancamentos.py`, `tests/contadores/test_lancamentos.py`

**Interfaces:**
- Consumes: Task 8 models/`obter_contador`; `tempo.limites_periodo`, `tempo.limites_datas`, `tempo.agora_utc`.
- Produces:
  - `registrar(db, usuario_id, contador_id, quantidade: int, token: UUID | None = None, ocorrido_em: datetime | None = None) -> Lancamento` — contador inativo → `ErroValidacao("Este contador está inativo.")`; `token` já usado pelo mesmo usuário → retorna o lançamento existente sem criar outro (tratar `IntegrityError` de corrida com savepoint); `ocorrido_em` no futuro (> agora + 5 min) → `ErroValidacao("A data não pode estar no futuro.")`.
  - `desfazer_ultimo(db, usuario_id, contador_id, periodo: Periodo, fuso: str, agora: datetime) -> Lancamento | None` — cancela o lançamento `tipo='normal'`, não cancelado, com `ocorrido_em` no período, de **maior `criado_em`** (desempate por `id`); `None` se não há.
  - `cancelar(db, usuario_id, lancamento_id: int) -> Lancamento` — já cancelado → `ErroValidacao("Este lançamento já foi cancelado.")`.
  - `corrigir(db, usuario_id, lancamento_id, quantidade: int, ocorrido_em: datetime) -> Lancamento` — em uma transação: cancela o original e cria um novo com mesmo `tipo`, `substitui_id = original.id`.
  - `totais_periodo(db, usuario_id, periodo: Periodo, fuso: str, agora: datetime) -> dict[int, int]` — `{contador_id: soma}` para todos os contadores do usuário; sem lançamentos válidos → `0` (é a tela de contadores).
  - `pode_desfazer(db, usuario_id, periodo, fuso, agora) -> set[int]` — ids de contadores com algum lançamento normal válido no período (para habilitar o `−`).
  - `@dataclass TotalGrupo(inicio: date, total: int | None)`.
  - `totais_agrupados(db, usuario_id, contador_id, de: date, ate: date, agrupar: Periodo, fuso: str) -> list[TotalGrupo]` — um item para **cada** dia/mês/ano do intervalo (ordem decrescente); `total=None` quando o grupo não tem nenhum lançamento (nem cancelado); `0` quando só tem cancelados. SQL com `date_trunc(:g, ocorrido_em AT TIME ZONE :fuso)`; preencher os vazios em Python.
  - `listar_lancamentos(db, usuario_id, contador_id, de: date, ate: date, fuso: str) -> list[Lancamento]` — inclui cancelados, ordem `ocorrido_em desc, id desc`.

- [ ] **Step 1: Write the failing tests** (use `SP` e `agora = datetime(2026, 10, 19, 15, tzinfo=utc)`):
  - `test_registrar_soma_no_total_do_dia` (passo 1 duas vezes + quantidade 30 → 32)
  - `test_registrar_mesmo_token_nao_duplica` (mesmo `uuid4()` duas vezes → mesmo `id`, total 1)
  - `test_total_dia_respeita_fuso` (com `agora = 2026-10-20T01:00Z`, que é 22h do dia 19 em SP: um lançamento em `2026-10-19T02:30Z` — 23:30 do dia 18 — **não** entra no total `dia`; um em `2026-10-20T00:30Z` — 21:30 do dia 19 — entra; total = quantidade só do segundo)
  - `test_desfazer_cancela_o_ultimo_registrado` (lançamento retroativo para 08h criado **depois** de um das 14h → `desfazer_ultimo` cancela o retroativo)
  - `test_desfazer_ignora_ajuste` (só existe ajuste de 40 → retorna `None`, total continua 40 no ano)
  - `test_desfazer_respeita_periodo` (lançamento de ontem; período `dia` → `None`; período `mes` → cancela)
  - `test_cancelar_nao_apaga` (linha continua existindo com `cancelado_em`; total cai)
  - `test_corrigir_preserva_original` (original cancelado; novo com `substitui_id`; total reflete o novo valor)
  - `test_registrar_no_futuro_erro`, `test_registrar_em_inativo_erro`
  - `test_totais_agrupados_distingue_vazio_de_zero` (dias 17, 18, 19: 17 sem nada → `None`; 18 só cancelado → `0`; 19 com 3 → `3`)
  - `test_totais_agrupados_por_mes`
  - `test_lancamento_de_outro_usuario_nao_encontrado` (`cancelar`/`corrigir` com id alheio → `NaoEncontrado`)
- [ ] **Step 2:** Run `uv run pytest tests/contadores -v` → FAIL. **Step 3:** Implementar. **Step 4:** Run → PASS.
- [ ] **Step 5: Commit** `feat: lançamentos, desfazer, correção e totais`

---

### Task 10: Tela de contadores

**Files:**
- Create: `app/contadores/routes.py`, `app/templates/contadores/lista.html`, `_contador.html`, `form.html`, `tests/contadores/test_routes.py`
- Modify: `app/main.py`, `app/static/css/app.css`, `app/static/js/app.js`

**Interfaces:**
- Consumes: Tasks 8–9.
- Produces:
  - `texto_meta(contador: Contador, total: int, periodo: Periodo) -> str | None` (em `routes.py` ou `app/contadores/apresentacao.py`) — `None` se sem meta ou `meta_periodo != periodo`; `maximo`: `"{total} de no máximo {meta}"` + (`" · acima da meta"` se total > meta); `minimo`: `"{total} de {meta}"` + (`" · meta atingida"` se total ≥ meta).
  - `ROTULO_PERIODO = {"dia": "hoje", "mes": "este mês", "ano": "este ano"}`.
  - Partial `_contador.html` (reusado no painel): recebe `contador`, `total`, `periodo`, `pode_desfazer: bool`, `token: str` (uuid4 novo a cada render), `voltar: str`. Contém: nome, unidade, `texto_meta`; botão `−` (`aria-label="Remover último lançamento de {nome}"`, `disabled` se não pode desfazer); número como botão (`aria-label="{total} {unidade} {rótulo}. Lançar outra quantidade"`) que abre `<dialog>` com `<input type="number" inputmode="numeric" min="1" required>` + Confirmar/Cancelar; botão `+` (`aria-label="Adicionar {passo} em {nome}"`). Os forms usam `hx-post`, `hx-target` no card, `hx-swap="outerHTML"`, `hx-sync="closest .contador:drop"`, e funcionam sem JS (POST normal + redirect 303 para `voltar`).
  - Respostas HTMX dos POSTs devolvem o card atualizado + `<div id="anuncio" hx-swap-oob="true">{nome}: {total} {rótulo}</div>`.
  - Rotas:
    - `GET /contadores?periodo=dia|mes|ano` (cookie `periodo_contadores`, padrão `dia`) — seletor Dia · Mês · Ano como `role="tablist"` de links; cards dos ativos; link "Gerenciar contadores"; vazio → `"Você ainda não tem contadores."` + botão "Criar contador".
    - `POST /contadores/{id}/mais` (`token`, `periodo`, `voltar`) → `registrar(quantidade=passo)`.
    - `POST /contadores/{id}/quantidade` (`quantidade`, `token`, `periodo`, `voltar`) → `ler_inteiro` + `registrar`; erro → card com mensagem `role="alert"` (status 400; HTMX configurado para trocar 400 também via `htmx.config.responseHandling` em `app.js`).
    - `POST /contadores/{id}/menos` (`periodo`, `voltar`) → `desfazer_ultimo`.
    - `GET /contadores/gerenciar` (ativos e inativos, com botão Ativar/Desativar), `GET /contadores/novo`, `POST /contadores`, `GET /contadores/{id}/editar`, `POST /contadores/{id}`, `POST /contadores/{id}/ativo` (`ativo=sim|nao`).
    - `voltar` aceito só se for `/` ou começar com `/contadores` (senão `/contadores`).
  - Form de contador: nome, unidade, passo (padrão 1), meta (valor + select período + select sentido "no máximo"/"pelo menos"), valor inicial + data (só na criação).

- [ ] **Step 1: Write the failing tests:**
  - `test_lista_vazia_convida_a_criar`
  - `test_criar_contador_pela_tela`
  - `test_mais_registra_e_devolve_card` (HTMX → 200, contém `>1<` no número e `id="anuncio"` com `"Cigarros: 1 hoje"`)
  - `test_mais_com_mesmo_token_duas_vezes` (total continua 1)
  - `test_quantidade_invalida_nao_registra` (para `"0"`, `"-3"`, `"abc"`, `"99999999999"`: 400, mensagem, total 0)
  - `test_menos_desfaz` e `test_menos_desabilitado_sem_lancamentos` (atributo `disabled` no botão)
  - `test_periodo_mes_soma_o_mes_e_fica_no_cookie`
  - `test_texto_meta` (unitário: máximo 5 com 7 → `"7 de no máximo 5 · acima da meta"`; mínimo 8 com 8 → `"8 de 8 · meta atingida"`; meta diária na vista mês → `None`)
  - `test_mais_em_contador_de_outro_usuario_404`
  - `test_desativar_some_da_tela`
  - `test_sem_js_redireciona_para_voltar` (sem `HX-Request` → 303 para `/`) e `test_voltar_externo_e_ignorado` (`voltar=https://mal.example` → 303 `/contadores`)
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implementar. **Step 4:** Run → PASS.
- [ ] **Step 5:** Verificação manual no celular (375px): tocar `+` rápido várias vezes, lançar 30 pelo número, `−`, trocar Dia/Mês/Ano; com leitor de tela (NVDA/TalkBack) o total é anunciado.
- [ ] **Step 6: Commit** `feat: tela de contadores`

---

### Task 11: Histórico

**Files:**
- Create: `app/historico/__init__.py`, `app/historico/routes.py`, `app/templates/historico/historico.html`, `corrigir.html`, `tests/historico/test_routes.py`
- Modify: `app/main.py`

**Interfaces:**
- Consumes: Task 9 (`listar_lancamentos`, `totais_agrupados`, `registrar`, `cancelar`, `corrigir`), Task 8 (`listar_contadores(ativos=None)`).
- Produces:
  - `GET /historico?contador=&de=&ate=&agrupar=dia|mes|ano` — padrões: primeiro contador ativo (ou o primeiro existente), últimos 30 dias até hoje local, `agrupar=dia`. Seletor de contador (inclui inativos, marcados "(inativo)"), campos de data, tabela de totais (`None` exibido como `—` com `<abbr title="sem registros">`), lista de lançamentos com data, hora local, quantidade, `"ajuste"` quando for o caso, cancelados riscados (`<del>`) com texto `"cancelado"` (não só visual), corrigidos com `"corrigido"` e link para o substituto. `de > ate` → mensagem `"A data inicial deve ser antes da final."`. Sem contadores → convite para criar.
  - `POST /historico/lancamentos` (`contador`, `quantidade`, `data`, `hora`) — lançamento retroativo (hora local do usuário convertida para UTC); redirect 303 para o histórico do contador.
  - `POST /historico/lancamentos/{id}/cancelar`.
  - `GET /historico/lancamentos/{id}/corrigir` e `POST /historico/lancamentos/{id}/corrigir` (`quantidade`, `data`, `hora`).

- [ ] **Step 1: Write the failing tests:** `test_historico_mostra_traco_para_dia_sem_registros`; `test_historico_mostra_cancelado` (texto `"cancelado"`); `test_lancamento_retroativo` (ontem 15:00 local aparece com `15:00`, total de ontem correto); `test_retroativo_no_futuro_erro`; `test_corrigir_pela_tela` (original `"cancelado"`, novo valor no total); `test_cancelar_lancamento_de_outro_usuario_404`; `test_datas_invertidas_mostra_erro`; `test_contador_inativo_aparece_no_seletor`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implementar. **Step 4:** Run → PASS.
- [ ] **Step 5: Commit** `feat: histórico de lançamentos com correção`

---

### Task 12: Painel inicial

**Files:**
- Create: `app/painel/__init__.py`, `app/painel/routes.py`, `app/templates/painel/painel.html`, `_secao_rotina.html`, `_secao_contadores.html`, `tests/painel/test_painel.py`
- Modify: `app/main.py`

**Interfaces:**
- Consumes: `rotina.service.listar_dia`, `contadores` (Tasks 8–10, incluindo `_contador.html` com `voltar="/"`, `periodo="dia"`), `tempo`.
- Produces:
  - `saudacao(hora_local: int) -> str` — `< 12` `"Bom dia"`, `< 18` `"Boa tarde"`, senão `"Boa noite"`.
  - `estado_atividade(atividade, agora_local: datetime) -> Literal["passada", "agora", "futura"]`.
  - `GET /` — cabeçalho `data_por_extenso(hoje)` + `"{saudação}, {nome}"`; seção **Rotina de hoje** (cada seção é um template próprio): atividades de hoje com horário e título, `"agora"` como selo de texto na atual, passadas com classe `passada` (esmaecidas, ainda legíveis/AA) ; sem atividades hoje → `"Nada planejado para hoje."` + link "Abrir rotina"; seção **Contadores**: cards ativos com total do dia; sem contadores → link para criar.

- [ ] **Step 1: Write the failing tests:** `test_saudacao` (11 → Bom dia, 12 → Boa tarde, 18 → Boa noite); `test_estado_atividade` (8–12 com agora 10:00 → agora; 12:00 → passada; 7:59 → futura); `test_painel_mostra_rotina_de_hoje_e_contadores` (com `agora_utc` patchado para 2026-10-19 13:00Z = 10h SP: contém `"Segunda-feira, 19 de outubro"`, `"Bom dia, Ana"`, título da atividade de hoje, não contém a de amanhã, contém o nome do contador); `test_painel_sem_dados_mostra_convites`; `test_painel_exige_login`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implementar. **Step 4:** Run → PASS.
- [ ] **Step 5: Commit** `feat: painel inicial`

---

### Task 13: Deploy, backup e documentação de operação

**Files:**
- Create: `Dockerfile`, `.dockerignore`, `fly.toml`, `Dockerfile.backup`, `scripts/backup.sh`, `docs/operacao.md`

**Interfaces:**
- Produces:
  - `Dockerfile`: `python:3.14-slim`, instala com `uv sync --frozen --no-dev`, roda `uvicorn app.main:app --host 0.0.0.0 --port 8080 --proxy-headers --forwarded-allow-ips="*"` (necessário para IP real no limite de login — `autenticar` usa `request.client.host`).
  - `fly.toml`: `[deploy] release_command = "alembic upgrade head"`; `[http_service] internal_port = 8080, force_https = true`; health check `GET /healthz`; região `gru`. Segredo `DATABASE_URL` (Neon, `sslmode=require`, driver `postgresql+psycopg://`).
  - Backup: `Dockerfile.backup` baseado em `postgres:17-alpine` + `aws-cli` + `curl`; `scripts/backup.sh`: `pg_dump -Fc "$BACKUP_DATABASE_URL" | aws s3 cp - "s3://$R2_BUCKET/minha-rotina/$(date -u +%Y-%m-%dT%H%MZ).dump" --endpoint-url "$R2_ENDPOINT"`, `set -euo pipefail`; em sucesso faz `curl -fsS "$BACKUP_PING_URL"` e em falha `curl "$BACKUP_PING_URL/fail"` (se a variável existir — ex.: healthchecks.io), saindo com código ≠ 0. Agendado como Fly Machine `--schedule daily`. Retenção de 30 dias via **regra de ciclo de vida do bucket R2** (configurada no painel da Cloudflare).
  - `docs/operacao.md`: primeiro deploy (criar app, `fly secrets set`, `fly deploy`), criar usuário em produção (`fly ssh console -C "python -m app.cli criar-usuario --email ... --nome ..."`), configurar o backup e a regra de 30 dias, **restauração** (`pg_restore --clean --no-owner -d <URL de uma branch Neon de teste> arquivo.dump` e conferência), rodar migrações localmente.

- [ ] **Step 1:** `docker build -t minha-rotina .` e `docker run` com `DATABASE_URL` local → `curl localhost:8080/healthz` responde `{"ok":true}`.
- [ ] **Step 2:** `docker build -f Dockerfile.backup -t rotina-backup .` e rodar contra o Postgres local com um bucket R2 de teste → arquivo `.dump` aparece no bucket.
- [ ] **Step 3:** Restaurar esse dump num banco vazio local seguindo `docs/operacao.md` → contagem de linhas de `lancamentos` igual à origem.
- [ ] **Step 4:** Deploy real no Fly + Neon **com a dona do projeto** (precisa das contas dela; não executar sem ela). Verificar HTTPS, login, criação de usuário pelo `fly ssh console`.
- [ ] **Step 5: Commit** `chore: deploy no Fly, backup no R2 e guia de operação`

---

### Task 14: Validação final da v1

**Files:**
- Create: `docs/validacao-v1.md` (registro do que foi verificado e problemas encontrados)

- [ ] **Step 1:** `uv run pytest -v` → tudo PASS.
- [ ] **Step 2:** Responsividade em 375, 768, 1280px em todas as telas: sem rolagem horizontal, alvos ≥ 44px.
- [ ] **Step 3:** Instalar o PWA no celular (Android Chrome e iOS Safari "Adicionar à Tela de Início") a partir do Fly; navegar no modo instalado, inclusive sem botão voltar; desligar a rede → página "Sem conexão".
- [ ] **Step 4:** Acessibilidade: Lighthouse acessibilidade ≥ 95 em `/`, `/rotina`, `/contadores`, `/historico`; percurso completo só com teclado; NVDA (desktop) e TalkBack/VoiceOver: registrar um cigarro e ouvir o novo total.
- [ ] **Step 5:** Integridade: com dois usuários, conferir que nenhum vê dados do outro trocando ids nas URLs; totais do contador = soma do histórico para dia, mês e ano.
- [ ] **Step 6:** Corrigir o que falhar (cada correção com teste, quando aplicável); registrar resultados em `docs/validacao-v1.md`.
- [ ] **Step 7: Commit** `docs: validação da v1`
