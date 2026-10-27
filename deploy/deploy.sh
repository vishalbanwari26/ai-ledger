#!/usr/bin/env bash
# Deploy AI Ledger to Nebius Serverless Endpoints (CPU only: the model runs on Token Factory).
# Prereqs: docker, the nebius CLI configured (`nebius profile create`), and an image registry you can push to.
# Usage:   IMAGE=ghcr.io/<you>/ai-ledger:latest NEBIUS_API_KEY=... ./deploy/deploy.sh
#          STEP=push   builds and pushes the image only (then make the package public)
#          STEP=create creates the endpoint from an image that is already pushed
# Default (STEP=all) does both. deploy/wizard.sh walks through the whole thing, including the manual steps.
set -euo pipefail
: "${IMAGE:?set IMAGE, e.g. ghcr.io/<you>/ai-ledger:latest (must be pullable by Nebius; public is simplest)}"
STEP="${STEP:-all}"
NAME="${NAME:-ai-ledger}"

if [[ "$STEP" == "all" || "$STEP" == "push" ]]; then
  # Nebius CPU platforms are amd64, so build for that even on an Apple Silicon laptop.
  docker buildx build --platform linux/amd64 -t "$IMAGE" --push .
fi

if [[ "$STEP" == "all" || "$STEP" == "create" ]]; then
  : "${NEBIUS_API_KEY:?set NEBIUS_API_KEY (use a key created just for this demo)}"
  # No --auth flag: judges need to open the demo URL. Abuse is bounded by the app's own hourly LLM cap.
  nebius ai endpoint create \
    --name "$NAME" \
    --image "$IMAGE" \
    --platform cpu-d3 \
    --preset 2vcpu-8gb \
    --disk-size 20Gi \
    --container-port 8080 \
    --env "NEBIUS_API_KEY=$NEBIUS_API_KEY,LEDGER_LLM_PER_HOUR=120" \
    --public

  ID=$(nebius ai endpoint get-by-name --name "$NAME" --format jsonpath='{.metadata.id}')
  echo "endpoint id: $ID"
  URL=$(nebius ai endpoint get "$ID" --format json \
    | jq -r '.status.public_endpoints[] | select(startswith("https://"))' | head -1)
  echo "ENDPOINT_URL=$URL"
  echo "stop when not needed:  nebius ai endpoint stop --id $ID"
  echo "delete after judging:  nebius ai endpoint delete --id $ID"
fi
