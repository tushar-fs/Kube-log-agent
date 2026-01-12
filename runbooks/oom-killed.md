# OOMKilled Runbook

## What Happened

The Linux kernel terminated your container because it exceeded the memory limit set in `resources.limits.memory`. This is not a Kubernetes bug — it's the kernel's OOM killer doing its job.

## Diagnosis

```bash
# Confirm OOM is the reason
kubectl describe pod <pod> | grep -i oom

# Check current resource limits
kubectl get pod <pod> -o jsonpath='{.spec.containers[*].resources}'

# Look at memory usage trend (requires metrics-server)
kubectl top pod <pod> --containers
```

## Common Root Causes

### JVM Heap Not Bounded

Java apps inside containers often don't respect container limits because the JVM reads host memory. Set `-XX:MaxRAMPercentage=75.0` instead of `-Xmx` so the JVM adapts to the container's limit.

### Unbounded In-Memory Cache

A cache that grows without eviction will consume all available memory over time. Audit any `dict`, `list`, or third-party cache (Redis client-side cache, LRU cache) for a max size setting.

### Memory Leak

Objects are being allocated but never freed. Profile with `memory_profiler` (Python), `pprof` (Go), or heap dumps (JVM). Common leak sites: unclosed file handles, circular references, global registries.

### Sudden Traffic Spike

The limit was appropriate for normal load but not for peak. Consider horizontal scaling (HPA) instead of raising the limit so the system can flex.

## Fix

1. Raise the memory limit as a short-term band-aid: edit the deployment and bump `resources.limits.memory`.
2. Set a matching `resources.requests.memory` — scheduler needs this to place pods on nodes with headroom.
3. Investigate the actual leak or misconfiguration so you're not just papering over it.

```yaml
resources:
  requests:
    memory: "256Mi"
  limits:
    memory: "512Mi"
```
