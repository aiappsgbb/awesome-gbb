# azure-resource-diagnostics

Wrapper skill auditing Azure diagnostic-settings coverage at an RG
scope. See [SKILL.md](SKILL.md) for the contract.

## Quick start

```bash
pip install azure-identity~=1.19 \
  azure-mgmt-monitor~=6.0 \
  azure-mgmt-resource~=23.1
python -m azure_resource_diagnostics --sub <sub-id> --rg <rg>
```

## Pin file

See [`references/upstream-pin.md`](references/upstream-pin.md). Tier B,
auto.
