#!/bin/sh
# Backup diário do banco para o Cloudflare R2 (ou qualquer S3 compatível).
#
# Variáveis:
#   BACKUP_DATABASE_URL  URL do Postgres (se ausente, usa DATABASE_URL do app)
#   R2_ENDPOINT          ex.: https://<account_id>.r2.cloudflarestorage.com
#   R2_BUCKET            nome do bucket
#   AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY  token de API do R2
#   BACKUP_PING_URL      (opcional) URL de monitoramento, ex.: healthchecks.io
set -eu
set -o pipefail

avisar() {
  if [ -n "${BACKUP_PING_URL:-}" ]; then
    curl -fsS -m 10 --retry 3 "${BACKUP_PING_URL}$1" > /dev/null || true
  fi
}
trap 'status=$?; if [ "$status" -ne 0 ]; then echo "Backup FALHOU (código $status)" >&2; avisar /fail; fi' EXIT

URL="${BACKUP_DATABASE_URL:-${DATABASE_URL:?Defina BACKUP_DATABASE_URL ou DATABASE_URL}}"
URL=$(printf '%s' "$URL" | sed 's#^postgresql+psycopg://#postgresql://#')
: "${R2_ENDPOINT:?Defina R2_ENDPOINT}"
: "${R2_BUCKET:?Defina R2_BUCKET}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-auto}"

NOME="minha-rotina/$(date -u +%Y-%m-%dT%H%MZ).dump"
ARQUIVO="/tmp/backup.dump"

echo "Gerando dump..."
# Primeiro em arquivo: se o pg_dump falhar, nada incompleto é enviado.
pg_dump --format=custom --no-owner --no-privileges --file="$ARQUIVO" "$URL"
pg_restore --list "$ARQUIVO" > /dev/null  # confere que o arquivo é legível

echo "Enviando s3://$R2_BUCKET/$NOME ($(du -h "$ARQUIVO" | cut -f1))..."
aws s3 cp "$ARQUIVO" "s3://$R2_BUCKET/$NOME" --endpoint-url "$R2_ENDPOINT" --only-show-errors
rm -f "$ARQUIVO"

echo "Backup concluído: $NOME"
avisar ""
