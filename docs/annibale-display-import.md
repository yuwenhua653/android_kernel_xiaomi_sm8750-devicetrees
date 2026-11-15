# Annibale display device tree import

The ten device-specific files in `qcom/display/display/` come from
[MiCode/vendor_qcom_opensource_display-devicetree](https://github.com/MiCode/vendor_qcom_opensource_display-devicetree/tree/db20397cfa5778d4e214bd1f2c282b19a1fec6f2/display),
branch `annibale-w-oss`, commit `db20397cfa5778d4e214bd1f2c282b19a1fec6f2`:

- `annibale-sde-display-mtp-overlay.dts` and `annibale-sde-display.dtsi`.
- The main and `-common.dtsi` files for each panel: `p11-42-02-0b`,
  `p11-42-0d-0a`, `p11-42-0d-0a-p00`, and `p11-42-0d-0a-p10`.

Source notices and device settings are retained. Trailing whitespace and final
newlines are normalized; spaces preceding indentation tabs are removed from
five lines in three files. These formatting fixes change the bytes of
`annibale-sde-display.dtsi`, the `p11-42-0d-0a` and `p11-42-0d-0a-p10` main
files, and the `p11-42-02-0b` and `p11-42-0d-0a-p10` common files. The other
five files are byte-identical to the upstream commit. For all ten files,
removing whitespace yields identical upstream and imported content; panel
command array values are unchanged. The source-hash evidence records the
original and imported byte counts and SHA256 values independently. No common
Qualcomm display file is replaced. `qcom/display/Kbuild` adds only
`display/annibale-sde-display-mtp-overlay.dtbo` to the non-VM Sun list.

The five formatting-only changes have the following byte counts and hashes:

| File | Upstream bytes | Imported bytes | Upstream SHA256 | Imported SHA256 |
| --- | ---: | ---: | --- | --- |
| `annibale-sde-display.dtsi` | 4352 | 4348 | `84b86b768d991ff0d754125d0448696a0c397b408e10680e180c5da5bab5dea8` | `7e40902b475c528417562b8525f414735fbc89d7e66c84fbec26b478f3f0f44b` |
| `dsi-panel-p11-42-02-0b-dsc-cmd-common.dtsi` | 5269 | 5270 | `5ddba35cec8c70933ecf496e79099a4add49b9d13038fafa07d564826999f6d9` | `028e384fcfd2d3abf1ad08ffe32b26de62d84257934dd7fc1f254b9fd924e779` |
| `dsi-panel-p11-42-0d-0a-dsc-cmd.dtsi` | 20966 | 20964 | `310d104df1614f302b1bcc87db60d9148429ac0e8c1eaf931166f98d07dae1a2` | `930f9b5d42a2d5bdf49ddbbe973dc9c7fed978e80b27cacafde48d98f6b3241b` |
| `dsi-panel-p11-42-0d-0a-p10-dsc-cmd-common.dtsi` | 4680 | 4672 | `4cf473da9124e8cc27e7ac32bd91ec76f052127fcadc078d38ef4f2c6d24f368` | `a8161c36cac62c58dbc1bb608191938857f83b91b9b23016b6aa27eaf7a6f958` |
| `dsi-panel-p11-42-0d-0a-p10-dsc-cmd.dtsi` | 67288 | 67286 | `8a8166a6788bc340d44f314b331cc3333b2b883f6882199af640027fa667d40c` | `93616c0ddd8f4a1dd0ae164dc1e3a2f3918150ebda9ab023982859656dadc414` |

The entry includes the existing LineageOS Sun display definitions, then adds
the four P11 panel variants. The upstream NT37801 fallback/default panel and
the Goodix, charge-screen, thermal-screen and fingerprint-screen panel lists
are retained. Its matching metadata is `qcom,board-id = <0x40008 0>` and
`xiaomi,miboard-id = <0xB 0>`.

## Validation

CPP and DTC succeed from the final repository paths. The generated overlay is
byte-identical to the isolated import used for the preceding reference audit:
SHA256 `c388f6c280b9f7bb11d65896f422855de3e10ef6150c9af76b40b874aa1d9c3f`.
DTC reports 187 warnings, which remain for later cleanup; this is not a
warning-free or schema-validation result.

The overlay merges successfully after the current Annibale SoC and camera
overlays on all eight LineageOS bases: `sun`, `sun-v2`, `sun-tp`, `sun-tp-v2`,
`sunp`, `sunp-v2`, `sunp-tp`, and `sunp-tp-v2`. No external display label is
missing. Goodix, charge-screen, thermal-screen and fingerprint-screen references
resolve to the four P11 panels and NT37801 fallback in their original order.
The default remains NT37801, the Goodix firmware name remains
`goodix_firmware_annibale`, and all properties of the four camera sensor nodes
remain unchanged after display composition. Because the Annibale entry already
includes the generic Sun display definitions, this test does not apply a
separate generic display overlay first.

After the final indentation cleanup, all eight display merges were repeated
using the revalidated SoC/camera inputs. Each final tree remains byte-identical
to its earlier validated result; the panel references, default panel, board
protection nodes, and camera sensor properties were checked again.

These checks cover DT compilation, overlay composition and selected references.
They do not establish display-driver compatibility, panel identification at
boot, screen output, touch operation, or a complete flashable DTBO image.
