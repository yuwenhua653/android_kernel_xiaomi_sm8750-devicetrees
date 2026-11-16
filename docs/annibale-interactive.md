# R18 combined peripheral composition validation

The module repository's R18 interactive candidates add source storage,
display/GPU, touch, NFC, haptics and key dependencies to the audio/network
subset. This repository adds a combined composition check; no panel commands,
GPIO assignments, camera tuning, audio selection or GPU power levels change.

```sh
python3 -B tools/validate_annibale_interactive.py \
  --kernel ../sm8750 --modules ../sm8750-modules \
  --dtc ../out/annibale-btf/scripts/dtc/dtc \
  --fdtoverlay ../out/annibale-btf/scripts/dtc/fdtoverlay \
  --output ../out/annibale-interactive-dt
```

Use a new output directory. The tool first runs the existing audio composition
and selector checks, then adds common/Annibale camera, the Annibale P11 display
overlay and the matching `sun-gpu` or `sun-v2-gpu` overlay. Eight SoC bases and
two amplifier families form sixteen compositions.

Checks cover the five Goodix panel phandles and device-specific firmware names,
enabled KGSL and SUN UFS PHY bindings, the TME QMP mailbox supplier, selected
smartpa/DMIC bindings, and preservation of all four camera sensor nodes after
display/GPU composition. DTC warnings are retained and counted in the result.
Failed checks produce no passing validation report.

The result is not a complete schema or pin-conflict audit, a bootloader DTBO
table, actual hardware identification, or a functional display/touch/camera
result. The original NT37801 fallback remains; no P11 panel or amplifier is
silently forced. Camera DT is included for regression checking even though
the module repository's interactive runtime subset still omits camera.
