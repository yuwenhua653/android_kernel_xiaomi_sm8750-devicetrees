# SPDX-License-Identifier: BSD-3-Clause
from pathlib import Path
import subprocess,json,hashlib
from annibale_fdt import Fdt,cells
import argparse
parser=argparse.ArgumentParser(description="Compile and check two opt-in audio families against eight SUN bases.")
parser.add_argument('--kernel',type=Path,required=True)
parser.add_argument('--modules',type=Path,required=True)
parser.add_argument('--dtc',type=Path,required=True)
parser.add_argument('--fdtoverlay',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
dts=Path(__file__).resolve().parents[1]
out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
kernel=args.kernel.resolve();modules=args.modules.resolve()
dtc=args.dtc.resolve();overlay=args.fdtoverlay.resolve()
# Check the real Kbuild's immediate always-y expansion, not only dtbo-y.
makefile=out/'selector.mk'
makefile.write_text('include '+str(dts/'qcom/audio/Kbuild')+'\n.PHONY: check\ncheck:\n\t@echo $(always-y)\n')
for variant in ['', 'tfa', 'sia', 'invalid', 'tfa sia']:
 r=subprocess.run(['make','-s','-f',str(makefile),'CONFIG_ARCH_SUN=y','ANNIBALE_AUDIO_VARIANT='+variant,'check'],capture_output=True,text=True)
 if variant in ['invalid','tfa sia']:
  assert r.returncode!=0,variant
 else:
  assert r.returncode==0,r.stderr
  selected=[s for s in r.stdout.split() if s.startswith('annibale-audio-')]
  assert selected==([] if not variant else ['annibale-audio-'+variant+'-test.dtbo']),selected
files=['sun','sun-v2','sun-tp','sun-tp-v2','sunp','sunp-v2','sunp-tp','sunp-tp-v2','annibale-sm8750-overlay','audio/sun-audio','audio/annibale-audio-tfa-test','audio/annibale-audio-sia-test']
for rel in files:
 name=rel.split('/')[-1];cpp=out/(name+'.pp.dts');blob=out/(name+'.dtb')
 with cpp.open('w') as f:subprocess.run(['gcc','-E','-nostdinc','-undef','-D__DTS__','-x','assembler-with-cpp','-I'+str(kernel/'include'),'-I'+str(dts/'qcom'),'-I'+str(modules/'qcom/opensource/audio-kernel/include'),str(dts/'qcom'/(rel+'.dts'))],stdout=f,check=True)
 with (out/(name+'.warnings')).open('w') as log:subprocess.run([str(dtc),'-@','-I','dts','-O','dtb','-o',str(blob),str(cpp)],stderr=log,check=True)
rows=[]
for name in files[:8]:
 for variant in ['tfa','sia']:
  result=out/(name+'-'+variant+'.dtb')
  subprocess.run([str(overlay),'-i',str(out/(name+'.dtb')),'-o',str(result),str(out/'annibale-sm8750-overlay.dtb'),str(out/'sun-audio.dtb'),str(out/f'annibale-audio-{variant}-test.dtb')],check=True)
  f=Fdt(result.read_bytes());snd=f.nodes[f.symbol('sun_snd')];ph={cells(v['phandle'])[0]:p for p,v in f.nodes.items() if 'phandle' in v}
  assert cells(snd['qcom,tdm-max-slots'])==[2]
  assert cells(snd['qcom,tdm-clk-attribute'])==[4]*8
  assert cells(snd['qcom,wsa-max-devs'])==[0]
  codec_paths=[ph[x] for x in cells(snd['xiaomi,smartpa-codecs'])]
  assert len(codec_paths)==len(set(codec_paths))==2
  wanted=[0x36,0x34] if variant=='tfa' else [0x6e,0x6c]
  compat=b'tfa,tfa98xx\0' if variant=='tfa' else b'si,sia91xx-i2c\0'
  for path,addr in zip(codec_paths,wanted):
   p=f.nodes[path];assert p.get('status',b'okay\0') in (b'okay\0',b'ok\0');assert p['compatible']==compat;assert cells(p['reg'])==[addr];assert cells(p['#sound-dai-cells'])==[0];assert 'xiaomi,annibale-audio' in p
  foreign=b'si,sia91xx-i2c\0' if variant=='tfa' else b'tfa,tfa98xx\0'
  assert not any(p.get('compatible')==foreign for p in f.nodes.values())
  pin=f.nodes[ph[cells(snd['qcom,sec-mi2s-gpios'])[0]]]
  active=[ph[x] for x in cells(pin['pinctrl-0'])]
  assert [f.nodes[p+'/mux']['pins'] for p in active]==[b'gpio121\0',b'gpio123\0',b'gpio122\0',b'gpio124\0']
  dmic=f.nodes[ph[cells(snd['qcom,cdc-dmic-enable-gpios'])[0]]]
  assert dmic['compatible']==b'qcom,msm-cdc-pinctrl\0'
  assert dmic['pinctrl-names']==b'aud_active\0aud_sleep\0'
  for state,level in [('pinctrl-0','output-high'),('pinctrl-1','output-low')]:
   nodes=[ph[x] for x in cells(dmic[state])]
   assert [f.nodes[p+'/mux']['pins'] for p in nodes]==[b'gpio183\0',b'gpio182\0']
   assert all(level in f.nodes[p+'/config'] for p in nodes)
  rows.append({'base':name,'variant':variant,'sha256':hashlib.sha256(result.read_bytes()).hexdigest(),'codec_nodes':codec_paths})
record={'status':'passed','compositions':rows,'checks':['default-off and exclusive Kbuild selector in always-y','two ordered homogeneous enabled-family codec phandles','no opposite-family codec nodes','secondary TDM 2 slots, eight clock attributes 4','secondary TDM pins 121/123/122/124','WSA count zero','DMIC enable GPIO183/182 active-high and sleep-low'], 'scope':'SoC + common audio + one candidate overlay; syntax and selected final-tree assertions only; not full peripheral composition, bootloader DT table or hardware.'}
(out/'validation.json').write_text(json.dumps(record,indent=2)+'\n');print('PASS',len(rows),'audio candidate compositions')
