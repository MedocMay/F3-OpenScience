#!/usr/bin/env bash
# 从 contracts/ 重新生成两端类型。改了 schema 就跑这个,别手改 generated/。
set -euo pipefail

# 工具缺失必须显式失败 —— 否则会静默生成过时类型,CI 漂移检查也发现不了
need() { command -v "$1" >/dev/null 2>&1 || { echo "✗ 缺少 $1:$2"; exit 1; }; }
need datamodel-codegen "pip install datamodel-code-generator"
need json2ts           "npm i -g json-schema-to-typescript"
cd "$(dirname "$0")/.."   # -> repo 根
echo "→ Python pydantic v2 (datamodel-code-generator)"
for f in verification_report ipc; do
  datamodel-codegen --input contracts/$f.schema.json --input-file-type jsonschema \
    --output generated/python/${f}_models.py --output-model-type pydantic_v2.BaseModel --use-standard-collections
done
datamodel-codegen --input contracts/sidecar.schema.json --input-file-type jsonschema \
  --output generated/python/sidecar/ --output-model-type pydantic_v2.BaseModel --use-standard-collections
echo "→ TypeScript (json-schema-to-typescript)"
for f in verification_report ipc sidecar; do
  json2ts -i contracts/$f.schema.json -o generated/ts/${f}.d.ts
done
echo "→ gRPC stubs (memory.proto) — 需要时启用:"
echo "   python:  python -m grpc_tools.protoc -Icontracts --python_out=generated/python --grpc_python_out=generated/python contracts/memory.proto"
echo "   ts:      protoc --ts_out=generated/ts -Icontracts contracts/memory.proto"
echo "✓ done. 别手改 generated/,它是 contracts/ 的产物。"
