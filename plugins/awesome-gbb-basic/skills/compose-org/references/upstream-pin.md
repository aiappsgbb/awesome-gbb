---
schema_version: 2
freshness_tier: A
automation_tier: auto
upstream:
  type: github_repo
  repo: arturcrmbot/zava-control-plane
  ref: main
  pinned_sha: 8240cf09e485926b9dfc30ca871462feccabc983
  pinned_commit_message: |
    Initial public release: Zava Control Plane — Apex Substrate
  license: MIT
  notes: |
    compose-org wraps the public substrate layout documented in SKILL.md. Validation checks the README and imports a documented data-fabric module without creating a customer fork.
packages: []
docs_to_revalidate:
  - https://github.com/arturcrmbot/zava-control-plane
  - https://github.com/arturcrmbot/zava-control-plane/blob/main/README.md
known_issues: []
validation:
  requires:
    - github_only
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail

    PINNED_SHA="${PINNED_SHA:-8240cf09e485926b9dfc30ca871462feccabc983}"
    REPO_URL="https://github.com/arturcrmbot/zava-control-plane"
    REF="main"
    WORK=".upstream-pin-smoke/compose-org"

    rm -rf "$WORK"
    mkdir -p "$WORK"
    git clone --quiet --depth 1 --branch "$REF" "$REPO_URL" "$WORK/repo"
    actual="$(git -C "$WORK/repo" rev-parse HEAD)"
    test "$actual" = "$PINNED_SHA"
    echo "pinned SHA verified: ${PINNED_SHA}"

    curl -fsSI -L "$REPO_URL" >/dev/null
    curl -fsSI -L "$REPO_URL/blob/main/README.md" >/dev/null
    echo "README link check ok"

    python - <<'PY'
    import importlib.util
    import pathlib
    root = pathlib.Path('.upstream-pin-smoke/compose-org/repo')
    required = [
        'api/server/data_fabric/client_brand_gen.py',
        'api/server/data_fabric/employee_gen.py',
        'api/shared/domains.py',
        'api/shared/functions.py',
        'api/shared/personas.py',
        'mocks',
    ]
    missing = [p for p in required if not (root / p).exists()]
    if missing:
        raise SystemExit(f'missing documented substrate paths: {missing}')
    spec = importlib.util.spec_from_file_location('client_brand_gen', root / 'api/server/data_fabric/client_brand_gen.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert hasattr(module, 'generate_clients_and_brands')
    PY
    echo "module import smoke ok"
  expected_output:
    - "pinned SHA verified"
    - "README link check ok"
    - "module import smoke ok"
  failure_signatures: []
last_validated: 2026-05-15
validated_by: ricchi
known_issues_count: 0
---

# Upstream pin — `compose-org` skill

This file is the **machine-readable validation contract** for the
`compose-org` skill. The YAML front-matter above is parsed by
`scripts/check-freshness.py` weekly; the prose below is the human audit trail.
Keep them in sync.

---

## 1. Pin

| Field | Value |
|-------|-------|
| **Upstream** | `arturcrmbot/zava-control-plane` |
| **Branch / tag** | `main` |
| **Pinned SHA** | `8240cf09e485926b9dfc30ca871462feccabc983` |
| **Pinned commit subject** | `Initial public release: Zava Control Plane — Apex Substrate` |
| **License** | `MIT` |
| **First authored against** | `2026-05-15` |
| **Last re-validated** | `2026-05-15` |

Refresh procedure:
```bash
git ls-remote https://github.com/arturcrmbot/zava-control-plane main
# Compare first column to pinned_sha in front-matter
```

---

## 2. Pinned packages (Tier B / mixed only)

No PyPI package is pinned for this Tier-A wrapper. The validation script uses
only `git`, `curl`, and the Python standard library.

---

## 3. Verification checklist (the executable contract)

> **For coding agents**: this section's `bash` block is what
> `validation.script` in the front-matter expands to. Keep them identical. The
> agent will run this script verbatim.

```bash
#!/usr/bin/env bash
set -euo pipefail

PINNED_SHA="${PINNED_SHA:-8240cf09e485926b9dfc30ca871462feccabc983}"
REPO_URL="https://github.com/arturcrmbot/zava-control-plane"
REF="main"
WORK=".upstream-pin-smoke/compose-org"

rm -rf "$WORK"
mkdir -p "$WORK"
git clone --quiet --depth 1 --branch "$REF" "$REPO_URL" "$WORK/repo"
actual="$(git -C "$WORK/repo" rev-parse HEAD)"
test "$actual" = "$PINNED_SHA"
echo "pinned SHA verified: ${PINNED_SHA}"

curl -fsSI -L "$REPO_URL" >/dev/null
curl -fsSI -L "$REPO_URL/blob/main/README.md" >/dev/null
echo "README link check ok"

python - <<'PY'
import importlib.util
import pathlib
root = pathlib.Path('.upstream-pin-smoke/compose-org/repo')
required = [
    'api/server/data_fabric/client_brand_gen.py',
    'api/server/data_fabric/employee_gen.py',
    'api/shared/domains.py',
    'api/shared/functions.py',
    'api/shared/personas.py',
    'mocks',
]
missing = [p for p in required if not (root / p).exists()]
if missing:
    raise SystemExit(f'missing documented substrate paths: {missing}')
spec = importlib.util.spec_from_file_location('client_brand_gen', root / 'api/server/data_fabric/client_brand_gen.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert hasattr(module, 'generate_clients_and_brands')
PY
echo "module import smoke ok"
```

**Expected output** must contain (substring match):

- `pinned SHA verified`
- `README link check ok`
- `module import smoke ok`

**Failure signatures** (treat as upstream regression — report distinctly):

- None.

---

## 4. Live smoke results (last successful run)

| Check | Result | Evidence |
|-------|--------|----------|
| `git clone --branch main` | ✅ | `pinned SHA verified` |
| README URL probes | ✅ | `README link check ok` |
| Substrate module import | ✅ | `module import smoke ok` |

Captured at `last_validated: 2026-05-15` by `ricchi`.

---

## 5. Known issues at this pin

No known issues are tracked for this pin.

---

## 6. Re-pin procedure

When upstream advances:

1. **Capture new SHA**:
   ```bash
   git ls-remote https://github.com/arturcrmbot/zava-control-plane main
   ```
2. **Update front-matter**: set `upstream.pinned_sha` to the new value and
   `upstream.pinned_commit_message` to the new commit subject.
3. **Run the validation script**:
   ```bash
   PINNED_SHA=<new-sha> bash -c "$(yq '.validation.script' upstream-pin.md)"
   ```
4. **Verify expected output**: each `expected_output[]` substring must appear
   in stdout.
5. **Update audit trail**: set `last_validated`, `validated_by`, and any known
   issue counts.
6. **Bump SKILL.md `metadata.version` PATCH** per AGENTS.md § 5.
7. **Open PR**: touch only `references/upstream-pin.md` and `SKILL.md`.

---

## 7. URLs to re-validate (link-rot detector input)

- <https://github.com/arturcrmbot/zava-control-plane>
- <https://github.com/arturcrmbot/zava-control-plane/blob/main/README.md>

---

## 8. Cross-references worth bookmarking

- `api/server/data_fabric/client_brand_gen.py` — module import smoke for the substrate data-fabric shape.
- `api/shared/domains.py`, `functions.py`, `personas.py` — registry paths compose-org rewrites in generated forks.
- `mocks/` — source layout for stack mock scaffolding.

---

## 9. Notes for the coding agent

> **If you're GHCP picking up a refresh issue for this skill:**
>
> 1. The `validation.script` in the front-matter is your spec. Run it.
> 2. If it passes, update front-matter (`pinned_sha`, `last_validated`,
>    `validated_by: copilot-bot`) and bump SKILL.md `metadata.version` PATCH.
>    Touch nothing else.
> 3. If it fails, comment on the issue with the failure output and do **not**
>    open a PR.
> 4. Never edit `references/data-realism/**`.
