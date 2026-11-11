"""매장과 운영 화면이 공유하는 색상, 터치 컨트롤과 메뉴 일러스트."""
import tkinter as tk
import customtkinter as ctk

BG = '#F5F6F2'
WHITE = '#FFFFFF'
INK = '#1E302B'
MUTED = '#6C7973'
LINE = '#E1E7E1'
GREEN = '#25634D'
ORANGE = '#B54F2A'


def setup_window(window, title, width=1280, height=820):
    ctk.set_appearance_mode('light')
    window.title(title)
    window.configure(fg_color=BG)
    scale = window._get_window_scaling()
    width = min(width, int((window.winfo_screenwidth() - 60) / scale))
    height = min(height, int((window.winfo_screenheight() - 110) / scale))
    window.geometry(f'{width}x{height}+20+20')
    window.minsize(min(1000, width), min(680, height))
    window.bind('<F11>', lambda event: window.attributes('-fullscreen', not window.attributes('-fullscreen')))
    window.bind('<Escape>', lambda event: window.attributes('-fullscreen', False))


def label(parent, text, size=16, color=INK, bold=False, **kwargs):
    return ctk.CTkLabel(parent, text=text, font=('Malgun Gothic', size, 'bold' if bold else 'normal'), text_color=color, **kwargs)


def button(parent, text, command, color=GREEN, secondary=False, **kwargs):
    options = dict(height=48, corner_radius=12, font=('Malgun Gothic', 16, 'bold'),
                   fg_color=LINE if secondary else color, text_color=INK if secondary else WHITE,
                   hover_color='#D3DDD5' if secondary else '#244C3D')
    options.update(kwargs)
    return ctk.CTkButton(parent, text=text, command=command, **options)


def segments(parent, values, variable, color=GREEN, command=None):
    return ctk.CTkSegmentedButton(parent, values=values, variable=variable, command=command,
        height=46, corner_radius=10, font=('Malgun Gothic', 15, 'bold'),
        fg_color=LINE, unselected_color=WHITE, unselected_hover_color='#EEF2ED',
        selected_color='#D4E5D9' if color == GREEN else '#F1D8C8',
        selected_hover_color='#C6DCCB' if color == GREEN else '#EAC9B2', text_color=INK)


class Dialog(ctk.CTkToplevel):
    def __init__(self, parent, title, height=540):
        super().__init__(parent)
        self.configure(fg_color=WHITE)
        self.title(title)
        self.transient(parent)
        self.resizable(False, False)
        width = 510
        scale = self._get_window_scaling()
        height = min(height, int((parent.winfo_screenheight() - 110) / scale))
        x = max(0, parent.winfo_rootx() + (parent.winfo_width() - int(width * scale)) // 2)
        y = max(0, parent.winfo_rooty() + (parent.winfo_height() - int(height * scale)) // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
        self.after(100, self._activate)
        self.bind('<Escape>', lambda event: self.destroy())

    def _activate(self):
        if self.winfo_exists():
            self.grab_set()
            self.focus_force()


def menu_art(parent, category, name, color, command=None):
    """외부 이미지 없이 확대 가능한 메뉴 종류별 일러스트."""
    canvas = tk.Canvas(parent, width=180, height=110, bg='#F0F3EC', highlightthickness=0, cursor='hand2' if command else '')
    canvas.create_oval(44, 88, 144, 102, fill='#DDE4D9', outline='')
    if category == '김밥류':
        for x, y in ((51, 62), (86, 45), (120, 65)):
            canvas.create_oval(x-22, y-23, x+22, y+23, fill='#213C2F', outline='')
            canvas.create_oval(x-17, y-18, x+17, y+18, fill='#FFFDF3', outline='')
            canvas.create_rectangle(x-8, y-9, x+1, y+9, fill='#EDAD42', outline='')
            canvas.create_rectangle(x+2, y-7, x+10, y+6, fill='#D77A4B', outline='')
            canvas.create_rectangle(x-7, y+3, x+8, y+10, fill='#6F9555', outline='')
    elif category == '식사/분식류':
        canvas.create_arc(36, 28, 150, 113, start=180, extent=180, fill='#E3A27A', outline='')
        canvas.create_oval(36, 34, 150, 64, fill='#AB522E', outline='')
        for i in range(5):
            canvas.create_line(55+i*17, 45, 65+i*15, 55, fill='#F7D6A0', width=6)
        canvas.create_line(102, 35, 148, 12, fill='#6F4B30', width=4)
        canvas.create_line(112, 37, 158, 14, fill='#6F4B30', width=4)
    else:
        drink = '#5C382A' if category == '커피' else '#E5AF64'
        if '라떼' in name:
            drink = '#C39A73'
        if category == '스무디':
            drink = '#D89EAA' if '딸기' in name else '#E9DCC1'
        canvas.create_line(105, 15, 96, 78, fill=color, width=5)
        canvas.create_polygon(57, 31, 126, 31, 117, 92, 67, 92, fill=drink, outline='#D3D8CB', width=2)
        canvas.create_rectangle(61, 50, 122, 74, fill='#FAF4E5', outline='')
        canvas.create_text(92, 62, text='B', fill=color, font=('Georgia', 18, 'bold'))
        canvas.create_oval(57, 26, 126, 37, fill='#E6D7BA', outline='#D3D8CB')
        canvas.create_line(105, 12, 102, 30, fill=color, width=5)
    if command:
        canvas.bind('<Button-1>', lambda event: command())
    return canvas
