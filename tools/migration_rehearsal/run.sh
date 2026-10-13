#!/usr/bin/env bash
# Rehearse a move from AvantFAX 3.3.5 to NamiFAX with real data: run the original PHP application (PHP 5.6 + MDB2 2.4.1 +
# MariaDB 10.3, SQL mode as in 2013), fill it through its own pages and classes, connect NamiFAX to the same database and
# archive folders, and compare. Needs docker and network access (the PHP image installs PEAR packages once).
# The original's source is no longer in the working tree: it is taken out of the git history (commit 9408385, the last one that has
# it; LEGACY_REF=<commit> uses another) into a temporary folder.
# Usage: tools/migration_rehearsal/run.sh [--keep]        (--keep leaves the containers running)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
WORK="${REHEARSAL_DIR:-$(mktemp -d)}"
PY="${PYTHON:-$ROOT/.venv/bin/python}"
LEGACY_REF="${LEGACY_REF:-9408385}"
NET=nami-rehearsal; DB=nami-rehearsal-db; APP=nami-rehearsal-app; IMG=nami-legacy-rehearsal

cleanup() { [ "${1:-}" = "--keep" ] || { docker rm -f "$APP" "$DB" >/dev/null 2>&1 || true; docker network rm "$NET" >/dev/null 2>&1 || true; }; }
trap 'cleanup "$KEEP"' EXIT
KEEP="${1:-}"
docker rm -f "$APP" "$DB" >/dev/null 2>&1 || true
docker network create "$NET" >/dev/null 2>&1 || true

echo "== the legacy application (the original's source from git $LEGACY_REF, in $WORK/app)"
git -C "$ROOT" cat-file -e "$LEGACY_REF^{commit}" 2>/dev/null || { echo "commit $LEGACY_REF is not in this repository (git fetch?)" >&2; exit 2; }
rm -rf "$WORK/app" "$WORK/original"; mkdir -p "$WORK/app" "$WORK/original"
git -C "$ROOT" archive "$LEGACY_REF" legacy | tar -x -C "$WORK/original"
LEGACY="$WORK/original/legacy"
cp -r "$LEGACY/avantfax/." "$WORK/app/"
cat > "$WORK/app/includes/local_config.php" <<PHP
<?php
	define('AFDB_ENGINE', 'mysql'); define('AFDB_HOST', '$DB'); define('AFDB_USER', 'avantfax');
	define('AFDB_PASS', 'd58fe49'); define('AFDB_NAME', 'avantfax');
	\$HYLASPOOL = '/var/spool/hylafax'; \$ENABLE_DID_ROUTING = false;
?>
PHP
chmod -R a+rwX "$WORK/app"
docker image inspect "$IMG" >/dev/null 2>&1 || docker build -q -t "$IMG" "$HERE"

echo "== MariaDB 10.3, the schema of 3.3.5 (create_tables.sql + db-update-330/334/335)"
docker run -d --name "$DB" --network "$NET" -e MARIADB_ROOT_PASSWORD=pw -p 127.0.0.1::3306 mariadb:10.3 --sql-mode= >/dev/null
for _ in $(seq 1 60); do docker exec "$DB" mysqladmin -uroot -ppw ping >/dev/null 2>&1 && break; sleep 2; done
docker exec "$DB" mysql -uroot -ppw -e "CREATE DATABASE avantfax DEFAULT CHARACTER SET utf8;
  GRANT ALL PRIVILEGES ON avantfax.* TO 'avantfax'@'%' IDENTIFIED BY 'd58fe49'; FLUSH PRIVILEGES;"
docker exec -i "$DB" mysql -uroot -ppw avantfax < "$LEGACY/create_tables.sql"
for n in 330 334 335; do docker exec -i "$DB" mysql -uroot -ppw avantfax < "$LEGACY/db-update-$n.sql" >/dev/null 2>&1 || true; done
DBPORT="$(docker port "$DB" 3306 | head -1 | sed 's/.*://')"

docker run -d --name "$APP" --network "$NET" -v "$WORK/app:/var/www/html" \
  -v "$HERE/php-quiet.ini:/usr/local/etc/php/conf.d/zz.ini" -p 127.0.0.1::80 "$IMG" >/dev/null
sleep 3
URL="http://127.0.0.1:$(docker port "$APP" 80 | head -1 | sed 's/.*://')"

echo "== fill it through its own pages (users, modems, categories, address book) and its own classes (faxes)"
"$PY" "$HERE/populate_legacy.py" "$URL"
"$PY" "$HERE/make_faxes.py" "$WORK/app"
chmod -R a+rwX "$WORK/app/faxes"
cp "$HERE/register_faxes.php" "$WORK/app/register_faxes.php"
docker exec "$APP" php /var/www/html/register_faxes.php 2>&1 | grep -E "^(OK|FAIL|archived)" || true
rm -f "$WORK/app/register_faxes.php"

echo "== connect NamiFAX to the same database and archive"
export REH_URL="mysql+pymysql://avantfax:d58fe49@127.0.0.1:$DBPORT/avantfax"
export NAMIFAX_SECRET_KEY=rehearsal NAMIFAX_SESSION_SECRET=rehearsal AVANTFAX_INSTALLDIR="$WORK/app"
export PYTHONWARNINGS=ignore
# The original cannot read the Argon2id hash that NamiFAX stores when someone logs in (its default), so a run that shares the database
# with the original program, and goes back to it, uses the original's format. NAMIFAX_PASSWORD_HASH=argon2 shows the default.
export NAMIFAX_PASSWORD_HASH="${NAMIFAX_PASSWORD_HASH:-md5}"
STATUS=0
"$PY" "$HERE/parity.py" "$URL" || STATUS=1
"$PY" "$HERE/two_way.py" "$URL" || STATUS=1
"$PY" "$HERE/check_text.py" ${STRICT:+--strict} || STATUS=1
echo "== the legacy application after NamiFAX has used the database"
"$PY" - "$URL" <<'PY' || STATUS=1
import http.cookiejar, re, sys, urllib.parse, urllib.request
base = sys.argv[1]
o = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
o.open(base + "/index.php").read()
o.open(base + "/index.php", urllib.parse.urlencode({"username": "carol", "password": "Carol#2013xy", "_submit_check": "1"}).encode()).read()
ids = sorted(set(re.findall(rb'id="faxid_(\d+)"', o.open(base + "/inbox.php").read())), key=int)
codes = {p: o.open(base + p).status for p in ("/addressbook.php", "/archive.php", "/emailbook.php", "/settings.php", "/outbox.php")}
print("legacy inbox:", [i.decode() for i in ids], "pages:", codes)
sys.exit(0 if ids and all(c == 200 for c in codes.values()) else 1)
PY
echo "== done (status $STATUS)"
exit $STATUS
