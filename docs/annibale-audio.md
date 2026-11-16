# R15: explicitly selected Annibale audio DT candidates

`qcom/audio/annibale-audio-{tfa,sia}-test.dts` reconstructs the selected smartpa
board wiring from the user's OS4.0.6.0.XPKCNXM DTBO. These are experimental
source-audio candidates, not a complete flashable DTBO image. They do not
replace the default common Qualcomm audio DT or the retained-stock HyperOS path.

Reference DTBO SHA256:
`e9582a2074d7f25af6f39204406a7c7212139f7d092e2e5010e226d3b27125c8`.
The sole extracted DTBO table entry supplied the TDM pinctrl, amplifier I2C
nodes, SIA platform nodes and associated GPIO wiring. This is reconstructed
DT source, **not** a published MiCode audio-devicetree release. Existing board
source provenance in `annibale-import.md` is separate.

| Property | Candidate mapping |
| --- | --- |
| Backend | Secondary TDM RX/TX, two slots, eight clock attributes equal to 4 |
| Clock / WS / DIN / DOUT | GPIO 121 / 123 / 122 / 124 |
| TFA pair | I2C 0x36 / 0x34, reset 108 / 107, IRQ 66 / 84 |
| SIA pair | I2C 0x6e / 0x6c, platform channels 0 / 1, reset 108 / 107 |
| Speaker switch | GPIO 67 |
| Selection contract | Two ordered `xiaomi,smartpa-codecs` phandles; explicit provider markers |

The candidates preserve selected stock electrical values, including existing
duplicate strings in SIA pin lists. They override the generic card's TDM,
digital routes, WCD-disable and WSA-count settings and disable four common WSA
codec nodes. They do not import unrelated USB switch or microphone-enable
policy. Those remaining board differences need separate driver and HAL review.

The stock overlay contains both smartpa families. It does not establish which
family is fitted in the user's phone. Choose exactly one only after hardware
identification:

```text
ANNIBALE_AUDIO_VARIANT=tfa
ANNIBALE_AUDIO_VARIANT=sia
```

An empty selector builds neither candidate; invalid or multiple selections
fail in Kbuild. The candidate is included in both `dtbo-y` and `always-y` when
selected for SUN. Use the matching `audio` profile in the modules repository.
Do not install both candidates or load these codecs beside stock counterparts.

## Reproduce static validation

Build `fdtoverlay` from the matching kernel's scripts/dtc sources if needed:

```sh
cc -O2 -I sm8750/scripts/dtc -I sm8750/scripts/dtc/libfdt \
  sm8750/scripts/dtc/fdtoverlay.c sm8750/scripts/dtc/util.c \
  sm8750/scripts/dtc/libfdt/*.c -o /tmp/annibale-fdtoverlay
python3 -B sm8750-devicetrees/tools/validate_annibale_audio.py \
  --kernel sm8750 --modules sm8750-modules \
  --dtc tools/kernel-build-tools/linux-x86/bin/dtc \
  --fdtoverlay /tmp/annibale-fdtoverlay --output out/audio-dt-check
```

The validator compiles eight SUN/SUNP bases and composes each with the Annibale
SoC overlay, common audio overlay and one candidate: 16 combinations. It checks
the real Kbuild selector, final codec phandles/addresses/markers, no opposite
family, TDM pin routing, slot and clock values. Compiler warnings are retained
per input; a successful merge is not a clean dt-schema check. The checked
composition excludes other peripheral overlays and does not prove bootloader
selection, firmware agreement, GPIO ownership at runtime or working audio.
