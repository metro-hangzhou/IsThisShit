# Export Fidelity TODOs

> Scope: CLI export UX completeness and media/content fidelity during export materialization.
> See also: [TODOs.napcat-research.md](TODOs.napcat-research.md) for official-doc, upstream-source, and GitHub-community coverage that should not live here.

## Completed

- [x] Add export profile commands:
  - `/export_onlyText`
  - `/export_TextImage`
  - `/export_TextImageEmoji`
- [x] Support `data_count=NN` and `--data-count NN`.
- [x] Print export summaries with per-segment and per-asset counts.
- [x] Make inline `data_count=` completion available from `/export d...`.
- [x] Make watch-mode completion keep `Up` / `Down` focused on the completion menu before date rolling.
- [x] Prefer original NTQQ media over thumbnail fallbacks when a thumbnail path is encountered.
- [x] Preserve animated image export better by upgrading `Thumb/*.jpg` to sibling `Ori/` or `OriTemp/` files when possible.
- [x] Correct misleading QQ cache extensions from file magic, for example GIF payloads stored under `.jpg`.
- [x] Make watch-mode export summary explicit about:
  - export time range
  - per-content exported counts for all normalized segment types
  - per-asset materialization in `actual/expected miss err` form
- [x] When an NTQQ `Ori/...` path is stale, also probe sibling `Thumb/...` variants such as `<stem>_0.jpg` and `<stem>_720.jpg`.
- [x] For `Emoji/emoji-recv/...` image records, also probe cross-tree NTQQ fallback locations under `Pic/<month>/Ori`, `Pic/<month>/OriTemp`, and `Pic/<month>/Thumb`.
- [x] Promote the narrow top-level NTQQ `Ori -> OriTemp/Thumb` sibling fallback into the formal `napcat_only` export path so stale `Pic/<month>/Ori/...` images can recover from local `_720/_0` thumb variants without broad cache scanning.
- [x] Add a shared per-run outcome cache for older repeated media assets so the same dead old image does not keep re-entering NapCat hydration/public-token recovery under different message contexts in one export.
- [x] Finalize the branch decision for the current phase: keep the vendored NapCat working branch for plugin evolution, but stop treating separate NapCat-core direct-download experiments as the default next step.
- [x] When `sourcePath` is blank but `file_name` exists, still perform root-level fallback lookup for file exports.
- [x] Treat blank NapCat `sourcePath/filePath` as "no resolved local path at export time", not as a reliable recalled/expired signal; keep context-first triage and targeted fallback.
- [x] For `file` / `video` / `speech` assets with blank local paths but preserved NapCat `file_id`, attempt public `get_file` / `get_record` download before local cache fallback.
- [x] Make legacy `Image/Group2` MD5 recovery two-stage: first-pass time-window acceleration, then a second-pass targeted MD5 lookup for still-missing assets whose cached files predate the export window.
- [x] Validate a real mixed `data_count=300` export slice to `miss=0` for `image`, `file`, `sticker.static`, and `sticker.dynamic` after resolver fixes and QQ-side lazy hydration.
- [x] Promote high-value formerly unsupported content into first-class normalized segment types:
  - forwarded chat bundles -> `forward`
  - gray-tip/system events -> `system`
  - ark/share cards -> `share`
- [x] Resolve forward bundles beyond preview text by calling NapCat `get_forward_msg` after history fetch and preserving recursive nested forwarded detail in export data.

## Open

- [ ] Stop accepting "generic missing" as a sufficient end state for forward/file/video last-mile fidelity work.
  If a residual missing is not already in a trusted class such as `qq_expired_after_napcat`, the exporter should be able to show a precise route-attempt chain and bounded local-evidence snapshot.
Otherwise treat it as an investigative failure and hand off to [TODOs.export-forensics.md](TODOs.export-forensics.md), not as ordinary fidelity debt.
- [ ] Continue auditing whether more QQ message content types are still being normalized into lossy placeholders too aggressively after `forward/system/share` support landed.
- [ ] Expand the live three-route benchmark beyond top-level `image`.
  The next benchmark pass must cover:
  - `file`
  - `speech`
  - `sticker / marketface`
  - any other media-bearing exported segment families still using NapCat hydration
  - nested media inside forwarded-chat bundles
- [ ] Promote old forwarded-chat embedded image hydration into a first-class recovery path.
  Current maintainer-side `data_count=2000` on `group_922065597` is down to only `5` image misses, but all `5` are nested inside older forwarded-chat bundles rather than top-level image messages.
  This is the current active fidelity focus. Immediate work should stay scoped to making nested forwarded media use the same per-element context hydration path as ordinary top-level assets inside the fast plugin, then rerun the three-route benchmark on a forward-heavy sample.
- [ ] Recheck forwarded `video` / `file` misses on the remote friend sample after the hidden-local-path and direct-`file_id` formal fallback fixes.
  A remote `group_751365230_20260315_224746.*` export still showed `19` `missing_after_napcat` assets, dominated by repeated forwarded videos/files from `Kurnal` / `Kurnal小号`.
  Investigation found a concrete gap:
  - some forwarded `video` segments preserve a Windows local cache path only in `segments[*].extra.url`
  - formal export previously ignored that local-path-like `url` and treated the asset as missing
- some surviving `file` assets (`uploaded_file`, `exports2.zip`) preserve a slash-prefixed public-looking `file_id` but no local path
- friend-side live export on `2026-03-16` exposed a concrete `get_file` integration bug:
  - exporter was sending both `file_id` and `file_name` into NapCat `get_file`
  - NapCat `GetFileBase` treats `payload.file` as authoritative and only falls back to `file_id` when `file` is empty
  - therefore exact file-id recovery for `uploaded_file` / `exports2.zip` was being accidentally downgraded into fuzzy name lookup
  - formal exporter now calls direct `get_file(file_id=...)` without the redundant `file` argument in the strict file-id path
- the same friend-side trace also showed a remaining forward-video production risk:
  - first forward video miss blocked for `~60s` before failing, then repeated misses became instant due to shared outcome cache
  - root cause is not missing path hints; the forwarded video segments already preserve hidden local-path-like `url` hints
  - the real issue is that targeted `/hydrate-forward-media` was still waiting on `downloadMedia(...)` before returning any useful token/path metadata
  - targeted forward hydration for `video` / `file` now returns metadata-first records immediately so Python can drive `public token -> get_file` / direct file-id recovery without waiting on a long plugin-side materialization attempt
  - formal export now also tries a narrow `file/video` segment-level `file_id -> get_file` fallback before declaring a true NapCat miss
  - plugin `/hydrate-forward-media` previously hydrated the entire forward bundle recursively even when exporter only needed one target asset; this increased timeout risk and widened failure blast radius on forward-heavy bundles
  - current plugin route now accepts target hints (`asset_type`, `file_name`, `md5`, `file_id`, `url`) and attempts a targeted in-bundle match before falling back to full-bundle collection
  - current code now upgrades local-path-like `download_hint.url/file/path` into a first-class local candidate
  - friend-side rerun on `2026-03-16` narrowed the remaining gap further:
    - the surviving `19` misses are still only `15` forwarded videos plus `4` file items (`uploaded_file` x3 and `exports2.zip`)
    - trace shows the worst slow steps were concentrated in:
      - one forwarded video taking about `180s`
      - three repeated `uploaded_file` misses taking about `120s` each
    - manual directory inspection on the friend machine confirmed the hinted `Video/2026-02/Ori/<uuid>.mp4` paths do not actually exist under those names at export time
    - current interpretation: metadata-only targeted forward hydration is still too conservative for video/file on this runtime; it returns stale or pre-download hints without forcing the single asset to materialize locally
  - current code now addresses that residual class by:
    - skipping the generic top-level `/hydrate-media` context route for assets that already carry `_forward_parent` hints
    - adding a second-stage targeted forward `materialize=true` request for unresolved `video` / `file` assets only
    - constraining that single-target materialization with a dedicated shorter timeout budget instead of re-entering whole-bundle recursive hydration
    - sharing missing outcomes for repeated forwarded `video` / `file` assets within one run even when they are recent, so a repeated unresolved `uploaded_file` does not pay the same slow path three times
  Next step:
  - rerun the friend-side export
  - if the file-like misses disappear but forwarded videos still miss before any manual click/download in QQ, continue deeper into plugin-side single-target forward-video materialization rather than stopping at stale local-path and `file_id` fixes
- [x] Measure whether the new forwarded-media direct-URL fallback materially reduces real nested-forward misses.
  Verified on `2026-03-14` with a live `export-history private 1507833383 --limit 5` run:
  - before the fix, `8` assets yielded `copied=2 missing=6`
  - after the fix, the same slice yielded `copied=5 reused=3 missing=0`
  - the newly recovered forwarded/nested-forwarded images all resolved through `napcat_forward_remote_url`
  Repository rule remains narrow:
  - only forwarded/nested-forwarded media may use direct-download of a still-live NapCat `url` when no stable path or public token is exposed
  - top-level media should still prefer path/token and must not globally flip to URL-first
- [ ] Use the three-route media benchmark to guide future fidelity work instead of guessing.
  Current benchmark entry point:
  - [scripts/benchmark_media_resolution.py](../../scripts/benchmark_media_resolution.py)
  Current explicit routes:
  - `napcat_context_only`
  - `napcat_public_token`
  - `legacy_md5_research_only`
  Benchmark first on representative JSONL slices before changing resolver order, bucket backoff, or token/hydration policy.
- [ ] Decide, from benchmark results, whether plugin-issued `public_file_token` plus public `get_image/get_file/get_record` should become the primary formal route over direct plugin-returned local paths for ordinary media families.
- [ ] Keep `legacy_md5_research_only` available for comparison, but do not reintroduce it into formal CLI export.
- [ ] Distinguish "original asset recovered" vs "thumbnail fallback recovered" explicitly in the manifest.
- [ ] Add a wider real-data smoke test for mixed image, sticker, video, speech, and file exports on a few-hundred-message slice.
- [ ] After friends upgrade to the latest extractor bundle, rerun a large remote full-history sample and compare miss rates by age bucket (`<=7d`, `8-30d`, `31-90d`, `91-180d`, `>180d`) to confirm whether nested-root discovery materially improves old `ntqq_pic` recovery.
- [ ] For the latest remote full-history sample (`group_763328502_20260310_204453.*`), manually verify a small set of representative missing images in QQ itself and classify each as:
  - visible with a real local path
  - visible in QQ but with no exposed local path
  - expired/unavailable in QQ
  Use those outcomes to decide whether the remaining misses are resolver gaps or genuinely unavailable old originals.
- [ ] Keep a regression probe for stale-month image recovery:
  - compare current `data_count=300 asJSONL` output against the `20260310_002020` / `20260309_181724` low-missing baselines
  - if `image missing` rises again, first verify:
    - old-month hydration skipping has not become too aggressive again
    - relative `/download?...` URLs are still resolved against the active NapCat HTTP base URL
    - context-hydrated images are allowed to land in a different month directory than the stale original `source_path`
- [ ] Check whether NTQQ exposes extra original media hints for animated images beyond `sourcePath` and current picked fields.
- [ ] Add a small operator-facing report that lists any content types seen in the source snapshot but not fully materialized.
- [x] Attempt proactive hydration of cloud-only assets before deeper local-cache fallback.
- [x] Correct the image/file hydration path for fast-history assets by preferring context-based fast-plugin `/hydrate-media` over public `get_image` / `get_file` when only raw fast-history IDs are available.
- [x] Preserve remote `marketface` GIF URLs during normalization and use them as the authoritative final fallback for sticker exports when local sticker files are absent.
- [x] Expand QQ media root auto-discovery to include one-level nested custom roots such as `D:\QQHOT\Tencent Files\...` instead of only direct drive-root `QQ` / `Tencent Files` paths.
- [x] Reuse a per-run asset-resolution cache so duplicated/reused assets do not rescan local roots, recompute legacy recovery, or rehydrate through NapCat multiple times in the same export.
- [x] Throttle `materialize_assets` progress redraws in root/watch CLI views so large exports do not lose throughput to per-asset terminal updates.
- [ ] Promote additional still-observed content families, if any remain, instead of leaving them in generic `unsupported`.

## Notes

- Old QQ `Image/Group2` lookup remains MD5-based because file names are obfuscated and not directly reversible.
- Legacy `Image/Group2` file timestamps cannot be treated as a hard exclusion rule; real cache files can predate the later message that references them.
- NTQQ `Thumb` paths are not authoritative for original media type. They are now treated as upgradeable fallbacks, not ideal final sources.
- Some NTQQ `Emoji/emoji-recv` assets are not recoverable from `Emoji/...` siblings alone; real fallback hits may live under the same month in `Pic/...`.
- Image/file hydration now has two tiers:
  - fast-history assets with preserved raw message context use fast-plugin `/hydrate-media` first
  - public-cache-token assets may still use public `get_image` / `get_file`
- A direct public `get_image` / `get_file` call is not authoritative for fast-history raw `fileUuid`; NapCat will often respond with `file not found` because the public action expects its own cache-token format rather than the raw internal UUID.
- NapCat source analysis confirms the native recovery path is context-driven `downloadMedia(msgId, chatType, peerUid, elementId, ...)`; exporter-side MD5 is only the legacy-cache fallback for obfuscated old QQ trees and should never be treated as the primary design path.
- NapCat public `get_image/get_file/get_record` are viable only when fed a NapCat-managed public media token. Raw fast-history `fileUuid` values are not those tokens.
- The current aggressive research route is: plugin gets full message context, plugin emits `public_action + public_file_token`, Python exporter then calls the matching public action.
- Public OneBot `image.data.file` can be just a file name in resolved forwarded content trees and must not be treated as a valid public `file_id` by normalization.
- A running NapCat runtime can continue serving the older fast plugin `/history` route while still lacking the newer `/hydrate-media` route. Export code should treat a 404 on `/hydrate-media` as a deployment-state issue, log it once, disable repeated probing for the current process, and ask the operator to restart NapCat if proactive hydration is required.
- Post-restart live validation now confirms `/hydrate-media` can recover recent `2026-03` image assets on the maintainer machine. Remaining misses in the tiny live sample were narrowed to `Emoji/marketface/<package_id>/...` sticker files that were simply absent locally.
- For old assets, repeated `/hydrate-media` misses can still slow large tail exports even without NapCat-side errors. The current mitigation is a per-process old-month failure bucket: after several failed remote hydration attempts in the same `asset_type + YYYY-MM` bucket, stop repeating remote hydration for that bucket and rely on local recovery plus manifest `missing` accounting.
- `sticker` in this repository means QQ market-face / 表情包 payloads (`mface`, `marketFaceElement`), not lightweight built-in `face` emoji.
- For `marketface` stickers, the authoritative final recovery path is now:
  - local `staticFacePath` / `dynamicFacePath` if present
  - then any other local cache recovery
  - then the QQ public remote GIF URL preserved during normalization
  - export keeps the native GIF payload as-is; do not generate derived static previews during export
- The latest `data_count=N` tail is chronological, not "recent by days". A low-traffic group can produce a 300-message slice spanning multiple months; export summary now reports the actual slice time range to avoid ambiguity.
- A recent remote Win10 sample showed `2026-03` images from the same minute where some `Pic/.../Ori/...` files existed and others did not. That pattern strongly suggests NTQQ can emit future-looking source paths before every original has actually landed on disk.
- A maintainer-side regression on `group_922065597` later showed a different stale-path pattern: some `2026-01` `emoji-recv` images were no longer recoverable from their recorded month, but context-based `/hydrate-media` returned valid local files under `2026-02`. Treat "month drift after hydration" as a normal recovery path, not a resolver anomaly.
- The maintainer-side regression was fixed by:
  - raising the "old asset bucket" threshold so only truly old assets enter repeated-hydration backoff
  - resolving relative `/download?...` hints against the active NapCat HTTP base URL before remote fallback download
- After that fix, a fresh live `data_count=300 asJSONL` export on `group_922065597` returned `assets copied=93 reused=20 missing=0` over the window `2026-01-12 .. 2026-03-12`.
- A large remote full-history sample (`group_763328502_20260310_195324.*`) showed these image-hit patterns:
  - `<=7d`: `missing=0`
  - `8-30d`: mixed recovery, `missing_rate≈0.355`
  - `31-90d`: poor recovery, `missing_rate≈0.709`
  - `91-180d`: poor recovery, `missing_rate≈0.696`
  - `>180d`: poor recovery, `missing_rate≈0.744`
  - `emoji-recv` had a much better overall hit rate than `ntqq_pic`, and most `reused` hits came from repeated `emoji-recv` meme images
  treat old `ntqq_pic` erosion as the dominant remote full-history fidelity problem after recent-hydration fixes have landed
- A maintainer-side `data_count=2000` export on `group_922065597` later confirmed that the remaining `5` image misses were not ordinary top-level images:
  - `2` images were inside a forwarded bundle from `2025-12-14`
  - `3` images were inside a forwarded bundle from `2026-01-10`
  use this as the current "last-mile" fidelity target after top-level image recovery has mostly stabilized
- Maintainer-side live probing on friend `1507833383` further established:
  - a top-level image URL can already be dead even when local path/token exist
  - but the tested `forward` / `nested-forward` image URLs were live and directly downloadable while path/token were absent
  so URL fallback should stay narrow and forwarded-media-specific rather than becoming a global media rule
- Benchmark on the maintainer machine against [group_922065597_20260313_011547.jsonl](../../exports/group_922065597_20260313_011547.jsonl) with `120` unique image assets found:
  - `qq_media_root_original_scan`: `54/120`, average about `9.1ms`
  - `legacy_md5_index`: `66/120`, average about `36.6ms` after cache warmup, but first cold-build max about `2.4s`
  - with local caches warm, all `120/120` assets resolved without needing NapCat hydration
  Treat this as evidence that MD5 fallback is viable and fast enough once indexed, but still secondary to direct paths and context hydration.
- On the maintainer machine, the current mixed-media fidelity baseline is:
  - `data_count=300` with `image/file/sticker` all reaching `miss=0`
  - a cautious post-restart `limit=20` live smoke where recent `marketface` stickers now materialize through the remote GIF fallback with `missing=0`
# Current Route Decision

- [x] Switch formal CLI export to NapCat-only strict media recovery.
- [x] Remove MD5/local cache fallback from formal export flow.
- [x] Add a plugin-issued public token route to the strict NapCat-only export path.
- [ ] Expand fast plugin context hydration to forwarded/nested forwarded media so remaining misses concentrate only on assets NapCat truly cannot recover.
- [ ] Close the remaining NapCat-only gaps revealed by the latest mixed-content benchmark:
  - `speech`:
    - older group sample still shows `0/8` even after the public-token fix:
      - report: [media_resolution_group922_speech_20260314_public_token_fix.json](../../state/benchmarks/media_resolution_group922_speech_20260314_public_token_fix.json)
      - all misses are in `91-180d` or `>180d`
    - fresh probe on [friend_1507833383_20260314_speech_probe.jsonl](../../exports/friend_1507833383_20260314_speech_probe.jsonl) now shows `napcat_context_only 1/1`
    - the recent `public token -> get_record` branch is now fixed on the maintainer runtime:
      - benchmark report: [media_resolution_friend1507833383_speech_probe_20260314_public_token_fix.json](../../state/benchmarks/media_resolution_friend1507833383_speech_probe_20260314_public_token_fix.json)
      - `napcat_context_only 1/1`, average `~7.959ms`
      - `napcat_public_token 1/1`, average `~12.917ms`
    - do not request `amr` conversion through `get_record`; NapCat may try `*.amr -> *.amr.amr` and fail with `Encoder not found`
    - on the current maintainer runtime, the speech public-token branch should request `out_format='mp3'`
    - align speech public token generation with NapCat core (`fileName` as custom token payload, raw `fileUuid` empty)
  - nested `forward` images: only `2/8` hits on both NapCat routes
    - clarify in code/docs that this means media inside recursively expanded forwarded bundles, not ordinary top-level images
    - malformed forward-parent hints without `element_id` must be filtered out client-side; otherwise `/hydrate-forward-media` just logs `element_id is required` and adds noise without improving fidelity
    - after a full NapCat restart and token-logic refresh, the live nested-forward probe is still `2/8`; treat forwarded-bundle context availability as the active blocker rather than stale route deployment
    - public `get_friend_msg_history(..., parse_mult_msg=true)` already shows the nested `forward.data.content` tree on the `1507833383` sample; do not treat missing nested media as a simple parse-tree absence
    - public `get_forward_msg` succeeds only for the outer forward ids on this sample; inner nested ids fail with `消息已过期或者为内层消息，无法获取转发消息`
    - investigate why plugin `/hydrate-forward-media` for outer payload `message_id_raw=7616346896018481986 / element_id=7616346896018481985 / peer_uid=u_PILHFfCbozu1GXYD_BVW7g / chat_type_raw=1` hangs past `120s`
  - `sticker` route parity is now partially resolved:
    - benchmark report: [media_resolution_group922_sticker_20260314_postrestart_fix.json](../../state/benchmarks/media_resolution_group922_sticker_20260314_postrestart_fix.json)
    - `direct_local_precheck 10/18`
    - `napcat_context_only 10/18`
    - `napcat_public_token 0/18`
    - maintainers should treat sticker public-token recovery as non-production on the current runtime and keep the formal route narrowed to local path + raw300 GIF remote URL
  - remaining mixed-export misses after the sticker fix are now all `image`, not `sticker`:
    - before: [group_922065597_20260314_160344.manifest.json](../../exports/group_922065597_20260314_160344.manifest.json) with `missing=25` including `8` sticker misses
    - after: [group_922065597_20260314_163723.manifest.json](../../exports/group_922065597_20260314_163723.manifest.json) with `missing=15`, all of them `image`
  - top-level image public-token remote URL fallback is now wired into formal export:
    - after [group_922065597_20260314_164529.manifest.json](../../exports/group_922065597_20260314_164529.manifest.json), mixed-export misses dropped again from `15` to `14`
    - one representative residual miss still showed:
      - `/hydrate-media` gives valid public token
      - `get_image(token)` returns only remote `multimedia.nt.qq.com.cn` URL
      - that URL is already `404`
      - local cache path still does not materialize
    - next fidelity work should assume some residual `2026-01/2026-02` misses may now be genuine runtime-unavailable assets rather than simple resolver omissions
  - `video` needs one more recent-sample benchmark pass; the current old-sample live result on `group_922065597_20260310_002020.jsonl` is only `1/2` for both NapCat routes
  - maintainer rerun now indicates the old `0/8` sample is not just a route mismatch; treat it as an age-biased availability problem unless a fresher counterexample appears
- [ ] Benchmark and compare:
  - context hydration only
  - plugin-issued public token plus public `get_image/get_file/get_record`
  - legacy MD5 research fallback
- [x] Add a first recent-file live comparison.
  Result on [group_922065597_20260313_011547.jsonl](../../exports/group_922065597_20260313_011547.jsonl):
  - `napcat_context_only`: `2/2`, avg `~18.1ms`
  - `napcat_public_token`: `2/2`, avg `~50.8ms`
  - legacy not applicable
- [x] Run the first live image benchmark for the three-route comparison.
  Result on [group_922065597_20260313_011547.jsonl](../../exports/group_922065597_20260313_011547.jsonl) with `120` unique images:
  - `napcat_context_only`: `74/120`, avg `~364.5ms`
  - `napcat_public_token`: `74/120`, avg `~24.9ms`
  - `legacy_md5_research_only`: `68/120`, avg `~43.0ms`
  Current interpretation: for ordinary image assets, public-token recovery has the best measured latency while matching context-only hit rate.
- [ ] Keep MD5/local cache benchmark tooling only for research comparison, never as silent production fallback.
