#!/usr/bin/env bash
# One-time, idempotent Azure setup for AI drafting of website recipe submissions.
#
# Creates, in the personal "Azure subscription 1" only:
#   - a resource group and an Azure AI Foundry (AIServices) resource in swedencentral
#   - a gpt-6-luna GlobalStandard deployment with small capacity
#   - an Entra app registration whose only credential is a GitHub OIDC federated
#     credential for masonrecipes/masonrecipes.github.io on the main branch, with
#     "Cognitive Services OpenAI User" on that one resource and nothing else
# Then prints the GitHub repository variables to set. Safe to re-run.
#
# Usage: az login, then ./scripts/setup-foundry.sh

set -euo pipefail

SUBSCRIPTION_NAME="Azure subscription 1"
LOCATION="swedencentral"
RESOURCE_GROUP="${RESOURCE_GROUP:-rg-mason-recipes-ai}"
DEPLOYMENT_NAME="gpt-6-luna"
MODEL_NAME="gpt-6-luna"
MODEL_VERSION="2026-09-22"
CAPACITY="${CAPACITY:-10}" # thousands of tokens per minute
APP_NAME="mason-recipes-github-intake"
REPO="masonrecipes/masonrecipes.github.io"
FEDERATED_NAME="github-main-branch"
FEDERATED_SUBJECT="repo:${REPO}:ref:refs/heads/main"
ROLE="Cognitive Services OpenAI User"

say() { printf '\n==> %s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

command -v az >/dev/null || die "Azure CLI (az) is not installed."
az account show --output none 2>/dev/null || die "Run 'az login' first."

say "Selecting subscription '${SUBSCRIPTION_NAME}'"
matches="$(az account list --all --query "length([?name=='${SUBSCRIPTION_NAME}'])" --output tsv)"
[[ "$matches" == "1" ]] || die "Expected exactly one subscription named '${SUBSCRIPTION_NAME}', found ${matches}. Refusing to continue."
az account set --subscription "$SUBSCRIPTION_NAME"
current="$(az account show --query name --output tsv)"
[[ "$current" == "$SUBSCRIPTION_NAME" ]] || die "Active subscription is '${current}', not '${SUBSCRIPTION_NAME}'. Refusing to continue."
SUBSCRIPTION_ID="$(az account show --query id --output tsv)"
TENANT_ID="$(az account show --query tenantId --output tsv)"
echo "Using subscription ${SUBSCRIPTION_ID} in tenant ${TENANT_ID}."

# The resource name is also its global DNS name, so derive a stable unique suffix.
ACCOUNT_NAME="${ACCOUNT_NAME:-mason-recipes-ai-${SUBSCRIPTION_ID:0:8}}"

say "Resource group ${RESOURCE_GROUP} (${LOCATION})"
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none

say "Azure AI Foundry resource ${ACCOUNT_NAME}"
if ! az cognitiveservices account show --name "$ACCOUNT_NAME" --resource-group "$RESOURCE_GROUP" --output none 2>/dev/null; then
  az cognitiveservices account create \
    --name "$ACCOUNT_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --kind AIServices \
    --sku S0 \
    --custom-domain "$ACCOUNT_NAME" \
    --yes \
    --output none
fi
RESOURCE_ID="$(az cognitiveservices account show --name "$ACCOUNT_NAME" --resource-group "$RESOURCE_GROUP" --query id --output tsv)"
# Keyless only: the workflow uses Entra tokens, so turn off API keys.
az resource update --ids "$RESOURCE_ID" --set properties.disableLocalAuth=true --output none

say "Model deployment ${DEPLOYMENT_NAME} (GlobalStandard, capacity ${CAPACITY})"
if ! az cognitiveservices account deployment show --name "$ACCOUNT_NAME" --resource-group "$RESOURCE_GROUP" \
    --deployment-name "$DEPLOYMENT_NAME" --output none 2>/dev/null; then
  az cognitiveservices account deployment create \
    --name "$ACCOUNT_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --deployment-name "$DEPLOYMENT_NAME" \
    --model-format OpenAI \
    --model-name "$MODEL_NAME" \
    --model-version "$MODEL_VERSION" \
    --sku-name GlobalStandard \
    --sku-capacity "$CAPACITY" \
    --output none
fi

say "Entra app registration ${APP_NAME}"
CLIENT_ID="$(az ad app list --display-name "$APP_NAME" --query "[0].appId" --output tsv)"
if [[ -z "$CLIENT_ID" ]]; then
  CLIENT_ID="$(az ad app create --display-name "$APP_NAME" --query appId --output tsv)"
fi
SP_OBJECT_ID="$(az ad sp list --filter "appId eq '${CLIENT_ID}'" --query "[0].id" --output tsv)"
if [[ -z "$SP_OBJECT_ID" ]]; then
  SP_OBJECT_ID="$(az ad sp create --id "$CLIENT_ID" --query id --output tsv)"
fi

say "Federated credential for ${FEDERATED_SUBJECT}"
existing_subject="$(az ad app federated-credential list --id "$CLIENT_ID" \
  --query "[?name=='${FEDERATED_NAME}'].subject | [0]" --output tsv)"
if [[ -z "$existing_subject" ]]; then
  az ad app federated-credential create --id "$CLIENT_ID" --parameters "$(cat <<EOF
{
  "name": "${FEDERATED_NAME}",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "${FEDERATED_SUBJECT}",
  "description": "GitHub Actions on ${REPO} main (issue events)",
  "audiences": ["api://AzureADTokenExchange"]
}
EOF
)" --output none
elif [[ "$existing_subject" != "$FEDERATED_SUBJECT" ]]; then
  die "Federated credential '${FEDERATED_NAME}' exists with subject '${existing_subject}'. Fix it by hand."
fi

say "Role '${ROLE}' on ${ACCOUNT_NAME} only"
assigned="$(az role assignment list --assignee "$SP_OBJECT_ID" --scope "$RESOURCE_ID" --role "$ROLE" \
  --query "length(@)" --output tsv)"
if [[ "$assigned" == "0" ]]; then
  # A new service principal can take a minute to replicate; retry briefly.
  for attempt in 1 2 3 4 5 6; do
    if az role assignment create \
        --assignee-object-id "$SP_OBJECT_ID" \
        --assignee-principal-type ServicePrincipal \
        --role "$ROLE" \
        --scope "$RESOURCE_ID" \
        --output none; then
      break
    fi
    [[ "$attempt" == "6" ]] && die "Could not assign '${ROLE}'."
    sleep 10
  done
fi

ENDPOINT="https://${ACCOUNT_NAME}.openai.azure.com"

say "Done. Set these GitHub repository variables (none of them are secrets):"
cat <<EOF

gh variable set AZURE_CLIENT_ID --repo ${REPO} --body "${CLIENT_ID}"
gh variable set AZURE_TENANT_ID --repo ${REPO} --body "${TENANT_ID}"
gh variable set AZURE_SUBSCRIPTION_ID --repo ${REPO} --body "${SUBSCRIPTION_ID}"
gh variable set AZURE_OPENAI_ENDPOINT --repo ${REPO} --body "${ENDPOINT}"
gh variable set AZURE_OPENAI_DEPLOYMENT --repo ${REPO} --body "${DEPLOYMENT_NAME}"

EOF
