# R24: single-overlay native DT containers

R23 validated a host-side sequence of separate board/audio/camera/display/GPU/
media/wireless overlays. A DTBO table is not an instruction to replay that
sequence. R24 compiles those same source layers together into one complete
Annibale overlay per SoC revision, and packages real DT containers. These remain
**offline partial qualification artifacts, not a flash package**.

## Outputs and selection

`tools/build_annibale_dt_images.py` produces:

- `dtb.img`: eight concatenated source SoC DTBs, in the observed OEM base order.
  This is a vendor_boot DTB-section payload, not a standalone DT table.
- Four explicit profiles: `tfa-default`, `tfa-native`, `sia-default`, `sia-native`.
  Each contains a version-0, 4096-byte-page DTBO table with exactly two entries:
  one complete v1 overlay and one complete v2 overlay.
- Individual overlays, 32 resulting merged trees, preprocessed source and
  compiler diagnostics, plus a hash/selection/equivalence report.

The amplifier choice remains unresolved on hardware. `default` and `native`
refer only to the existing opt-in P11 PB display quirks; neither selects
HyperOS compatibility. All four are native-source candidates. Never concatenate
profiles or use these DTs with the retained-stock HyperOS module plan.

Optional table ID/revision/custom fields remain zero like the OEM table. The
root selectors identify Annibale board 0x40008, Xiaomi board 0xB, the four
reviewed SUN/SUNP/TP SoCs and exactly one silicon revision per entry. Each of
the eight base selectors matches exactly one complete entry. The two generic
SUNP bases also advertised SoCs 705/706; the packaged Annibale bases narrow that
metadata to 639 and preserve every other property. This avoids advertising
unsupported device candidates. Real Xiaomi bootloader selection is untested.

## Compilation and equivalence

Each existing layer is preprocessed independently with its existing include
paths. Its single DTS/plugin header is removed, the bodies are compiled in
R23 order under one header, and final root metadata narrows the revision.
Preprocessor output hashes cover included source text. No source-driver C,
firmware, carveout or register value is changed by this packaging step.

For every composition, the complete node/property sets are compared with the
hash-checked R23 result. Phandle definitions and references at the compiler's
`__fixups__`/`__local_fixups__` offsets are resolved to node paths. All other
property bytes must match exactly. GPIO numbers, clock arguments and arbitrary
integers are not guessed to be phandles. The comparison also rejects dangling
references and duplicate phandles. Existing multimedia, interactive and OEM
wireless binding checks are rerun after the single overlay application.
This is structural equivalence to R23, not independent proof that all R23
hardware bindings are electrically correct or every enabled device has a driver.

The containers are created and independently dumped by AOSP `mkdtimg`; the
validator reads their exact offsets/sizes and checks extracted bytes. Duplicate
revision entries are rejected and reversed table order still selects correctly.
The concatenated base payload is also read back with exact bounds and selector
checks. Truncated, duplicate and invalid-magic base inputs are rejected.

```sh
python3 -B tools/build_annibale_dt_images.py \
  --kernel ../sm8750 --modules ../sm8750-modules \
  --dtc /path/to/dtc --fdtoverlay /path/to/fdtoverlay \
  --mkdtimg /path/to/mkdtimg \
  --wireless-input /path/to/r23-wireless-validation \
  --output /path/to/new-native-dt-images
```

The comparison input must contain all 32 R23 cases and matching hashes. It is
not an attestation of the input report's provenance; this round uses the
retained local R23 build. The new base readback guard was added after the full
build started and was also run separately on its actual final `dtb.img`, with
three malformed-image cases, recorded in the R24 validation record.

## Remaining integration

The DT containers still need complete native vendor_boot/platform ramdisk,
init_boot, DLKM filesystem and ROM build ownership, image size/AVB checks,
actual amplifier identification and bootloader testing. No recovery image or
flash script is produced. DTC diagnostics are retained; a successful compile
is not a clean full DT-schema/GPIO-conflict audit.

See [R24 validation](annibale-r24-validation.json) and the modules repository's
[ramdisk integration](https://github.com/yuwenhua653/android_kernel_xiaomi_sm8750-modules/blob/annibale/Documentation/xiaomi/annibale-ramdisk-integration.md).
The container layout follows the [AOSP DTB/DTBO partition format](https://source.android.com/docs/core/architecture/dto/partitions).
