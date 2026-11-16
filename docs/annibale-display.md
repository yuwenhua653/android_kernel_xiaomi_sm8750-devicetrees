# R19: native P11 PB display experiment

Use `ANNIBALE_DISPLAY_MODE=native` only with the paired R19 source display
module. The default is empty/off. Unknown modes, non-SUN platforms and trusted
VM builds are rejected by the actual display Kbuild selector.

Apply `qcom/display/display/annibale-native-panel-test.dts` after the existing
Annibale display overlay. It enables `xiaomi,annibale-pb-quirks` on exactly
three existing P11 PB panel candidates (regular, P00, P10). It does not force
panel selection and does not alter P11 PA, NT37801, panel commands, supplies,
backlight limits, audio selection or camera sensors. Building the extra DTBO
is not enough to make a flashable bootloader DTBO table or install it into a ROM.

The source driver checks exact PB ID `0x0050313150420d0a` and the published
one-byte HS read of `0xda`. It reads the physical revision under the panel
lock before the first eligible nonzero backlight write each power cycle.
Only a successful one-byte result below `0x80` enables Xiaomi's nonzero
DBV-below-15 correction; unknown/new revisions retain normal handling.
Power-off waits at least 5 ms before the GPIO sequence, as in MiCode's P11 PB
path. The default DT composition enables neither behavior.

Validation:

```sh
python3 -B sm8750-devicetrees/tools/validate_annibale_interactive.py \
  --kernel sm8750 --modules sm8750-modules \
  --dtc out/annibale-btf/scripts/dtc/dtc \
  --fdtoverlay out/annibale-btf/scripts/dtc/fdtoverlay --output out/dt-r19
python3 -B sm8750-devicetrees/tools/validate_annibale_display.py \
  --fixtures out/dt-r19 --output out/display-negative-check.json
```

The first command checks 32 compositions (8 bases, TFA/SIA, default/native)
and proves the extra overlay changes only the three booleans. It also retains
R18 touch, camera, audio, GPU, UFS and TME checks. Existing DTC warnings are
recorded. The second evaluates five actual Kbuild selections and rejects
eight malformed fixtures; it is not a comprehensive DT schema check.

No proprietary firmware, display HAL or Xiaomi display feature ABI is added.
HBM/LHBM, dimming, AOD, ESD and real hardware operation remain unverified.
Retain HyperOS's coherent stock stack and DT policy; this overlay is for the
native source qualification path only. Full implementation and source
provenance are in the modules repository's
`Documentation/xiaomi/annibale-display.md`.
