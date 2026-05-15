import os
import re
import sys
import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from tkinterdnd2 import TkinterDnD

# 获取应用实际所在目录（兼容 EXE 和源码模式）
if getattr(sys, 'frozen', False):
    APP_DIR = Path(sys.executable).parent
else:
    APP_DIR = Path(__file__).parent
CONFIG_FILE = APP_DIR / 'config.json'


def smart_convert(text: str) -> str:
    """将纯文本智能转换为 Markdown 格式"""
    lines = text.splitlines()
    n = len(lines)

    # ── 行类型常量 ──
    T_BLANK, T_HEADING, T_CODE, T_LIST, T_TABLE, T_SEP, T_TEXT = range(7)

    # ── 代码/命令关键字（排除这些被误判为标题） ──
    CODE_KEYWORDS = {
        'def', 'class', 'import', 'from', 'return', 'assert', 'if', 'elif',
        'else', 'for', 'while', 'try', 'except', 'finally', 'with', 'as',
        'raise', 'yield', 'lambda', 'pass', 'break', 'continue', 'global',
        'nonlocal', 'del', 'print', 'self', 'cls', 'true', 'false', 'none',
        'int', 'float', 'str', 'bool', 'list', 'dict', 'tuple', 'set',
        'async', 'await', 'match', 'case',
    }
    COMMAND_PREFIXES = ('pip ', 'npm ', 'yarn ', 'pnpm ', 'npx ', 'git ',
                        'docker ', 'kubectl ', 'go ', 'cargo ', 'rustc ',
                        'node ', 'python ', 'pytest ', 'mypy ', 'flake8 ',
                        'black ', 'isort ', 'poetry ', 'conda ', 'brew ',
                        'choco ', 'winget ', 'sudo ', 'apt ', 'yum ',
                        'curl ', 'wget ', 'echo ', 'export ', 'set ',
                        '#!', '//', '<!--')

    def classify(i: int):
        """返回 (类型, 起始行号, 结束行号)"""
        line = lines[i]
        s = line.strip()
        if not s:
            return T_BLANK, i, i

        # 分隔线
        if re.match(r'^[-=*_]{3,}$', s.replace(' ', '').replace('\t', '')):
            return T_SEP, i, i

        # 列表项
        if re.match(r'^[-*+]\s', s) or re.match(r'^\d+[.、)\s]\s', s) or re.match(r'^[•●○◆◇■□▶▷→⇒]\s', s):
            j = i
            while j < n:
                sj = lines[j].strip()
                if not (re.match(r'^[-*+]\s', sj) or re.match(r'^\d+[.、)\s]\s', sj) or re.match(r'^[•●○◆◇■□▶▷→⇒]\s', sj)):
                    break
                j += 1
            return T_LIST, i, j - 1

        # 表格行（| 分隔 或 tab 分隔的多列）
        if s.count('|') >= 2:
            j = i
            while j < n and lines[j].strip().count('|') >= 2:
                j += 1
            return T_TABLE, i, j - 1
        # Tab 分隔的表格（至少 3 列）
        if '\t' in s and len(s.split('\t')) >= 3:
            j = i
            while j < n and '\t' in lines[j].strip() and len(lines[j].strip().split('\t')) >= 3:
                j += 1
            return T_TABLE, i, j - 1
        # 空格/中文空格对齐的表格（至少 3 列，连续多行相同列数）
        cols = re.split(r'\s{2,}|\t', s)
        if len(cols) >= 3:
            j = i + 1
            while j < n:
                sj = lines[j].strip()
                if not sj:
                    break
                cols2 = re.split(r'\s{2,}|\t', sj)
                if len(cols2) < 3:
                    break
                # 检查列数是否相近
                if abs(len(cols2) - len(cols)) > 2:
                    break
                j += 1
            if j - i >= 2:
                return T_TABLE, i, j - 1

        # 代码行
        first_word = s.split()[0].lower() if s.split() else ''
        first_word_stripped = first_word.rstrip(':')  # 去掉冒号后缀（如 else:）
        is_code_keyword = first_word_stripped in CODE_KEYWORDS
        # 命令检测：前缀后紧跟拉丁字符或数字（不是中文），避免误匹配中文句子
        is_command = False
        for p in COMMAND_PREFIXES:
            if s.startswith(p):
                rest = s[len(p):]
                if rest and re.match(r'[a-zA-Z0-9./_\\-]', rest[0]):
                    is_command = True
                    break
        is_decorator = s.startswith('@')
        is_indented = line.startswith('    ') or line.startswith('\t')

        if is_code_keyword or is_command or is_decorator or is_indented:
            j = i
            while j < n:
                sj = lines[j].strip()
                if not sj:
                    j += 1
                    continue
                fw = sj.split()[0].lower() if sj.split() else ''
                fw_s = fw.rstrip(':')
                is_cont = (fw_s in CODE_KEYWORDS or
                           any(sj.startswith(p) for p in COMMAND_PREFIXES) or
                           sj.startswith('@') or
                           sj.startswith((']', ')', '}')) or  # 闭合括号继续代码块
                           lines[j].startswith('    ') or
                           lines[j].startswith('\t'))
                if not is_cont:
                    break
                j += 1
            # 回退到最后一个非空行
            while j > i and not lines[j - 1].strip():
                j -= 1
            if j - i >= 2:
                return T_CODE, i, j - 1
            # 单行命令也作为代码处理（避免被误判为标题）
            if is_command or is_decorator:
                return T_CODE, i, i

        # 标题检测：短行，前后有空行，不是代码
        CODE_CONTENT_WORDS = {'def', 'class', 'import', 'from', 'return', 'assert',
                              'if', 'elif', 'else', 'for', 'while', 'try', 'except',
                              'with', 'raise', 'yield', 'lambda', 'pass', 'break',
                              'continue', '@'}
        if len(s) <= 80 and s[-1] not in '。！？.!?：:':
            prev_empty = (i == 0) or (not lines[i - 1].strip())
            next_empty = (i == n - 1) or (not lines[i + 1].strip())
            if prev_empty and next_empty:
                # 排除包含代码关键字的行（如 "pytest 使用 assert 关键字"）
                words_in_line = set(s.lower().split())
                has_code_words = bool(words_in_line & CODE_CONTENT_WORDS)
                if not has_code_words:
                    return T_HEADING, i, i

        # 普通文本
        return T_TEXT, i, i

    def guess_heading_level(s: str) -> int:
        s = s.strip()
        if re.match(r'^\d+[.、]', s):
            return 3
        if len(s) <= 15:
            return 1
        if len(s) <= 30:
            return 2
        return 3

    def format_urls(s: str) -> str:
        return re.sub(r'(https?://[^\s<>"\'）)]+)', r'[\1](\1)', s)

    # ── 主处理：先分类，再输出 ──
    result = []
    i = 0
    while i < n:
        typ, start, end = classify(i)
        if typ == T_BLANK:
            i += 1
            continue

        # 每段前加一个空行（除非是开头）
        if result:
            result.append('')

        if typ == T_SEP:
            result.append('---')
            i = end + 1
            continue

        if typ == T_HEADING:
            level = guess_heading_level(lines[start])
            result.append(f"{'#' * level} {lines[start].strip()}")
            i = end + 1
            continue

        if typ == T_LIST:
            for idx in range(start, end + 1):
                s = lines[idx].strip()
                match = re.match(r'^(\d+)[.、)\s]\s+(.*)', s)
                if match:
                    result.append(f"{match.group(1)}. {match.group(2)}")
                else:
                    body = re.sub(r'^[-*+•●○◆◇■□▶▷→⇒]\s*', '', s)
                    result.append(f"- {body}")
            i = end + 1
            continue

        if typ == T_TABLE:
            rows = []
            col_count = 0
            for idx in range(start, end + 1):
                s = lines[idx].strip()
                if '|' in s:
                    cells = [c.strip() for c in s.split('|') if c.strip()]
                elif '\t' in s:
                    cells = [c.strip() for c in s.split('\t') if c.strip()]
                else:
                    cells = [c.strip() for c in re.split(r'\s{2,}', s) if c.strip()]
                col_count = max(col_count, len(cells))
                rows.append('| ' + ' | '.join(cells) + ' |')
            if rows:
                result.extend(rows)
                result.append('| ' + ' | '.join(['---'] * col_count) + ' |')
            i = end + 1
            continue

        if typ == T_CODE:
            result.append('```')
            for idx in range(start, end + 1):
                s = lines[idx]
                result.append(s)
            result.append('```')
            i = end + 1
            continue

        if typ == T_TEXT:
            para = []
            j = start
            while j < n:
                t, s2, e2 = classify(j)
                if t != T_TEXT:
                    break
                para.append(format_urls(lines[j].strip()))
                j = e2 + 1
            if para:
                result.append(' '.join(para))
            i = j
            continue

        i += 1

    return '\n'.join(result)


class TxtToMdConverter(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title('TXT → Markdown 批量转换器')
        self.geometry('720x600')
        self.minsize(600, 500)

        self.files = []
        self.output_dir = self._load_config()

        self._build_ui()
        # 加载配置后刷新显示
        if self.output_dir:
            self.lbl_output_dir.config(text=self.output_dir, fg='black')

    def _build_ui(self):
        # 标题
        title_frame = tk.Frame(self)
        title_frame.pack(fill=tk.X, padx=15, pady=(15, 5))
        tk.Label(title_frame, text='TXT → Markdown 转换器',
                 font=('Microsoft YaHei', 16, 'bold')).pack(anchor=tk.W)
        tk.Label(title_frame, text='批量将文本文件转换为 Markdown 格式',
                 font=('Microsoft YaHei', 10),
                 fg='gray').pack(anchor=tk.W)

        # 操作按钮区
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=15, pady=10)

        self.btn_select = tk.Button(
            btn_frame, text='📁 选择文件', command=self._select_files,
            font=('Microsoft YaHei', 10), padx=12, pady=4
        )
        self.btn_select.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_output = tk.Button(
            btn_frame, text='📂 选择输出目录', command=self._select_output_dir,
            font=('Microsoft YaHei', 10), padx=12, pady=4
        )
        self.btn_output.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_clear = tk.Button(
            btn_frame, text='🗑 清空列表', command=self._clear_files,
            font=('Microsoft YaHei', 10), padx=12, pady=4
        )
        self.btn_clear.pack(side=tk.LEFT)

        # 文件列表
        list_frame = tk.Frame(self)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 10))

        tk.Label(list_frame, text='已选文件（支持拖拽 TXT 文件到此处）：',
                 font=('Microsoft YaHei', 10)).pack(anchor=tk.W)

        list_box_frame = tk.Frame(list_frame)
        list_box_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(list_box_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.listbox = tk.Listbox(
            list_box_frame, yscrollcommand=scrollbar.set,
            font=('Microsoft YaHei', 10), selectmode=tk.EXTENDED,
            relief=tk.SUNKEN, borderwidth=1
        )
        self.listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)

        # 注册拖拽
        self.listbox.drop_target_register('*')
        self.listbox.dnd_bind('<<Drop>>', self._on_drop)

        # 绑定右键删除
        self.listbox.bind('<Delete>', self._remove_selected)
        self.listbox.bind('<BackSpace>', self._remove_selected)

        # 右键菜单
        self._context_menu = tk.Menu(self, tearoff=0)
        self._context_menu.add_command(label='移除选中', command=self._remove_selected)
        self._context_menu.add_command(label='清空全部', command=self._clear_files)
        self.listbox.bind('<Button-3>', self._show_context_menu)

        # 输出目录显示
        dir_frame = tk.Frame(self)
        dir_frame.pack(fill=tk.X, padx=15, pady=(0, 5))
        tk.Label(dir_frame, text='输出目录：',
                 font=('Microsoft YaHei', 10)).pack(side=tk.LEFT)
        self.lbl_output_dir = tk.Label(
            dir_frame, text='（未选择）', font=('Microsoft YaHei', 10),
            fg='gray', anchor=tk.W
        )
        self.lbl_output_dir.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 转换按钮 + 进度条
        action_frame = tk.Frame(self)
        action_frame.pack(fill=tk.X, padx=15, pady=(0, 10))

        self.btn_convert = tk.Button(
            action_frame, text='🔄 一键转换', command=self._convert_all,
            font=('Microsoft YaHei', 11, 'bold'), padx=20, pady=6,
            bg='#4A90D9', fg='white', relief=tk.RAISED, borderwidth=0
        )
        self.btn_convert.pack(side=tk.LEFT, padx=(0, 15))

        self.progress = ttk.Progressbar(
            action_frame, mode='determinate', length=200
        )
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 日志区
        log_frame = tk.Frame(self)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

        tk.Label(log_frame, text='转换日志：',
                 font=('Microsoft YaHei', 10)).pack(anchor=tk.W)

        log_box_frame = tk.Frame(log_frame)
        log_box_frame.pack(fill=tk.BOTH, expand=True)

        log_scrollbar = tk.Scrollbar(log_box_frame)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_text = tk.Text(
            log_box_frame, yscrollcommand=log_scrollbar.set,
            font=('Consolas', 10), relief=tk.SUNKEN, borderwidth=1,
            height=8, state=tk.DISABLED
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        log_scrollbar.config(command=self.log_text.yview)

    def _select_files(self):
        paths = filedialog.askopenfilenames(
            title='选择要转换的 TXT 文件',
            filetypes=[('文本文件', '*.txt'), ('所有文件', '*.*')]
        )
        for path in paths:
            if path not in self.files:
                self.files.append(path)
        self._refresh_list()

    def _select_output_dir(self):
        path = filedialog.askdirectory(title='选择输出目录')
        if path:
            self.output_dir = path
            self.lbl_output_dir.config(text=path, fg='black')
            self._save_config(path)


    def _load_config(self) -> str:
        """从配置文件加载输出目录"""
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                path = data.get('output_dir', '')
                if path and os.path.isdir(path):
                    return path
        except Exception:
            pass
        return ''

    def _save_config(self, path: str):
        """保存输出目录到配置文件"""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump({'output_dir': path}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _clear_files(self):
        self.files.clear()
        self._refresh_list()

    def _on_drop(self, event):
        """处理拖拽文件"""
        raw = event.data
        if not raw:
            return
        # tkinterdnd2 返回的路径可能是 {} 包裹或 file:// 格式
        paths = []
        for item in raw.split():
            item = item.strip('{}')
            if item.startswith('file://'):
                item = item[7:]
            # URL 解码
            from urllib.parse import unquote
            item = unquote(item)
            # 处理 Windows 路径前的多余斜杠（/C:/path → C:/path）
            if len(item) >= 3 and item[0] == '/' and item[2] == ':':
                item = item[1:]
            if os.path.isfile(item) and item.lower().endswith('.txt'):
                if item not in self.files:
                    paths.append(item)
        if paths:
            self.files.extend(paths)
            self._refresh_list()

    def _refresh_list(self):
        self.listbox.delete(0, tk.END)
        for i, f in enumerate(self.files, 1):
            name = os.path.basename(f)
            self.listbox.insert(tk.END, f'{i}. {name}')

    def _remove_selected(self, event=None):
        selected = self.listbox.curselection()
        if not selected:
            return
        for idx in reversed(selected):
            del self.files[idx]
        self._refresh_list()

    def _show_context_menu(self, event):
        try:
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(self.listbox.nearest(event.y))
            self._context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._context_menu.grab_release()

    def _log(self, message: str, tag: str = 'info'):
        self.log_text.config(state=tk.NORMAL)
        if tag == 'success':
            self.log_text.insert(tk.END, f'✅ {message}\n')
        elif tag == 'error':
            self.log_text.insert(tk.END, f'❌ {message}\n')
        elif tag == 'warning':
            self.log_text.insert(tk.END, f'⚠️ {message}\n')
        else:
            self.log_text.insert(tk.END, f'  {message}\n')
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.update_idletasks()

    def _convert_all(self):
        if not self.files:
            messagebox.showwarning('提示', '请先选择要转换的 TXT 文件')
            return
        if not self.output_dir:
            messagebox.showwarning('提示', '请先选择输出目录')
            return

        self.btn_convert.config(state=tk.DISABLED)
        self.progress['value'] = 0
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete('1.0', tk.END)
        self.log_text.config(state=tk.DISABLED)

        total = len(self.files)
        success = 0
        fail = 0

        self._log(f'开始转换 {total} 个文件...\n')

        for idx, filepath in enumerate(self.files):
            filename = os.path.basename(filepath)
            name_no_ext = os.path.splitext(filename)[0]
            output_path = os.path.join(self.output_dir, f'{name_no_ext}.md')

            # 处理文件重名
            counter = 1
            while os.path.exists(output_path):
                output_path = os.path.join(self.output_dir, f'{name_no_ext}_{counter}.md')
                counter += 1

            try:
                with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                    text = f.read()

                md_text = smart_convert(text)

                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(md_text)

                self._log(f'{filename} → {os.path.basename(output_path)}', 'success')
                success += 1

            except Exception as e:
                self._log(f'{filename} → 失败: {str(e)}', 'error')
                fail += 1

            # 更新进度
            self.progress['value'] = ((idx + 1) / total) * 100
            self.update_idletasks()

        self._log(f'\n转换完成！成功 {success} 个，失败 {fail} 个', 'success')
        self.progress['value'] = 100
        self.btn_convert.config(state=tk.NORMAL)

        if fail == 0:
            messagebox.showinfo('完成', f'全部 {success} 个文件转换成功！')
        elif success > 0:
            messagebox.showwarning('完成', f'成功 {success} 个，失败 {fail} 个，请查看日志')
        else:
            messagebox.showerror('错误', '所有文件转换失败，请查看日志')


if __name__ == '__main__':
    app = TxtToMdConverter()
    app.mainloop()
