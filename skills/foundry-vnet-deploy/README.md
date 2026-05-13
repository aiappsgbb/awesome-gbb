# foundry-vnet-deploy

Deploy Azure AI Foundry with **Agent Setup inside a private Virtual Network**
using vendored Bicep templates and a guided interview that runs
`az deployment group create` end-to-end.

## Source

This skill is onboarded from the public peer repository:

- **Upstream**: <https://github.com/asevillano/foundry-vnet-deploy>
- **Author**: Angel Sevillano (Microsoft)
- **License**: MIT

The Bicep templates under [`templates/`](./templates/) are vendored
**byte-for-byte** from upstream — they are the canonical artifact
maintained by the upstream author. Treat them with the same discipline
as `references/data-realism/*.md` (per `AGENTS.md` § 2.2): do **not**
edit them to fix per-deployment quirks; adjust the generated
`.bicepparam` instead. If you find a real bug, open an issue on the
upstream repo first so every consumer of the template benefits.

## What changed during onboarding

The instructional body of [`SKILL.md`](./SKILL.md) was adapted from
upstream with these deltas (also documented in the SKILL.md's "Source"
section so consumers see them in-line):

1. Frontmatter rewritten to `AGENTS.md` § 2.4 shape — folded
   `description: >` with USE FOR / DO NOT USE FOR trigger phrases,
   `metadata.version: "1.0.0"`; upstream's `argument-hint` field dropped
   (preserved conceptually as a callout under "# Goal").
2. Removed the upstream rule **"Respond in Spanish as the user works in
   Spanish"** — the `awesome-gbb` catalog is language-neutral, so the
   skill responds in whatever language the current session is using.
3. Updated **Rule 6** to reference the `templates/` subfolder convention
   used across the catalog (per `AGENTS.md` § 7), instead of "same
   directory as this SKILL.md".
4. Added **Reference Files**, **Input contract / Output artifacts**, and
   **See Also** sections to integrate with the rest of the catalog
   (cross-links to `azure-tenant-isolation`, `foundry-hosted-agents`,
   `threadlight-deploy`, `foundry-cross-resource`,
   `citadel-spoke-onboarding`, `foundry-observability`).
5. Workflow steps (interview, parameter generation, retry path,
   post-deploy verification) are preserved as written by the upstream
   author.

The Bicep templates were copied without modification. SHA256 parity
against the upstream `main` branch was verified at onboarding time.

## Keeping in sync with upstream

When the upstream repo ships an update:

```powershell
# 1. Clone upstream to a scratch dir
$tmp = "$env:TEMP\foundry-vnet-deploy-upstream"
if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
git clone --depth 1 https://github.com/asevillano/foundry-vnet-deploy $tmp

# 2. Diff templates byte-for-byte
$srcRoot = "$tmp"
$dstRoot = "C:\Users\<u>\Repos\awesome-gbb\skills\foundry-vnet-deploy\templates"
foreach ($f in Get-ChildItem -Recurse -File $srcRoot |
                Where-Object { $_.Name -notin 'README.md','SKILL.md' }) {
  $rel = $f.FullName.Substring($srcRoot.Length + 1)
  $dst = Join-Path $dstRoot $rel
  $h1 = (Get-FileHash $f.FullName -Algorithm SHA256).Hash
  $h2 = if (Test-Path $dst) { (Get-FileHash $dst -Algorithm SHA256).Hash } else { 'missing' }
  if ($h1 -ne $h2) { Write-Host "DRIFT: $rel" -ForegroundColor Yellow }
}

# 3. If drift exists, copy upstream over templates/ wholesale and bump
#    metadata.version per AGENTS.md § 5 (PATCH for template-only updates,
#    MINOR if SKILL.md gained new behaviour or selectors, MAJOR if a
#    documented contract was renamed/removed).
```

After a sync, mirror the skill folder to `~/.copilot/skills/` per
`AGENTS.md` § 6 and verify SHA256 parity.

## See also

- [Repo-root `AGENTS.md`](../../AGENTS.md) — contributor + sub-agent guide
  (frontmatter rules, scrub discipline, mass-edit playbook)
- [Repo-root `README.md`](../../README.md) — full catalog index
- [`SKILL.md`](./SKILL.md) — the canonical contract this skill exports
