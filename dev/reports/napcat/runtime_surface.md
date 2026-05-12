# NapCat Runtime Surface

> Date: 2026-03-27
> Scope: classify the checked-in `NapCat/` tree as runtime shell, mutable state, plugin surface, generated artifacts, and repo launch bridges.

## Why this exists

`NapCat/` is not a single kind of thing.

It currently mixes:

- packaged runtime shell
- mutable local runtime state
- repo-relevant plugin code
- generated `node_modules` / static build outputs
- launcher hooks that bridge the parent repo into the vendored runtime

Without a surface map, later work drifts into treating cache, logs, plugins, and packaged binaries as if they had the same maintenance meaning.

## Canonical classification

### 1. Vendored runtime shell

Top-level `NapCat/` files and packaged launcher/runtime pieces:

- `NapCat/index.js`
- `NapCat/package.json`
- `NapCat/node.exe`
- `NapCat/napcat.bat`
- `NapCat/*.dll`
- `NapCat/wrapper.node`
- `NapCat/win64/`

Meaning:

- this is the packaged runtime shell checked into the parent repo
- treat it as vendored runtime payload, not as canonical architecture docs

### 2. Runtime root

`NapCat/napcat/` is the real runtime root for the local packaged NapCat instance.

It contains several different surfaces that must not be blurred together:

- mutable runtime state
- launchers / bootstrap scripts
- plugin surface
- generated web / node artifacts
- native support payloads

### 3. Mutable runtime state

Mutable local state inside `NapCat/napcat/`:

- `cache/`
- `config/`
- `logs/`

Meaning:

- these reflect local operator/runtime state
- they are useful for diagnosis
- they are not stable architecture truth

### 4. Plugin surface

Repo-relevant plugin surfaces:

- `NapCat/napcat/plugins/napcat-plugin-builtin/`
- `NapCat/napcat/plugins/napcat-plugin-qq-data-fast/`
- `NapCat/napcat/config/plugins/`

Meaning:

- this is the part of the vendored runtime most directly coupled to the parent repo's exporter work
- plugin code and plugin config are legitimate repo integration surface

### 5. Generated runtime artifacts

Generated or packaged heavy runtime artifacts:

- `NapCat/napcat/node_modules/`
- `NapCat/napcat/static/`
- `NapCat/napcat/native/`

Meaning:

- these are runtime payloads or generated assets
- do not use them as the first place to infer parent-repo design intent
- do not let refactor work drift into general dependency/build noise

### 6. Repo launcher bridge

Repo-side bridge files:

- [start_napcat_logged.bat](../../../start_napcat_logged.bat)
- [restart_napcat_service.ps1](../../../restart_napcat_service.ps1)
- `state/napcat_logs/`
- `state/config/napcat_quick_login_uin.txt`

Meaning:

- these are parent-repo integration hooks around the vendored runtime
- they are not upstream NapCat internals, but they are part of this repo's operational runtime surface

## What not to do

- do not flatten `NapCat/` into ordinary parent-repo source
- do not treat `node_modules/` churn as a repository architecture signal
- do not treat `cache/` or `logs/` as canonical project state
- do not put runtime-surface policy inside random plugin files or launcher scripts only

## What this surface is for

This surface should answer:

- where local runtime state actually lives
- which parts of `NapCat/` are safe to classify as vendored shell only
- which parts are repository-owned integration surface
- where plugin/runtime debugging should start before deeper upstream source reading
