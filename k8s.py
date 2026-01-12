import sys
from kubernetes import client, config
from kubernetes.client.rest import ApiException


CRASH_STATES = {"CrashLoopBackOff", "Error", "OOMKilled", "CreateContainerConfigError"}


def load_kube_client() -> client.CoreV1Api:
    try:
        config.load_kube_config()
    except config.ConfigException:
        print("\033[1;31mError:\033[0m Could not load kubeconfig. Is kubectl configured?")
        sys.exit(1)
    return client.CoreV1Api()


def find_crashing_pods(v1: client.CoreV1Api, namespace: str) -> list[dict]:
    try:
        pods = v1.list_namespaced_pod(namespace=namespace)
    except ApiException as e:
        if e.status == 403:
            print(f"\033[1;31mError:\033[0m No permission to list pods in namespace '{namespace}'.")
        else:
            print(f"\033[1;31mError:\033[0m Kubernetes API returned {e.status}: {e.reason}")
        sys.exit(1)

    crashing = []
    for pod in pods.items:
        if not pod.status.container_statuses:
            continue
        for cs in pod.status.container_statuses:
            waiting = cs.state.waiting
            # a pod restartCount > 3 with a recent restart is just as broken as CrashLoopBackOff
            if (waiting and waiting.reason in CRASH_STATES) or cs.restart_count > 3:
                crashing.append({
                    "pod": pod.metadata.name,
                    "namespace": pod.metadata.namespace,
                    "container": cs.name,
                    "reason": waiting.reason if waiting else f"restart_count={cs.restart_count}",
                    "restart_count": cs.restart_count,
                })
    return crashing


def fetch_logs(v1: client.CoreV1Api, pod: str, namespace: str, container: str, lines: int = 500) -> str:
    try:
        # previous=True grabs the last terminated container's logs, which is
        # where the actual crash output lives — not the current (pending) container
        logs = v1.read_namespaced_pod_log(
            name=pod,
            namespace=namespace,
            container=container,
            tail_lines=lines,
            previous=True,
        )
        return logs
    except ApiException as e:
        if e.status == 400:
            # Pod hasn't completed a full cycle yet, fall back to current container logs
            try:
                logs = v1.read_namespaced_pod_log(
                    name=pod,
                    namespace=namespace,
                    container=container,
                    tail_lines=lines,
                )
                return logs
            except ApiException:
                pass
        print(f"\033[1;33mWarning:\033[0m Could not fetch logs for {pod}/{container}: {e.reason}")
        return ""
