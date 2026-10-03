#!/usr/bin/env bash
# Linux: captura/configura credenciais do ReqSys Teams Gateway.
#
# Modo sem admin (app ja preparado e consentimento do usuario permitido):
#   ./scripts/configurar-teams-graph.sh --acquire-delegated-token --update-env-file
#
# Modo app-only (exige ser dono do app ou administrador para criar segredo;
# permissoes de aplicacao e admin consent exigem funcao administrativa):
#   ./scripts/configurar-teams-graph.sh --create-secret --update-env-file
#
# Dependencias: Azure CLI (az), curl e jq.
set -euo pipefail

APP_DISPLAY_NAME="ReqSys Enterprise"
APP_ID=""
GRANT_PERMISSIONS=false
CREATE_SECRET=false
ACQUIRE_DELEGATED_TOKEN=false
UPDATE_ENV_FILE=false

GRAPH_APP_ID="00000003-0000-0000-c000-000000000000"
CHAT_CREATE_ROLE_ID="d9c48af6-9ad9-47ad-82c3-63757137b9af"
CHAT_READWRITE_ALL_ROLE_ID="294ce7c9-31ba-490a-ad7d-97a7d075e4ed"
DELEGATED_SCOPES="openid profile offline_access https://graph.microsoft.com/Chat.ReadWrite https://graph.microsoft.com/ChatMessage.Send"

usage() {
  cat <<'EOF'
Uso:
  configurar-teams-graph.sh [opcoes]

Opcoes:
  --app-id ID                  usa um App Registration especifico
  --app-display-name NOME      procura o app pelo nome (padrao: ReqSys Enterprise)
  --grant-permissions          adiciona Chat.Create/Chat.ReadWrite.All app-only
                               e tenta conceder admin consent
  --create-secret              cria um novo client secret com validade de 1 ano
  --acquire-delegated-token    login por device code para chats delegados
  --update-env-file            grava os valores no .env ignorado pelo Git
  -h, --help                   mostra esta ajuda

Sem opcoes mutaveis, o script apenas descobre e relata a configuracao.
Segredos e tokens nunca sao impressos no terminal.
EOF
}

while (($#)); do
  case "$1" in
    --app-id) APP_ID="${2:?valor ausente para --app-id}"; shift 2 ;;
    --app-display-name) APP_DISPLAY_NAME="${2:?valor ausente para --app-display-name}"; shift 2 ;;
    --grant-permissions) GRANT_PERMISSIONS=true; shift ;;
    --create-secret) CREATE_SECRET=true; shift ;;
    --acquire-delegated-token) ACQUIRE_DELEGATED_TOKEN=true; shift ;;
    --update-env-file) UPDATE_ENV_FILE=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Opcao desconhecida: $1" >&2; usage >&2; exit 2 ;;
  esac
done

for command_name in az curl jq; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "[ERRO] Dependencia ausente: $command_name" >&2
    exit 1
  fi
done

if ! account_json="$(az account show --output json 2>/dev/null)"; then
  echo "[ERRO] Azure CLI sem sessao. Execute: az login" >&2
  exit 1
fi

tenant_id="$(jq -r '.tenantId // empty' <<<"$account_json")"
signed_user="$(jq -r '.user.name // "desconhecido"' <<<"$account_json")"

if [[ -n "$APP_ID" ]]; then
  app_json="$(az ad app show --id "$APP_ID" --output json)"
else
  apps_json="$(az ad app list --display-name "$APP_DISPLAY_NAME" --output json)"
  app_count="$(jq 'length' <<<"$apps_json")"
  if [[ "$app_count" -eq 0 ]]; then
    echo "[ERRO] App '$APP_DISPLAY_NAME' nao encontrado; informe --app-id." >&2
    exit 1
  fi
  if [[ "$app_count" -gt 1 ]]; then
    echo "[AVISO] Mais de um app encontrado; usando o primeiro." >&2
  fi
  app_json="$(jq '.[0]' <<<"$apps_json")"
fi

client_id="$(jq -r '.appId // empty' <<<"$app_json")"
app_name="$(jq -r '.displayName // empty' <<<"$app_json")"
sp_json="$(az ad sp show --id "$client_id" --output json)"
service_principal_id="$(jq -r '.id // empty' <<<"$sp_json")"

echo "Conta: $signed_user"
echo "Tenant: $tenant_id"
echo "App: $app_name ($client_id)"
echo "Service principal: $service_principal_id"

graph_sp_id="$(az ad sp show --id "$GRAPH_APP_ID" --query id --output tsv)"
assignments_json="$(az rest \
  --method GET \
  --url "https://graph.microsoft.com/v1.0/servicePrincipals/$service_principal_id/appRoleAssignments" \
  --output json)"

missing_roles=()
for role_spec in "Chat.Create:$CHAT_CREATE_ROLE_ID" "Chat.ReadWrite.All:$CHAT_READWRITE_ALL_ROLE_ID"; do
  role_name="${role_spec%%:*}"
  role_id="${role_spec#*:}"
  if jq -e --arg id "$role_id" '.value[]? | select(.appRoleId == $id)' <<<"$assignments_json" >/dev/null; then
    echo "[OK] Permissao app-only $role_name concedida"
  else
    echo "[FALTA] Permissao app-only $role_name"
    missing_roles+=("$role_spec")
  fi
done

if $GRANT_PERMISSIONS && ((${#missing_roles[@]})); then
  for role_spec in "${missing_roles[@]}"; do
    role_name="${role_spec%%:*}"
    role_id="${role_spec#*:}"
    echo "Adicionando e consentindo $role_name..."
    az ad app permission add \
      --id "$client_id" \
      --api "$GRAPH_APP_ID" \
      --api-permissions "${role_id}=Role" >/dev/null
    body="$(jq -nc \
      --arg principalId "$service_principal_id" \
      --arg resourceId "$graph_sp_id" \
      --arg appRoleId "$role_id" \
      '{principalId:$principalId,resourceId:$resourceId,appRoleId:$appRoleId}')"
    az rest \
      --method POST \
      --url "https://graph.microsoft.com/v1.0/servicePrincipals/$service_principal_id/appRoleAssignments" \
      --headers "Content-Type=application/json" \
      --body "$body" >/dev/null
    echo "[OK] $role_name concedida"
  done
elif ((${#missing_roles[@]})); then
  echo "[INFO] Use --grant-permissions somente com uma conta administrativa autorizada."
fi

new_secret=""
if $CREATE_SECRET; then
  echo "Criando novo client secret..."
  credential_json="$(az ad app credential reset --id "$client_id" --years 1 --append --output json)"
  new_secret="$(jq -r '.password // empty' <<<"$credential_json")"
  if [[ -z "$new_secret" ]]; then
    echo "[ERRO] Azure CLI nao retornou o novo secret." >&2
    exit 1
  fi
  echo "[OK] Secret criado; valor oculto."
fi

delegated_token=""
delegated_expires_in=""
if $ACQUIRE_DELEGATED_TOKEN; then
  echo "Iniciando login delegado por device code..."
  device_json="$(curl --fail-with-body --silent --show-error \
    --request POST \
    --header "Content-Type: application/x-www-form-urlencoded" \
    --data-urlencode "client_id=$client_id" \
    --data-urlencode "scope=$DELEGATED_SCOPES" \
    "https://login.microsoftonline.com/$tenant_id/oauth2/v2.0/devicecode")"
  jq -r '.message' <<<"$device_json"

  device_code="$(jq -r '.device_code' <<<"$device_json")"
  interval="$(jq -r '.interval // 5' <<<"$device_json")"
  expires_in="$(jq -r '.expires_in' <<<"$device_json")"
  deadline=$((SECONDS + expires_in))

  while ((SECONDS < deadline)); do
    sleep "$interval"
    token_json="$(curl --silent --show-error \
      --request POST \
      --header "Content-Type: application/x-www-form-urlencoded" \
      --data-urlencode "grant_type=urn:ietf:params:oauth:grant-type:device_code" \
      --data-urlencode "client_id=$client_id" \
      --data-urlencode "device_code=$device_code" \
      "https://login.microsoftonline.com/$tenant_id/oauth2/v2.0/token")"
    oauth_error="$(jq -r '.error // empty' <<<"$token_json")"
    case "$oauth_error" in
      authorization_pending) continue ;;
      slow_down) interval=$((interval + 5)); continue ;;
      authorization_declined|expired_token)
        echo "[ERRO] Login delegado: $oauth_error" >&2
        exit 1
        ;;
      "")
        delegated_token="$(jq -r '.access_token // empty' <<<"$token_json")"
        delegated_expires_in="$(jq -r '.expires_in // empty' <<<"$token_json")"
        break
        ;;
      *)
        echo "[ERRO] OAuth: $oauth_error - $(jq -r '.error_description // empty' <<<"$token_json")" >&2
        exit 1
        ;;
    esac
  done
  if [[ -z "$delegated_token" ]]; then
    echo "[ERRO] Device code expirou sem concluir o login." >&2
    exit 1
  fi
  echo "[OK] Token delegado obtido; validade aproximada: ${delegated_expires_in}s. Valor oculto."
fi

set_env_var() {
  local file="$1" key="$2" value="$3" temp_file
  temp_file="$(mktemp)"
  if [[ -f "$file" ]]; then
    awk -v key="$key" -v value="$value" '
      BEGIN { found=0 }
      index($0, key "=") == 1 { print key "=" value; found=1; next }
      { print }
      END { if (!found) print key "=" value }
    ' "$file" >"$temp_file"
  else
    printf '%s=%s\n' "$key" "$value" >"$temp_file"
  fi
  chmod 600 "$temp_file"
  mv "$temp_file" "$file"
}

if $UPDATE_ENV_FILE; then
  repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  env_file="$repo_root/.env"
  set_env_var "$env_file" "AZURE_TENANT_ID" "$tenant_id"
  set_env_var "$env_file" "AZURE_CLIENT_ID" "$client_id"
  set_env_var "$env_file" "TEAMS_GRAPH_APP_SERVICE_PRINCIPAL_ID" "$service_principal_id"
  [[ -n "$new_secret" ]] && set_env_var "$env_file" "AZURE_CLIENT_SECRET" "$new_secret"
  [[ -n "$delegated_token" ]] && set_env_var "$env_file" "TEAMS_DELEGATED_TOKEN" "$delegated_token"
  chmod 600 "$env_file"
  echo "[OK] .env atualizado com permissao 600."
else
  echo "[INFO] Use --update-env-file para persistir os valores."
fi

echo "AZURE_TENANT_ID=$tenant_id"
echo "AZURE_CLIENT_ID=$client_id"
echo "AZURE_CLIENT_SECRET=$([[ -n "$new_secret" ]] && echo '[criado; oculto]' || echo '[nao criado]')"
echo "TEAMS_DELEGATED_TOKEN=$([[ -n "$delegated_token" ]] && echo '[capturado; oculto e temporario]' || echo '[nao capturado]')"
