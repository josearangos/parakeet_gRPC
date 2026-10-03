#!/bin/sh
# Regenerate gRPC/protobuf Python code from proto/speech.proto. Never edit the output by hand.
set -e
cd "$(dirname "$0")/.."
python -m grpc_tools.protoc -I proto --python_out=generated --grpc_python_out=generated proto/speech.proto
