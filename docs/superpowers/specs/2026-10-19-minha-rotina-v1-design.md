# minha-rotina — Design da primeira versão

Data: 2026-10-19
Status: aguardando aprovação

Este documento descreve a primeira versão do **minha-rotina**, um painel pessoal para planejar a semana e registrar quantidades do dia a dia (cigarros, copos de água, minutos de estudo...). Ele parte do resumo original da dona do projeto e incorpora o que foi decidido na conversa de design.

Convenção: itens marcados com **(decisão do Claude)** foram escolhas técnicas ou de UX feitas durante o design, não pedidas explicitamente — a dona do projeto pode revê-las. O resto foi dito ou confirmado por ela.

---

## 1. Intenção

Um único lugar para:

1. **Planejar** como a semana vai ser usada (rotina semanal).
2. **Registrar** o que de fato aconteceu, rápido, com um toque (contadores).
3. **Acompanhar** os totais e o histórico ao longo do tempo.

Esses três conceitos ficam separados no código e nos dados: planejamento é intenção, registro é fato, acompanhamento é cálculo sobre os registros. O app deve ser útil desde a primeira versão e crescer aos poucos (hábitos, tarefas, estatísticas, IA vêm depois, só se o uso pedir).

## 2. Objetivos, não-objetivos e anti-objetivos

**Objetivos da v1**
- Rotina semanal por semana (com datas), com cópia da semana anterior.
- Contadores genéricos criados pelo próprio usuário, com registro individual de cada lançamento.
- Totais sempre calculados a partir dos registros.
- Histórico consultável e corrigível sem perder o rastro da correção.
- Painel inicial com seções fixas (Rotina de hoje + Contadores).
- Web responsiva instalável como PWA.
- Vários usuários, cada um vendo só os próprios dados.

**Não-objetivos da v1** (não implementar agora, mesmo estando no resumo original)
- Hábitos, tarefas, registro por texto livre, IA, estatísticas/gráficos, comparação planejado × realizado.
- Offline, push notifications, background sync.
- Cadastro de usuário pela interface, recuperação de senha por email, login social.
- Painel personalizável pelo usuário.
- Compartilhamento ou colaboração entre usuários.

**Anti-objetivos** (coisas que fariam a v1 ser um fracasso mesmo "funcionando")
- Total exibido divergir do histórico.
- Registrar um cigarro exigir mais que um toque, ou abrir formulário.
- Um usuário enxergar qualquer dado de outro.
- Perder dados (sem backup, ou correção que apaga o registro original).
- Frontend com cara de template genérico, ou complexo de manter.

## 3. Stack e infraestrutura

| Item | Escolha | Origem |
|---|---|---|
| Backend | Python + **FastAPI** | Python: dona. FastAPI: decisão do Claude |
| Banco | **PostgreSQL** no **Neon** | dona |
| Migrações | **Alembic**, com SQLAlchemy 2.x | decisão do Claude |
| Frontend | HTML renderizado no servidor com **Jinja2** + **HTMX** para interações parciais; CSS escrito à mão; JS mínimo e sem build | decisão do Claude (pedido da dona: nada de overengineering, boa manutenção) |
| Deploy da aplicação | **Fly.io**, HTTPS | dona |
| Backup do banco | `pg_dump` diário enviado ao **Cloudflare R2**, retenção de 30 dias | Cloudflare: dona. R2/frequência/retenção: decisão do Claude |
| Testes | **pytest** contra um PostgreSQL real (local/CI) | decisão do Claude |

Sem framework JS, sem bundler, sem Node na pipeline. Se surgir necessidade pontual de comportamento no cliente (ex.: popover de quantidade), JS vanilla em arquivo estático pequeno.

Onde o job de backup roda (máquina agendada no Fly, GitHub Actions, etc.) fica a critério do builder; o requisito é: diário, automático, falha visível (log/alerta simples), e um procedimento de restauração documentado e testado ao menos uma vez.

## 4. Usuários e acesso

- Login por **email e senha**. Sem tela de cadastro.
- Contas são criadas pela **linha de comando**, pela dona do projeto, que controla quem tem acesso. O CLI deve permitir: criar usuário (email, nome, senha digitada sem eco), redefinir senha, desativar usuário.
- Cada usuário tem: email, nome (usado na saudação), fuso horário (padrão `America/Sao_Paulo`).
- **Isolamento total**: toda consulta e toda escrita filtra pelo usuário logado. Acessar um id de outro usuário retorna 404. Isso deve ter testes explícitos.
- Senhas com hash **argon2** (decisão do Claude).
- Sessão em cookie `HttpOnly`, `Secure`, `SameSite=Lax`, com duração longa (~90 dias, renovada com uso) para que no celular o app fique logado (decisão do Claude).
- Proteção CSRF nos formulários/requests HTMX que alteram dados (decisão do Claude).
- Limite simples de tentativas de login por email/IP (decisão do Claude).
- Tela de conta mínima: ver email, trocar fuso horário, sair.

## 5. Tempo e fuso

- Todos os instantes gravados em UTC (`timestamptz`).
- "Hoje", "este mês", "este ano" são calculados no **fuso do usuário**.
- **O dia vira à meia-noite** (um cigarro às 02h conta para o dia novo) — dona.
- A semana começa na **segunda-feira** (decisão do Claude).
- Se o usuário trocar de fuso, **todos os totais passam a ser calculados no fuso atual**, inclusive os do passado. Não há histórico de fusos nem fuso gravado por lançamento na v1 (decisão do Claude; troca de fuso é rara e a regra simples mantém totais e histórico consistentes). Atividades guardam data e hora locais e não são afetadas.

## 6. Rotina semanal (planejamento)

### 6.1 Modelo mental

Não existe um "modelo eterno" de rotina. **Cada semana tem seu próprio planejamento**, com datas reais. Para não refazer tudo, há a opção de **copiar a semana anterior** e depois editar livremente — dona.

### 6.2 Atividade

Campos: título (obrigatório), data, hora de início, hora de fim, descrição (opcional), cor (opcional, de uma paleta curta dentro do estilo visual — decisão do Claude).

Regras (decisões do Claude, confirmadas pela dona):
- Fim > início, no mesmo dia. Atividades não atravessam a meia-noite na v1.
- Sobreposição é permitida; a grade mostra lado a lado.
- Dias sem atividade são normais.

### 6.3 Criar para vários dias

No formulário de criação, os dias da semana aparecem como botões (S T Q Q S S D). Marcar vários cria **uma atividade por dia**, ligadas por um identificador de grupo. Ao editar ou excluir uma atividade de um grupo, o app pergunta: **"Só este dia" / "Todos os dias desta semana"**. Editar uma semana nunca afeta outra semana.

Detalhes do grupo (decisão do Claude):
- "Todos os dias desta semana" altera só os campos em comum (título, horários, descrição, cor). Não muda quais dias o grupo cobre: para adicionar um dia, cria-se uma atividade nova; para tirar, exclui-se "só este dia".
- Editar "só este dia" **tira aquele dia do grupo** (ele passa a ser uma atividade avulsa), para que uma edição futura em "todos" não sobrescreva o ajuste pontual.

### 6.4 Copiar semana anterior

- Semana vazia mostra o estado vazio "Semana sem rotina" com botão **Copiar semana anterior**.
- O botão também fica disponível em semanas já preenchidas; nesse caso pede confirmação e **substitui** as atividades da semana atual.
- A cópia nunca acontece automaticamente.
- Copia título, horários, dia da semana correspondente, descrição, cor, e preserva os agrupamentos (com novos ids de grupo).
- Se a semana anterior estiver vazia, o botão informa isso em vez de não fazer nada.

### 6.5 Visualizações

Um seletor **Grade · Dia · Lista** na tela Rotina — dona (as três opções do mockup).

- **Grade**: 7 colunas × horários. No celular, compacta (abreviações); toque no bloco abre a atividade.
- **Dia**: seletor de dias com data no topo (deslizar para o lado também troca de dia), atividades do dia em linha do tempo legível.
- **Lista**: todos os dias da semana em sequência, tipo agenda.

Padrão: **Dia** no celular (abrindo no dia de hoje), **Grade** no computador; o app lembra a última visualização escolhida (decisão do Claude). Navegação entre semanas por setas ‹ › e atalho "Hoje".

A faixa de horários visível na grade (ex.: 06h–23h, ajustando às atividades existentes) fica a critério do builder.

## 7. Contadores (registro)

### 7.1 Configuração de um contador

Criado pelo usuário, sem mexer em código. Campos:

- **Nome** (ex.: "Cigarros").
- **Unidade** (texto livre curto: "unidade", "copo", "minuto"...).
- **Passo padrão**: quanto um toque no `+` soma (ex.: 1 cigarro, 15 minutos). Inteiro ≥ 1.
- **Meta** (opcional): valor + período (**dia / mês / ano**) + sentido (**no máximo** / **pelo menos**). Ex.: "no máximo 5 por dia", "pelo menos 8 por dia", "pelo menos 12 por mês". (Sentido da meta: decisão do Claude — o resumo tinha exemplos dos dois tipos.)
- **Ativo / inativo**. Inativo some do painel e da tela de contadores, mas o histórico permanece consultável. Contadores não são apagados de verdade na v1 se tiverem lançamentos (decisão do Claude).
- **Valor inicial** (opcional, só na criação): vira um **lançamento do tipo "ajuste"** com a data informada (ex.: "já fiz 40 treinos antes do app"), para que o total continue batendo com o histórico (decisão do Claude).
- Ordem de exibição: fica a critério do builder (ordem de criação já atende; reordenar é um extra).

Quantidades são **inteiras** na v1 (decisão do Claude; a dona pode pedir decimais).

### 7.2 Lançamento (a ocorrência)

**Cada lançamento é um registro individual no banco** — nunca se guarda só o total. Um lançamento tem: id, contador, usuário, **quantidade** (inteiro > 0), **momento em que aconteceu**, momento em que foi criado, tipo (normal/ajuste), e informações de cancelamento/correção.

- Toque no `+` → um lançamento com quantidade = passo padrão, no momento atual.
- **Toque no número** → abre um campo pequeno com teclado numérico; digita a quantidade (ex.: 30) e confirma → um lançamento com essa quantidade, no momento atual — dona pediu lançar quantidades maiores; a interação é decisão do Claude.
- Toque no `−` → **cancela o último lançamento válido dentro do período em exibição** (o lançamento inteiro, mesmo que seja 30). "Último" = o **registrado mais recentemente** (`criado_em`), considerando só lançamentos do tipo **normal** — o `−` nunca cancela um ajuste (ex.: o valor inicial de 40 treinos); ajustes só se cancelam pelo histórico (decisão do Claude). Desabilitado quando o período não tem lançamentos normais válidos.
- Cancelar **não apaga**: marca `cancelado_em`. Lançamentos cancelados saem dos totais e aparecem riscados no histórico.
- **Correção** (no histórico: mudar horário ou quantidade de um lançamento): cancela o original e cria um novo que referencia o original (`substitui_id`). Assim fica preservado que houve correção e qual era o valor anterior (decisão do Claude).
- **Lançamento retroativo** no histórico ("esqueci de registrar ontem às 15h"): cria lançamento com momento informado (decisão do Claude).
- **Proteção contra duplicidade**: cada ação de `+`/lançamento carrega um token gerado no cliente; o banco tem unicidade sobre esse token, de modo que um duplo toque ou reenvio não gera dois lançamentos (decisão do Claude).
- Após cada ação, feedback visível e anunciado a leitores de tela (ex.: "Cigarros: 8 hoje"), e opção de desfazer imediata é desejável mas não obrigatória (o `−` já cobre).

### 7.3 Totais

Total de um período = soma das quantidades dos lançamentos **não cancelados** do contador cujo momento cai no período, no fuso do usuário. Nunca existe contador "incrementado" separadamente. Se no futuro for preciso agregar por desempenho, será dado derivado e recalculável — não na v1.

### 7.4 Tela de contadores

- Seletor **Dia · Mês · Ano** no topo; **todos os contadores** passam a exibir o total do período atual escolhido (hoje / este mês / este ano) — dona.
- O `+` e o lançamento por quantidade sempre registram no momento atual, qualquer que seja a visualização.
- O app lembra a última visualização (decisão do Claude).
- A meta só aparece quando o período da meta coincide com a visualização (decisão do Claude). Indicação de meta não pode depender só de cor (texto como "7 de no máximo 5").
- Acesso a criar/editar/desativar contadores a partir desta tela.
- Semana e "total desde o início" **não** estão na v1 (podem entrar no seletor depois sem mudar o modelo).

### 7.5 Histórico

Por contador:
- Lista de lançamentos com data, hora, quantidade, tipo e estado (válido / cancelado / corrigido).
- Filtro por intervalo de datas.
- Totais por dia (e por mês/ano) no intervalo.
- **Período sem lançamentos é mostrado como "sem registros" ("—"), não como 0.** Um período cujos lançamentos foram todos cancelados mostra 0.
- Ações: corrigir, cancelar, lançar retroativo.

## 8. Painel inicial

Seções **fixas**, definidas pelo app (o usuário não reorganiza):

1. Cabeçalho: data por extenso e saudação com o nome ("Bom dia, Natalia").
2. **Rotina de hoje**: atividades de hoje com horário e título; a atividade em andamento marcada "agora"; as que já terminaram ficam esmaecidas ou recolhidas (detalhe do builder). Se a semana não tem rotina, um atalho para a tela Rotina.
3. **Contadores**: contadores ativos com total **do dia**, `−`, número tocável e `+` — mesmas interações da tela de contadores.

As seções são componentes separados no código para que hábitos/tarefas/resumo entrem depois sem reescrever o painel.

## 9. Navegação

Quatro áreas: **Início · Rotina · Contadores · Histórico**. No celular, barra inferior; no computador, barra lateral ou superior (builder decide). Conta/configurações por um ícone no cabeçalho. Navegação funciona igual no navegador e no modo PWA instalado (sem depender do botão voltar do navegador para nada essencial).

## 10. Visual

Direção escolhida pela dona: **"Calmo"** (opção A dos mockups).

- Fundo cor de papel (≈ `#f6f3ee`), texto quase preto quente (≈ `#2b2a27`), acento verde suave (≈ `#4f7d55` / `#3f6b45`), superfícies brancas com bordas bege claras.
- Títulos com serifa (ex.: Georgia ou uma serifa web equivalente), corpo em sans-serif do sistema.
- Cartões com cantos arredondados, botões `+` circulares com acento verde preenchido e `−` em tom suave.
- Pequenas transições quando o número muda são bem-vindas.
- Os valores de cor são ponto de partida; o builder ajusta para garantir contraste AA.

Modo escuro não é requisito da v1 (decisão do Claude).

Os mockups de referência ficam em `.superpowers/brainstorm/` (arquivos `visual-direction.html` e `planner-layout.html`).

## 11. Acessibilidade (desde o início)

HTML semântico; todos os controles com rótulo acessível (`−` = "Remover último lançamento de Cigarros"); foco visível; tudo operável por teclado; alvos de toque ≥ 44px; contraste AA; informação nunca só por cor; mudanças de total anunciadas via região `aria-live`; mensagens de erro ligadas aos campos; respeitar `prefers-reduced-motion`.

## 12. PWA

- Manifest com nome, ícones, cores do tema, `display: standalone`, `start_url` no painel.
- Service worker mínimo que atenda aos critérios de instalação e faça cache apenas de arquivos estáticos (CSS, ícones). **Nenhum dado é servido do cache** — sem offline na v1.
- Sem conexão, mostrar uma página simples "sem conexão" em vez do erro do navegador.
- Funciona em HTTPS no Fly.

## 13. Modelo de dados preliminar

Nomes ilustrativos; o builder pode ajustar, mantendo as responsabilidades.

**usuarios**: id, email (único, case-insensitive), nome, senha_hash, fuso_horario, ativo, criado_em.

**sessoes**: (se a sessão for guardada no servidor) id/token, usuario_id, criado_em, expira_em. Alternativa de cookie assinado fica a critério do builder.

**atividades_planejadas**: id, usuario_id, data, hora_inicio, hora_fim, titulo, descricao, cor, grupo_id (nullable), criado_em, atualizado_em.
- Índice por (usuario_id, data). A semana é derivada da data.
- Excluir atividade é exclusão real (é planejamento, não histórico).

**contadores**: id, usuario_id, nome, unidade, passo, meta_valor, meta_periodo (dia/mes/ano), meta_sentido (maximo/minimo), ativo, posicao, criado_em, atualizado_em.

**lancamentos**: id, contador_id, usuario_id, quantidade (> 0), ocorrido_em (timestamptz), criado_em, tipo (normal/ajuste), cancelado_em (nullable), substitui_id (nullable, FK para lancamentos), token_cliente (único, nullable).
- Índice por (contador_id, ocorrido_em).
- `usuario_id` redundante com o do contador, para facilitar o filtro de isolamento; deve ser consistente (validação/constraint).

Separação exigida pelo resumo: configuração (`contadores`, `usuarios`), planejamento (`atividades_planejadas`), registros (`lancamentos`), resultados calculados (consultas, sem tabela).

## 14. Integridade

- Validações no backend para tudo (o frontend pode validar também, mas não substitui).
- Operações de correção (cancelar + criar substituto) e de copiar semana (apagar + inserir) em **uma transação**.
- Erros apresentados em português claro, sem perder o que o usuário digitou.

## 15. Etapas de implementação (resumo; o plano detalhado vem depois)

1. **Base**: projeto FastAPI, banco + Alembic, usuários e CLI, login/sessão, layout com navegação, estilo base "Calmo", manifest/service worker, deploy no Fly com Neon, backup no R2.
2. **Rotina semanal**: CRUD de atividades, criação para vários dias com grupo, três visualizações, navegação entre semanas, copiar semana anterior.
3. **Contadores**: CRUD de contadores, lançamentos (+, quantidade, −), totais por dia/mês/ano, histórico com correção e retroativo, proteção contra duplicidade.
4. **Painel**: seções Rotina de hoje e Contadores.
5. **Validação**: responsividade, instalação PWA no celular, acessibilidade (teclado + leitor de tela), testes de integridade e isolamento entre usuários, restauração de backup testada.

Ao fim de cada etapa: o que foi feito, decisões técnicas, testes, limitações e próximo passo.

## 16. Deixado para o builder

- Estrutura de pastas e organização interna dos módulos (mantendo rotina, contadores e painel como módulos separados).
- Sessão no servidor vs. cookie assinado.
- Faixa de horários da grade; tratamento visual de atividades já passadas no painel.
- Onde roda o job de backup e como o alerta de falha é emitido.
- Ordenação dos contadores.
- Tipografia exata e ajustes finos de cor dentro da direção "Calmo".
- Ícones do PWA (simples, provisórios).

## 17. Decisões do Claude para revisão rápida

FastAPI · Jinja2 + HTMX sem build · Alembic · argon2 · sessão ~90 dias · R2 diário com 30 dias de retenção · semana começa na segunda · atividades não atravessam meia-noite · sobreposição permitida · uma atividade por dia ligada por grupo, com pergunta "só este dia / todos" · copiar semana substitui com confirmação · visualização padrão Dia (celular) / Grade (computador) · meta com sentido "no máximo / pelo menos" · quantidades inteiras · valor inicial vira lançamento de ajuste · correção = cancelar + novo lançamento ligado · lançamento retroativo no histórico · token anti-duplicidade · `−` cancela o último lançamento normal por ordem de registro, nunca um ajuste · "todos os dias" edita só campos em comum; editar "só este dia" tira o dia do grupo · totais sempre no fuso atual do usuário · contador com lançamentos não é apagado, só desativado · sem modo escuro na v1.
