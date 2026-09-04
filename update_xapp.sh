#!/bin/bash

set -e

namespace="ricxapp"
xapp_name="hw-python"
version="1.0.0"

echo "================================================="
echo " Deploy / Update xApp: $xapp_name (v$version)"
echo " Namespace: $namespace"
echo "================================================="

echo "----------------- 1. Onboarding the xApp chart -----------------"
dms_cli onboard init/config-file.json init/schema.json

echo "----------------- 2. Terminating previous xApp pod -----------------"
dms_cli uninstall $xapp_name $namespace || true

echo -n "Waiting pod termination"
while kubectl get pods -n $namespace 2>/dev/null | grep -q "$namespace-$xapp_name-"; do
    sleep 1
    echo -n "."
done
printf "\n"

echo "----------------- 3. Removing previous Docker image -----------------"
docker image rm 127.0.0.1:5001/$xapp_name:$version 2>/dev/null || true

echo "----------------- 4. Building new Docker image -----------------"
docker build . -t 127.0.0.1:5001/$xapp_name:$version --network host

echo "----------------- 5. Pushing new Docker image to registry -----------------"
docker push 127.0.0.1:5001/$xapp_name:$version

echo "----------------- 6. Installing the xApp chart -----------------"
dms_cli install $xapp_name $version $namespace

echo -n "Waiting for pod to become ready (1/1)"
while ! kubectl get pods -n $namespace | grep "$namespace-$xapp_name-" | grep -q "1/1"; do
    if kubectl get pods -n $namespace | grep "$namespace-$xapp_name-" | grep -q "CrashLoopBackOff"; then 
        printf "\n%s\n" "INSTALLATION ERROR: Pod entered CrashLoopBackOff"
        kubectl logs POD/$(kubectl get pods -n $namespace | grep "$namespace-$xapp_name-" | awk '{print $1}') -n $namespace || true
        exit 1
    fi
    sleep 1
    echo -n "."
done
printf "\n"

echo "================================================="
echo " xApp $xapp_name deployed successfully!"
echo "================================================="
echo "Follow live logs with: ./log_xapp.sh or kubectl logs -f POD/... -n $namespace"
sleep 1
pod_name=$(kubectl get pods -n $namespace | grep "$namespace-$xapp_name-" | awk '{print $1}')
kubectl logs "$pod_name" -n $namespace | tail -n 15 || true
