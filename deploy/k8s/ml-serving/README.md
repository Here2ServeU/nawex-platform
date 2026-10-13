# ML serving manifests (`golden-ml` namespace)

| File | What | Kinds |
|---|---|---|
| `namespace.yaml` | Namespace (Pod Security baseline) + GPU / MIG ResourceQuota | Namespace, ResourceQuota |
| `inferenceservice.yaml` | KServe custom predictor for the fraud model (OIP V2, canary 10 %, concurrency autoscaling 2–10) | InferenceService (CRD), ServiceAccount, PVC |
| `vllm.yaml` | vLLM OpenAI-compatible LLM server on 1 GPU, HF model via env, PVC weight cache | PVC, Deployment, Service |
| `triton.yaml` | NVIDIA Triton on a MIG 3g.40gb slice, model repository on a PVC | PVC, Deployment, Service |
| `triton-model-repository/` | Example Triton repository layout and `config.pbtxt` | — |
| `networkpolicy.yaml` | Default-deny ingress; allow only the gateways and Prometheus | NetworkPolicy |

Prerequisites: KServe (Serverless mode needs Knative Serving + Istio or Kourier) for the
InferenceService, and the NVIDIA GPU Operator (`../gpu-operator/`) for `nvidia.com/gpu` and
`nvidia.com/mig-*` resources.

```bash
kubectl apply -f deploy/k8s/ml-serving/namespace.yaml
kubectl apply -f deploy/k8s/ml-serving/
kubectl -n golden-ml get inferenceservice fraud-detector       # READY, URL, traffic split
```

## The fraud model predictor

The predictor runs the platform image with `golden serve model-server`, i.e.
`golden.ai.serving.app:app` — `FraudModelServer` from `src/golden/ai/serving/`. It resolves
`fraud-detector@champion` in the registry copied to `/mnt/models` and serves the Open Inference
Protocol:

```bash
curl -s -H "Host: fraud-detector.golden-ml.example.com" http://$INGRESS/v2/models/fraud-detector/infer \
  -d '{"inputs":[{"name":"features","shape":[1,7],"datatype":"FP32","data":[6.2,0,1,0,0,0,1]}]}'
# -> {"model_name":"fraud-detector","model_version":"3","outputs":[{"name":"probability",...},{"name":"is_fraud",...}]}
#    response header: x-model-version: 3
```

**Canary.** Change the predictor (new image tag, or `GOLDEN_SERVING_ALIAS=challenger`) and apply:
KServe creates a new revision that receives `canaryTrafficPercent` (10 %) of traffic. Watch error
rate / latency / score distribution, then set `canaryTrafficPercent: 100` to promote or `0` to roll
back. Registry-level champion moves (`golden model promote` / rollback) are picked up without a new
revision through `POST /v2/models/fraud-detector/reload`.

**Autoscaling.** Knative KPA scales on in-flight requests (`scaleMetric: concurrency`,
`scaleTarget: 20`) between `minReplicas: 2` (never cold on the payment path) and `maxReplicas: 10`.

## vLLM

`MODEL_ID` selects the Hugging Face model (default `Qwen/Qwen2.5-7B-Instruct`, Apache-2.0, fits a
24 GB+ GPU in bf16). Gated models read `HF_TOKEN` from the optional `hf-token` Secret:

```bash
kubectl -n golden-ml create secret generic hf-token --from-literal=token=hf_xxx
kubectl -n golden-ml port-forward svc/vllm 8000:8000
curl -s localhost:8000/v1/chat/completions -H 'content-type: application/json' \
  -d '{"model":"qwen2.5-7b-instruct","messages":[{"role":"user","content":"hello"}]}'
```

Only pods labelled `app.kubernetes.io/component=agent-ops` in namespace `golden` (the LLM gateway)
may connect; point the gateway's OpenAI-compatible provider at `http://vllm.golden-ml:8000/v1`.

## Validation

`scripts/ci/validate-infra.sh` runs `kubeconform -strict -ignore-missing-schemas` over `deploy/k8s`
(Kubernetes 1.30 schemas). Built-in kinds are fully validated; the `InferenceService` CRD is skipped
for lack of a schema.
