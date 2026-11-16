#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Check the actual Kbuild selector and reject malformed P11 overlay fixtures."""
import argparse
import json
from pathlib import Path
import subprocess

from annibale_fdt import Fdt
from validate_annibale_interactive import check


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    kbuild = Path(__file__).resolve().parents[1] / 'qcom/display/Kbuild'
    makefile = 'include ' + str(kbuild) + '\nall:\n\t@echo $(always-y)\n'
    rows = []
    for mode, sun, vm, success in [('', 'y', 'n', True), ('native', 'y', 'n', True),
                                  ('invalid', 'y', 'n', False), ('native', 'n', 'n', False),
                                  ('native', 'y', 'y', False)]:
        result = subprocess.run(['make', '-s', '-f', '-', 'all', 'ANNIBALE_DISPLAY_MODE='+mode,
                                 'CONFIG_ARCH_SUN='+sun, 'CONFIG_ARCH_QTI_VM='+vm],
                                input=makefile, text=True, capture_output=True)
        assert (result.returncode == 0) == success, result.stderr
        if success:
            entries = result.stdout.split()
            assert ('display/annibale-native-panel-test.dtbo' in entries) == (mode == 'native')
            assert entries.count('display/annibale-native-panel-test.dtbo') == (mode == 'native')
            assert 'display/annibale-sde-display-mtp-overlay.dtbo' in entries
        rows.append({'mode': mode, 'sun': sun, 'vm': vm, 'accepted': success})
    root = args.fixtures
    camera = Fdt((root / 'sun-tfa-camera.dtb').read_bytes())
    original = (root / 'sun-tfa-interactive.dtb').read_bytes()
    native = (root / 'sun-tfa-interactive-native.dtb').read_bytes()
    check(Fdt(original), 'tfa', camera)
    check(Fdt(native), 'tfa', camera, True)
    rejected = []
    for case in ('default_as_native', 'native_as_default', 'pa_gate', 'wrong_id',
                 'read_length', 'read_command', 'read_state', 'brightness_range'):
        tree = Fdt(original if case == 'default_as_native' else native)
        pb = tree.nodes[tree.symbol('dsi_p11_42_0d_0a_dsc_cmd')]
        if case == 'pa_gate':
            tree.nodes[tree.symbol('dsi_p11_42_02_0b_dsc_cmd')]['xiaomi,annibale-pb-quirks'] = b''
        elif case == 'wrong_id': pb['mi,panel-id'] = bytes(8)
        elif case == 'read_length': pb['mi,panel-build-id-read-length'] = (2).to_bytes(4, 'big')
        elif case == 'read_command': pb['mi,mdss-dsi-panel-build-id-read-command'] = bytes(8)
        elif case == 'read_state': pb['mi,mdss-dsi-panel-build-id-read-command-state'] = b'dsi_lp_mode\0'
        elif case == 'brightness_range': pb['qcom,mdss-dsi-bl-max-level'] = (6750).to_bytes(4, 'big')
        try:
            check(tree, 'tfa', camera, case != 'native_as_default')
        except ValueError as error:
            rejected.append({'case': case, 'reason': str(error)})
        else:
            raise AssertionError('accepted malformed fixture: ' + case)
    args.output.write_text(json.dumps({'status': 'passed', 'kbuild': rows, 'rejected': rejected}, indent=2)+'\n')
    print('PASS: five Kbuild selections and eight rejected display fixtures')


if __name__ == '__main__':
    main()
