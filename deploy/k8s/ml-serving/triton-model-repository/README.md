# Triton model repository layout

Triton loads every model directory under `--model-repository` (here `/models`, the
`triton-model-repository` PVC). With `--model-control-mode=poll` it picks up new versions every 30 s,
so publishing a model is "copy a new numbered directory", and rollback is "delete it".

```
/models
└── fraud_onnx/                 # model name -> POST /v2/models/fraud_onnx/infer
    ├── config.pbtxt            # inputs/outputs, batching, instance groups, version policy
    ├── 1/
    │   └── model.onnx          # version 1
    └── 2/
        └── model.onnx          # version 2 (served alongside 1 per version_policy)
```

Other backends use the same shape: `model.plan` (TensorRT), `model.pt` (PyTorch TorchScript),
`model.savedmodel/` (TensorFlow) or `model.py` (Python backend).

`fraud_onnx/config.pbtxt` in this directory is a working example for the platform's fraud model
exported to ONNX (7 float inputs per row, matching `golden.ai.lifecycle.fraud_model.FEATURES`):

* `max_batch_size: 256` + `dynamic_batching` — Triton coalesces concurrent requests into one GPU
  batch, waiting at most 2 ms (`max_queue_delay_microseconds`) — the same idea as
  `FraudModelServer.infer_batch`, done by the server.
* `instance_group { count: 2, kind: KIND_GPU }` — two copies of the model on the (MIG) device so a
  long request does not block short ones.
* `version_policy: { latest { num_versions: 2 } }` — serve the two newest versions; clients can pin
  one with `/v2/models/fraud_onnx/versions/2/infer` (champion/challenger by URL).

Publish:

```bash
kubectl -n golden-ml cp fraud_onnx/ <loader-pod>:/models/fraud_onnx/   # or sync from S3/GCS
curl -s triton.golden-ml:8000/v2/models/fraud_onnx | jq .               # metadata
curl -s triton.golden-ml:8000/v2/models/fraud_onnx/ready -o /dev/null -w '%{http_code}\n'
```

Triton can also read `s3://`, `gs://` and `as://` repositories directly
(`--model-repository=s3://bucket/models`), which removes the PVC.
