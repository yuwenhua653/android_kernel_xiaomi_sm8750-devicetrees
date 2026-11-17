# R23: Annibale-only WLAN / Bluetooth composition

This extends the R22 interactive + multimedia DT candidates with dedicated
`wlan/annibale-kiwi-cnss.dtsi` and `bt/annibale-kiwi-bt.dtsi` includes. Generic
Qualcomm boards are unchanged. `annibale-wireless-test.dts` is an incremental
qualification overlay, not a final flashable DTBO image.

The source reference is the user's annibale OS4.0.6.0.XPKCNXM OTA. Operation and
partition hashes were checked, but cryptographic OTA signatures were not.
The selected factual bindings and provenance are in
[annibale-os406-wireless-contract.json](annibale-os406-wireless-contract.json).
All eight OEM base/overlay combinations share the same normalized contract.
The repository contains no proprietary firmware or complete OEM partition.

Board corrections: BT PMIC GPIO power-source 1 (GPIO3/6), no RTC6226 FM device,
no generic WLAN XOCAL/WCAL consumer, enable UART14 and existing SLIM NGD while
preserving its phandle. Existing Bluetooth FMD cells remain in place. Original
camera/display/audio properties must survive wireless composition. Existing
root-port address/size cells are retained; OEM resolves equivalent 3/2 through
its PCIe ancestor. Provider arguments are decoded by their cell count rather
than guessing phandles from numeric values.

```sh
python3 -B tools/validate_annibale_wireless.py \
  --kernel ../sm8750 --modules ../sm8750-modules \
  --dtc /path/to/dtc --fdtoverlay /path/to/fdtoverlay \
  --output /path/to/new-output
```

Optional `--multimedia-input` reuses the complete, hash-checked R22 32-case
matrix; an arbitrary input report does not prove current-source provenance.
Without it, the earlier validators run first. Kbuild opt-in is
`ANNIBALE_WIRELESS_MODE=native` with SUN and non-VM; no default enablement.
Root overlay metadata selects the eight reviewed SoC/revision pairs, board
0x40008 and Xiaomi 0xB. A root fragment preserves the preceding candidate's
revision-specific msm-id. Actual bootloader DTBO selection is still untested.

Result: 32 compositions (8 bases x 2 amp families x 2 display modes), each with
68 selected nodes and 52 supplier entries; 224 rejected DT mutations, 7
selector cases and 5 parser unit tests. Prior media/interactive checks rerun.
This does not cover full electrical/schema/GPIO-conflict analysis or prove
probe, firmware, HAL, RF/BT audio performance, suspend or boot success.

Pair with the modules repository's R23 wireless policy, which adds the matching
`msm_geni_serial` HS UART driver and explicit OF supplier ordering. Native and
retained-stock HyperOS profiles remain separate. Detailed cross-repository
instructions: [annibale-wireless.md](https://github.com/yuwenhua653/android_kernel_xiaomi_sm8750-modules/blob/annibale/Documentation/xiaomi/annibale-wireless.md).
Exact local results: [annibale-r23-validation.json](annibale-r23-validation.json).
