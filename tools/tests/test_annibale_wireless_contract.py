# SPDX-License-Identifier: BSD-3-Clause
"""Reject ambiguous/dangling DT references while preserving numeric GPIO arguments."""
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from annibale_wireless_contract import active, normalize


def cell(*v):
    return struct.pack('>' + 'I' * len(v), *v)


class WirelessContractTests(unittest.TestCase):
    def setUp(self):
        self.tree = SimpleNamespace(nodes={
            '/': {}, '/soc': {}, '/gpio': {'phandle': cell(3), '#gpio-cells': cell(2)},
            '/cpu': {'phandle': cell(16)}, '/soc/wlan': {'wlan-en-gpio': cell(3, 16, 0)}},
            symbol=lambda _: '/pci/rootport')

    def test_gpio_argument_equal_to_another_phandle_stays_numeric(self):
        refs = set()
        value = normalize(self.tree, '/soc/wlan', refs, set())
        self.assertEqual(value['wlan-en-gpio'], [{'provider': '/gpio', 'args': [16, 0]}])
        self.assertEqual(refs, {'/gpio'})

    def test_unresolved_gpio_provider_fails(self):
        self.tree.nodes['/soc/wlan']['wlan-en-gpio'] = cell(99, 16, 0)
        with self.assertRaisesRegex(ValueError, 'unresolved'):
            normalize(self.tree, '/soc/wlan', set(), set())

    def test_short_gpio_specifier_fails(self):
        self.tree.nodes['/soc/wlan']['wlan-en-gpio'] = cell(3, 16)
        with self.assertRaisesRegex(ValueError, 'truncated'):
            normalize(self.tree, '/soc/wlan', set(), set())

    def test_disabled_ancestor_blocks_enabled_child(self):
        self.tree.nodes['/soc']['status'] = b'disabled\0'
        self.tree.nodes['/soc/wlan']['status'] = b'okay\0'
        with self.assertRaisesRegex(ValueError, '/soc'):
            active(self.tree, '/soc/wlan')

    def test_absent_status_is_enabled(self):
        active(self.tree, '/soc/wlan')
