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

MACHINE_ID=""
MACHINE_INITIAL_STATE="unknown"
MACHINE_FINAL_STATE="unknown"
MACHINE_STARTED_FOR_BACKUP=false
MACHINE_RESTORED_TO_INITIAL_STATE=false
MACHINE_START_AT=""
MACHINE_READY_AT=""
MACHINE_RESTORE_AT=""
REMOTE_SCRIPT=""
REMOTE_DB=""
REMOTE_META=""
REMOTE_CLEANED=false

machine_state() {
  flyctl machine list -a "$FLY_APP" --json > work/machines-current.json
  MACHINE_ID="$MACHINE_ID" python - <<'PY'
import json, os
machine_id=os.environ['MACHINE_ID']
for item in json.load(open('work/machines-current.json')):
    if str(item.get('id','')) == machine_id:
        print(str(item.get('state','unknown')).lower())
        raise SystemExit(0)
raise SystemExit(f'Machine {machine_id} não encontrada.')
PY
}

cleanup_remote() {
  [[ "$REMOTE_CLEANED" == true ]] && return 0
  if [[ -n "$MACHINE_ID" && -n "$REMOTE_SCRIPT" ]]; then
    flyctl ssh console -a "$FLY_APP" --machine "$MACHINE_ID" -C "rm -f '$REMOTE_SCRIPT' '$REMOTE_DB' '$REMOTE_META'" >/dev/null 2>&1 || true
  fi
  REMOTE_CLEANED=true
}

restore_machine_state() {
  [[ -z "$MACHINE_ID" ]] && return 0
  if [[ "$MACHINE_STARTED_FOR_BACKUP" == true && "$MACHINE_RESTORED_TO_INITIAL_STATE" != true ]]; then
    cleanup_remote
    flyctl machine stop "$MACHINE_ID" -a "$FLY_APP" --wait-timeout 60s
    flyctl machine wait "$MACHINE_ID" -a "$FLY_APP" --state stopped --wait-timeout 60s
    MACHINE_FINAL_STATE=$(machine_state)
    [[ "$MACHINE_FINAL_STATE" == "stopped" ]]
    MACHINE_RESTORED_TO_INITIAL_STATE=true
    MACHINE_RESTORE_AT=$(python -c 'from datetime import UTC,datetime; print(datetime.now(UTC).isoformat())')
  elif [[ "$MACHINE_STARTED_FOR_BACKUP" != true ]]; then
    MACHINE_FINAL_STATE=$(machine_state)
    MACHINE_RESTORED_TO_INITIAL_STATE=true
  fi
}

write_lifecycle_summary() {
  mkdir -p "artifacts/backup/$ASSET_ID"
  MACHINE_ID="$MACHINE_ID" MACHINE_INITIAL_STATE="$MACHINE_INITIAL_STATE" MACHINE_FINAL_STATE="$MACHINE_FINAL_STATE" \
  MACHINE_STARTED_FOR_BACKUP="$MACHINE_STARTED_FOR_BACKUP" MACHINE_RESTORED_TO_INITIAL_STATE="$MACHINE_RESTORED_TO_INITIAL_STATE" \
  MACHINE_START_AT="$MACHINE_START_AT" MACHINE_READY_AT="$MACHINE_READY_AT" MACHINE_RESTORE_AT="$MACHINE_RESTORE_AT" \
  python - <<'PY'
import json, os
p=f"artifacts/backup/{os.environ['ASSET_ID']}/machine-lifecycle.json" if 'ASSET_ID' in os.environ else None
if not p:
    raise SystemExit('ASSET_ID ausente')
def b(name): return os.environ.get(name,'false').lower() == 'true'
data={
  'schema_version':'1.0.0',
  'machine_id':os.environ.get('MACHINE_ID',''),
  'machine_initial_state':os.environ.get('MACHINE_INITIAL_STATE','unknown'),
  'machine_started_for_backup':b('MACHINE_STARTED_FOR_BACKUP'),
  'machine_ready_at':os.environ.get('MACHINE_READY_AT','') or None,
  'machine_final_state':os.environ.get('MACHINE_FINAL_STATE','unknown'),
  'machine_restored_to_initial_state':b('MACHINE_RESTORED_TO_INITIAL_STATE'),
  'machine_start_at':os.environ.get('MACHINE_START_AT','') or None,
  'machine_restore_at':os.environ.get('MACHINE_RESTORE_AT','') or None,
}
with open(p,'w',encoding='utf-8') as f:
    json.dump(data,f,ensure_ascii=False,sort_keys=True,separators=(',',':'))
PY
}

cleanup() {
  rc=$?
  trap - EXIT
  set +e
  cleanup_remote
  restore_machine_state
  restore_rc=$?
  export ASSET_ID
  write_lifecycle_summary
  lifecycle_rc=$?
  if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
    {
      echo "### Fly Machine lifecycle"
      echo "- machine_initial_state: $MACHINE_INITIAL_STATE"
      echo "- machine_started_for_backup: $MACHINE_STARTED_FOR_BACKUP"
      echo "- machine_final_state: $MACHINE_FINAL_STATE"
      echo "- machine_restored_to_initial_state: $MACHINE_RESTORED_TO_INITIAL_STATE"
    } >> "$GITHUB_STEP_SUMMARY"
  fi
  rm -rf work
  if [[ $restore_rc -ne 0 || $lifecycle_rc -ne 0 ]]; then rc=1; fi
  exit "$rc"
}
trap cleanup EXIT

flyctl machine list -a "$FLY_APP" --json > work/machines.json
readarray -t machine_cfg < <(python - <<'PY'
import json
items=json.load(open('work/machines.json'))
if not items:
    raise SystemExit('Nenhuma Fly Machine encontrada para o app.')
priority={'started':0,'running':0,'stopped':1}
compatible=[]
for item in items:
    state=str(item.get('state','unknown')).lower()
    if state in priority:
        compatible.append((priority[state],str(item.get('id','')),state))
if not compatible:
    states=','.join(sorted({str(x.get('state','unknown')).lower() for x in items}))
    raise SystemExit(f'Nenhuma Fly Machine em estado suportado para backup. estados={states}')
compatible.sort()
_, machine_id, state=compatible[0]
print(machine_id)
print(state)
PY
)
MACHINE_ID=${machine_cfg[0]}; MACHINE_INITIAL_STATE=${machine_cfg[1]}; MACHINE_FINAL_STATE=$MACHINE_INITIAL_STATE

if [[ "$MACHINE_INITIAL_STATE" == "stopped" ]]; then
  MACHINE_START_AT=$(python -c 'from datetime import UTC,datetime; print(datetime.now(UTC).isoformat())')
  flyctl machine start "$MACHINE_ID" -a "$FLY_APP"
  MACHINE_STARTED_FOR_BACKUP=true
  flyctl machine wait "$MACHINE_ID" -a "$FLY_APP" --state started --wait-timeout 90s
  MACHINE_FINAL_STATE=$(machine_state)
  [[ "$MACHINE_FINAL_STATE" == "started" || "$MACHINE_FINAL_STATE" == "running" ]]
  MACHINE_READY_AT=$(python -c 'from datetime import UTC,datetime; print(datetime.now(UTC).isoformat())')
else
  MACHINE_RESTORED_TO_INITIAL_STATE=true
  MACHINE_READY_AT=$(python -c 'from datetime import UTC,datetime; print(datetime.now(UTC).isoformat())')
fi

REMOTE_SCRIPT="/tmp/reqsys-backup-${GITHUB_RUN_ID}.py"; REMOTE_DB="/tmp/${ASSET_ID}-${GITHUB_RUN_ID}.db"; REMOTE_META="/tmp/${ASSET_ID}-${GITHUB_RUN_ID}.json"
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

cleanup_remote
restore_machine_state
export ASSET_ID
write_lifecycle_summary

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
ASSET_ID="$ASSET_ID" python - <<'PY'
import json, os
base=f"artifacts/backup/{os.environ['ASSET_ID']}"
with open(f"{base}/evidence.json",encoding='utf-8') as f: evidence=json.load(f)
with open(f"{base}/machine-lifecycle.json",encoding='utf-8') as f: lifecycle=json.load(f)
evidence['machine_lifecycle']=lifecycle
with open(f"{base}/evidence.json",'w',encoding='utf-8') as f:
    json.dump(evidence,f,ensure_ascii=False,sort_keys=True,separators=(',',':'))
PY
[[ "$MACHINE_RESTORED_TO_INITIAL_STATE" == true ]]
[[ $QRC -ne 2 ]]
