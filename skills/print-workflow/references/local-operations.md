# 安装与本机操作

## 1. 配置运行环境

需要 Windows、PowerShell 7、Python 3.11+。已有 Fusion/Blender/Bambu Studio 与对应 MCP 按本机配置使用。

在技能根目录运行：

```powershell
& .\scripts\setup.ps1 -PythonExecutable 'C:\实际路径\python.exe'
```

`setup.ps1` 创建 `scripts/.runtime`，安装锁定依赖，并在配置缺失时复制 `config.example.json` 到 `config.json`。已有配置保留。若 Windows 的 python 商店别名不可用，传入真实 Python 可执行文件路径。

编辑 `scripts/config.json`：

| 配置项 | 用途 |
|---|---|
| model_root | 每个模型项目文件夹的上级目录 |
| bambu_exe | Bambu Studio 可执行文件完整路径 |
| blender_exe | Blender 可执行文件完整路径 |
| blender_start_script | 本机现有 MCP 启动脚本；没有则留空并从 Blender 启动插件 |
| fusion_launcher | 本机 FusionLauncher 完整路径；升级后可能变化 |
| fusion_endpoint | 本地 Fusion MCP 地址，默认 http://127.0.0.1:27182/mcp |

`config.json`、运行环境、缓存和日志已被 `.gitignore` 排除。示例保存目录可按用户偏好调整。

## 2. 检查与新建项目

```powershell
$wf = '.\scripts\工作流.ps1'
& $wf doctor
& $wf init '模型名称' --software fusion
```

软件可选 `fusion`、`blender`。已有模型文件夹不会被覆盖；继续项目用 `status`。尚未配置默认目录时可为测试明确指定 `--root`。

启动现有工具：`& .\scripts\启动工具.ps1 -Tool fusion`，也可选 `blender` / `bambu`。已打开的 Blender 没有 MCP 时会提示在当前实例启动插件，不替换当前场景。随后用真实 MCP 工具验证响应。

## 3. 提交文件、记录确认

```powershell
$p = 'D:\AI建模\模型名称'
& $wf status $p
& $wf submit $p design "$p\01-方案\需求与方案.md" "$p\01-方案\效果图.png"
# 只有用户真正同意当前版本后，才把实际答复填入下一条命令。
& $wf confirm $p design --user-quote '这里必须替换为用户真实答复'
```

`model` 阶段需要源文件（Fusion 为 F3D，Blender 为 BLEND）、STL、实际截图和与 STL 哈希匹配的通过报告。`slice` 阶段需要含 G-code 的 3MF、已填写的审查 Markdown，另应加入预览、报告和打印说明。

## 4. 检查、导入、切片

```powershell
& $wf mesh-check "$p\03-打印文件\模型.stl" --output "$p\05-检查\mesh-v1.json"
# 以下导入要求 model 阶段已确认，且导入文件属于确认清单。
& $wf open-bambu $p "$p\03-打印文件\模型.stl"
```

在 Bambu Studio 核对打印条件，设置摆放、对象材料、支撑绘制和工艺参数，将工程保存到模型文件夹，例如 `04-切片/项目-v1.3mf`。在 GUI 切片并查看实际预览；也可使用本机 CLI：

```powershell
& $wf slice $p "$p\04-切片\项目-v1.3mf"
& $wf inspect-3mf "$p\04-切片\已切片-v1.3mf" --output "$p\05-检查\slice-v1.json"
```

CLI 使用项目内设置，不猜打印机、材料或支撑；每次创建独立输出目录。须核对工程确实对应已确认模型。输出参数依据 [Bambu 官方 CLI 文档](https://github.com/bambulab/BambuStudio/wiki/Command-Line-Usage)，实际能力以本机版本为准。

STL 检查失败返回 2，其他操作失败返回 1。报告已存在时拒绝覆盖。温度列表来自实际指令，可能包括预热、清理和关闭，不是全程打印温度。

## 5. 交付和测试

```powershell
& $wf package $p
& .\scripts\.runtime\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
```

打包仅在三次确认都有效时成功，且要求源文件、STL、3MF。确认清单应包含所有要交付的工程、预览、检查和说明。项目状态和文件校验和会收入包。实物状态不会自动升级为已验证。

测试用临时合成资料，不调用 CAD、不运行切片、不联系打印机；它检验流程逻辑和解析器，不能替代本机软件联调。
