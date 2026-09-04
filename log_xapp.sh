#!/bin/bash

namespace="ricxapp"
xapp_name="hw-python"

pod_name=$(kubectl get pods -n "$namespace" 2>/dev/null | grep "$namespace-$xapp_name-" | awk '{print $1}' | head -n 1)

if [ -z "$pod_name" ]; then
    echo "Erro: Pod da xApp $xapp_name não encontrado no namespace $namespace."
    exit 1
fi

echo "================================================="
echo " Streaming logs from pod: $pod_name (Namespace: $namespace)"
echo " Press Ctrl+C to stop"
echo "================================================="

kubectl logs -f "$pod_name" -n "$namespace"
