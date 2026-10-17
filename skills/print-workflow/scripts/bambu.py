"""Local Bambu Studio adapter. No device upload or print commands."""
import json
import re
import subprocess
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


# 步骤6：读取真实切片包与指令；这不能代替支撑可拆性和关键层预览。
def inspect_3mf(path):
    path = Path(path).resolve()
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        bad = z.testzip()
        if bad:
            raise ValueError('3MF 校验失败：' + bad)
        result = {'file': str(path), 'gcode': [], 'settings': {},
                  'plates': [],
                  'preview_images': [n for n in names if n.endswith('.png')],
                  'visual_review': 'required', 'physical_print': 'not_verified'}
        for name in names:
            if name.endswith('slice_info.config'):
                for plate in ET.fromstring(z.read(name)).findall('plate'):
                    result['plates'].append({
                        'metadata': {e.get('key'): e.get('value') for e in plate.findall('metadata')},
                        'filaments': [dict(e.attrib) for e in plate.findall('filament')],
                    })
            if name.endswith('project_settings.config'):
                settings = json.loads(z.read(name))
                keys = ['printer_model', 'printer_settings_id', 'nozzle_diameter',
                        'print_settings_id', 'filament_settings_id', 'filament_type',
                        'layer_height', 'wall_loops', 'sparse_infill_density',
                        'enable_support', 'support_type', 'support_filament',
                        'support_interface_filament', 'support_top_z_distance',
                        'support_bottom_z_distance', 'curr_bed_type', 'brim_type']
                result['settings'] = {k: settings[k] for k in keys if k in settings}
            if name.lower().endswith('.gcode'):
                g = z.read(name).decode('utf-8', errors='replace')
                metadata = {}
                for line in g.splitlines():
                    if line.startswith('; HEADER_BLOCK_END') or line.startswith('; CONFIG_BLOCK_START'):
                        break
                    if line.startswith(';') and re.search(
                        r'^;\s*(total|model printing time|filament used)', line, re.I):
                        for part in line[1:].split(';'):
                            fields = re.split(r'\s*[:=]\s*', part.strip(), maxsplit=1)
                            if len(fields) == 2:
                                metadata[fields[0]] = fields[1]
                temps = {}
                for command in ['M104', 'M109', 'M140', 'M190']:
                    temps[command] = sorted(set(float(v) for v in re.findall(
                        rf'(?m)^\s*{command}\b[^;\r\n]*?\bS([0-9]+(?:\.[0-9]+)?)', g)))
                result['gcode'].append({'member': name, 'bytes': len(g.encode()),
                                        'metadata': metadata, 'commanded_temperatures_C': temps})
        result['sliced'] = bool(result['gcode'])
        return result


# 步骤6：只生成本机文件，不上传、不加热、不启动打印。
def run_slice(exe, model, output, settings_args=()):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    target = output / 'sliced.3mf'
    command = [str(exe), '--debug', '2', *settings_args, '--slice', '0',
               '--outputdir', str(output), '--export-3mf', target.name, str(Path(model).resolve())]
    (output / 'command.json').write_text(json.dumps(command, ensure_ascii=False, indent=2), encoding='utf-8')
    with (output / 'bambu.log').open('w', encoding='utf-8') as log:
        p = subprocess.run(command, cwd=output, stdout=log, stderr=subprocess.STDOUT,
                           timeout=600, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if p.returncode or not target.is_file():
        raise RuntimeError(f'Bambu 切片未完成，退出码 {p.returncode}，查看 {output / "result.json"} 和 bambu.log')
    report = inspect_3mf(target)
    if not report['sliced']:
        raise RuntimeError('输出 3MF 没有 G-code，不能视为已切片。')
    (output / 'slice-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report

