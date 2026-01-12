# CrashLoopBackOff Runbook

## Overview

A pod in `CrashLoopBackOff` means Kubernetes is repeatedly trying to restart a container that keeps exiting with a non-zero status code. The backoff time increases exponentially (10s → 20s → 40s → … up to 5min) to avoid hammering a broken dependency.

## Common Causes

### OOMKilled — Out of Memory

The container exceeded its memory limit and was killed by the kernel OOM killer.

Check: `kubectl describe pod <pod> | grep -A5 OOM`

Fix: Increase the `resources.limits.memory` in the pod spec, or find and fix the memory leak. Common culprits are unbounded caches, missing stream closes, or a misconfigured JVM heap.

### Application Crash on Startup

The process exits immediately after starting. Usually a missing env var, bad config, or failed DB connection.

Check: `kubectl logs <pod> --previous` — look for the last few lines before exit.

Fix: Ensure all required environment variables are set via ConfigMaps or Secrets. Validate external dependencies (database, message broker) are reachable from within the cluster.

### Liveness Probe Killing the Container

If a liveness probe is misconfigured (too aggressive `failureThreshold` or wrong path), Kubernetes will kill the container before it finishes initializing.

Fix: Increase `initialDelaySeconds` to give the app time to warm up. Prefer readiness probes over liveness probes for most startup checks.

### Entrypoint / Command Error

The container's CMD or ENTRYPOINT is wrong — the binary doesn't exist, has wrong permissions, or the working directory is missing.

Check: `kubectl describe pod <pod>` → look at `Command` and `Args`.

Fix: Test the image locally with `docker run --entrypoint sh <image>` to verify the binary path.

## Useful Commands

```bash
# See the last crash reason
kubectl describe pod <pod-name> -n <namespace>

# Grab logs from the previous (crashed) container
kubectl logs <pod-name> --previous -n <namespace>

# Watch restart count in real time
kubectl get pods -n <namespace> -w
```
