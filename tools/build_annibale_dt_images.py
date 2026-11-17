#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Build native DT containers with one complete overlay per SoC revision.

Offline partial qualification only: no bootloader/AVB/device access. Recompile
existing source layers into one overlay; never ask a bootloader to replay the
host's fdtoverlay sequence or concatenate independent overlay blobs as one DT.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess

from annibale_fdt import Fdt, cells
from annibale_dt_equivalence import equivalent, require
from validate_annibale_interactive import check as interactive
from validate_annibale_multimedia import check as multimedia
from validate_annibale_wireless import check as wireless

# OEM vendor_boot order, restricted to the eight reviewed Annibale selectors.
BASES = {'sun-tp-v2': (0x100026a, 0x20000), 'sun-tp': (0x100026a, 0x10000),
         'sun-v2': (618, 0x20000), 'sun': (618, 0x10000),
         'sunp-tp-v2': (0x100027f, 0x20000), 'sunp-tp': (0x100027f, 0x10000),
         'sunp-v2': (639, 0x20000), 'sunp': (639, 0x10000)}
SOCS = (618, 639, 0x100026a, 0x100027f)


def parse_bases(data):
    """Read the actual vendor_boot DTB-section payload, without a DT table."""
    offset, result = 0, {}
    by_pair = {pair: name for name, pair in BASES.items()}
    while offset < len(data):
        require(offset + 40 <= len(data), 'truncated base DTB header')
        magic, size = struct.unpack_from('>II', data, offset)
        require(magic == 0xd00dfeed and size >= 40 and offset + size <= len(data), 'invalid base DTB extent')
        blob = data[offset:offset + size]
        ids = cells(Fdt(blob).nodes['/']['qcom,msm-id'])
        require(len(ids) == 2 and tuple(ids) in by_pair, 'unreviewed base selector')
        name = by_pair[tuple(ids)]
        require(name not in result, 'duplicate base selector')
        result[name] = blob
        offset += size
    require(list(result) == list(BASES), 'incomplete/reordered base image')
    return result


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_table(data):
    require(len(data) >= 32, 'short DT table')
    magic, total, header, entry, count, offset, page, version = struct.unpack_from('>8I', data)
    require((magic, header, entry, offset, page, version) == (0xd7b7ab1e, 32, 32, 32, 4096, 0),
            'unexpected DT table layout')
    require(total == len(data) and count == 2 and offset + count * entry <= total, 'invalid DT table extent/count')
    end, blobs = offset + count * entry, []
    for i in range(count):
        size, start, ident, rev, *custom = struct.unpack_from('>8I', data, offset + i * entry)
        require(not any([ident, rev, *custom]), 'unexpected optional DT table selector')
        require(size >= 40 and start >= end and start + size <= total, 'overlapping/out-of-range DT entry')
        blob = data[start:start + size]
        require(struct.unpack_from('>II', blob) == (0xd00dfeed, size), 'entry is not one complete FDT')
        blobs.append(blob)
        end = start + size
    require(end == total, 'unexpected DT table trailing payload')
    return blobs


def selectors(blob):
    props = Fdt(blob).nodes['/']
    ids = cells(props['qcom,msm-id'])
    require(len(ids) == 8 and len(set(zip(ids[::2], ids[1::2]))) == 4, 'invalid overlay SoC selector')
    require(cells(props['qcom,board-id']) == [0x40008, 0] and
            cells(props['xiaomi,miboard-id']) == [0xB, 0], 'wrong Annibale board selector')
    result = set(zip(ids[::2], ids[1::2]))
    require(result in ({(s, 0x10000) for s in SOCS}, {(s, 0x20000) for s in SOCS}), 'unexpected SoC/revision set')
    return result


def selection_matrix(blobs):
    selected = [selectors(blob) for blob in blobs]
    result = {}
    for name, pair in BASES.items():
        matches = [i for i, ids in enumerate(selected) if pair in ids]
        require(len(matches) == 1, 'missing/ambiguous overlay selection: ' + name)
        result[name] = matches[0]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('kernel', 'modules', 'dtc', 'fdtoverlay', 'mkdtimg', 'wireless-input', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    previous = args.wireless_input.resolve()
    report = json.loads((previous / 'validation.json').read_text())
    expected = {(b, f, d) for b in BASES for f in ('tfa', 'sia') for d in ('default', 'native')}
    require(report['status'] == 'passed' and len(report['compositions']) == 32 and
            {(r['base'], r['family'], r['display_mode']) for r in report['compositions']} == expected,
            'incomplete R23 input matrix')
    contract_file = repo / 'docs/annibale-os406-wireless-contract.json'
    require(digest(contract_file) == report['stock_contract_sha256'], 'wireless reference changed')
    contract = json.loads(contract_file.read_text())
    old = {}
    for row in report['compositions']:
        stem = f"{row['base']}-{row['family']}-interactive" + ('-native' if row['display_mode'] == 'native' else '')
        path = previous / (stem + '-multimedia-wireless.dtb')
        require(digest(path) == row['sha256'], 'stale R23 comparison input')
        old[row['base'], row['family'], row['display_mode']] = path
    out = args.output.resolve()
    require(not out.exists(), 'output must not exist')
    out.mkdir(parents=True)
    work = out / 'work'
    work.mkdir()
    cached = {}
    inputs = {}

    def preprocess(relative):
        if relative not in cached:
            source = repo / 'qcom' / (relative + '.dts')
            cmd = ['gcc', '-E', '-nostdinc', '-undef', '-D__DTS__', '-x', 'assembler-with-cpp',
                   '-I' + str(args.kernel.resolve() / 'include'), '-I' + str(repo / 'qcom')]
            for inc in ('audio-kernel/include', 'camera-kernel', 'display-drivers/include'):
                cmd += ['-I' + str(args.modules.resolve() / 'qcom/opensource' / inc)]
            text = subprocess.check_output(cmd + [str(source)], text=True)
            require(text.count('/dts-v1/;') == 1 and text.count('/plugin/;') <= 1,
                    'unexpected DTS header structure')
            inputs[relative] = hashlib.sha256(text.encode()).hexdigest()
            cached[relative] = text.replace('/dts-v1/;', '').replace('/plugin/;', '')
        return cached[relative]

    def compile_tree(name, text):
        source, blob = work / (name + '.pp.dts'), work / (name + '.dtb')
        source.write_text(text)
        with (work / (name + '.warnings')).open('w') as warnings:
            subprocess.run([str(args.dtc), '-@', '-I', 'dts', '-O', 'dtb', '-o', str(blob), str(source)],
                           stderr=warnings, check=True)
        return blob

    bases = {}
    for name, (soc, rev) in BASES.items():
        # Exclude 705/706 from generic SUNP selectors without changing its hardware nodes.
        body = preprocess(name)
        unfiltered = compile_tree(name + '-unfiltered', '/dts-v1/;\n' + body)
        base = compile_tree(name, '/dts-v1/;\n' + body + f'\n/ {{ qcom,msm-id = <{soc} {rev}>; }};\n')
        a, b = Fdt(unfiltered.read_bytes()), Fdt(base.read_bytes())
        a.nodes['/']['qcom,msm-id'] = b.nodes['/']['qcom,msm-id']
        require(a.nodes == b.nodes, 'base selector narrowing changed hardware properties')
        bases[name] = base
    concatenated = b''.join(p.read_bytes() for p in bases.values())
    (out / 'dtb.img').write_bytes(concatenated)
    unpacked = parse_bases((out / 'dtb.img').read_bytes())
    require(unpacked == {n: p.read_bytes() for n, p in bases.items()}, 'base image changed DTB bytes')
    rows, profiles = [], {}
    for family in ('tfa', 'sia'):
        for mode in ('default', 'native'):
            profile = out / (family + '-' + mode)
            profile.mkdir()
            overlays = []
            for rev in ('v1', 'v2'):
                gpu = 'sun-gpu' if rev == 'v1' else 'sun-v2-gpu'
                layers = ['annibale-sm8750-overlay', 'audio/sun-audio', f'audio/annibale-audio-{family}-test',
                          'camera/sun-camera', 'camera/annibale-sm8750-camera-sensor',
                          'display/display/annibale-sde-display-mtp-overlay', 'graphics/gpu/' + gpu]
                if mode == 'native':
                    layers.append('display/display/annibale-native-panel-test')
                layers += [f'annibale-multimedia-{rev}-test', 'annibale-wireless-test']
                revision = 0x10000 if rev == 'v1' else 0x20000
                ids = ' '.join(f'{soc} {revision}' for soc in SOCS)
                source = '/dts-v1/;\n/plugin/;\n' + '\n'.join(preprocess(layer) for layer in layers)
                # The wireless layer's own metadata accepts both revisions; final table entries must not.
                source += f'\n/ {{ qcom,msm-id = <{ids}>; }};\n'
                compiled = compile_tree(f'annibale-{family}-{mode}-{rev}', source)
                overlay = profile / (rev + '.dtbo')
                overlay.write_bytes(compiled.read_bytes())
                overlays.append(overlay)
            image = profile / 'dtbo.img'
            subprocess.run([str(args.mkdtimg), 'create', str(image), '--page_size=4096',
                            *map(str, overlays)], check=True)
            with (profile / 'mkdtimg-dump.txt').open('w') as stream:
                subprocess.run([str(args.mkdtimg), 'dump', str(image)], stdout=stream, check=True)
            blobs = parse_table(image.read_bytes())
            require(blobs == [p.read_bytes() for p in overlays], 'table changed overlay bytes')
            matrix = selection_matrix(blobs)
            # Reject both duplicate v1 and duplicate v2 entries, including reversed ordering.
            for malformed in ([blobs[0], blobs[0]], [blobs[1], blobs[1]]):
                try:
                    selection_matrix(malformed)
                except ValueError:
                    pass
                else:
                    raise ValueError('ambiguous revision selection accepted')
            reversed_matrix = selection_matrix(list(reversed(blobs)))
            require(all(reversed_matrix[n] == 1 - i for n, i in matrix.items()), 'selection depends on entry order')
            for name, base in bases.items():
                selected = overlays[matrix[name]]
                merged = profile / (name + '.dtb')
                subprocess.run([str(args.fdtoverlay), '-i', str(base), '-o', str(merged), str(selected)], check=True)
                before, after = Fdt(old[name, family, mode].read_bytes()), Fdt(merged.read_bytes())
                evidence = equivalent(before, after, Fdt(selected.read_bytes()))
                multimedia(after, 'v2' if name.endswith('-v2') else 'v1')
                # Entire tree equivalence above compares the camera sensors to the prior layered tree.
                interactive(after, family, after, mode == 'native')
                wireless(after, contract['profiles'][contract['bases'][name]['profile']])
                rows.append({'base': name, 'family': family, 'display_mode': mode, 'entry': matrix[name],
                             **evidence, 'sha256': digest(merged)})
            profiles[profile.name] = {'dtbo_sha256': digest(image), 'entries': 2, 'selection': matrix}
    result = {'schema_version': 1, 'status': 'passed', 'flashable': False, 'boot_verified': False,
              'kernel_driver_rebuild': False, 'dtb_sha256': digest(out / 'dtb.img'),
              'base_order': list(BASES), 'source_preprocessor_sha256': inputs,
              'previous_report_sha256': digest(previous / 'validation.json'),
              'tools_sha256': {n: digest(getattr(args, n)) for n in ('dtc', 'fdtoverlay', 'mkdtimg')},
              'profiles': profiles, 'compositions': rows, 'ambiguous_table_rejections': 8,
              'reversed_table_checks': 4,
              'scope': 'Single complete overlay application, full property equivalence with fixup-aware phandle normalization, exact base selector narrowing and DT table integrity. Not bootloader, electrical, AVB or complete device qualification.'}
    (out / 'validation.json').write_text(json.dumps(result, indent=2) + '\n')
    (out / 'README.txt').write_text('OFFLINE NATIVE DT QUALIFICATION; NOT A FLASH PACKAGE.\n'
                                  'dtb.img is eight concatenated SoC DTBs for a vendor_boot DTB section.\n'
                                  'Each profile contains a two-entry DTBO table; choose one amp/display profile.\n'
                                  'Never mix these native candidates into retained-stock HyperOS.\n')
    print('PASS: 4 DTBO containers, 8 complete overlays, 32 single-overlay compositions; NOT boot-qualified')


if __name__ == '__main__':
    main()
