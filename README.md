# 3D 打印完整工作流 · print-workflow

面向 Codex 的中文 3D 打印技能：从需求沟通、选择建模软件，到效果图确认、建模检查、Bambu Studio 切片审查与交付。

**三次用户确认：效果图方案 → 实际模型 → 最终切片。** Fusion 360 用于参数化/机械建模，Blender 用于雕刻/艺术造型，Bambu Studio 为主切片软件。

## 快速入口

- [技能说明与流程图](skills/print-workflow/README.md)
- [技能指令 SKILL.md](skills/print-workflow/SKILL.md)
- [六步流程逐步注解](skills/print-workflow/references/workflow-notes.md)
- [安装、配置与本机命令](skills/print-workflow/references/local-operations.md)
- [支撑与质量检查清单](skills/print-workflow/scripts/templates/切片审查.md)
- [验证范围与限制](skills/print-workflow/references/validation.md)
- [下载 ZIP](https://github.com/chengzi0223/print-workflow/archive/refs/heads/main.zip)

## 六步主流程

1. **提出需求**：记录用途、环境、参考图和已有零件。
2. **选择软件**：按模型特点选择 Fusion 或 Blender，优先 MCP；尊重用户指定。
3. **确认细节**：确定尺寸、外观、拆件、配合、公差、修改要求以及打印机/喷嘴/材料。
4. **效果图确认**：生成预览、按反馈修改，用户确认后才实际建模。
5. **模型确认**：完成建模和几何检查，展示真实模型；修改至用户确认后才导入切片。
6. **切片与质量审查**：按需求调参，查看真实切片路径，检查支撑覆盖和拆除、首层、桥接、薄壁、稳定性与翘边风险。

补充环节：展示时间、耗材和风险，请用户确认最终切片；保存源文件、工程、检查与完整包；根据实物打印和装配反馈修订。需要改模型时返回模型确认。

## 安装与使用

适用环境：Windows、PowerShell 7、Python 3.11+、Codex。运行建模和切片时，另需本机已安装相应软件及可用 MCP/桌面操作能力。本仓库不包含这些商业软件或 MCP 插件安装包。

1. 下载并解压本仓库，或运行 `git clone https://github.com/chengzi0223/print-workflow.git`。
2. 将 `skills/print-workflow` 整个文件夹复制到 Codex 的技能目录。默认是用户目录下 `.codex/skills`；设置了 `CODEX_HOME` 时使用其 `skills` 子目录。已有同名技能先比较并备份，不直接覆盖。
3. 在复制后的技能文件夹运行以下命令，将 Python 路径换成自己的真实路径：

```powershell
& .\scripts\setup.ps1 -PythonExecutable 'C:\实际路径\python.exe'
```

4. 编辑生成的 `scripts/config.json`，填写模型保存目录和 Bambu/Fusion/Blender 的实际软件路径。
5. 打开新聊天，调用 `$print-workflow`，例如“使用 $print-workflow 帮我设计一个可打印的收纳盒”。先按提示确定需求，流程不会直接跳过确认开始建模。

项目按方案、源文件、打印文件、切片、检查、交付分区；确认记录在 `workflow.json`。变更文件后，旧版本的确认会失效。

## 本地验证

安装后进入技能文件夹：

```powershell
& .\scripts\.runtime\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
& .\scripts\工作流.ps1 doctor
```

测试使用临时合成数据，不访问打印机。`doctor` 报告本机配置与连接状态；端口可达不能代替实际 MCP 响应和具体模型检查。

公开包包含脚本、模板和测试；不包含作者的本机配置、运行环境、个人知识库、实际项目文件或打印机凭据。

## 使用边界

脚本自动化覆盖项目初始化、阶段/哈希检查、STL 基础检查、Bambu 工程切片与打包。需求决策、实际建模、关键层预览、支撑拆除判断和质量取舍仍需 AI 与用户结合实际软件完成。软件检查不保证无翘边、强度达标或装配成功；实物结果单独验证。没有自动上传、加热或启动打印的功能。

## 许可

本仓库原创技能文档与脚本采用 [MIT 许可证](LICENSE)。依赖和外部软件仍适用各自的许可证和使用条款。
