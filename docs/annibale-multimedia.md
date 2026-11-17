# R22 Annibale multimedia candidates

The v1/v2 test overlays compose the existing SUN video and EVA bindings with
Annibale board selectors. Both DTBO selection metadata and a merged-root
fragment carry board 0x40008 / Xiaomi board 0xB. The root fragment is necessary:
libfdt overlay application does not copy top-level DTBO metadata into the base.

Select `ANNIBALE_MULTIMEDIA_REV=v1` or `v2` explicitly for Kbuild. SUN is required;
VM, invalid and multiple selections fail. Empty selection emits neither new
target. These are opt-in qualification targets, not a shipped DTBO table.

Run `tools/validate_annibale_multimedia.py` with the same kernel/module sources
and host dtc/fdtoverlay used by interactive validation. It composes eight SUN
bases x two audio families x default/native display, then applies the matching
media revision. It verifies board/SoC selectors, video compatible, EVA revision,
firmware carveout references, clocks/resets, power domains/supplies, interconnects
and IOMMU references. Existing camera/audio/display/touch/UFS checks run again.
Wrong revision, wrong board, disabled clock provider and unresolved clock handle
mutations must be rejected. This is not full DT schema or electrical validation.

Pair with the modules repository's R22 `annibale-multimedia-{tfa,sia}-partitions.json`
for source staging. Do not replace stock HyperOS DT or mix these source-module
lists with OEM modules. Exact firmware, HAL behavior, final board wiring and
bootloader packaging remain unqualified. See `annibale-r22-validation.json`.
