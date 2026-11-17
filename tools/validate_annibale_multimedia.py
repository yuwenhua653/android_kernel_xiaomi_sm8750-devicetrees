#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Compose multimedia with all interactive variants; not a flash DTBO builder."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from annibale_fdt import Fdt, cells
from validate_annibale_interactive import check as check_interactive, require


def check(tree, revision):
    require(revision in ('v1', 'v2'), 'unknown SoC revision')
    nodes = tree.nodes
    ph = {cells(p['phandle'])[0]: n for n, p in nodes.items() if 'phandle' in p}
    root = nodes['/']
    require(cells(root['qcom,board-id']) == [0x40008, 0], 'Annibale board selector lost')
    require(cells(root['xiaomi,miboard-id']) == [0xB, 0], 'Annibale Xiaomi selector lost')
    version = 0x10000 if revision == 'v1' else 0x20000
    require(cells(root['qcom,msm-id']) == [n for soc in (618, 639, 0x100026a, 0x100027f)
                                          for n in (soc, version)], 'wrong SoC selector')
    video, eva = tree.symbol('msm_vidc'), tree.symbol('msm_cvp')
    require(nodes[video]['compatible'] == (b'qcom,sm8750-vidc\0' if revision == 'v1'
                                          else b'qcom,sm8750-vidc-v2\0'), 'wrong video revision')
    require(cells(nodes[eva]['soc_ver']) == [version], 'wrong EVA revision')
    require(nodes[eva]['cvp,firmware-name'] == b'evass\0', 'EVA firmware selection changed')
    for n in (video, eva):
        require(nodes[n].get('status', b'okay\0') in (b'ok\0', b'okay\0'), 'media node disabled')
    selected = [n for n in nodes if n in (video, eva) or n.startswith((video + '/', eva + '/'))]
    references = []
    typed = {'clocks': '#clock-cells', 'resets': '#reset-cells',
             'power-domains': '#power-domain-cells', 'iommus': '#iommu-cells',
             'interconnects': '#interconnect-cells'}
    for name in selected:
        for key, value in nodes[name].items():
            if key not in typed and not key.endswith('-supply') and key != 'memory-region':
                continue
            values, index = cells(value), 0
            while index < len(values):
                require(values[index] in ph, f'{name}:{key} unresolved provider')
                target = ph[values[index]]
                p = nodes[target]
                require(p.get('status', b'okay\0') in (b'ok\0', b'okay\0'),
                        f'{name}:{key} disabled provider {target}')
                count = cells(p[typed[key]])[0] if key in typed else 0
                require(index + count + 1 <= len(values), f'{name}:{key} truncated specifier')
                references.append({'node': name, 'property': key, 'provider': target})
                index += count + 1
    for consumer, label in ((video, 'video_mem'), (eva, 'cvp_mem')):
        require(ph[cells(nodes[consumer]['memory-region'])[0]] == tree.symbol(label),
                'wrong multimedia firmware carveout')
    require(tree.symbol('video_mem') != tree.symbol('cvp_mem'), 'firmware carveouts alias')
    for label in ('videocc', 'evacc', 'apps_smmu', 'gcc', 'mmss_noc'):
        require(any(r['provider'] == tree.symbol(label) for r in references),
                'missing media supplier: ' + label)
    return {'video_node': video, 'eva_node': eva, 'revision': revision,
            'provider_references': references}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('kernel', 'modules', 'dtc', 'fdtoverlay', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--interactive-input', type=Path, help='Reuse hash-checked interactive validation output')
    args = parser.parse_args()
    dts = Path(__file__).resolve().parents[1]
    out = args.output.resolve()
    if out.exists():
        parser.error('output must not exist')
    out.mkdir(parents=True)
    selector = out / 'selector.mk'
    selector.write_text('include ' + str(dts / 'qcom/Makefile') + '\n.PHONY: check\ncheck:\n\t@echo $(always-y)\n')
    for rev, arch, vm in [('', 'y', 'n'), ('v1', 'y', 'n'), ('v2', 'y', 'n'),
                          ('v1 v2', 'y', 'n'), ('auto', 'y', 'n'), ('v%', 'y', 'n'), ('v1', 'n', 'n'), ('v2', 'y', 'y')]:
        run = subprocess.run(['make', '-s', '-f', str(selector), 'check',
                              'ANNIBALE_MULTIMEDIA_REV=' + rev, 'CONFIG_ARCH_SUN=' + arch,
                              'CONFIG_ARCH_QTI_VM=' + vm], text=True, capture_output=True)
        valid = rev in ('', 'v1', 'v2') and arch == 'y' and vm != 'y'
        require((run.returncode == 0) == valid, 'multimedia Kbuild selector gate failed')
        if valid:
            selected = [n for n in run.stdout.split() if n.startswith('annibale-multimedia-')]
            require(selected == ([] if not rev else [f'annibale-multimedia-{rev}-test.dtbo']),
                    'multimedia target missing from always-y or implicitly enabled')
    interactive = args.interactive_input.resolve() if args.interactive_input else out / 'interactive'
    if not args.interactive_input:
        subprocess.run([sys.executable, '-B', str(dts / 'tools/validate_annibale_interactive.py'),
                        '--kernel', str(args.kernel), '--modules', str(args.modules),
                        '--dtc', str(args.dtc), '--fdtoverlay', str(args.fdtoverlay),
                        '--output', str(interactive)], check=True)
    previous = json.loads((interactive / 'validation.json').read_text())
    expected = {(b, f, m) for b in ('sun', 'sun-v2', 'sun-tp', 'sun-tp-v2', 'sunp', 'sunp-v2', 'sunp-tp', 'sunp-tp-v2')
                for f in ('tfa', 'sia') for m in ('default', 'native')}
    require(previous['status'] == 'passed' and len(previous['compositions']) == 32 and
            {(r['base'], r['family'], r['display_mode']) for r in previous['compositions']} == expected,
            'incomplete interactive input matrix')
    for rev in ('v1', 'v2'):
        source = 'annibale-multimedia-' + rev + '-test'
        with (out / (source + '.pp.dts')).open('w') as stream:
            subprocess.run(['gcc', '-E', '-nostdinc', '-undef', '-D__DTS__', '-x', 'assembler-with-cpp',
                            '-I' + str(args.kernel.resolve() / 'include'), '-I' + str(dts / 'qcom'),
                            str(dts / 'qcom' / (source + '.dts'))], stdout=stream, check=True)
        with (out / (source + '.warnings')).open('w') as stream:
            subprocess.run([str(args.dtc), '-@', '-I', 'dts', '-O', 'dtb', '-o', str(out / (source + '.dtb')),
                            str(out / (source + '.pp.dts'))], stderr=stream, check=True)
    rows = []
    previous = json.loads((interactive / 'validation.json').read_text())
    for row in previous['compositions']:
        base, family, native = row['base'], row['family'], row['display_mode'] == 'native'
        rev = 'v2' if base.endswith('-v2') else 'v1'
        name = f'{base}-{family}-interactive' + ('-native' if native else '')
        require(hashlib.sha256((interactive / (name + '.dtb')).read_bytes()).hexdigest() == row['sha256'],
                'stale interactive DT bytes')
        result = out / (name + '-multimedia.dtb')
        subprocess.run([str(args.fdtoverlay), '-i', str(interactive / (name + '.dtb')),
                        '-o', str(result), str(out / f'annibale-multimedia-{rev}-test.dtb')], check=True)
        tree = Fdt(result.read_bytes())
        check_interactive(tree, family, Fdt((interactive / f'{base}-{family}-camera.dtb').read_bytes()), native)
        evidence = check(tree, rev)
        # Exercise rejection on real compiled DTs, not fixtures invented to match this checker.
        mutations = []
        wrong_revision = deepcopy(tree)
        wrong_revision.nodes[wrong_revision.symbol('msm_cvp')]['soc_ver'] = bytes(4)
        mutations.append(wrong_revision)
        disabled = deepcopy(tree)
        disabled.nodes[disabled.symbol('evacc')]['status'] = b'disabled\0'
        mutations.append(disabled)
        unresolved = deepcopy(tree)
        unresolved.nodes[unresolved.symbol('msm_vidc')]['clocks'] = b'\xff' * 8
        mutations.append(unresolved)
        wrong_board = deepcopy(tree)
        wrong_board.nodes['/']['qcom,board-id'] = bytes(8)
        mutations.append(wrong_board)
        for mutated in mutations:
            try:
                check(mutated, rev)
            except ValueError:
                pass
            else:
                raise ValueError('accepted invalid multimedia DT mutation')
        rows.append({'base': base, 'family': family, 'display_mode': row['display_mode'], **evidence,
                     'sha256': hashlib.sha256(result.read_bytes()).hexdigest()})
    report = {'status': 'passed', 'compositions': rows, 'flashable': False, 'boot_verified': False,
              'negative_checks': len(rows) * 4, 'selector_checks': 8,
              'scope': '32 real compositions, explicit SoC revision, Annibale IDs, media phandle providers and prior interactive binding checks. Not complete DT schema/GPIO/firmware/HAL or bootloader selection validation.'}
    (out / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'PASS: {len(rows)} multimedia compositions; NOT boot-qualified')


if __name__ == '__main__':
    main()
