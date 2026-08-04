#!/bin/sh
# Резервное копирование базы данных.
#
# П. 4.1.3 ТЗ: копирование ежесуточно, хранение копий за 7 суток, допустимая
# потеря данных при аварии носителя — не более 24 часов.
#
# Здесь же ротация недельных копий: суточные защищают от свежей ошибки,
# недельные — от той, что заметили не сразу.
#
# Установка в расписание (ежесуточно в 03:30):
#   crontab -e
#   30 3 * * * /opt/grants-komi/deploy/backup.sh >> /var/log/grants-backup.log 2>&1

set -eu

PROJECT_DIR="${PROJECT_DIR:-/opt/grants-komi}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/grants-komi}"
DAILY_KEEP=7
WEEKLY_KEEP=4

cd "$PROJECT_DIR"
. ./.env

mkdir -p "$BACKUP_DIR/daily" "$BACKUP_DIR/weekly"

STAMP=$(date +%Y-%m-%d)
FILE="$BACKUP_DIR/daily/grants-$STAMP.dump"

# Формат -Fc сжат и позволяет восстанавливать отдельные таблицы,
# а не только базу целиком
docker compose -f docker-compose.prod.yml exec -T db \
	pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > "$FILE"

# Пустой файл означает, что выгрузка не удалась: лучше заметить сразу,
# чем обнаружить это при восстановлении
if [ ! -s "$FILE" ]; then
	echo "ОШИБКА: выгрузка пуста, копия удалена"
	rm -f "$FILE"
	exit 1
fi

echo "$(date '+%F %T') копия создана: $FILE ($(du -h "$FILE" | cut -f1))"

# По понедельникам суточная копия дублируется в недельные
if [ "$(date +%u)" = "1" ]; then
	cp "$FILE" "$BACKUP_DIR/weekly/grants-$STAMP.dump"
fi

# Ротация: старые копии удаляются, чтобы диск не заполнился
find "$BACKUP_DIR/daily" -name '*.dump' -mtime +$DAILY_KEEP -delete
find "$BACKUP_DIR/weekly" -name '*.dump' -mtime +$((WEEKLY_KEEP * 7)) -delete

echo "суточных копий: $(ls -1 "$BACKUP_DIR/daily" | wc -l), недельных: $(ls -1 "$BACKUP_DIR/weekly" | wc -l)"
