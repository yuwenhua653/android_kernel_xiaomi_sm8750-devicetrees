# SPDX-License-Identifier: BSD-3-Clause
"""Normalize reviewed wireless bindings without treating numeric arguments as phandles."""
import re
from annibale_fdt import cells

LABELS = ('wlan_kiwi', 'bluetooth', 'slim_msm', 'qupv3_se14_4uart', 'pcie0',
          'cnss_pci0', 'cnss_wlan_mem', 'bt_en', 'bt_fmd_clk_en', 'cnss_bt_sw_ctrl',
          'cnss_wlan_en_active', 'cnss_wlan_en_sleep', 'cnss_wlan_sw_ctrl',
          'cnss_wlan_sw_ctrl_wl_cx', 'fmd_set', 'fmd_chg_pon', 'fmd_cnt2_stop')
TYPED = {'clocks': '#clock-cells', 'resets': '#reset-cells',
         'interconnects': '#interconnect-cells', 'iommus': '#iommu-cells',
         'dmas': '#dma-cells', 'power-domains': '#power-domain-cells',
         'interrupts-extended': '#interrupt-cells'}
SINGLE = {'nvmem-cells', 'memory-region', 'qcom,qmp', 'qcom,iommu-group'}
SUPPLIER_KEYS = ('compatible', 'reg', '#gpio-cells', '#clock-cells', '#reset-cells',
                 '#interconnect-cells', '#iommu-cells', '#dma-cells', '#interrupt-cells',
                 'regulator-name', 'regulator-min-microvolt', 'regulator-max-microvolt')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def active(tree, path):
    while True:
        require(tree.nodes[path].get('status', b'okay\0') in (b'ok\0', b'okay\0'),
                'disabled wireless node/provider: ' + path)
        if path == '/':
            break
        path = path.rsplit('/', 1)[0] or '/'


def normalize(tree, name, references, pins):
    ph = {cells(p['phandle'])[0]: n for n, p in tree.nodes.items() if 'phandle' in p}
    out = {}
    for key, value in tree.nodes[name].items():
        if key in ('phandle', 'linux,phandle'):
            continue
        gpio = key.endswith(('-gpio', '-gpios')) or key == 'gpios'
        pin = re.fullmatch(r'pinctrl-[0-9]+', key) is not None
        if key in TYPED or key in SINGLE or key.endswith('-supply') or pin or gpio:
            data, index, items = cells(value), 0, []
            while index < len(data):
                require(data[index] in ph, f'{name}:{key}: unresolved phandle')
                provider = ph[data[index]]
                count_key = '#gpio-cells' if gpio else TYPED.get(key)
                count = cells(tree.nodes[provider][count_key])[0] if count_key else 0
                require(index + count + 1 <= len(data), f'{name}:{key}: truncated specifier')
                items.append({'provider': provider, 'args': data[index + 1:index + count + 1]})
                references.add(provider)
                if pin:
                    pins.add(provider)
                index += count + 1
            out[key] = items
        elif key == 'iommu-addresses':
            # This contract scopes this format to the reviewed PCI function.
            data = cells(value)
            require(name.endswith('/cnss_pci0_iommu_region_partition') and len(data) % 6 == 0,
                    'unexpected iommu-addresses layout')
            out[key] = [{'provider': ph[data[i]], 'args': data[i + 1:i + 6]}
                        for i in range(0, len(data), 6)]
            references.update(ph[data[i]] for i in range(0, len(data), 6))
        elif key in ('msi-map', 'iommu-map'):
            data = cells(value)
            require(len(data) % 4 == 0, 'truncated PCI mapping')
            out[key] = [{'rid': data[i], 'provider': ph[data[i + 1]],
                         'args': data[i + 2:i + 4]} for i in range(0, len(data), 4)]
            references.update(ph[data[i + 1]] for i in range(0, len(data), 4))
        elif key == 'status':
            out[key] = 'enabled' if value in (b'ok\0', b'okay\0') else value.hex()
        else:
            out[key] = value.hex()
    # OEM omits these two properties on the root port; Linux resolves them
    # through its PCI controller ancestor. LOS explicitly supplies the same 3/2.
    if name == tree.symbol('pcie0_rp'):
        for key in ('#address-cells', '#size-cells'):
            ancestor = name
            while key not in tree.nodes[ancestor]:
                ancestor = ancestor.rsplit('/', 1)[0] or '/'
                require(ancestor != '/', 'PCI address/size cells missing')
            out[key] = tree.nodes[ancestor][key].hex()
    return out


def contract(tree):
    selected = set()
    for label in LABELS:
        path = tree.symbol(label)
        selected.update(n for n in tree.nodes if n == path or n.startswith(path + '/'))
    references, pins, result = set(), set(), {}
    for path in sorted(selected):
        active(tree, path)
        result[path] = normalize(tree, path, references, pins)
    for pin in sorted(pins):
        for path in sorted(n for n in tree.nodes if n == pin or n.startswith(pin + '/')):
            active(tree, path)
            result[path] = normalize(tree, path, references, set())
    suppliers = {}
    for path in sorted(references):
        active(tree, path)
        props = tree.nodes[path]
        suppliers[path] = {k: props[k].hex() for k in SUPPLIER_KEYS if k in props}
        # A cell's offset is meaningful only with its NVMEM parent's base/type.
        if path in [tree.symbol(n) for n in ('fmd_set', 'fmd_chg_pon', 'fmd_cnt2_stop')]:
            parent = path.rsplit('/', 1)[0]
            suppliers[parent] = {k: tree.nodes[parent][k].hex() for k in SUPPLIER_KEYS if k in tree.nodes[parent]}
    require(not any(b'rtc6226' in p.get('compatible', b'').split(b'\0') for p in tree.nodes.values()),
            'unexpected reference-board FM node')
    uart_paths = []
    for path, props in tree.nodes.items():
        if b'qcom,msm-geni-serial-hs' not in props.get('compatible', b'').split(b'\0'):
            continue
        try:
            active(tree, path)
        except ValueError:
            continue
        uart_paths.append(path)
    aliases = {k: v.hex() for k, v in tree.nodes.get('/aliases', {}).items()
               if k.startswith(('serial', 'hsuart'))}
    return {'nodes': result, 'suppliers': suppliers, 'enabled_hs_uart_paths': sorted(uart_paths),
            'serial_aliases': aliases}
