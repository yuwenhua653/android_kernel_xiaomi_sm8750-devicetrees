# Annibale haptics selection (R3)

The Annibale PMIC overlay adds `xiaomi,annibale-haptics` before the existing
`qcom,hv-haptics` compatible on `pmih010x_haptics`. This opts into the Xiaomi HAL
control subset in the matching kernel when `CONFIG_INPUT_QCOM_HV_HAPTICS_XIAOMI`
is enabled. No PMIC registers, effect tables, motor period, voltages, NVMEM links
or calibration thresholds are changed. This is a local integration compatible,
not a property copied from MiCode. The binding schema accepts the new
two-compatible sequence; the YAML was parsed, but full dt-schema was not run.

See the kernel repository's `Documentation/xiaomi/annibale-haptics.md` for the
source revision, implemented attributes, test method and missing calibration
policy. This DT update alone does not enable a working Xiaomi HAL.

Validation on 2026-11-15 re-preprocessed and compiled the Annibale SoC overlay,
then applied it followed by sun-camera, Annibale camera and Annibale display to
sun, sun-v2, sun-tp, sun-tp-v2, sunp, sunp-v2, sunp-tp and sunp-tp-v2. Comparing
all flattened-tree nodes and property bytes with the R2 validated results found
only the haptics compatible change in each chain. The existing 99 SoC overlay
warnings remain. These are composition checks, not dt-schema, hardware or
flashable DTBO-image validation. The source hash manifest includes this edit.
