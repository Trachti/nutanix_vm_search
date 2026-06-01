# Nutanix VM Search Tool

Search Nutanix VMs from the command line through Prism Central.

## Features

- Search by name, UUID, IP, MAC, cluster, subnet, power state, or category
- Table output
- JSON output
- Result limiting

## Configuration

Edit `nutanix_vm_search.py`:

```python
NTNX_PRISMCENTRAL_IP = "YOUR_IP:9440"
PC_TOKEN = "YOUR GENERATED TOKEN FROM nutanix_auth.py"
```

## Usage

```bash
python nutanix_vm_search.py --name web
python nutanix_vm_search.py --ip 10.10.10.15
python nutanix_vm_search.py --mac 50:6b:8d
python nutanix_vm_search.py --power-state ON
python nutanix_vm_search.py --category Environment=Production
python nutanix_vm_search.py --name web --json
```

## Safety Notes

Read-only script. Do not commit real tokens, IP addresses, or internal details.

## Disclaimer

Example script. Test in a safe environment before production use.
