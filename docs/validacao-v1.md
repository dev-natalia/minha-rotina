# Validação da v1

Data: 2026-10-19 · Ambiente: local (Docker Postgres 17) e produção (https://minha-rotina.fly.dev)

## Resultado

| Verificação | Como | Resultado |
|---|---|---|
| Testes automatizados | `uv run pytest` | **203 passaram**, nenhum falhou |
| Produção no ar | `/healthz`, `/login`, `/` → `/login`, `http` → `https`, manifest, `sw.js`, `/offline` | OK (2 máquinas em `gru`, health check passando) |
| Backup diário | máquina `backup-diario` (agendada, `daily`) | 1ª execução no R2: `minha-rotina/2026-10-19T0849Z.dump`, código 0 |
| Restauração | dump → banco vazio, contagem por tabela | idêntica em `usuarios`, `atividades_planejadas`, `contadores`, `lancamentos`, `alembic_version` |
| Responsividade | 14 telas × 375 / 768 / 1280 px | nenhuma rolagem horizontal |
| Alvos de toque | todos os links/botões/campos visíveis | ≥ 44 px (exceto link dentro de texto, "ver correção", permitido pela WCAG) |
| Acessibilidade automática | axe-core 4.10.2, regras WCAG 2.2 A/AA + boas práticas, 13 telas | **0 violações** em celular (360 px úteis), tablet e computador |
| Teclado | Tab/Enter/Esc nos contadores, diálogo, formulários | foco visível; foco volta ao mesmo botão após `+`/`−`; diálogo fecha com Esc |
| Leitor de tela (anúncio) | região `aria-live` | anuncia "Cigarros: 5 hoje" etc. após cada lançamento |
| Integridade dos totais | contadores × histórico (tabela e lista), dia/mês/ano | iguais para todos os contadores nos 3 períodos |
| Isolamento entre usuários | 2ª usuária acessando ids da 1ª pela URL (11 rotas) | todas **404**; nada alterado; painel sem dados alheios |

## Problemas encontrados e corrigidos nesta etapa

- **Alvos de toque menores que 44 px:** link "minha-rotina" (26 px), "Ver semana"/"Ver todos" no painel (22 px) e seletores Grade/Dia/Lista e Dia/Mês/Ano (36 px). Agora todos têm 44 px.
- **Blocos sobrepostos na Grade do celular com menos de 24 px** (WCAG 2.5.8): a grade passa a ocupar a largura toda no celular, a coluna de horas ficou com 20 px e as linhas da grade viraram sombras (não ocupam largura). Duas atividades no mesmo horário ficam com ≥ 24 px a partir de 360 px de tela.

## Limitações conhecidas

- **Três ou mais atividades no mesmo horário** ainda geram blocos estreitos na Grade do celular. As vistas Dia e Lista mostram as mesmas atividades com alvos grandes.
- O Lighthouse não estava disponível neste ambiente; a auditoria usou o axe-core (o mesmo motor de regras de acessibilidade do Lighthouse).
- O deploy precisa de `fly deploy --local-only` (o builder remoto do Fly recusou a conta com 401/403).

## Falta fazer pela dona do projeto (precisa do celular)

- [ ] **Instalar o PWA:** abrir https://minha-rotina.fly.dev no Chrome do Android (menu ⋮ → *Instalar app*) ou no Safari do iPhone (Compartilhar → *Adicionar à Tela de Início*).
- [ ] No app instalado: entrar, registrar um cigarro, trocar de tela pela barra inferior, voltar ao painel.
- [ ] **Sem internet** (modo avião) abrir o app: deve aparecer a página "Sem conexão" com "Tentar de novo".
- [ ] **Leitor de tela** (TalkBack no Android / VoiceOver no iPhone): tocar no `+` de um contador e ouvir o novo total.
