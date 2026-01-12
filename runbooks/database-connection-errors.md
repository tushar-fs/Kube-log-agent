# Database Connection Errors Runbook

## Symptoms

Pod crashes on startup with log lines like:
- `could not connect to server: Connection refused`
- `dial tcp: connect: connection refused`
- `FATAL: password authentication failed for user`
- `could not translate host name to address`

## Diagnosis

```bash
# Check if the DB service resolves inside the cluster
kubectl run -it --rm debug --image=busybox --restart=Never -- \
  nslookup <db-service-name>.<namespace>.svc.cluster.local

# Test TCP connectivity
kubectl run -it --rm debug --image=busybox --restart=Never -- \
  nc -zv <db-host> <db-port>
```

## Common Causes

### Wrong Hostname or Port in Config

The most common cause. The app is pointing at `localhost`, a dev hostname, or a stale IP instead of the Kubernetes service DNS name.

Fix: Use the full in-cluster DNS: `<service>.<namespace>.svc.cluster.local`

### Database Pod Not Ready Yet

If the DB and the app start at the same time, the app may win the race. Kubernetes doesn't guarantee startup order.

Fix: Add an `initContainer` that polls for DB readiness before the main container starts:

```yaml
initContainers:
  - name: wait-for-db
    image: busybox
    command: ['sh', '-c', 'until nc -z db-service 5432; do sleep 2; done']
```

### Wrong Credentials in Secret

The secret exists but has the wrong value (base64 encoding issue, trailing newline, etc.).

Fix: Decode and verify: `kubectl get secret <name> -o jsonpath='{.data.password}' | base64 -d`

### Network Policy Blocking Egress

A NetworkPolicy may be blocking traffic from the app namespace to the DB namespace.

Fix: Check `kubectl get networkpolicies -A` and ensure egress from the app pods to the DB port is allowed.
