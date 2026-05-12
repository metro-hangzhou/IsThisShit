# NapCat Runtime State And Plugins

> Date: 2026-03-27
> Scope: detail the mutable state, plugin surface, and repo-owned launch/state bridges around the local `NapCat/` runtime.

## Mutable state map

### `NapCat/napcat/config/`

Observed local config files include:

- `napcat.json`
- `napcat_<uin>.json`
- `napcat_protocol_<uin>.json`
- `onebot11_<uin>.json`
- `plugins.json`
- `webui.json`
- `config/plugins/`

Meaning:

- this is the operator/runtime configuration surface
- it is mutable and machine-local
- it must be read as current runtime state, not as repository-wide policy text

### `NapCat/napcat/cache/`

Observed local runtime cache includes at least QR/login artifacts.

Meaning:

- ephemeral runtime cache
- useful for diagnosis
- not canonical repo state

### `NapCat/napcat/logs/`

Meaning:

- live runtime log sink inside the vendored runtime
- separate from repo-side `state/napcat_logs/` launcher logs

## Plugin surface

### Checked-in runtime plugins

Observed plugin directories:

- `napcat-plugin-builtin`
- `napcat-plugin-qq-data-fast`

Maintenance meaning:

- `napcat-plugin-builtin`
  - upstream/runtime reference surface
  - mostly example/reference for plugin behavior
- `napcat-plugin-qq-data-fast`
  - repository-relevant performance and hydration extension
  - direct exporter-facing integration surface

### Mirrored plugin config

Observed mirrored config surface:

- `NapCat/napcat/config/plugins/napcat-plugin-builtin/`
- `NapCat/napcat/config/plugins/napcat-plugin-qq-data-fast/`

Meaning:

- runtime config and plugin code are separate surfaces
- plugin behavior questions should distinguish:
  - code route missing
  - config disabled/misaligned
  - process not restarted after code change

## Generated artifact surface

### `node_modules/`

Meaning:

- packaged dependency payload
- high churn, low design-signal
- do not audit this first unless the evidence points to packaging or dependency drift

### `static/`

Meaning:

- built WebUI/frontend payload
- treat as generated runtime artifact unless the task is explicitly about WebUI packaging

### `native/`

Meaning:

- runtime-native support binaries/addons
- relevant for packaging/runtime startup issues, not ordinary exporter semantics

## Repo-side launcher and state bridge

### Launcher entry

- [start_napcat_logged.bat](../../../start_napcat_logged.bat)

What it does:

- locates the vendored launcher
- injects quick-login UIN when available
- writes repo-side log pointers under `state/napcat_logs/`
- launches NapCat via an elevated wrapper when needed

### Restart helper

- [restart_napcat_service.ps1](../../../restart_napcat_service.ps1)

What it does:

- finds repo-scoped NapCat/QQ-related processes
- stops them
- optionally starts the launcher again

### Repo-side state

- `state/napcat_logs/`
- `state/config/napcat_quick_login_uin.txt`

Meaning:

- this is repository-owned operator state
- it belongs to the parent repo bridge, not to upstream NapCat source truth

## Operational rules

- plugin code changes require a real NapCat restart before new routes are live
- config drift, launcher drift, and plugin-code drift are different failure classes
- when debugging repo/runtime coupling, start with:
  - launcher bridge
  - plugin presence/config
  - restart state
  - then deeper runtime/source inspection
- do not use runtime logs/cache as substitute for canonical handbook policy
