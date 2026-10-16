#!/usr/bin/env bash
# Regenerate src/suncharts_api (low-level client) from openapi.json with a pinned openapi-generator.
# The ergonomic layer in src/suncharts is hand-written and never touched by this script.
#   scripts/generate.sh                 # uses ./openapi.json
#   SPEC=path/to/openapi.json scripts/generate.sh
set -euo pipefail
cd "$(dirname "$0")/.."
OAG_VERSION=7.26.0
SPEC=${SPEC:-openapi.json}
[ "$SPEC" != openapi.json ] && cp "$SPEC" openapi.json
JAR=${OAG_JAR:-${XDG_CACHE_HOME:-$HOME/.cache}/openapi-generator/openapi-generator-cli-$OAG_VERSION.jar}
if [ ! -f "$JAR" ]; then
  mkdir -p "$(dirname "$JAR")"
  curl -sSfLo "$JAR" "https://repo1.maven.org/maven2/org/openapitools/openapi-generator-cli/$OAG_VERSION/openapi-generator-cli-$OAG_VERSION.jar"
fi
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
python3 scripts/normalize-spec.py openapi.json > "$TMP/spec.json"
java -jar "$JAR" generate -q -g python -i "$TMP/spec.json" -o "$TMP/out" --skip-validate-spec \
  --additional-properties=packageName=suncharts_api,projectName=suncharts-sdk,packageVersion=0.0.0,hideGenerationTimestamp=true \
  --global-property=apiTests=false,modelTests=false,apiDocs=false,modelDocs=false
rm -rf src/suncharts_api && cp -R "$TMP/out/suncharts_api" src/suncharts_api
echo "generated src/suncharts_api from $(python3 -c 'import json;print(json.load(open("openapi.json"))["info"]["version"])') spec"
