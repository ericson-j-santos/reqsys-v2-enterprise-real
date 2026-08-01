#!/usr/bin/env bash
set -euo pipefail
: "${ASSET_JSON:?}" "${FLY_API_TOKEN:?}" "${RESTIC_REPOSITORY:?}" "${RESTIC_PASSWORD:?}" "${RUN_URL:?}" "${CORRELATION_ID:?}"
mkdir -p work/config artifacts/backup
printf '%s\n' "$ASSET_JSON" > work/config/asset.json
readarray -t cfg < <(python - <<'PY'
import json
x=json.load(open('work/config/asset.json'))
for k in ('id','environment','fly_app','database_path','rpo_target_minutes','rto_target_seconds'): print(x[k])
r=x['retention']; print(r['keep_daily'],r['keep_weekly'],r['keep_monthly'],r['keep_yearly'],sep='\n')
PY
)
ASSET_ID=${cfg[0]}; TARGET_ENV=${cfg[1]}; FLY_APP=${cfg[2]}; DB_PATH=${cfg[3]}; KEEP_DAILY=${cfg[6]}; KEEP_WEEKLY=${cfg[7]}; KEEP_MONTHLY=${cfg[8]}; KEEP_YEARLY=${cfg[9]}
mkdir -p "work/source/$ASSET_ID"
flyctl machine list -a "$FLY_APP" --json > work/machines.json
MACHINE_ID=$(python - <<'PY'
import json
m=[x for x in json.load(open('work/machines.json')) if str(x.get('state','')).lower() in {'started','running'}]
if not m: raise SystemExit('Nenhuma Fly Machine em execução.')
print(m[0]['id'])
PY
)
REMOTE_SCRIPT="/tmp/reqsys-backup-${GITHUB_RUN_ID}.py"; REMOTE_DB="/tmp/${ASSET_ID}-${GITHUB_RUN_ID}.db"; REMOTE_META="/tmp/${ASSET_ID}-${GITHUB_RUN_ID}.json"
cleanup(){ flyctl ssh console -a "$FLY_APP" --machine "$MACHINE_ID" -C "rm -f '$REMOTE_SCRIPT' '$REMOTE_DB' '$REMOTE_META'" >/dev/null 2>&1 || true; rm -rf work; }
trap cleanup EXIT
flyctl ssh sftp put scripts/remote_sqlite_backup.py "$REMOTE_SCRIPT" -a "$FLY_APP" --machine "$MACHINE_ID" --mode 0700
flyctl ssh console -a "$FLY_APP" --machine "$MACHINE_ID" -C "python '$REMOTE_SCRIPT' --source '$DB_PATH' --target '$REMOTE_DB' --metadata '$REMOTE_META'"
flyctl ssh sftp get "$REMOTE_DB" "work/source/$ASSET_ID/reqsys.db" -a "$FLY_APP" --machine "$MACHINE_ID"
flyctl ssh sftp get "$REMOTE_META" "work/source/$ASSET_ID/source.json" -a "$FLY_APP" --machine "$MACHINE_ID"
python scripts/reqsys_free_tier_backup.py manifest --database "work/source/$ASSET_ID/reqsys.db" --output work/local.json
ASSET_ID="$ASSET_ID" python - <<'PY'
import json,os
r=json.load(open(f"work/source/{os.environ['ASSET_ID']}/source.json")); l=json.load(open('work/local.json'))
assert r['sha256']==l['sha256'] and r['table_counts']==l['table_counts'] and r['quick_check']==l['quick_check']=='ok'
PY
STARTED_AT=$(python -c 'from datetime import UTC,datetime; print(datetime.now(UTC).isoformat())')
restic cat config >/dev/null 2>&1 || restic init
restic backup "work/source/$ASSET_ID" --host "reqsys-$TARGET_ENV" --tag "asset:$ASSET_ID" --tag "environment:$TARGET_ENV" --json > work/backup.json
SNAPSHOT_ID=$(python - <<'PY'
import json
s=None
for line in open('work/backup.json'):
 x=json.loads(line)
 if x.get('message_type')=='summary': s=x.get('snapshot_id')
if not s: raise SystemExit('snapshot_id ausente')
print(s)
PY
)
restic forget --tag "asset:$ASSET_ID" --keep-daily "$KEEP_DAILY" --keep-weekly "$KEEP_WEEKLY" --keep-monthly "$KEEP_MONTHLY" --keep-yearly "$KEEP_YEARLY" --prune > work/retention.txt
restic check
restic stats --mode raw-data --json > work/stats.json
set +e; python scripts/reqsys_free_tier_backup.py quota --stats work/stats.json --warn 8589934592 --hard 9663676416 --output work/quota.json; QRC=$?; set -e
START_NS=$(date +%s%N); mkdir -p work/restored; restic restore "$SNAPSHOT_ID" --target work/restored
RESTORED_DB=$(find work/restored -type f -path "*/$ASSET_ID/reqsys.db" -print -quit); [[ -n "$RESTORED_DB" ]]
python scripts/reqsys_free_tier_backup.py manifest --database "$RESTORED_DB" --output work/restored.json
RTO=$(python -c "print(($(date +%s%N)-$START_NS)/1_000_000_000)"); COMPLETED_AT=$(python -c 'from datetime import UTC,datetime; print(datetime.now(UTC).isoformat())')
mkdir -p "artifacts/backup/$ASSET_ID"
python scripts/reqsys_free_tier_backup.py evidence --asset work/config/asset.json --source "work/source/$ASSET_ID/source.json" --restored work/restored.json --quota work/quota.json --snapshot-id "$SNAPSHOT_ID" --run-url "$RUN_URL" --correlation-id "$CORRELATION_ID" --started-at "$STARTED_AT" --completed-at "$COMPLETED_AT" --rto "$RTO" --output "artifacts/backup/$ASSET_ID/evidence.json"
[[ $QRC -ne 2 ]]
