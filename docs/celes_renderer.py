#!/usr/bin/env python3
"""
celes_viewer.py — Standalone Celes 0.1.5 renderer
Zero dependencies beyond Python stdlib (tkinter included).
Requires Python 3.8+

Usage:
  python celes_viewer.py                  # opens file dialog
  python celes_viewer.py document.celes   # opens directly
"""

import sys
import os
import re
import subprocess
import platform
import threading
import tempfile
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, font as tkfont

# ─────────────────────────────────────────────────────────────────────
# TOKENIZER
# ─────────────────────────────────────────────────────────────────────

def find_brace(s, start):
    depth = 0
    for i in range(start, len(s)):
        if s[i] == '{': depth += 1
        elif s[i] == '}':
            depth -= 1
            if depth == 0: return i
    return -1

def parse_attrs(attr_str):
    attrs = {}
    for m in re.finditer(r'-(\w+)(?:=(\S+?))?(?=\s+-\w|$)', attr_str):
        attrs[m.group(1)] = m.group(2) if m.group(2) is not None else True
    return attrs

def split_line(line):
    line = line.strip()
    if line.startswith(';') or line.startswith('<!'): return [line]
    result, i = [], 0
    while i < len(line):
        if line[i] != '<': break
        te = line.find('>', i)
        if te == -1: result.append(line[i:]); break
        after = te + 1
        if after < len(line) and line[after] == '{':
            close = find_brace(line, after)
            if close != -1: result.append(line[i:close+1]); i = close+1; continue
        result.append(line[i:after]); i = after
    return result if result else [line]

def parse_tag_line(line):
    line = line.strip()
    if not line: return None
    if line.startswith(';'):   return ('comment',     {}, line[1:].strip())
    if line.startswith('<!'): return ('declaration', {}, line)
    if not line.startswith('<'): return ('error', {}, line)
    te = line.find('>')
    if te == -1: return ('error', {}, line)
    hm = re.match(r'^([\w+]+)(.*)', line[1:te], re.DOTALL)
    if not hm: return ('error', {}, line)
    tagname = hm.group(1).lower()
    attrs   = parse_attrs(hm.group(2))
    rest    = line[te+1:].strip()
    if not rest: return (tagname, attrs, None)
    if not rest.startswith('{'): return ('error', {}, f'Missing braces: <{tagname}>')
    close = find_brace(rest, 0)
    if close == -1: return ('error', {}, f'Unclosed brace: <{tagname}>')
    return (tagname, attrs, rest[1:close])

def tokenize(source):
    tokens = []
    lines  = source.split('\n')
    i = 0
    while i < len(lines):
        raw = lines[i]
        depth = sum(1 if c=='{' else -1 if c=='}' else 0 for c in raw)
        while depth > 0 and i + 1 < len(lines):
            i += 1
            raw += '\n' + lines[i]
            depth += sum(1 if c=='{' else -1 if c=='}' else 0 for c in lines[i])
        if raw.strip():
            for single in split_line(raw):
                if single.strip():
                    r = parse_tag_line(single)
                    if r: tokens.append(r)
        i += 1
    return tokens


# ─────────────────────────────────────────────────────────────────────
# THEME
# ─────────────────────────────────────────────────────────────────────

THEME = {
    'bg':           '#FAFAF8',
    'text':         '#1A1A1A',
    'muted':        '#555555',
    'dim':          '#999999',
    'accent':       '#D4622A',
    'code_bg':      '#F0EDE8',
    'code_fg':      '#333333',
    'bq_bar':       '#D4622A',
    'bq_bg':        '#FFF8F5',
    'table_head':   '#F5F0EB',
    'table_border': '#DDDDDD',
    'mark_bg':      '#FFE066',
    'mark_fg':      '#333300',
    'nav_bg':       '#1E1E2E',
    'nav_fg':       '#CDD6F4',
    'nav_btn':      '#313244',
    'error_bg':     '#FFF0F0',
    'error_fg':     '#CC0000',
    'link':         '#1A73E8',
    'media_bg':     '#F0EDE8',
    'media_fg':     '#666655',
    'play_bg':      '#1E1E2E',
    'play_fg':      '#CDD6F4',
}

FONT_FAMILY = 'Georgia'
MONO_FAMILY = 'Courier'
SANS_FAMILY = 'Helvetica'

FONT_SIZES = {
    'h1': 28, 'h2': 22, 'h3': 18, 'h4': 15, 'h5': 13, 'h6': 12,
    'body': 12, 'small': 10, 'code': 11, 'caption': 10,
}

MAX_IMG_WIDTH  = 780
MAX_IMG_HEIGHT = 500


# ─────────────────────────────────────────────────────────────────────
# INLINE SPANS  → list of (text, [tag_names])
# ─────────────────────────────────────────────────────────────────────

def inline_spans(content, base_tags=None, raw=False):
    base_tags = base_tags or []
    if content is None: return []
    if raw: return [(content, list(base_tags))]
    spans, i = [], 0
    while i < len(content):
        ts = content.find('<', i)
        if ts == -1:
            if content[i:]: spans.append((content[i:], list(base_tags)))
            break
        if content[i:ts]: spans.append((content[i:ts], list(base_tags)))
        te = content.find('>', ts)
        if te == -1: spans.append((content[ts:], list(base_tags))); break
        hdr = content[ts+1:te]
        hm  = re.match(r'^([\w+]+)(.*)', hdr, re.DOTALL)
        if not hm: spans.append((content[ts:te+1], list(base_tags))); i = te+1; continue
        name  = hm.group(1).lower()
        attrs = parse_attrs(hm.group(2))
        after = te + 1
        inner, end = '', after
        if after < len(content) and content[after] == '{':
            close = find_brace(content, after)
            if close != -1: inner = content[after+1:close]; end = close+1
        extra = list(base_tags)
        if   name == 'bold':        extra.append('bold')
        elif name == 'italic':      extra.append('italic')
        elif name == 'bold+italic': extra += ['bold','italic']
        elif name == 'underline':   extra.append('underline')
        elif name == 'strike':      extra.append('overstrike')
        elif name == 'super':       extra.append('super')
        elif name == 'sub':         extra.append('sub')
        elif name == 'mark':        extra.append('mark')
        elif name == 'code':        extra.append('code_inline')
        elif name == 'coloredtext':
            extra.append(f'color_{attrs.get("color","")}')
        elif name == 'link':
            url = inner; lbl = attrs.get('body', inner)
            spans.append((lbl, list(base_tags) + ['link', f'HREF:{url}']))
            i = end; continue
        elif name == 'button':
            url = inner; lbl = attrs.get('body', inner)
            spans.append((f' {lbl} ', list(base_tags) + ['button', f'HREF:{url}']))
            i = end; continue
        elif name == 'checkmark':
            ch = '☑' if 'check' in attrs else '☐'
            spans.append((ch + ' ', list(base_tags)))
            spans += inline_spans(inner, list(base_tags)); i = end; continue
        elif name == 'nestquote':
            spans += [('\n    ', list(base_tags))]
            spans += inline_spans(inner, list(base_tags) + ['nestquote'])
            spans += [('\n', list(base_tags))]; i = end; continue
        elif name == 'newline':
            spans.append(('\n', list(base_tags))); i = end; continue
        elif name == 'empty':
            spans.append((inner, list(base_tags))); i = end; continue
        else:
            spans += inline_spans(inner, extra); i = end; continue
        spans += inline_spans(inner, extra)
        i = end
    return spans


# ─────────────────────────────────────────────────────────────────────
# MEDIA HELPERS
# ─────────────────────────────────────────────────────────────────────

def open_with_system(path_or_url):
    """Open a file or URL with the OS default application."""
    system = platform.system()
    try:
        if system == 'Windows':
            os.startfile(path_or_url)
        elif system == 'Darwin':
            subprocess.Popen(['open', path_or_url])
        else:
            subprocess.Popen(['xdg-open', path_or_url])
    except Exception as e:
        messagebox.showerror('Open error', str(e))


def is_url(s):
    return s.startswith('http://') or s.startswith('https://')



# ── Optional Pillow for JPEG / WebP / BMP support ────────────────────
try:
    from PIL import Image as _PilImage, ImageTk as _PilImageTk
    _PILLOW = True
except ImportError:
    _PILLOW = False


def fetch_image_bytes(src, base_dir=None):
    """
    Load raw image bytes from a local path or URL.
    Returns (bytes, suffix, error_str) — error_str is None on success.
    """
    suffix = Path(src).suffix.lower() or '.png'
    if is_url(src):
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0 Safari/537.36'
            ),
            'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
            'Referer': src,
        }
        try:
            req = urllib.request.Request(src, headers=headers)
            with urllib.request.urlopen(req, timeout=12) as resp:
                ct = resp.headers.get('Content-Type', '')
                if   'jpeg' in ct or 'jpg' in ct: suffix = '.jpg'
                elif 'gif'  in ct:                suffix = '.gif'
                elif 'webp' in ct:                suffix = '.webp'
                elif 'bmp'  in ct:                suffix = '.bmp'
                elif 'png'  in ct:                suffix = '.png'
                data = resp.read()
                return data, suffix, None
        except urllib.error.HTTPError as e:
            return None, suffix, f'HTTP {e.code} — server refused the request'
        except urllib.error.URLError as e:
            return None, suffix, f'Network error: {e.reason}'
        except Exception as e:
            return None, suffix, str(e)
    else:
        p = Path(src)
        if not p.is_absolute() and base_dir:
            p = Path(base_dir) / p
        if p.exists():
            try:
                return p.read_bytes(), suffix, None
            except Exception as e:
                return None, suffix, str(e)
        else:
            return None, suffix, f'File not found: {p}'


def make_photo_image(raw_bytes, suffix):
    """
    Convert raw image bytes to a Tk-compatible PhotoImage.
    Strategy (in order):
      1. Pillow (PIL) — handles JPEG, WebP, BMP, TIFF, and everything else
      2. tk.PhotoImage with temp file — native PNG and GIF
    Returns (PhotoImage, width, height) or (None, 0, 0).
    """
    if not raw_bytes:
        return None, 0, 0

    # ── Strategy 1: Pillow ────────────────────────────────────────────
    if _PILLOW:
        try:
            import io
            pil_img = _PilImage.open(io.BytesIO(raw_bytes))
            pil_img = pil_img.convert('RGBA') if pil_img.mode in ('RGBA','LA','P') \
                      else pil_img.convert('RGB')

            # Scale down if necessary
            w, h = pil_img.size
            if w > MAX_IMG_WIDTH or h > MAX_IMG_HEIGHT:
                ratio = min(MAX_IMG_WIDTH / w, MAX_IMG_HEIGHT / h)
                pil_img = pil_img.resize(
                    (int(w * ratio), int(h * ratio)),
                    _PilImage.LANCZOS
                )

            photo = _PilImageTk.PhotoImage(pil_img)
            return photo, photo.width(), photo.height()
        except Exception:
            pass   # fall through to native attempt

    # ── Strategy 2: native Tk (PNG / GIF only) ───────────────────────
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(raw_bytes)
            tmp = f.name

        img = tk.PhotoImage(file=tmp)
        w, h = img.width(), img.height()

        if w > MAX_IMG_WIDTH or h > MAX_IMG_HEIGHT:
            factor = max(w // MAX_IMG_WIDTH, h // MAX_IMG_HEIGHT) + 1
            img = img.subsample(factor, factor)
            w, h = img.width(), img.height()

        return img, w, h
    except Exception:
        return None, 0, 0
    finally:
        if tmp:
            try: os.unlink(tmp)
            except: pass


# ─────────────────────────────────────────────────────────────────────
# MAIN APPLICATION
# ─────────────────────────────────────────────────────────────────────

class CelesViewer(tk.Tk):
    def __init__(self, filepath=None):
        super().__init__()
        self.title('Celes Viewer')
        self.geometry('920x720')
        self.configure(bg=THEME['nav_bg'])
        self.minsize(480, 360)

        self._current_file  = None
        self._base_dir      = None
        self._photo_refs    = []    # keep PhotoImage refs alive (GC protection)
        self._color_tags    = set()
        self._href_map      = {}    # stable_tag → url
        self._href_counter  = 0

        self._build_ui()
        self._setup_text_tags()

        if filepath:
            self._open_file(filepath)
        else:
            self._prompt_open()

    # ── UI ───────────────────────────────────────────────────────────

    def _build_ui(self):
        bar = tk.Frame(self, bg=THEME['nav_bg'], padx=12, pady=7)
        bar.pack(fill='x', side='top')

        tk.Label(bar, text='Celes 0.1.5', bg=THEME['accent'], fg='#ffffff',
                 font=(SANS_FAMILY, 9, 'bold'), padx=6, pady=2).pack(side='left')

        self._title_lbl = tk.Label(bar, text='', bg=THEME['nav_bg'], fg=THEME['nav_fg'],
                                   font=(SANS_FAMILY, 11))
        self._title_lbl.pack(side='left', padx=12)

        self._file_lbl = tk.Label(bar, text='', bg=THEME['nav_bg'], fg='#555577',
                                  font=(MONO_FAMILY, 9))
        self._file_lbl.pack(side='left')

        for lbl, cmd in [('Open', self._prompt_open), ('Reload', self._reload)]:
            tk.Button(bar, text=lbl, bg=THEME['nav_btn'], fg=THEME['nav_fg'],
                      relief='flat', font=(SANS_FAMILY, 9), padx=10, pady=2,
                      activebackground='#45475a', activeforeground='#fff',
                      cursor='hand2', bd=0, command=cmd).pack(side='right', padx=3)

        frame = tk.Frame(self, bg=THEME['bg'])
        frame.pack(fill='both', expand=True)

        vsb = tk.Scrollbar(frame, orient='vertical')
        vsb.pack(side='right', fill='y')

        self._text = tk.Text(
            frame, wrap='word',
            bg=THEME['bg'], fg=THEME['text'],
            font=(FONT_FAMILY, FONT_SIZES['body']),
            relief='flat', bd=0,
            padx=60, pady=40,
            cursor='arrow', state='disabled',
            yscrollcommand=vsb.set,
            spacing1=2, spacing3=2,
            selectbackground='#C8E0FF',
        )
        self._text.pack(fill='both', expand=True)
        vsb.config(command=self._text.yview)

        self.bind('<Control-o>', lambda e: self._prompt_open())
        self.bind('<Control-r>', lambda e: self._reload())
        self.bind('<F5>',        lambda e: self._reload())

    def _setup_text_tags(self):
        t = self._text
        for lvl, key in enumerate(['h1','h2','h3','h4','h5','h6'], 1):
            sz = FONT_SIZES[key]
            t.tag_config(key, font=(FONT_FAMILY, sz, 'bold'),
                         foreground=THEME['text'],
                         spacing1=max(14, sz//2), spacing3=6)

        t.tag_config('bold',        font=(FONT_FAMILY, FONT_SIZES['body'], 'bold'))
        t.tag_config('italic',      font=(FONT_FAMILY, FONT_SIZES['body'], 'italic'))
        t.tag_config('underline',   underline=True)
        t.tag_config('overstrike',  overstrike=True)
        t.tag_config('super',       font=(FONT_FAMILY, FONT_SIZES['small']), offset=5)
        t.tag_config('sub',         font=(FONT_FAMILY, FONT_SIZES['small']), offset=-4)
        t.tag_config('mark',        background=THEME['mark_bg'], foreground=THEME['mark_fg'])
        t.tag_config('code_inline', font=(MONO_FAMILY, FONT_SIZES['code']),
                     background=THEME['code_bg'], foreground=THEME['code_fg'])
        t.tag_config('link',        foreground=THEME['link'], underline=True)
        t.tag_config('button',      foreground='#ffffff', background=THEME['accent'])
        t.tag_config('para',        spacing3=6)
        t.tag_config('blockquote',  lmargin1=30, lmargin2=30,
                     font=(FONT_FAMILY, FONT_SIZES['body'], 'italic'),
                     foreground='#555555', spacing1=4, spacing3=4)
        t.tag_config('nestquote',   lmargin1=55, lmargin2=55,
                     font=(FONT_FAMILY, FONT_SIZES['body'], 'italic'),
                     foreground='#777777')
        t.tag_config('codeblock',   font=(MONO_FAMILY, FONT_SIZES['code']),
                     background=THEME['code_bg'], foreground=THEME['code_fg'],
                     lmargin1=20, lmargin2=20, spacing1=8, spacing3=8)
        for n in range(1, 4):
            ind = 25 * n
            t.tag_config(f'list{n}', lmargin1=ind, lmargin2=ind+18, spacing3=3)
        t.tag_config('section_label', font=(SANS_FAMILY, FONT_SIZES['caption'], 'bold'),
                     foreground=THEME['dim'], justify='center', spacing1=18, spacing3=18)
        t.tag_config('error_tag',  background=THEME['error_bg'], foreground=THEME['error_fg'],
                     font=(MONO_FAMILY, FONT_SIZES['small']))
        t.tag_config('table_head_cell', font=(SANS_FAMILY, FONT_SIZES['body'], 'bold'),
                     background=THEME['table_head'])
        t.tag_config('table_cell',      font=(SANS_FAMILY, FONT_SIZES['body']))
        t.tag_config('dim',   foreground=THEME['dim'],  font=(SANS_FAMILY, FONT_SIZES['small']))
        t.tag_config('muted', foreground=THEME['muted'])

        t.tag_bind('link',   '<Button-1>', self._on_link_click)
        t.tag_bind('button', '<Button-1>', self._on_link_click)
        for tg in ('link', 'button'):
            t.tag_bind(tg, '<Enter>', lambda e: self._text.config(cursor='hand2'))
            t.tag_bind(tg, '<Leave>', lambda e: self._text.config(cursor='arrow'))

    # ── FILE OPS ─────────────────────────────────────────────────────

    def _prompt_open(self, *_):
        path = filedialog.askopenfilename(
            title='Open Celes Document',
            filetypes=[('Celes files', '*.celes'), ('All files', '*.*')])
        if path: self._open_file(path)

    def _open_file(self, path):
        p = Path(path)
        if not p.exists():
            messagebox.showerror('File not found', str(p)); return
        try:
            source = p.read_text(encoding='utf-8')
        except Exception as e:
            messagebox.showerror('Read error', str(e)); return
        self._current_file = p
        self._base_dir     = str(p.parent)
        self.title(f'Celes Viewer — {p.name}')
        self._file_lbl.config(text=str(p))
        self._render(source)

    def _reload(self, *_):
        if self._current_file: self._open_file(self._current_file)

    # ── RENDER ───────────────────────────────────────────────────────

    def _render(self, source):
        t = self._text
        t.config(state='normal')
        t.delete('1.0', 'end')

        # Clean up previous state
        self._href_map.clear()
        self._href_counter = 0
        self._photo_refs.clear()
        for tag in list(self._color_tags):
            try: t.tag_delete(tag)
            except: pass
        self._color_tags.clear()

        tokens    = tokenize(source)
        doc_title = 'Celes Document'
        bg_color  = None
        author    = None
        date_str  = None

        for tok in tokens:
            n = tok[0]
            if n == 'title':      doc_title = tok[2] or ''
            elif n == 'author':   author    = tok[2] or ''
            elif n == 'date':     date_str  = tok[2] or ''
            elif n == 'background' and bg_color is None:
                bg_color = (tok[2] or '').strip()

        try:    t.config(bg=bg_color or THEME['bg'])
        except: t.config(bg=THEME['bg'])

        self._title_lbl.config(text=doc_title)

        # Document header
        if doc_title:
            self._insert_heading(doc_title, 1)
        meta = '  '.join(filter(None, [author, date_str]))
        if meta:
            self._insert(meta + '\n', ['dim'])
        self._insert('\n', [])

        i = 0
        while i < len(tokens):
            name, attrs, content = tokens[i]

            if name in ('comment','declaration','title','author','date','background'):
                i += 1

            elif name == 'header':
                sz = attrs.get('size', '1')
                self._insert_heading(content or '', int(sz) if sz.isdigit() else 1)
                i += 1

            elif name == 'section':
                self._insert_section(content or '')
                i += 1

            elif name == 'line':
                align   = attrs.get('align', 'left')
                justify = {'left':'left','center':'center','right':'right'}.get(align,'left')
                self._insert_inline(content or '', ['para'], justify=justify)
                self._insert('\n\n', [])
                i += 1

            elif name == 'blockquote':
                self._insert_blockquote(content or '')
                i += 1

            elif name == 'codeblock':
                self._insert_codeblock(content or '')
                i += 1

            elif name == 'image':
                src = (content or '').strip()
                self._insert_image(src)
                i += 1

            elif name == 'linkimage':
                src = attrs.get('image', '')
                url = (content or '').strip()
                self._insert_image(src, link_url=url)
                i += 1

            elif name == 'video':
                src   = (content or '').strip()
                self._insert_media_button(src, kind='video', attrs=attrs)
                i += 1

            elif name == 'audio':
                src   = (content or '').strip()
                self._insert_media_button(src, kind='audio', attrs=attrs)
                i += 1

            elif name == 'table':
                cols = [c.strip() for c in (content or '').split(',')]
                rows = []
                i += 1
                while i < len(tokens) and tokens[i][0] == 'item':
                    rows.append([c.strip() for c in (tokens[i][2] or '').split(',')])
                    i += 1
                self._insert_table(cols, rows)

            elif name == 'list':
                i = self._insert_list(tokens, i, depth=1)

            elif name == 'newline':
                self._insert('\n', []); i += 1

            elif name == 'pagebreak':
                self._insert('\n' + '─'*60 + '\n\n', ['dim']); i += 1

            elif name == 'insertspace':
                self._insert('\n', [])
                self._insert('─'*60 + '\n', ['dim'])
                self._insert('\n', [])
                i += 1

            elif name == 'error':
                self._insert(f'⚠ {content}\n', ['error_tag']); i += 1

            else:
                i += 1

        t.config(state='disabled')
        t.yview_moveto(0)

    # ── INSERT PRIMITIVES ────────────────────────────────────────────

    def _insert(self, text, tags):
        self._text.insert('end', text, tags)

    def _resolve_dynamic_tags(self, stags):
        t = self._text
        resolved = []
        for tag in stags:
            if tag.startswith('color_'):
                color = tag[6:]
                if tag not in self._color_tags:
                    try: t.tag_config(tag, foreground=color); self._color_tags.add(tag)
                    except: pass
                resolved.append(tag)
            elif tag.startswith('HREF:'):
                url  = tag[5:]
                htag = f'_href_{self._href_counter}'
                self._href_counter += 1
                self._href_map[htag] = url
                t.tag_config(htag)
                t.tag_bind(htag, '<Button-1>', self._on_link_click)
                t.tag_bind(htag, '<Enter>', lambda e: self._text.config(cursor='hand2'))
                t.tag_bind(htag, '<Leave>', lambda e: self._text.config(cursor='arrow'))
                resolved.append(htag)
            else:
                resolved.append(tag)
        return resolved

    def _insert_inline(self, content, base_tags, justify='left'):
        t    = self._text
        jtag = f'_j_{justify}'
        if jtag not in t.tag_names():
            t.tag_config(jtag, justify=justify)
        for text, stags in inline_spans(content, base_tags):
            resolved = self._resolve_dynamic_tags(stags) + [jtag]
            t.insert('end', text, resolved)

    def _insert_heading(self, content, level):
        level = max(1, min(6, level))
        key   = f'h{level}'
        for text, stags in inline_spans(content, [key]):
            self._text.insert('end', text, stags)
        self._insert('\n\n', [])

    def _insert_section(self, label):
        line = '─' * 28
        self._insert(f'\n{line}  {label.upper()}  {line}\n\n', ['section_label'])

    def _insert_blockquote(self, content):
        self._insert('  ┃  ', ['blockquote'])
        self._insert_inline(content, ['blockquote'])
        self._insert('\n\n', [])

    def _insert_codeblock(self, content):
        padded = '\n'.join('  ' + ln for ln in (content or '').split('\n'))
        self._insert('\n' + padded + '\n\n', ['codeblock'])

    def _insert_table(self, cols, rows):
        t = self._text
        if not cols: return
        widths = [max(len(c), 4) for c in cols]
        for row in rows:
            for ci, cell in enumerate(row):
                if ci < len(widths): widths[ci] = max(widths[ci], len(cell))

        def fmt_row(cells):
            parts = []
            for ci, w in enumerate(widths):
                cell = cells[ci] if ci < len(cells) else ''
                parts.append(' ' + cell.ljust(w) + ' ')
            return '│' + '│'.join(parts) + '│'

        top = '┌' + '┬'.join('─'*(w+2) for w in widths) + '┐'
        mid = '├' + '┼'.join('─'*(w+2) for w in widths) + '┤'
        bot = '└' + '┴'.join('─'*(w+2) for w in widths) + '┘'

        self._insert('  ' + top + '\n', ['dim'])
        self._insert('  ' + fmt_row(cols) + '\n', ['table_head_cell'])
        self._insert('  ' + mid + '\n', ['dim'])
        for row in rows:
            self._insert('  ' + fmt_row(row) + '\n', ['table_cell'])
        self._insert('  ' + bot + '\n\n', ['dim'])

    def _insert_list(self, tokens, i, depth):
        tag_name = {1:'list', 2:'sublist', 3:'subsublist'}.get(depth, 'list')
        ltag     = f'list{min(depth, 3)}'
        bullet   = {1:'•', 2:'◦', 3:'▸'}[min(depth, 3)]
        counter  = 0
        while i < len(tokens) and tokens[i][0] == tag_name:
            _, attrs, content = tokens[i]
            numbered = attrs.get('bullet', 'circle') == 'number'
            indent   = '    ' * (depth - 1)
            if numbered:
                counter += 1; prefix = f'{indent}{counter}. '
            else:
                prefix = f'{indent}{bullet} '
            self._insert(prefix, [ltag, 'dim'])
            self._insert_inline(content or '', [ltag])
            self._insert('\n', [])
            i += 1
            next_tag = {1:'sublist', 2:'subsublist'}.get(depth)
            if next_tag and i < len(tokens) and tokens[i][0] == next_tag:
                i = self._insert_list(tokens, i, depth + 1)
        self._insert('\n', [])
        return i

    # ── IMAGE RENDERING ──────────────────────────────────────────────

    def _insert_image(self, src, link_url=None):
        """Load and embed a real image in the Text widget."""
        t = self._text

        # Loading label while fetching
        load_lbl = tk.Label(t, text=f'  ⏳  Loading image…',
                            bg=THEME['media_bg'], fg=THEME['media_fg'],
                            font=(SANS_FAMILY, FONT_SIZES['small']),
                            padx=12, pady=6, anchor='w')
        t.window_create('end', window=load_lbl, padx=0, pady=4)
        self._insert('\n\n', [])

        def do_load():
            raw, suffix, err = fetch_image_bytes(src, self._base_dir)
            self.after(0, lambda: self._finish_image(load_lbl, raw, suffix, err, src, link_url))

        threading.Thread(target=do_load, daemon=True).start()

    def _finish_image(self, placeholder, raw, suffix, fetch_err, src, link_url):
        """Called on main thread after image fetch completes."""
        t = self._text
        t.config(state='normal')

        img, w, h = make_photo_image(raw, suffix) if raw else (None, 0, 0)

        if img is None:
            # Build a detailed, actionable error widget
            is_jpeg = suffix in ('.jpg', '.jpeg')
            is_blocked = fetch_err and ('HTTP 4' in fetch_err or 'refused' in fetch_err)

            if fetch_err:
                reason = fetch_err
            elif is_jpeg and not _PILLOW:
                reason = 'JPEG format requires Pillow.  Run:  pip install Pillow'
            else:
                reason = 'Could not decode image.'

            err_frame = tk.Frame(t, bg=THEME['error_bg'], padx=10, pady=8)
            tk.Label(err_frame,
                     text=f'⚠  {reason}',
                     bg=THEME['error_bg'], fg=THEME['error_fg'],
                     font=(SANS_FAMILY, FONT_SIZES['small']),
                     wraplength=700, justify='left').pack(anchor='w')
            short = Path(src).name if not is_url(src) else src
            tk.Label(err_frame,
                     text=short,
                     bg=THEME['error_bg'], fg='#AA8888',
                     font=(MONO_FAMILY, FONT_SIZES['caption'])).pack(anchor='w')

            idx = t.index(placeholder)
            placeholder.destroy()
            t.window_create(idx, window=err_frame, padx=0, pady=4)
            t.config(state='disabled')
            return

        # Keep reference so GC doesn't destroy it
        self._photo_refs.append(img)

        # Build image container
        container = tk.Frame(t, bg=THEME['bg'], padx=0, pady=4)

        lbl = tk.Label(container, image=img, bg=THEME['bg'], cursor='arrow')
        lbl.pack(anchor='w')

        # Caption under image
        short = Path(src).name if not is_url(src) else src
        cap = tk.Label(container, text=short,
                       bg=THEME['bg'], fg=THEME['dim'],
                       font=(SANS_FAMILY, FONT_SIZES['caption']))
        cap.pack(anchor='w', pady=(2, 0))

        if link_url:
            lbl.config(cursor='hand2')
            lbl.bind('<Button-1>', lambda e, u=link_url: open_with_system(u))
            cap.config(text=f'{short}  →  {link_url}', cursor='hand2')
            cap.bind('<Button-1>', lambda e, u=link_url: open_with_system(u))

        # Replace placeholder widget with real image
        idx = t.index(placeholder)
        placeholder.destroy()
        t.window_create(idx, window=container, padx=0, pady=4)
        t.config(state='disabled')

    # ── MEDIA BUTTON (VIDEO / AUDIO) ─────────────────────────────────

    def _insert_media_button(self, src, kind, attrs):
        """Embed a styled Play button that opens the media in the OS player."""
        t = self._text

        icon  = '▶' if kind == 'video' else '♪'
        label = Path(src).name if src else src
        flags = []
        if 'loop'     in attrs: flags.append('loop')
        if 'autoplay' in attrs: flags.append('autoplay')
        if 'mute'     in attrs: flags.append('muted')
        flag_str = '  [' + ', '.join(flags) + ']' if flags else ''

        outer = tk.Frame(t, bg=THEME['bg'], pady=4)

        card = tk.Frame(outer, bg=THEME['play_bg'],
                        padx=0, pady=0)
        card.pack(anchor='w', fill='x')

        play_btn = tk.Button(
            card,
            text=f'  {icon}  Play',
            bg=THEME['accent'], fg='#ffffff',
            font=(SANS_FAMILY, 11, 'bold'),
            relief='flat', bd=0, padx=16, pady=10,
            activebackground='#b84e1e', activeforeground='#ffffff',
            cursor='hand2',
            command=lambda s=src: open_with_system(s)
        )
        play_btn.pack(side='left')

        info_frame = tk.Frame(card, bg=THEME['play_bg'], padx=12, pady=8)
        info_frame.pack(side='left', fill='x', expand=True)

        tk.Label(info_frame,
                 text=kind.upper() + flag_str,
                 bg=THEME['play_bg'], fg=THEME['accent'],
                 font=(MONO_FAMILY, FONT_SIZES['caption'], 'bold')).pack(anchor='w')

        tk.Label(info_frame,
                 text=label,
                 bg=THEME['play_bg'], fg=THEME['nav_fg'],
                 font=(MONO_FAMILY, FONT_SIZES['small'])).pack(anchor='w')

        t.window_create('end', window=outer, padx=0, pady=4)
        self._insert('\n\n', [])

    # ── LINK CLICK ───────────────────────────────────────────────────

    def _on_link_click(self, event):
        t     = self._text
        index = t.index(f'@{event.x},{event.y}')
        for tag in t.tag_names(index):
            if tag in self._href_map:
                open_with_system(self._href_map[tag]); return


# ─────────────────────────────────────────────────────────────────────
# RECENT FILES  (stored in ~/.celes_viewer_recent)
# ─────────────────────────────────────────────────────────────────────

RECENT_PATH = Path.home() / '.celes_viewer_recent'
MAX_RECENT  = 10

def load_recent():
    try:
        lines = RECENT_PATH.read_text(encoding='utf-8').splitlines()
        return [l for l in lines if l.strip() and Path(l.strip()).exists()][:MAX_RECENT]
    except Exception:
        return []

def save_recent(filepath):
    filepath = str(Path(filepath).resolve())
    entries  = [filepath] + [e for e in load_recent() if e != filepath]
    try:
        RECENT_PATH.write_text('\n'.join(entries[:MAX_RECENT]), encoding='utf-8')
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────
# WELCOME SCREEN
# ─────────────────────────────────────────────────────────────────────

class WelcomeScreen(tk.Tk):
    """
    Shown on startup when no file is passed.
    Lets the user browse, open a recent file, or drag-and-drop.
    Returns the chosen path via self.chosen_path after mainloop ends.
    """

    def __init__(self):
        super().__init__()
        self.title('Celes Viewer')
        self.resizable(False, False)
        self.configure(bg=THEME['nav_bg'])
        self.chosen_path = None
        self._build()
        self._center()

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw   = self.winfo_screenwidth()
        sh   = self.winfo_screenheight()
        self.geometry(f'{w}x{h}+{(sw-w)//2}+{(sh-h)//2}')

    def _build(self):
        # ── Header bar
        bar = tk.Frame(self, bg=THEME['nav_bg'], padx=20, pady=14)
        bar.pack(fill='x')
        tk.Label(bar, text='Celes 0.1.5', bg=THEME['accent'], fg='#ffffff',
                 font=(SANS_FAMILY, 9, 'bold'), padx=7, pady=3).pack(side='left')
        tk.Label(bar, text='Viewer', bg=THEME['nav_bg'], fg=THEME['nav_fg'],
                 font=(SANS_FAMILY, 13)).pack(side='left', padx=10)

        # ── Body
        body = tk.Frame(self, bg=THEME['bg'], padx=32, pady=24)
        body.pack(fill='both', expand=True)

        # Drop zone
        self._drop_zone = tk.Label(
            body,
            text='Drop a .celes file here\nor',
            bg='#F0EDE8',
            fg=THEME['muted'],
            font=(SANS_FAMILY, 12),
            width=38, height=5,
            relief='flat',
            justify='center',
        )
        self._drop_zone.pack(pady=(0, 12))
        self._drop_zone.bind('<Button-1>', lambda e: self._browse())

        # Try to enable real drag-and-drop (tkinterdnd2 optional)
        self._setup_dnd()

        # Browse button
        browse_btn = tk.Button(
            body,
            text='  Browse for file…',
            bg=THEME['accent'], fg='#ffffff',
            font=(SANS_FAMILY, 11, 'bold'),
            relief='flat', bd=0,
            padx=20, pady=10,
            activebackground='#b84e1e',
            cursor='hand2',
            command=self._browse,
        )
        browse_btn.pack(fill='x', pady=(0, 20))

        # Recent files
        recent = load_recent()
        if recent:
            tk.Label(body, text='RECENT FILES',
                     bg=THEME['bg'], fg=THEME['dim'],
                     font=(MONO_FAMILY, 8, 'bold')).pack(anchor='w', pady=(0, 6))

            frame = tk.Frame(body, bg=THEME['bg'])
            frame.pack(fill='x')

            for path in recent:
                p = Path(path)
                row = tk.Frame(frame, bg=THEME['bg'])
                row.pack(fill='x', pady=1)

                icon = tk.Label(row, text='◈', bg=THEME['bg'], fg=THEME['accent'],
                                font=(SANS_FAMILY, 10))
                icon.pack(side='left', padx=(0, 6))

                name_lbl = tk.Label(
                    row,
                    text=p.name,
                    bg=THEME['bg'], fg=THEME['text'],
                    font=(SANS_FAMILY, 10, 'bold'),
                    cursor='hand2', anchor='w',
                )
                name_lbl.pack(side='left')

                dir_lbl = tk.Label(
                    row,
                    text=str(p.parent),
                    bg=THEME['bg'], fg=THEME['dim'],
                    font=(SANS_FAMILY, 9),
                    cursor='hand2', anchor='w',
                )
                dir_lbl.pack(side='left', padx=(4, 0))

                for widget in (row, icon, name_lbl, dir_lbl):
                    widget.bind('<Button-1>',
                                lambda e, p=path: self._open(p))
                    widget.bind('<Enter>',
                                lambda e, r=row: r.config(bg='#EDE8E0') or
                                [w.config(bg='#EDE8E0') for w in r.winfo_children()])
                    widget.bind('<Leave>',
                                lambda e, r=row: r.config(bg=THEME['bg']) or
                                [w.config(bg=THEME['bg']) for w in r.winfo_children()])
        else:
            tk.Label(body, text='No recent files.',
                     bg=THEME['bg'], fg=THEME['dim'],
                     font=(SANS_FAMILY, 10)).pack(anchor='w')

        # Footer hint
        tk.Label(body,
                 text='Ctrl+O to open  ·  Escape to quit',
                 bg=THEME['bg'], fg=THEME['dim'],
                 font=(MONO_FAMILY, 8)).pack(pady=(18, 0))

        self.bind('<Control-o>', lambda e: self._browse())
        self.bind('<Escape>',    lambda e: self.destroy())

    def _setup_dnd(self):
        """Enable drag-and-drop if tkinterdnd2 is installed, otherwise hint the user."""
        try:
            from tkinterdnd2 import DND_FILES, TkinterDnD
            # If tkinterdnd2 is available, register drop target
            self._drop_zone.drop_target_register(DND_FILES)
            self._drop_zone.dnd_bind('<<Drop>>', self._on_drop)
            self._drop_zone.config(text='Drop a .celes file here\nor click to browse')
        except Exception:
            self._drop_zone.config(text='Click to browse for a .celes file\nor use the button below')

    def _on_drop(self, event):
        path = event.data.strip().strip('{}')
        if path.lower().endswith('.celes'):
            self._open(path)
        else:
            messagebox.showwarning('Wrong file type',
                                   f'Expected a .celes file, got:\n{Path(path).name}')

    def _browse(self):
        path = filedialog.askopenfilename(
            title='Open Celes Document',
            filetypes=[('Celes files', '*.celes'), ('All files', '*.*')],
        )
        if path:
            self._open(path)

    def _open(self, path):
        self.chosen_path = str(path)
        self.destroy()


# ─────────────────────────────────────────────────────────────────────
# PATCH CelesViewer to record recent files on open
# ─────────────────────────────────────────────────────────────────────

_orig_open_file = CelesViewer._open_file

def _patched_open_file(self, path):
    _orig_open_file(self, path)
    if self._current_file:
        save_recent(self._current_file)

CelesViewer._open_file = _patched_open_file


# ─────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        prog='celes_viewer',
        description='Celes 0.1.5 — standalone document viewer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''\
examples:
  python celes_viewer.py                   open welcome screen
  python celes_viewer.py doc.celes         open file directly
  python celes_viewer.py path/to/doc.celes open with full path
        ''',
    )
    parser.add_argument(
        'file', nargs='?', default=None,
        metavar='FILE',
        help='.celes file to open (optional — shows picker if omitted)',
    )
    parser.add_argument(
        '--version', action='version', version='Celes Viewer 0.1.5',
    )
    parser.add_argument(
        '--clear-recent', action='store_true',
        help='clear the recent files list and exit',
    )

    args = parser.parse_args()

    if args.clear_recent:
        try:
            RECENT_PATH.unlink()
            print('Recent files cleared.')
        except FileNotFoundError:
            print('No recent files to clear.')
        return

    filepath = args.file

    if filepath is None:
        # Show welcome screen first
        welcome = WelcomeScreen()
        welcome.mainloop()
        filepath = welcome.chosen_path
        if not filepath:
            return   # user closed the welcome screen without choosing

    app = CelesViewer(filepath)
    app.mainloop()


if __name__ == '__main__':
    main()