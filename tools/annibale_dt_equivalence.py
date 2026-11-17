# SPDX-License-Identifier: BSD-3-Clause
"""Compare layered and single-pass DTs using compiler-recorded reference offsets.

Only phandle definitions and references identified by the aggregate overlay's
fixup metadata are canonicalized. All other bytes (including numeric arguments)
are exact. This does not infer references by matching integers to phandles.
"""
from annibale_fdt import cells


def require(ok, message):
    if not ok:
        raise ValueError(message)


def phandles(tree):
    result = {}
    for path, props in tree.nodes.items():
        if 'phandle' not in props:
            continue
        value = cells(props['phandle'])
        require(len(value) == 1 and value[0] not in (0, 0xffffffff), 'invalid phandle')
        require(value[0] not in result, 'duplicate phandle')
        result[value[0]] = path
        if 'linux,phandle' in props:
            require(props['linux,phandle'] == props['phandle'], 'conflicting phandle aliases')
    return result


def reference_locations(overlay, merged):
    external = overlay.refs()
    local = phandles(overlay)

    def absolute(path, seen=()):
        pieces = path.split('/')
        require(len(pieces) >= 3 and pieces[1].startswith('fragment@') and pieces[2] == '__overlay__',
                'reference outside an overlay fragment: ' + path)
        fragment = '/' + pieces[1]
        require(fragment not in seen, 'cyclic fragment target')
        props = overlay.nodes[fragment]
        if 'target-path' in props:
            target = props['target-path'].rstrip(b'\0').decode()
        elif (fragment, 'target', 0) in external:
            target = merged.symbol(external[fragment, 'target', 0])
        else:
            target = absolute(local[cells(props['target'])[0]], seen + (fragment,))
        require(target in merged.nodes, 'unresolved fragment target')
        return target.rstrip('/') + ('/' + '/'.join(pieces[3:]) if pieces[3:] else '') or '/'

    locations = {}
    for path, key, offset in external:
        if '/__overlay__' in path:
            locations.setdefault((absolute(path), key), set()).add(offset)
    for path, props in overlay.nodes.items():
        if not path.startswith('/__local_fixups__/'):
            continue
        original = path[len('/__local_fixups__'):]
        if '/__overlay__' not in original:
            continue
        for key, value in props.items():
            locations.setdefault((absolute(original), key), set()).update(cells(value))
    return locations


def canonical(tree, locations):
    handles, result = phandles(tree), {}
    for path, props in tree.nodes.items():
        result[path] = {}
        for key, value in props.items():
            if key in ('phandle', 'linux,phandle'):
                continue
            fragments, last = [], 0
            for offset in sorted(locations.get((path, key), ())):
                require(offset % 4 == 0 and last <= offset and offset + 4 <= len(value),
                        'invalid reference offset')
                handle = cells(value[offset:offset + 4])[0]
                require(handle in handles, 'dangling reference: ' + path + ':' + key)
                fragments.extend((value[last:offset].hex(), handles[handle]))
                last = offset + 4
            fragments.append(value[last:].hex())
            result[path][key] = fragments
    return result


def equivalent(previous, merged, overlay):
    locations = reference_locations(overlay, merged)
    old, new = canonical(previous, locations), canonical(merged, locations)
    require(old.keys() == new.keys(), 'node set changed during aggregation')
    for path in old:
        require(old[path].keys() == new[path].keys(), 'property set changed: ' + path)
        for key in old[path]:
            require(old[path][key] == new[path][key], 'property changed: ' + path + ':' + key)
    return {'nodes_compared': len(new), 'reference_properties': len(locations),
            'properties_compared': sum(len(p) for p in new.values())}
