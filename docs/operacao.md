# Operação do minha-rotina

Guia para colocar o app no ar, administrar contas e cuidar dos backups.

- **App:** Fly.io (região `gru`, São Paulo), imagem do `Dockerfile`.
- **Banco:** PostgreSQL no Neon.
- **Backup:** `pg_dump` diário enviado ao Cloudflare R2 (`Dockerfile.backup` + `scripts/backup.sh`), guardado por 30 dias.

---

## 1. Desenvolvimento local

```bash
docker compose up -d                    # Postgres 17 (bancos rotina e rotina_test)
cp .env.example .env                    # na primeira vez
uv run alembic upgrade head             # cria/atualiza as tabelas
uv run uvicorn app.main:app --reload    # http://localhost:8000
uv run pytest                           # testes (usam o banco rotina_test)
```

Criar um usuário local (rode num terminal de verdade: a senha é digitada sem aparecer):

```bash
uv run python -m app.cli criar-usuario --email voce@exemplo.com --nome "Seu nome"
```

## 2. Banco no Neon (uma vez)

1. Crie um projeto no Neon, na região **AWS São Paulo (sa-east-1)** se disponível, com **Postgres 17**.
2. Copie a *connection string* do banco (formato `postgresql://usuario:senha@ep-....neon.tech/neondb?sslmode=require`).
   O app aceita esse formato como está; não precisa trocar nada.
3. Use a string **com pooling** (host com `-pooler`) para o app.

## 3. Primeiro deploy no Fly (uma vez)

Pré-requisito: [flyctl](https://fly.io/docs/flyctl/install/) instalado e `fly auth login` feito.

```bash
fly launch --no-deploy --copy-config      # cria o app usando o fly.toml (aceite o nome ou troque)
fly secrets set DATABASE_URL="postgresql://...neon.tech/neondb?sslmode=require"
fly deploy --local-only                   # constrói no seu Docker, roda as migrações (release_command) e publica
```

> Use `--local-only`: nesta conta o builder remoto do Fly recusou o envio da imagem (401/403).
> Com `--local-only` a imagem é construída pelo Docker da sua máquina e enviada pronta.

Conferir:

```bash
fly status
curl https://<seu-app>.fly.dev/healthz    # deve responder {"ok":true}
```

O app usa HTTPS automaticamente em `https://<seu-app>.fly.dev`. A máquina fica **sempre ligada**
(`auto_stop_machines = "off"`, `min_machines_running = 1`): não há espera de cold start no primeiro acesso.

Ela roda com **256 MB** de propósito: dois apps sempre ligados (`minha-rotina` + `caderno-de-gastos`)
somam 512 + 256 = 768 MB, que é exatamente a franquia do plano legado do Fly (3 VMs `shared-cpu-1x 256MB`).
Subir para 512 MB faz a conta passar da franquia (~US$ 2–3/mês).

### Só IPv4 (sem IPv6 dedicado)

O app **não** tem endereço IPv6 dedicado — só o IPv4 compartilhado. Boa parte dos acessos via IPv6
(principalmente em rede móvel) dava erro ou ficava pendurada antes de cair para o IPv4. Para conferir:

```bash
fly ips list -a minha-rotina        # deve aparecer só a linha "v4 ... public ingress (shared)"
```

Se um dia aparecer um IPv6 dedicado, remova com `fly ips release <endereço> -a minha-rotina`.

## 4. Contas de usuário em produção

As contas só são criadas pela linha de comando:

```bash
fly ssh console --pty -C "python -m app.cli criar-usuario --email pessoa@exemplo.com --nome Nome"
fly ssh console --pty -C "python -m app.cli redefinir-senha --email pessoa@exemplo.com"
fly ssh console --pty -C "python -m app.cli desativar-usuario --email pessoa@exemplo.com"
```

Use sempre `--pty`: sem ele o `fly ssh console -C` não abre um terminal de verdade, a senha aparece na tela e,
no Windows, o Enter chegava como `
` (o CLI agora descarta esse ``, mas o `--pty` evita o problema de vez).

Desativar bloqueia o acesso na hora (as sessões abertas deixam de valer) e preserva os dados.

Se aparecer **"app has no started VMs"**: a máquina do app agora fica sempre ligada, então isso só deve
acontecer se ela tiver sido parada à mão. Ligue e rode o comando logo em seguida, indicando a máquina:

```bash
fly machine list                         # pegue o ID de uma máquina do app (não a backup-diario)
fly machine start <id>
fly ssh console --pty --machine <id> -C "python -m app.cli criar-usuario --email ... --nome ..."
```

Abrir o site no navegador também liga a máquina. "TLS handshake timeout" é instabilidade de rede: repita o comando.

## 5. Atualizações

```bash
uv run pytest      # tudo verde antes de publicar
fly deploy --local-only   # as migrações novas rodam sozinhas antes da versão nova entrar no ar
```

## 6. Backup diário no Cloudflare R2

### 6.1 Preparar o R2 (uma vez)

1. No painel da Cloudflare: **R2 → Create bucket**, por exemplo `minha-rotina-backups`.
2. No bucket: **Settings → Object lifecycle rules → Add rule**: apagar objetos com prefixo `minha-rotina/`
   **30 dias** depois de criados. É isso que mantém só os últimos 30 dias.
3. **R2 → Manage API tokens → Create API token** com permissão **Object Read & Write** só nesse bucket.
   Anote o *Access Key ID*, o *Secret Access Key* e o endpoint `https://<account_id>.r2.cloudflarestorage.com`.

### 6.2 Configurar no Fly (uma vez)

```bash
fly secrets set \
  R2_ENDPOINT="https://<account_id>.r2.cloudflarestorage.com" \
  R2_BUCKET="minha-rotina-backups" \
  AWS_ACCESS_KEY_ID="<access key id>" \
  AWS_SECRET_ACCESS_KEY="<secret access key>"
```

Opcional, mas recomendado: crie um check gratuito em [healthchecks.io](https://healthchecks.io) com período de 1 dia
e configure `fly secrets set BACKUP_PING_URL="https://hc-ping.com/<uuid>"`. Se o backup falhar ou não rodar,
você recebe um email.

O script usa o `DATABASE_URL` do app. Para usar outra conexão (por exemplo, a sem pooling, recomendada para
`pg_dump`), defina `BACKUP_DATABASE_URL`.

### 6.3 Agendar a máquina de backup

```bash
# 1) Constrói a imagem de backup no seu Docker e envia ao registro do Fly (não publica nada no app).
fly deploy --build-only --push --local-only --dockerfile Dockerfile.backup --image-label backup
#    Confira no log de build: "load build definition from Dockerfile.backup" e "postgres:17-alpine".
#    Anote o digest que aparece no fim ("backup: digest: sha256:...").

# 2) Cria a máquina agendada apontando para esse digest exato.
fly machine run registry.fly.io/<seu-app>@sha256:<digest> --schedule daily --restart no --region gru --name backup-diario --vm-memory 256 --detach
```

> Não coloque `dockerfile = ...` na seção `[build]` do `fly.toml`: essa configuração passa por cima do
> `--dockerfile Dockerfile.backup` e a "imagem de backup" sai igual à do app (foi o que aconteceu na primeira tentativa).

A máquina já roda uma vez ao ser criada. Conferir:

```bash
fly machine list                       # backup-diario aparece como "stopped" depois de terminar
fly logs --no-tail --machine <id>      # deve ter "Backup concluído: minha-rotina/....dump" e "exited normally with code: 0"
```

A máquina recebe os secrets do app automaticamente. Confira também no painel do R2 se o `.dump` apareceu.

Para atualizar o script de backup no futuro: repita o passo 1, destrua a máquina antiga
(`fly machine destroy <id>`) e crie de novo com o digest novo.

## 7. Restaurar um backup

Teste a restauração de vez em quando (pelo menos uma vez depois de configurar). O procedimento abaixo foi
validado localmente: o banco restaurado ficou com as mesmas linhas em todas as tabelas.

1. Baixe o arquivo do R2 (painel da Cloudflare ou `aws s3 cp s3://<bucket>/minha-rotina/<arquivo>.dump . --endpoint-url <R2_ENDPOINT>`).
2. No Neon, crie uma **branch** nova (por exemplo `restauracao-teste`). Nunca restaure direto em cima do banco principal sem antes testar.
3. Restaure na branch:

   ```bash
   pg_restore --no-owner --no-privileges --exit-on-error -d "postgresql://...branch...neon.tech/neondb?sslmode=require" arquivo.dump
   ```

4. Confira as contagens:

   ```sql
   select count(*) from usuarios;
   select count(*) from atividades_planejadas;
   select count(*) from contadores;
   select count(*) from lancamentos;
   ```

5. Para usar a restauração de verdade, aponte o app para ela: `fly secrets set DATABASE_URL="<url da branch>"` (o app reinicia sozinho).

O Neon também guarda um histórico próprio (*point-in-time restore*), útil para desfazer algo das últimas horas sem precisar do dump.

## 8. Problemas comuns

| Sintoma | O que verificar |
|---|---|
| `curl` no Windows falha com "Connection was reset" / `schannel` | Problema do cliente, não do app: use `curl -4 --ssl-no-revoke` ou teste no navegador. |
| `/healthz` falha | `fly logs`; o `DATABASE_URL` está certo? O projeto no Neon está ativo? |
| Deploy para no `release_command` | Migração com erro: rode `uv run alembic upgrade head` localmente contra uma branch do Neon para ver a mensagem. |
| Muitos "Email ou senha incorretos" | Após 5 erros em 15 minutos o email fica bloqueado por um tempo; espere ou redefina a senha pelo CLI. |
| Backup não aparece no R2 | `fly logs --machine <id>`; confira `R2_ENDPOINT`, `R2_BUCKET` e o token. |
