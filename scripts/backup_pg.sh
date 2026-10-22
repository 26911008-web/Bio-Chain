#!/usr/bin/env bash
# Backup harian PostgreSQL Bio-Chain (F17) — pg_dump format custom + rotasi + uji pulih ringan.
#
# Pasang di server (cron, pukul 02.15 WIB):
#   15 2 * * *  BIOCHAIN_PG_URL=postgresql://biochain:***@localhost:5432/biochain /opt/biochain/scripts/backup_pg.sh
# Opsional salin ke luar server (wajib untuk pemulihan bencana): BACKUP_RSYNC_TARGET=user@host:/backup/biochain
#
# Pulihkan:
#   createdb biochain_restore && pg_restore --no-owner -d biochain_restore /var/backups/biochain/biochain-YYYYMMDD-HHMM.dump
# Untuk RPO menit (bukan harian) gunakan pgBackRest/WAL-G dengan archive_command — skrip ini adalah lapisan minimum.
set -euo pipefail

: "${BIOCHAIN_PG_URL:?set BIOCHAIN_PG_URL=postgresql://user:pass@host:port/db}"
DIR="${BACKUP_DIR:-/var/backups/biochain}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
mkdir -p "$DIR"
umask 077                                      # dump berisi data pribadi → hanya pemilik yang bisa membaca

STAMP="$(date +%Y%m%d-%H%M)"
OUT="$DIR/biochain-$STAMP.dump"
pg_dump --format=custom --compress=6 --no-owner --file="$OUT.partial" "$BIOCHAIN_PG_URL"
mv "$OUT.partial" "$OUT"

# Uji integritas: daftar isi arsip harus terbaca dan memuat tabel inti
pg_restore --list "$OUT" | grep -q "TABLE DATA public harvests" || { echo "BACKUP RUSAK: $OUT" >&2; exit 2; }
sha256sum "$OUT" > "$OUT.sha256"

find "$DIR" -name 'biochain-*.dump*' -mtime +"$KEEP_DAYS" -delete
if [ -n "${BACKUP_RSYNC_TARGET:-}" ]; then
  rsync -a --chmod=F600 "$OUT" "$OUT.sha256" "$BACKUP_RSYNC_TARGET/"
fi
echo "{\"event\":\"backup_ok\",\"file\":\"$OUT\",\"bytes\":$(stat -c %s "$OUT")}"
