# azure-backup-readiness

Wrapper skill auditing Azure backup coverage (RSV + Backup Vault) at
an RG scope. See [SKILL.md](SKILL.md) for the contract.

## Quick start

```bash
pip install azure-identity~=1.19 \
  azure-mgmt-recoveryservices~=3.0 \
  azure-mgmt-recoveryservicesbackup~=9.1 \
  azure-mgmt-dataprotection~=2.0
python -m azure_backup_readiness --sub <sub-id> --rg <rg>
```

## Pin file

See [`references/upstream-pin.md`](references/upstream-pin.md). Tier B,
auto.
