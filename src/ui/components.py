"""共享UI组件"""
import tkinter as tk
from tkinter import ttk
from src.ui.theme import COLORS, FONTS, SPACING, RADIUS


class CardFrame(ttk.Frame):
    def __init__(self, parent, title="", **kwargs):
        style_name = f'Card.TFrame'
        style = ttk.Style()
        style.configure(style_name, background=COLORS['bg_card'])
        super().__init__(parent, style=style_name, **kwargs)
        
        if title:
            header = ttk.Label(self, text=title, font=FONTS['subtitle'], foreground=COLORS['text_primary'])
            header.pack(anchor='w', padx=SPACING['lg'], pady=(SPACING['md'], SPACING['sm']))
            ttk.Separator(self, orient='horizontal').pack(fill='x', padx=SPACING['lg'])


class PrimaryButton(ttk.Button):
    def __init__(self, parent, text="", command=None, **kwargs):
        style_name = 'Primary.TButton'
        style = ttk.Style()
        style.configure(style_name, 
                       background=COLORS['primary'],
                       foreground='white',
                       font=FONTS['body'],
                       padding=(SPACING['lg'], SPACING['sm']))
        style.map(style_name,
                 background=[('active', COLORS['primary_hover']), ('pressed', COLORS['primary_hover'])])
        super().__init__(parent, text=text, command=command, style=style_name, **kwargs)


class SecondaryButton(ttk.Button):
    def __init__(self, parent, text="", command=None, **kwargs):
        style_name = 'Secondary.TButton'
        style = ttk.Style()
        style.configure(style_name,
                       background=COLORS['bg_card'],
                       foreground=COLORS['primary'],
                       font=FONTS['body'],
                       padding=(SPACING['md'], SPACING['xs']),
                       borderwidth=1,
                       relief='solid')
        style.map(style_name,
                 background=[('active', COLORS['primary_light'])])
        super().__init__(parent, text=text, command=command, style=style_name, **kwargs)


class FormRow(ttk.Frame):
    def __init__(self, parent, label_text="", widget=None, **kwargs):
        super().__init__(parent, **kwargs)
        if label_text:
            lbl = ttk.Label(self, text=label_text, font=FONTS['body'], foreground=COLORS['text_secondary'])
            lbl.pack(side='left', padx=(0, SPACING['sm']))
        if widget:
            widget.pack(side='left', fill='x', expand=True)


class InfoLabel(ttk.Label):
    def __init__(self, parent, text="", **kwargs):
        super().__init__(parent, text=text, font=FONTS['body_small'], 
                        foreground=COLORS['text_secondary'], **kwargs)


def create_label_entry(parent, label_text, textvariable=None, width=30, **kwargs):
    frame = ttk.Frame(parent)
    lbl = ttk.Label(frame, text=label_text, font=FONTS['body'], foreground=COLORS['text_secondary'])
    lbl.pack(side='left', padx=(0, SPACING['sm']))
    entry = ttk.Entry(frame, textvariable=textvariable, width=width, **kwargs)
    entry.pack(side='left', fill='x', expand=True)
    return frame, entry


def create_labeled_widget(parent, label_text, widget, width_label=80):
    frame = ttk.Frame(parent)
    frame.pack(fill='x', pady=SPACING['xs'])
    lbl = ttk.Label(frame, text=label_text, font=FONTS['body'], 
                   foreground=COLORS['text_secondary'], width=width_label, anchor='w')
    lbl.pack(side='left', padx=(0, SPACING['sm']))
    widget.pack(side='left', fill='x', expand=True)
    return frame
