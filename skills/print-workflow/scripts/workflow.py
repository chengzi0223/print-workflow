"""Versioned, user-confirmed local modeling-to-slicing workflow."""
import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
# 配置不随仓库上传；每台电脑按 config.example.json 填写实际软件路径。
CONFIG_PATH = BASE / 'config.json'
CONFIG = json.loads(CONFIG_PATH.read_text(encoding='utf-8-sig')) if CONFIG_PATH.exists() else {}

def configured(key):
    value = CONFIG.get(key)
    if not value:
        raise ValueError(f'请先在 scripts/config.json 设置 {key}，参见安装说明。')
    return value
STAGES = ('design', 'model', 'slice')
LABELS = {'design': '需求与效果图确认', 'model': '实际模型确认', 'slice': '切片最终确认'}


def now():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def save(path, data):
    path = Path(path)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def read_project(project):
    root = Path(project).resolve()
    return root, json.loads((root / 'workflow.json').read_text(encoding='utf-8'))


# 三个确认节点都绑定文件哈希；上游变化会使下游确认失效。
def stage_valid(data, stage):
    for key in STAGES[:STAGES.index(stage) + 1]:
        item = data['stages'].get(key, {})
        if not item.get('confirmation') or not item.get('evidence'):
            return False
        for e in item['evidence']:
            path = Path(e['path'])
            if not path.is_file() or digest(path) != e['sha256']:
                return False
    return True


def require(data, stage):
    if not stage_valid(data, stage):
        raise ValueError(f'{LABELS[stage]}尚未完成或文件已变化；请重新展示对应成果并取得用户确认。')


def write_event(root, data, action, detail):
    data['history'].append({'at': now(), 'action': action, 'detail': detail})
    save(root / 'workflow.json', data)


# 步骤1—3：建立项目与需求模板，不创建几何模型，也不自动同意方案。
def initialize(name, software, root=None):
    # A model name is one Windows folder, never an arbitrary path.
    reserved = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)),
                *(f'LPT{i}' for i in range(1, 10))}
    if (not name.strip() or name in {'.', '..'} or name.rstrip(' .') != name or
        any(c in name for c in '<>:"/\\|?*') or any(ord(c) < 32 for c in name) or
        name.split('.')[0].upper() in reserved):
        raise ValueError('模型名称必须是有效的单个文件夹名称。')
    project = Path(root or configured('model_root')).resolve() / name
    if project.exists():
        raise ValueError('文件夹已存在；继续原项目或选择新版本名称，不覆盖原有模型。')
    project.mkdir(parents=True)
    for folder in ['01-方案', '02-源文件', '03-打印文件', '04-切片', '05-检查', '06-交付']:
        (project / folder).mkdir()
    for template, dest in [('需求与方案.md', '01-方案'), ('切片审查.md', '05-检查'),
                           ('实物反馈.md', '05-检查')]:
        shutil.copy2(BASE / 'templates' / template, project / dest / template)
    data = {'schema_version': 1, 'name': name, 'software': software, 'created_at': now(),
            'slicer': 'Bambu Studio', 'stages': {}, 'history': [], 'physical_validation': 'not_verified'}
    save(project / 'workflow.json', data)
    return {'project': str(project), 'next': '讨论需求、尺寸和打印条件；制作效果图，等待用户确认。'}


# 步骤4/5/补充7：登记实际展示给用户的文件版本，并清除旧确认。
def submit(project, stage, files):
    root, data = read_project(project)
    index = STAGES.index(stage)
    if index:
        require(data, STAGES[index - 1])
    paths = list(dict.fromkeys(Path(f).resolve() for f in files))
    if any(not p.is_file() for p in paths):
        raise ValueError('提交证据中的文件不存在。')
    if any(p.name == 'workflow.json' for p in paths):
        raise ValueError('状态文件不能作为确认文件。')
    suffixes = {p.suffix.lower() for p in paths}
    has_image = bool(suffixes & {'.png', '.jpg', '.jpeg', '.webp'})
    if stage == 'design' and ('.md' not in suffixes or not has_image):
        raise ValueError('方案确认需同时提交需求文档和效果图。')
    if stage == 'model':
        source = '.f3d' if data['software'] == 'fusion' else '.blend'
        stls = [p for p in paths if p.suffix.lower() == '.stl']
        if source not in suffixes or not stls or not has_image:
            raise ValueError('模型确认需源文件、STL 和实际模型截图。')
        reports = []
        for p in paths:
            if p.suffix.lower() == '.json':
                reports.append(json.loads(p.read_text(encoding='utf-8')))
        for stl in stls:
            if not any(isinstance(r, dict) and r.get('sha256') == digest(stl) and
                       r.get('basic_mesh_checks_passed') is True for r in reports):
                raise ValueError('每个 STL 都需要对应当前哈希且通过的 mesh-check JSON 报告。')
    if stage == 'slice':
        from bambu import inspect_3mf
        if not any(p.suffix.lower() == '.3mf' and inspect_3mf(p)['sliced'] for p in paths):
            raise ValueError('切片确认必须包含带 G-code 的 3MF。')
        if not any(p.suffix.lower() == '.md' for p in paths):
            raise ValueError('切片确认还需提交已填写的切片审查文档。')
    # Resubmission invalidates this approval and every downstream approval.
    for key in STAGES[index:]:
        data['stages'].pop(key, None)
    data['stages'][stage] = {'submitted_at': now(),
                            'evidence': [{'path': str(p), 'sha256': digest(p)} for p in paths]}
    write_event(root, data, 'submit', {'stage': stage, 'files': [str(p) for p in paths]})
    return {'stage': stage, 'state': 'awaiting_user_confirmation', 'files': [str(p) for p in paths]}


# 只能在用户明确同意当前版本后记录真实答复；本函数不能鉴别答复真实性。
def confirm(project, stage, user_quote):
    root, data = read_project(project)
    if not user_quote.strip():
        raise ValueError('必须记录用户对当前成果的实际明确答复。')
    index = STAGES.index(stage)
    if index:
        require(data, STAGES[index - 1])
    item = data['stages'].get(stage)
    if not item:
        raise ValueError('先提交当前版本的成果供用户审阅。')
    for e in item['evidence']:
        if not Path(e['path']).is_file() or digest(e['path']) != e['sha256']:
            raise ValueError('展示后文件已变化；重新提交并请用户确认当前版本。')
    item['confirmation'] = {'at': now(), 'user_quote': user_quote}
    write_event(root, data, 'user_confirmation', {'stage': stage, 'user_quote': user_quote})
    return {'stage': stage, 'state': 'confirmed', 'note': '此记录不构成启动打印授权。'}


def status(project):
    root, data = read_project(project)
    statuses = {key: ('confirmed_current' if stage_valid(data, key) else
                     'pending_or_changed') for key in STAGES}
    next_stage = next((LABELS[k] for k in STAGES if not stage_valid(data, k)), '可打包交付')
    return {'project': str(root), 'software': data['software'], 'stages': statuses,
            'next': next_stage, 'physical_validation': data['physical_validation']}


# 步骤5：模型确认有效且文件在确认清单内，才允许导入 Bambu Studio。
def open_bambu(project, path):
    _, data = read_project(project)
    require(data, 'model')
    path = Path(path).resolve()
    approved = {e['path'] for e in data['stages']['model']['evidence']}
    if str(path) not in approved or path.suffix.lower() not in {'.stl', '.3mf', '.step', '.stp'}:
        raise ValueError('只导入本次模型确认中列出的 STL/STEP/3MF 文件。')
    subprocess.Popen([configured('bambu_exe'), str(path)])
    return {'opened': str(path), 'next': '检查实际打印机、喷嘴、耗材与参数，保存 Bambu 3MF 工程。'}


# 步骤6：从已配置的 Bambu 3MF 切片；成功后仍需逐层预览和最终确认。
def slice_project(project, path):
    from bambu import inspect_3mf, run_slice
    root, data = read_project(project)
    require(data, 'model')
    path = Path(path).resolve()
    if path.suffix.lower() != '.3mf' or not path.is_relative_to(root):
        raise ValueError('请把已配置的 Bambu 3MF 工程保存到本模型文件夹。')
    info = inspect_3mf(path)
    settings = info['settings']
    if not all(settings.get(k) for k in ['printer_settings_id', 'print_settings_id', 'filament_settings_id']):
        raise ValueError('3MF 缺少完整预设；请先在 Bambu Studio 选择设备、工艺和耗材并保存项目。')
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    out = root / '04-切片' / stamp
    report = run_slice(configured('bambu_exe'), path, out)
    data['stages'].pop('slice', None)
    write_event(root, data, 'slice_generated', {'input': str(path), 'input_sha256': digest(path),
                                               'output': report['file'], 'review': 'pending'})
    return report


# 补充8：三次确认都有效才生成完整包；物理打印状态不会自动变成通过。
def package(project):
    root, data = read_project(project)
    require(data, 'slice')
    files = {}
    for stage in STAGES:
        for e in data['stages'][stage]['evidence']:
            path = Path(e['path'])
            # Keep external Fusion originals in archive without moving them.
            relative = str(path.relative_to(root)) if path.is_relative_to(root) else f'外部源文件/{path.name}'
            if relative in files and files[relative] != path:
                raise ValueError('交付包存在同名源文件，请先使用不同文件名。')
            if relative.startswith('06-交付') or path.suffix.lower() == '.zip':
                raise ValueError('不要把旧交付包作为新交付的确认文件。')
            files[relative] = path
    suffixes = {p.suffix.lower() for p in files.values()}
    source = '.f3d' if data['software'] == 'fusion' else '.blend'
    if source not in suffixes or '.stl' not in suffixes or '.3mf' not in suffixes:
        raise ValueError('交付需包含可编辑源文件、STL 和已切片 3MF；请在模型确认中列出源文件。')
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    target = root / '06-交付' / (data['name'] + '-' + stamp + '.zip')
    checksums = {name: digest(path) for name, path in files.items()}
    with zipfile.ZipFile(target, 'x', zipfile.ZIP_DEFLATED) as z:
        for name, path in files.items():
            z.write(path, name)
        z.write(root / 'workflow.json', 'workflow.json')
        z.writestr('SHA256.json', json.dumps(checksums, ensure_ascii=False, indent=2))
        z.writestr('交付说明.txt', '本包记录软件检查及用户确认。实物打印和装配尚需验证。\n启动打印需要另行明确授权。\n')
    with zipfile.ZipFile(target) as z:
        if z.testzip():
            raise ValueError('交付包完整性检查失败。')
    return {'package': str(target), 'sha256': digest(target), 'physical_validation': 'not_verified'}


def doctor():
    result = {'at': now(), 'bambu_installed': Path(CONFIG.get('bambu_exe', '')).is_file(),
              'blender_installed': Path(CONFIG.get('blender_exe', '')).is_file(),
              'fusion_launcher_installed': Path(CONFIG.get('fusion_launcher', '')).is_file()}
    for name, port in [('fusion', 27182), ('blender', 9876)]:
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=2):
                result[name + '_port'] = 'reachable_not_protocol_verified'
        except OSError:
            result[name + '_port'] = 'unreachable'
    try:
        payload = {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
            'protocolVersion': '2024-11-05', 'capabilities': {},
            'clientInfo': {'name': 'print-workflow-doctor', 'version': '1'}}}
        req = urllib.request.Request(CONFIG.get('fusion_endpoint', 'http://127.0.0.1:27182/mcp'), json.dumps(payload).encode(),
                                     {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'})
        with urllib.request.urlopen(req, timeout=8) as response:
            raw = response.read().decode()
        if raw.lstrip().startswith('{'):
            rpc = json.loads(raw)
        else:
            rpc = json.loads(next(line[5:] for line in raw.splitlines() if line.startswith('data:')))
        result['fusion_mcp'] = 'ready' if rpc.get('result', {}).get('serverInfo') else 'invalid_response'
    except Exception as e:
        result['fusion_mcp'] = type(e).__name__
    result['blender_mcp'] = 'use get_blendfile_summary_path_info to verify actual protocol'
    return result


def main():
    parser = argparse.ArgumentParser(description='本机 3D 打印工作流；所有用户确认必须来自聊天中的真实答复。')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor')
    p = sub.add_parser('init'); p.add_argument('name'); p.add_argument('--software', choices=['fusion', 'blender'], required=True); p.add_argument('--root')
    for cmd in ['status', 'package']:
        p = sub.add_parser(cmd); p.add_argument('project')
    p = sub.add_parser('submit'); p.add_argument('project'); p.add_argument('stage', choices=STAGES); p.add_argument('files', nargs='+')
    p = sub.add_parser('confirm'); p.add_argument('project'); p.add_argument('stage', choices=STAGES); p.add_argument('--user-quote', required=True)
    for cmd in ['open-bambu', 'slice']:
        p = sub.add_parser(cmd); p.add_argument('project'); p.add_argument('file')
    for cmd in ['mesh-check', 'inspect-3mf']:
        p = sub.add_parser(cmd); p.add_argument('file'); p.add_argument('--output')
    args = parser.parse_args()
    if args.command == 'doctor': result = doctor()
    elif args.command == 'init': result = initialize(args.name, args.software, args.root)
    elif args.command == 'status': result = status(args.project)
    elif args.command == 'submit': result = submit(args.project, args.stage, args.files)
    elif args.command == 'confirm': result = confirm(args.project, args.stage, args.user_quote)
    elif args.command == 'open-bambu': result = open_bambu(args.project, args.file)
    elif args.command == 'slice': result = slice_project(args.project, args.file)
    elif args.command == 'package': result = package(args.project)
    elif args.command == 'mesh-check':
        from mesh_check import check_stl
        result = check_stl(args.file)
    else:
        from bambu import inspect_3mf
        result = inspect_3mf(args.file)
    if getattr(args, 'output', None):
        output = Path(args.output)
        if output.exists():
            raise ValueError('报告文件已存在，请使用新版本文件名。')
        save(output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.command == 'mesh-check' and not result['basic_mesh_checks_passed']:
        return 2
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as e:
        print(f'工作流停止：{e}', file=sys.stderr)
        sys.exit(1)
