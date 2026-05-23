#!/bin/bash
# Argamag Equine Registry — Автомат backup script
# Тохиргоо
APP_DIR="$HOME/Desktop/horse"
DB_FILE="$APP_DIR/data/horse.db"
BACKUP_DIR="$APP_DIR/backups"
ICLOUD_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/ArgamagBackup"
KEEP_DAYS=30  # Хэдэн хоногийн backup хадгалах

DATE=$(date +%Y-%m-%d)
TIME=$(date +%H%M)

mkdir -p "$BACKUP_DIR"
mkdir -p "$ICLOUD_DIR" 2>/dev/null

# 1. Локал backup
BACKUP_FILE="$BACKUP_DIR/horse_${DATE}_${TIME}.db"
cp "$DB_FILE" "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "✅ Локал backup: $BACKUP_FILE"
else
    echo "❌ Backup амжилтгүй!" >&2
    exit 1
fi

# 2. iCloud backup (хамгийн сүүлийн хувилбар)
ICLOUD_FILE="$ICLOUD_DIR/horse_${DATE}.db"
cp "$DB_FILE" "$ICLOUD_FILE" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "☁️  iCloud backup: $ICLOUD_FILE"
else
    echo "⚠️  iCloud backup алдаа (iCloud тохиргоогоо шалгаарай)"
fi

# 3. Хуучин backup устгах (30 хоногоос өмнөх)
find "$BACKUP_DIR" -name "horse_*.db" -mtime +$KEEP_DAYS -delete
echo "🗑️  ${KEEP_DAYS} хоногоос хуучин backup устгагдлаа"

# 4. Backup тоо харуулах
COUNT=$(ls "$BACKUP_DIR"/horse_*.db 2>/dev/null | wc -l)
SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)
echo "📦 Нийт backup: ${COUNT} файл (${SIZE})"
echo "✅ Backup дууслаа: $(date '+%Y-%m-%d %H:%M')"
