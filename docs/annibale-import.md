R16 extends the [audio candidates](annibale-audio.md) with the OS4 DMIC enable provider and pins; see annibale-r16-validation.json.

R15 adds separately selected [audio DT candidates](annibale-audio.md); the earlier checks below did not include audio.

# Annibale SoC device-tree import

This change adds the REDMI K90 / POCO F8 Pro (`annibale`) board overlay to the
LineageOS SM8750 device-tree baseline, together with the matching camera and
display board overlays. Audio and the complete peripheral/bootloader DTBO
image composition remain outside these checks. No device boot or hardware
test has been performed.

## Sources

* Qualcomm/LineageOS baseline:
  `LineageOS/android_kernel_qcom_sm8750-devicetrees`, `lineage-22.2`,
  `450710a3aac3af54ef46504df2d46afecd6aa0eb`.
* Published Xiaomi board source:
  `MiCode/kernel_devicetree`, `annibale-w-oss`,
  `32fd4ddcedd46baa579643b3894c37c0fccccb91`.

The following MiCode files are carried over with their existing source content
and notices. Trailing whitespace, spaces preceding indentation tabs, and final
blank lines are normalized. Original and imported SHA256 values are recorded
separately in `annibale-source-imports.json`; the source files are not all
byte-identical to MiCode. Charging arrays and other DT values are unchanged by
whitespace normalization. Local integration adjustments are listed below.

```
qcom/annibale-sm8750-overlay.dts
qcom/annibale-sm8750.dtsi
qcom/annibale-charger-common.dtsi
qcom/annibale-nfc-pinctrl.dtsi
qcom/mca.dtsi
qcom/sm8750-ir-sensor-common.dtsi
qcom/sm8750-xiaomi-common.dtsi
```

`annibale-sm8750.dtsi` explicitly includes the USB PHY register binding that
MiCode obtained through its modified shared `sun-mtp.dtsi`. It also selects
`annibale_gtp_thp_config.ini` using the driver's `goodix,thp-config-name`
property. The existing `goodix_firmware_annibale` and
`goodix_cfg_group_annibale` names remain intact. No calibration file from
another device is included here. These names must be supplied by the matching
vendor firmware; file presence and touch functionality are not established by
a DT compile.

## Board-scoped composition

Shared Qualcomm DTS files are not replaced or downgraded. Three Annibale-only
copies are derived from the LineageOS baseline and apply the reviewed MiCode
board differences:

| File | Baseline and changes |
| --- | --- |
| `annibale-mtp.dtsi` | `sun-mtp.dtsi`: selects the two Annibale composition files, disables the unused SD controller and removes its external feedback clock property, and omits the reference I2C ST FTS touch node. |
| `annibale-pmic-overlay.dtsi` | `sun-pmic-overlay.dtsi`: omits the unused DBO3 regulator and reference thermistor/thermal-zone map, and names the complete XO protection zone `xo-therm` as published by MiCode. |
| `annibale-thermal-overlay.dtsi` | `sun-thermal-overlay.dtsi`: directs all 14 existing XO cooling maps to `xo-therm`, omits the reference `sys-therm-2` map, and retains the newer LineageOS SOCd protection maps. |

`sm8750-xiaomi-common.dtsi` selects the Annibale MTP composition and retains the
unaltered v8 PMIC include and v8 OCP adjustments from `sun-mtp-v8.dtsi`.
The unused I2C touchscreen controller stays disabled; Annibale's SPI Goodix
touchscreen owns GPIOs 161/162.

This separation is necessary for a plugin overlay: separate references to an
external target create separate fragments. A later `/delete-node/` directive
cannot reliably remove reference-platform nodes introduced in an earlier
fragment. Omitting them from the Annibale composition avoids both duplicate
labels and unwanted nodes in the final merged tree.

The board's original ADC channel definitions in `annibale-sm8750.dtsi` replace
the reference-platform thermistor definitions. XO trips at 78, 80 and 90 degrees
C and all CPU/CDSP/GPU/modem/display cooling maps remain present. The newer
LineageOS `socd_trip` and its cooling maps are retained. The unused
`PERIDOT_REGULATOR_OCP_PIANO` variant is not imported.

`annibale-los-compat.dtsi` adds the two real MiCode nodes missing from the
Qualcomm base:

* `mca,adsp_glink` under the existing `/soc/qcom,pmic_glink` bus, with the
  compatible and initial status from MiCode `sun.dtsi`; the Annibale charging
  file enables it.
* `usb_nop_phy` under `/soc`, with `usb-nop-xceiv` from MiCode `sun-usb.dtsi`,
  matching the published Annibale high-speed DWC3 wiring.

The same file adds MiCode's two PMK8550 bark interrupt children under the
existing `qcom,pmk8550@0/pon_hlos@1300` node. They require the paired
`CONFIG_INPUT_PM8941_PWRKEY_XIAOMI` driver support selected by the kernel's
`annibale_board.config`; the original power and volume-down key nodes remain.

These nodes do not replace their drivers. MCA, Goodix, hardware identification,
and the remaining vendor-module dependencies must be built and validated with
the kernel.

## Camera board overlay

`qcom/camera/annibale-sm8750-camera-sensor.dts` and its `.dtsi` come from
`MiCode/vendor_qcom_proprietary_camera-devicetree`, `annibale-w-oss`, commit
`4900e29d927aaca00f52fc51e07055197ca72569`. They are added to
`qcom/camera/config/sun.mk` without replacing the common Qualcomm camera tree.
The tested composition order is the Annibale SoC overlay, the existing
`sun-camera.dtbo`, then `annibale-sm8750-camera-sensor.dtbo`. All eight base
variants accept this chain.

The sensor overlay selects `qcom,csiphy-v2.3.0-p11` on `cam_csiphy2`. The matching
P11 CSIPHY register table and selection logic are included in the paired
`camera-kernel` import. Its `cam_csiphy_soc.o` compiled successfully as AArch64
with Android Clang r510928, without warnings. This is an object-build check;
neither it nor DT syntax and overlay application proves a complete `camera.ko`,
camera firmware, userspace HAL, sensor power sequencing, or capture functionality.

The ten Annibale/P11 display-specific files and their source identity are
documented in [annibale-display-import.md](annibale-display-import.md). They
reuse the unchanged LineageOS common display DTS files; no panel calibration
from another phone is substituted.

## Build entry and checks

`qcom/Makefile` adds `annibale-sm8750-overlay.dtbo` to `SUN_BOARDS`. With
`CONFIG_ARCH_SUN=y`, Make expands eight combined targets, for `sun`, `sun-v2`,
`sun-tp`, `sun-tp-v2`, `sunp`, `sunp-v2`, `sunp-tp`, and `sunp-tp-v2`, and lists
the overlay in `sun-overlays-dtb-y`.

Checks performed on this source integration:

* GCC preprocessing and DTC compilation of the board overlay and all eight
  unchanged LineageOS base trees.
* Successful `fdtoverlay` application to all eight bases.
* Final-tree assertions for the Goodix firmware/config names, active MCA GLINK
  child, no-op USB PHY, disabled reference touchscreen bus, absent ST FTS/DBO3
  nodes, and absent reference `sys-therm-*` zones.
* Correct Annibale ADC names, complete XO trips, all 14 cooling maps, resolved
  trip references, and retention of the SOCd trip.
* Both PMK8550 bark children and their interrupt tuples, while preserving the
  original power and volume-down key nodes.
* The complete tested SoC, common camera, Annibale camera, and Annibale display
  overlay chain on all eight bases. Panel references resolve in their original
  order, and all four camera sensor nodes retain their properties after display
  composition.

The final whitespace cleanup was rechecked against all 12 preprocessed inputs
(eight bases and four overlays). They match the validated compiler inputs byte
for byte. Every SoC/camera result and every final display-composed tree remains
byte-identical to its result before that cleanup. The final eight merged trees
also pass the board, thermal, camera, and panel-reference assertions above.

The SoC overlay produces 99 DTC warnings, the existing common camera overlay
20, the Annibale sensor overlay 26, and the display overlay 187. Each unchanged
base produces 211 warnings. These vendor/reference warnings are not suppressed
or treated as hardware validation. The test did not compile a full
kernel, assemble a full peripheral overlay set, validate a bootloader DT table,
or establish module ABI compatibility. Do not flash the standalone test DTBO.

A minimal host compilation uses `gcc -E -nostdinc -undef -D__DTS__ -x
assembler-with-cpp`, the matching kernel's `include` directory, and this
repository's `qcom` directory, followed by `dtc -@ -I dts -O dtb` and
`fdtoverlay -i BASE.dtb -o MERGED.dtb annibale-sm8750-overlay.dtbo`.
