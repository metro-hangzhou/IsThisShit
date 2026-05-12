# NapCat QQ Data Fast Plugin

This directory contains the project-owned NapCat runtime plugin used by the QQ exporter.

NapCat itself is treated as an external runtime dependency and should be referenced through the upstream `NapNeko/NapCatQQ` checkout/submodule. Keep exporter-specific plugin code here instead of maintaining it inside the vendored/runtime `NapCat/` tree.

Deployment note:

- Copy or sync this directory into the active NapCat runtime plugin directory when running local exports.
- Restart NapCat after plugin code changes; new plugin routes are not live until the runtime reloads.
- Do not treat this plugin as a NapCat internal API dependency. Message access still goes through the public OneBot HTTP/WS surface plus this explicit local plugin route.
