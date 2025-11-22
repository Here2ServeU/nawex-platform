#!/usr/bin/env bash
set -euo pipefail

echo "==============================================="
echo "   T2S ENTERPRISE PLATFORM — DEPLOYMENT SCRIPT"
echo "==============================================="

# -------------------------------------------------
# 0. Delete old namespaces (if they exist)
# -------------------------------------------------
echo "[1/8] Cleaning old namespaces..."

for ns in monitoring apps aiops argocd; do
  if kubectl get namespace "$ns" >/dev/null 2>&1; then
    echo "Deleting namespace: $ns"
    kubectl delete namespace "$ns" --wait=true
  else
    echo "Namespace $ns does not exist. Skipping."
  fi
done

echo "[OK] Old namespaces removed."
echo

# -------------------------------------------------
# 1. Install kube-prometheus-stack
# -------------------------------------------------
echo "[2/8] Installing Prometheus/Grafana..."

helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace

echo "[OK] Monitoring stack deployed."
echo

# -------------------------------------------------
# 2. Deploy Express Web App
# -------------------------------------------------
echo "[3/8] Deploying Express Web App..."

helm upgrade --install express-web-app ./charts/express-web-app \
  -n apps --create-namespace

echo "[OK] Express Web App deployed."
echo

# -------------------------------------------------
# 3. Deploy AIOps Microservice
# -------------------------------------------------
echo "[4/8] Deploying AIOps Engine..."

helm upgrade --install aiops ./charts/aiops \
  -n aiops --create-namespace

echo "[OK] AIOps Engine deployed."
echo

# -------------------------------------------------
# 4. Install ArgoCD
# -------------------------------------------------
echo "[5/8] Installing ArgoCD..."

kubectl create namespace argocd || true

helm repo add argo https://argoproj.github.io/argo-helm
helm repo update

helm upgrade --install argocd argo/argo-cd \
  -n argocd \
  --set server.service.type=ClusterIP

echo "[OK] ArgoCD installed."
echo

# -------------------------------------------------
# 5. Apply GitOps Application (Express Web App)
# -------------------------------------------------
echo "[6/8] Applying GitOps app (express-web-app)..."

kubectl apply -f argocd/express-web-app.yaml

echo "[OK] GitOps application applied."
echo

# -------------------------------------------------
# 6. Summary
# -------------------------------------------------
echo "======================================================"
echo " DEPLOYMENT COMPLETE — T2S ENTERPRISE PLATFORM READY"
echo "======================================================"
echo
echo "Namespaces created:"
echo "  - monitoring"
echo "  - apps"
echo "  - aiops"
echo "  - argocd"
echo
echo "To access ArgoCD UI:"
echo "  kubectl port-forward svc/argocd-server -n argocd 8080:443"
echo
echo "To access Grafana:"
echo "  kubectl -n monitoring port-forward svc/kube-prometheus-stack-grafana 3000:80"
echo
echo "To access AIOps Dashboard:"
echo "  bash scripts/port-forward-aiops.sh"
echo
echo "======================================================"
