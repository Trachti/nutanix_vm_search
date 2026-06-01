import http.client
import json
import ssl
import time

NTNX_PRISMCENTRAL_IP = "YOUR_IP:9440"
PC_TOKEN = "YOUR GENERATED TOKEN FROM nutanix_auth.py"


def get_conn(host=NTNX_PRISMCENTRAL_IP):
    context = ssl._create_unverified_context()
    return http.client.HTTPSConnection(host, context=context)


def api_request(method, url, payload=None, host=NTNX_PRISMCENTRAL_IP, token=PC_TOKEN, extra_headers=None):
    conn = get_conn(host)
    headers = {
        "Accept": "application/json",
        "Authorization": token,
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)
    body = None if payload is None else payload if isinstance(payload, str) else json.dumps(payload)
    conn.request(method, url, body=body, headers=headers)
    res = conn.getresponse()
    raw = res.read().decode("utf-8")
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        data = {"raw": raw}
    if res.status >= 400:
        raise RuntimeError(f"API error {res.status} on {host}{url}: {data}")
    return data, res.status


def task_uuid(response):
    return (response.get("status", {}).get("execution_context", {}).get("task_uuid")
            or response.get("task_uuid")
            or response.get("status", {}).get("task_uuid"))


def wait_for_task(task_id, timeout=300, interval=5):
    start = time.time()
    while time.time() - start < timeout:
        data, _ = api_request("GET", f"/api/nutanix/v3/tasks/{task_id}")
        status = str(data.get("status", "")).upper()
        if status in {"SUCCEEDED", "FAILED", "ABORTED"}:
            return data
        time.sleep(interval)
    raise TimeoutError(f"Task {task_id} reached timeout after {timeout}s.")


def list_vms(page_size=100):
    offset, results = 0, []
    while True:
        payload = {"kind": "vm", "length": page_size, "offset": offset}
        data, _ = api_request("POST", "/api/nutanix/v3/vms/list", payload)
        entities = data.get("entities", [])
        if not entities:
            break
        results.extend(entities)
        total = data.get("metadata", {}).get("total_matches")
        offset += page_size
        if total is not None and offset >= total:
            break
    return results


def get_vm_by_name(name):
    for vm in list_vms():
        if vm.get("spec", {}).get("name") == name:
            return vm
    return None


def get_vm(uuid_):
    data, _ = api_request("GET", f"/api/nutanix/v3/vms/{uuid_}")
    return data


def put_vm(uuid_, vm_data, timeout=300, interval=5):
    response, _ = api_request("PUT", f"/api/nutanix/v3/vms/{uuid_}", vm_data)
    tid = task_uuid(response)
    if tid:
        result = wait_for_task(tid, timeout=timeout, interval=interval)
        if str(result.get("status", "")).upper() != "SUCCEEDED":
            raise RuntimeError(f"Task failed: {result}")
    return get_vm(uuid_)

import argparse


def info(vm):
    meta, spec, status = vm.get("metadata", {}), vm.get("spec", {}), vm.get("status", {})
    res = status.get("resources") or spec.get("resources") or {}
    cluster = status.get("cluster_reference") or spec.get("cluster_reference") or {}
    ips, macs, subnets = [], [], []
    for nic in res.get("nic_list", []) or []:
        if nic.get("mac_address"): macs.append(nic["mac_address"])
        for ep in nic.get("ip_endpoint_list", []) or []:
            if ep.get("ip"): ips.append(ep["ip"])
        if nic.get("subnet_reference", {}).get("name"): subnets.append(nic["subnet_reference"]["name"])
    return {"name": spec.get("name") or status.get("name"), "uuid": meta.get("uuid"), "cluster": cluster.get("name"), "cluster_uuid": cluster.get("uuid"), "power_state": res.get("power_state"), "ips": ips, "macs": macs, "subnets": subnets, "categories": meta.get("categories") or {}}


def has(value, needle): return needle is None or needle.lower() in str(value or "").lower()

def cat_match(cats, expr):
    if not expr: return True
    if "=" not in expr: return expr in cats
    k, v = expr.split("=", 1); return str(cats.get(k.strip(), "")).lower() == v.strip().lower()


def match(row, args):
    if not has(row["name"], args.name): return False
    if not has(row["uuid"], args.uuid): return False
    if args.cluster and not (has(row["cluster"], args.cluster) or has(row["cluster_uuid"], args.cluster)): return False
    if args.power_state and str(row.get("power_state") or "").lower() != args.power_state.lower(): return False
    if args.ip and not any(has(x, args.ip) for x in row["ips"]): return False
    if args.mac and not any(has(x, args.mac) for x in row["macs"]): return False
    if args.subnet and not any(has(x, args.subnet) for x in row["subnets"]): return False
    for expr in args.category or []:
        if not cat_match(row["categories"], expr): return False
    return True


def main():
    p = argparse.ArgumentParser(description="Search Nutanix VMs from the command line through Prism Central.")
    p.add_argument("--name"); p.add_argument("--uuid"); p.add_argument("--ip"); p.add_argument("--mac"); p.add_argument("--cluster"); p.add_argument("--power-state", choices=["ON", "OFF", "UNKNOWN"]); p.add_argument("--subnet"); p.add_argument("--category", action="append"); p.add_argument("--json", action="store_true"); p.add_argument("--limit", type=int, default=0)
    args = p.parse_args(); rows = [info(v) for v in list_vms()]; rows = [r for r in rows if match(r, args)]; rows.sort(key=lambda x: str(x.get("name") or "").lower())
    if args.limit > 0: rows = rows[:args.limit]
    if args.json: print(json.dumps(rows, indent=2, ensure_ascii=False)); return
    if not rows: print("No matching VMs found."); return
    for r in rows:
        print(f"{r['name']} | {r['uuid']} | {r.get('cluster')} | {r.get('power_state')} | IPs: {', '.join(r['ips'])} | MACs: {', '.join(r['macs'])}")
    print(f"\nMatches: {len(rows)}")

if __name__ == "__main__": main()
