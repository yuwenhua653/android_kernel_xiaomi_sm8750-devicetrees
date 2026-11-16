#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Compose source audio, camera, display and GPU candidates; never build a flash DTBO."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from annibale_fdt import Fdt, cells


def require(condition, message):
    if not condition:
        raise ValueError(message)


def strings(value):
    return value.rstrip(b'\0').decode().split('\0')


def check(tree, family, camera_before):
    nodes = tree.nodes
    ph = {cells(p['phandle'])[0]: n for n, p in nodes.items() if 'phandle' in p}
    panel_labels = ['dsi_p11_42_0d_0a_dsc_cmd', 'dsi_p11_42_02_0b_dsc_cmd',
                    'dsi_p11_42_0d_0a_p00_dsc_cmd', 'dsi_p11_42_0d_0a_p10_dsc_cmd',
                    'dsi_nt37801_amoled_video']
    expected_panels = [tree.symbol(n) for n in panel_labels]
    touch = [(n, p) for n, p in nodes.items() if b'xiaomi,touch-spi' in p.get('compatible', b'').split(b'\0')]
    require(len(touch) == 1, 'expected one Goodix node')
    require([ph[n] for n in cells(touch[0][1]['panel'])] == expected_panels, 'touch panel references changed')
    for key, value in [('goodix,firmware-name', b'goodix_firmware_annibale\0'),
                       ('goodix,config-name', b'goodix_cfg_group_annibale\0'),
                       ('goodix,thp-config-name', b'annibale_gtp_thp_config.ini\0')]:
        require(touch[0][1][key] == value, 'touch firmware/config selection changed')
    gpu = nodes[tree.symbol('msm_gpu')]
    require('qcom,kgsl-3d0' in strings(gpu['compatible']), 'missing KGSL GPU binding')
    require(gpu.get('status') in (b'ok\0', b'okay\0'), 'GPU is disabled')
    ufs = nodes[tree.symbol('ufshc_mem')]
    phy = nodes[ph[cells(ufs['phys'])[0]]]
    require('qcom,ufs-phy-qmp-v4-sun' in strings(phy['compatible']), 'UFS PHY does not match native plan')
    require(ufs.get('status', b'okay\0') in (b'ok\0', b'okay\0'), 'UFS is disabled')
    tme = [(n, p) for n, p in nodes.items() if b'qcom,tmecom-qmp-client' in p.get('compatible', b'').split(b'\0')]
    require(len(tme) == 1, 'missing TME client')
    qmp = nodes[ph[cells(tme[0][1]['mboxes'])[0]]]
    require(qmp['compatible'] == b'qcom,qmp-mbox\0', 'unexpected TME mailbox provider')
    snd = nodes[tree.symbol('sun_snd')]
    require(cells(snd['qcom,tdm-max-slots']) == [2], 'audio TDM slots overwritten')
    codecs = [ph[n] for n in cells(snd['xiaomi,smartpa-codecs'])]
    compatible = b'tfa,tfa98xx\0' if family == 'tfa' else b'si,sia91xx-i2c\0'
    require(len(codecs) == 2 and all(nodes[n]['compatible'] == compatible for n in codecs), 'audio family overwritten')
    dmic = nodes[ph[cells(snd['qcom,cdc-dmic-enable-gpios'])[0]]]
    require(dmic['compatible'] == b'qcom,msm-cdc-pinctrl\0', 'DMIC provider overwritten')
    # No final overlay may silently rewrite the already composed sensor nodes.
    sensors = {n: p for n, p in camera_before.nodes.items()
               if any(c in p.get('compatible', b'').split(b'\0')
                      for c in (b'qcom,cam-sensor', b'qcom,cam-i2c-sensor'))}
    require(len(sensors) == 4, 'expected four Annibale sensors')
    require(all(nodes[n] == p for n, p in sensors.items()), 'display/GPU composition changed sensor properties')
    return {'touch_node': touch[0][0], 'panel_candidates': expected_panels,
            'gpu_compatible': strings(gpu['compatible']), 'ufs_phy_compatible': strings(phy['compatible']),
            'camera_nodes_preserved': sorted(sensors), 'audio_codec_nodes': codecs}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('kernel', 'modules', 'dtc', 'fdtoverlay', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    dts = Path(__file__).resolve().parents[1]
    out = args.output.resolve()
    if out.exists():
        parser.error('output must not exist')
    out.mkdir(parents=True)
    audio = out / 'audio'
    subprocess.run([sys.executable, '-B', str(dts / 'tools/validate_annibale_audio.py'),
                    '--kernel', str(args.kernel), '--modules', str(args.modules),
                    '--dtc', str(args.dtc), '--fdtoverlay', str(args.fdtoverlay),
                    '--output', str(audio)], check=True)
    sources = ['camera/sun-camera', 'camera/annibale-sm8750-camera-sensor',
               'display/display/annibale-sde-display-mtp-overlay',
               'graphics/gpu/sun-gpu', 'graphics/gpu/sun-v2-gpu']
    for source in sources:
        name = source.split('/')[-1]
        with (out / (name + '.pp.dts')).open('w') as stream:
            subprocess.run(['gcc', '-E', '-nostdinc', '-undef', '-D__DTS__', '-x', 'assembler-with-cpp',
                            '-I' + str(args.kernel.resolve() / 'include'), '-I' + str(dts / 'qcom'),
                            '-I' + str(args.modules.resolve() / 'qcom/opensource/camera-kernel'),
                            '-I' + str(args.modules.resolve() / 'qcom/opensource/display-drivers/include'),
                            str(dts / 'qcom' / (source + '.dts'))], stdout=stream, check=True)
        with (out / (name + '.warnings')).open('w') as stream:
            subprocess.run([str(args.dtc), '-@', '-I', 'dts', '-O', 'dtb', '-o', str(out / (name + '.dtb')),
                            str(out / (name + '.pp.dts'))], stderr=stream, check=True)
    rows = []
    for base in ('sun', 'sun-v2', 'sun-tp', 'sun-tp-v2', 'sunp', 'sunp-v2', 'sunp-tp', 'sunp-tp-v2'):
        gpu = 'sun-v2-gpu' if base.endswith('-v2') else 'sun-gpu'
        for family in ('tfa', 'sia'):
            camera = out / f'{base}-{family}-camera.dtb'
            subprocess.run([str(args.fdtoverlay), '-i', str(audio / f'{base}-{family}.dtb'),
                            '-o', str(camera), str(out / 'sun-camera.dtb'),
                            str(out / 'annibale-sm8750-camera-sensor.dtb')], check=True)
            result = out / f'{base}-{family}-interactive.dtb'
            subprocess.run([str(args.fdtoverlay), '-i', str(camera), '-o', str(result),
                            str(out / 'annibale-sde-display-mtp-overlay.dtb'), str(out / (gpu + '.dtb'))], check=True)
            evidence = check(Fdt(result.read_bytes()), family, Fdt(camera.read_bytes()))
            rows.append({'base': base, 'family': family, 'gpu_overlay': gpu, **evidence,
                         'sha256': hashlib.sha256(result.read_bytes()).hexdigest()})
    warnings = {str(p.relative_to(out)): p.read_text().count('Warning (') for p in sorted(out.rglob('*.warnings'))}
    report = {'status': 'passed', 'compositions': rows, 'dtc_warning_counts': warnings,
              'flashable': False, 'boot_verified': False,
              'scope': 'Eight bases x two audio families, followed by common/Annibale camera, P11 display and matching GPU overlay. Selected binding checks only; not complete DT schema, GPIO conflicts, bootloader table or hardware validation.'}
    (out / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'PASS: {len(rows)} interactive compositions; NOT boot-qualified')


if __name__ == '__main__':
    main()
