#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Qualify Annibale wireless DT wiring against reviewed OS4.0.6.0 bindings."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

from annibale_fdt import Fdt, cells
from annibale_wireless_contract import contract, require
from validate_annibale_interactive import check as check_interactive
from validate_annibale_multimedia import check as check_media


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(tree, expected):
    actual = contract(tree)
    for section in ('nodes', 'suppliers'):
        require(actual[section].keys() == expected[section].keys(), section + ': node set mismatch')
        for path in expected[section]:
            require(actual[section][path] == expected[section][path], 'wireless binding mismatch: ' + path)
    require(actual['enabled_hs_uart_paths'] == expected['enabled_hs_uart_paths'], 'HS UART instance set changed')
    require(actual['serial_aliases'] == expected['serial_aliases'], 'serial aliases changed')
    return {'nodes': len(actual['nodes']), 'suppliers': len(actual['suppliers'])}


def preserve(before, after):
    allowed = {before.symbol('slim_msm'): {'status'}, before.symbol('qupv3_se14_4uart'): {'status'},
               before.symbol('pcie0_rp'): {'#address-cells', '#size-cells'}}
    for path, old in before.nodes.items():
        require(path in after.nodes, 'wireless removed an existing node')
        if path == '/__symbols__':
            require(all(after.nodes[path].get(k) == v for k, v in old.items()), 'wireless rewrote existing symbol')
            continue
        changed = {k for k in old.keys() | after.nodes[path].keys() if old.get(k) != after.nodes[path].get(k)}
        require(changed <= allowed.get(path, set()), 'wireless rewrote existing properties: ' + path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('kernel', 'modules', 'dtc', 'fdtoverlay', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--multimedia-input', type=Path, help='Reuse complete, hash-checked R22 output')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    out = args.output.resolve()
    if out.exists():
        parser.error('output must not exist')
    out.mkdir(parents=True)
    policy = repo / 'docs/annibale-os406-wireless-contract.json'
    baseline = json.loads(policy.read_text())
    require(baseline['schema_version'] == 1, 'unsupported wireless contract')
    selector = out / 'selector.mk'
    selector.write_text('include ' + str(repo / 'qcom/Makefile') + '\n.PHONY: check\ncheck:\n\t@echo $(always-y)\n')
    selection_cases = [('', 'y', 'n'), ('native', 'y', 'n'), ('auto', 'y', 'n'),
                       ('n%', 'y', 'n'), ('native native', 'y', 'n'), ('native', 'n', 'n'), ('native', 'y', 'y')]
    for mode, sun, vm in selection_cases:
        run = subprocess.run(['make', '-s', '-f', str(selector), 'check', 'ANNIBALE_WIRELESS_MODE=' + mode,
                              'CONFIG_ARCH_SUN=' + sun, 'CONFIG_ARCH_QTI_VM=' + vm], capture_output=True, text=True)
        good = mode in ('', 'native') and sun == 'y' and vm == 'n'
        require((run.returncode == 0) == good, 'Kbuild wireless selection gate failed')
        if good:
            selected = [n for n in run.stdout.split() if n == 'annibale-wireless-test.dtbo']
            require(selected == ([] if not mode else ['annibale-wireless-test.dtbo']), 'wireless target missing/implicitly enabled')
    parent = args.multimedia_input.resolve() if args.multimedia_input else out / 'multimedia'
    if not args.multimedia_input:
        subprocess.run([sys.executable, '-B', str(repo / 'tools/validate_annibale_multimedia.py'),
                        '--kernel', str(args.kernel), '--modules', str(args.modules), '--dtc', str(args.dtc),
                        '--fdtoverlay', str(args.fdtoverlay), '--output', str(parent)], check=True)
    report = json.loads((parent / 'validation.json').read_text())
    expected_cases = {(b, f, m) for b in baseline['bases'] for f in ('tfa', 'sia') for m in ('default', 'native')}
    require(report['status'] == 'passed' and len(report['compositions']) == 32 and
            {(r['base'], r['family'], r['display_mode']) for r in report['compositions']} == expected_cases,
            'incomplete media input matrix')
    with (out / 'wireless.pp.dts').open('w') as stream:
        subprocess.run(['gcc', '-E', '-nostdinc', '-undef', '-D__DTS__', '-x', 'assembler-with-cpp',
                        '-I' + str(args.kernel.resolve() / 'include'), '-I' + str(repo / 'qcom'),
                        str(repo / 'qcom/annibale-wireless-test.dts')], stdout=stream, check=True)
    overlay = out / 'wireless.dtbo'
    with (out / 'wireless.warnings').open('w') as stream:
        subprocess.run([str(args.dtc), '-@', '-I', 'dts', '-O', 'dtb', '-o', str(overlay),
                        str(out / 'wireless.pp.dts')], stderr=stream, check=True)
    meta = Fdt(overlay.read_bytes()).nodes['/']
    require(cells(meta['qcom,board-id']) == [0x40008, 0] and cells(meta['xiaomi,miboard-id']) == [0xB, 0],
            'wrong overlay board selector')
    ids = cells(meta['qcom,msm-id'])
    require(len(ids) == 16 and set(zip(ids[::2], ids[1::2])) ==
            {(soc, rev) for soc in (618, 639, 0x100026a, 0x100027f) for rev in (0x10000, 0x20000)},
            'wrong overlay SoC/revision selector')
    rows = []
    for row in report['compositions']:
        base, family = row['base'], row['family']
        native = row['display_mode'] == 'native'
        stem = f'{base}-{family}-interactive' + ('-native' if native else '') + '-multimedia'
        source = parent / (stem + '.dtb')
        require(digest(source) == row['sha256'], 'stale multimedia DT bytes')
        result = out / (stem + '-wireless.dtb')
        subprocess.run([str(args.fdtoverlay), '-i', str(source), '-o', str(result), str(overlay)], check=True)
        previous, tree = Fdt(source.read_bytes()), Fdt(result.read_bytes())
        expected = baseline['profiles'][baseline['bases'][base]['profile']]
        evidence = check(tree, expected)
        preserve(previous, tree)
        check_interactive(tree, family, previous, native)
        check_media(tree, 'v2' if base.endswith('-v2') else 'v1')
        mutations = []
        for label, key, value in [('bt_en', 'power-source', struct.pack('>I', 2)),
                                  ('slim_msm', 'status', b'disabled\0'),
                                  ('qupv3_se14_4uart', 'status', b'disabled\0'),
                                  ('bluetooth', 'qcom,bt-reset-gpio', struct.pack('>III', 0xffffffff, 3, 0))]:
            bad = deepcopy(tree)
            bad.nodes[bad.symbol(label)][key] = value
            mutations.append(bad)
        bad = deepcopy(tree)
        wlan = bad.nodes[bad.symbol('wlan_kiwi')]
        gpio = cells(wlan['wlan-en-gpio'])
        gpio[1] = 18
        wlan['wlan-en-gpio'] = struct.pack('>III', *gpio)
        mutations.append(bad)
        extra_uart = deepcopy(tree)
        extra_uart.nodes['/soc/unexpected-hsuart'] = {'compatible': b'qcom,msm-geni-serial-hs\0'}
        mutations.append(extra_uart)
        extra_fm = deepcopy(tree)
        extra_fm.nodes['/soc/unexpected-fm'] = {'compatible': b'rtc6226\0'}
        mutations.append(extra_fm)
        for bad in mutations:
            try:
                check(bad, expected)
            except (ValueError, KeyError):
                pass
            else:
                raise ValueError('accepted mutated wireless wiring')
        rows.append({'base': base, 'family': family, 'display_mode': row['display_mode'], **evidence,
                     'sha256': digest(result)})
    result = {'status': 'passed', 'compositions': rows, 'negative_checks': len(rows) * 7,
              'selector_checks': len(selection_cases), 'stock_contract_sha256': digest(policy),
              'multimedia_report_sha256': digest(parent / 'validation.json'),
              'overlay_sha256': digest(overlay), 'flashable': False, 'boot_verified': False,
              'scope': 'Selected stock wireless bindings and supplier identity, existing-node preservation, prior interactive/media checks. Not full electrical/schema/GPIO conflict, firmware/HAL or bootloader qualification.'}
    (out / 'validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(f'PASS: {len(rows)} wireless compositions; NOT boot-qualified')


if __name__ == '__main__':
    main()
