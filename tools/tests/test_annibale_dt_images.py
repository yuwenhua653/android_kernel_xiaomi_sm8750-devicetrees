# SPDX-License-Identifier: BSD-3-Clause
import copy
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from annibale_fdt import Fdt
from annibale_dt_equivalence import equivalent
from build_annibale_dt_images import BASES, SOCS, parse_table, selection_matrix


def tree(nodes):
    value = Fdt.__new__(Fdt)
    value.nodes = nodes
    return value


def cell(*values):
    return struct.pack('>' + 'I' * len(values), *values)


class EquivalenceTests(unittest.TestCase):
    def setUp(self):
        self.overlay = tree({'/': {}, '/fragment@0': {'target-path': b'/soc\0'},
                             '/fragment@0/__overlay__': {}, '/fragment@0/__overlay__/consumer': {},
                             '/__fixups__': {'provider': b'/fragment@0/__overlay__/consumer:gpios:0\0'}})
        self.before = tree({'/': {}, '/soc': {}, '/soc/provider': {'phandle': cell(1)},
                            '/soc/consumer': {'gpios': cell(1, 1, 0)},
                            '/__symbols__': {'provider': b'/soc/provider\0'}})
        self.after = copy.deepcopy(self.before)
        self.after.nodes['/soc/provider']['phandle'] = cell(2)
        self.after.nodes['/soc/consumer']['gpios'] = cell(2, 1, 0)

    def test_relocation_keeps_numeric_argument_equal_to_old_phandle(self):
        self.assertEqual(equivalent(self.before, self.after, self.overlay)['reference_properties'], 1)

    def test_changed_numeric_argument_is_not_normalized(self):
        self.after.nodes['/soc/consumer']['gpios'] = cell(2, 2, 0)
        with self.assertRaisesRegex(ValueError, 'property changed'):
            equivalent(self.before, self.after, self.overlay)

    def test_dangling_reference_rejected(self):
        self.after.nodes['/soc/consumer']['gpios'] = cell(3, 1, 0)
        with self.assertRaisesRegex(ValueError, 'dangling'):
            equivalent(self.before, self.after, self.overlay)

    def test_extra_property_rejected(self):
        self.after.nodes['/soc/consumer']['status'] = b'disabled\0'
        with self.assertRaisesRegex(ValueError, 'property set changed'):
            equivalent(self.before, self.after, self.overlay)

    def test_duplicate_phandle_rejected(self):
        self.after.nodes['/soc/duplicate'] = {'phandle': cell(2)}
        with self.assertRaisesRegex(ValueError, 'duplicate phandle'):
            equivalent(self.before, self.after, self.overlay)


class TableTests(unittest.TestCase):
    def image(self):
        blob = cell(0xd00dfeed, 40) + bytes(32)
        return bytearray(cell(0xd7b7ab1e, 176, 32, 32, 2, 32, 4096, 0) +
                         cell(40, 96, 0, 0, 0, 0, 0, 0) + cell(40, 136, 0, 0, 0, 0, 0, 0) + blob + blob)

    def test_table_extracts_exact_entries(self):
        self.assertEqual(list(map(len, parse_table(self.image()))), [40, 40])

    def test_overlapping_entry_rejected(self):
        data = self.image()
        struct.pack_into('>I', data, 68, 96)
        with self.assertRaisesRegex(ValueError, 'overlapping'):
            parse_table(data)

    def test_truncated_table_rejected(self):
        with self.assertRaisesRegex(ValueError, 'extent'):
            parse_table(self.image()[:-1])

    def test_ambiguous_revision_rejected(self):
        with patch('build_annibale_dt_images.selectors', return_value={(s, 0x10000) for s in SOCS}):
            with self.assertRaisesRegex(ValueError, 'missing/ambiguous'):
                selection_matrix([b'v1', b'v1'])

    def test_selection_does_not_depend_on_table_order(self):
        choices = {b'v1': {(s, 0x10000) for s in SOCS}, b'v2': {(s, 0x20000) for s in SOCS}}
        with patch('build_annibale_dt_images.selectors', side_effect=choices.__getitem__):
            a, b = selection_matrix([b'v1', b'v2']), selection_matrix([b'v2', b'v1'])
        self.assertTrue(all(a[n] == 1 - b[n] for n in BASES))
