# TXT to MD Converter

一键批量将 TXT 文件转换为 Markdown 格式的桌面应用。

## 使用方式

### 便携版（即开即用）
1. 解压 `TXT-to-MD-Converter-Portable.zip`
2. 双击 `TXT-to-MD-Converter.exe`
3. 选择 TXT 文件 → 选择输出目录 → 一键转换

### 安装版（生成安装包）
1. 下载 [Inno Setup](https://jrsoftware.org/isdl.php)（免费，约 3MB）
2. 安装后右键 `installer.iss` → **Compile**
3. 在 `installer/` 目录下得到 `TXT-to-MD-Converter-Setup.exe`
4. 分发此安装包给任意 Windows 电脑

## 功能
- 拖拽 / 选择 TXT 文件
- 智能识别标题、列表、代码块、表格
- 指定输出目录（退出自动保存）
- 进度条 + 实时日志反馈

## 技术栈
- Python + Tkinter（GUI）
- PyInstaller（打包为 EXE）
- tkinterdnd2（拖拽支持）
- Inno Setup（安装包制作）
