import os
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import json
from tkinter import colorchooser
from node import Node, snap, NODE_LIBRARY
from pipeline_runner import PipelineRunner
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from tkhtmlview import HTMLLabel
import plotly.graph_objects as go
from matplotlib.backends.backend_pdf import PdfPages

class PipelinePilotEmulator(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Pipeline Pilot Emulator")
        self.geometry("2560x1440")

        self.configure(background='#B0C4DE')
        style = ttk.Style()
        style.theme_use('clam')  
        style.configure('Main.TFrame', background='#B0C4DE')
        style.configure('White.TFrame', background='white')

        self.MAIN_BG = '#B0C4DE'
        self.BUTTON_BG = '#6A8BA9'
        self.TEXT_COLOR = 'black'
        style.configure('Main.TButton',
                        background='#FFF5EE',
                        foreground=self.TEXT_COLOR,
                        bordercolor='#000000',
                        font=('Arial', 11),
                        padding=5)
        style.map('Main.TButton',
                 background=[('active', '#FFE4C4')],
                 relief=[('pressed', 'sunken'), ('!pressed', 'raised')])
        
        style.configure('Main.Horizontal.TProgressbar',
            background='#4CAF50', 
            troughcolor='#778899', 
            troughrelief='flat',
            thickness=30, 
            borderwidth=0,
            relief='flat'
        )

        button_styles = {
            'Run': ('green', '#98FB98', '#45a049'),
            'Pause': ('grey', '#DCDCDC', '#757575'),
            'Stop': ('red', '#F08080', '#CD5C5C')
        }

        for name, (color, bg, active_bg) in button_styles.items():
            style.configure(f'{color}.TButton',
                            foreground='black',
                            background=bg,
                            bordercolor='#000000',
                            font=('Arial', 12),
                            padding=5)
            style.map(f'{color}.TButton',
                     background=[('active', active_bg), ('!active', bg)],
                     relief=[('pressed', 'sunken'), ('!pressed', 'raised')])
        
        self.add_mode = False
        self.new_node_type = None
        self.connect_mode = False
        self.edge_start = None
        self.nodes = {}
        self.edges = []
        self.selected_node = None
        self.selected_edge = None
        self.snap_to_grid = False
        self.grid_size = 20
        self.grid_visible = False
        self.grid_lines = []
        self.grid_var = tk.BooleanVar(value=self.snap_to_grid)
        self.scale_factor = 1.0
        self.scale_var = tk.StringVar()
        self._update_scale_display()
        self.base_grid_size = 20
        self.visible_grid_size = self.base_grid_size
        self.current_data = None
        
        self._create_widgets()
        self.canvas.bind("<Configure>", self._handle_canvas_resize)
        self.canvas.bind("<B2-Motion>", lambda e: self._update_grid())
        self.runner = PipelineRunner(self)

    def _create_widgets(self):
        toolbar = tk.Frame(self, bg=self.MAIN_BG)
        toolbar.pack(fill=tk.X)
    
        left_toolbar = tk.Frame(toolbar, bg=self.MAIN_BG)
        left_toolbar.pack(side=tk.LEFT, padx=5)
    
        for txt, txt_tooltip, cmd in [
            ("Add Node", "Add node", self.open_type_selector),
            ("Connect", "Connect nodes", self.enable_connect),
            ("Delete", "Delete item", self.delete_selected),
            ("Save", "Save pipeline in folder", self.save_scheme),
            ("Load", "Load pipeline", self.load_scheme),
            ("Cancel", "Cancel action", self.disable_modes)
        ]:
            btn = ttk.Button(left_toolbar, text=txt, command=cmd, style='Main.TButton')
            btn.pack(side=tk.LEFT, padx=3, pady=5)
            self._create_tooltip(btn, txt_tooltip)

        right_toolbar = tk.Frame(toolbar, bg=self.MAIN_BG)
        right_toolbar.pack(side=tk.RIGHT, padx=5)
    
        controls = tk.Frame(right_toolbar, bg=self.MAIN_BG)
        controls.pack(side=tk.LEFT)

        control_buttons = [
            ("▶", "Run", self.run_pipeline, 'green'),
            ("⏸", "Pause", self.pause_pipeline, 'grey'),
            ("⏹", "Stop", self.stop_pipeline, 'red')
        ]

        for icon, txt, cmd, color in control_buttons:
            btn = ttk.Button(
                controls,
                text=icon,
                command=cmd,
                style=f'{color}.TButton'
            )
            btn.pack(side=tk.LEFT, padx=2, pady=5)
            self._create_tooltip(btn, f"{txt} pipeline")

        self.progress = ttk.Progressbar(
            right_toolbar,
            style='Main.Horizontal.TProgressbar',
            length=200
        )
        self.progress.pack(side=tk.LEFT, padx=5, pady=5, fill=tk.Y) 

        content = ttk.Frame(self, style='Main.TFrame')
        content.pack(fill=tk.BOTH, expand=True)

        canvas_frame = tk.Frame(
            content,
            bg='black',  
            bd=1,      
            relief='solid'
        )
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
    
        self.canvas = tk.Canvas(
            canvas_frame,
            bg="white",
            highlightthickness=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=1, pady=1) 
    
        right_sidebar = ttk.Frame(content, style='Main.TFrame')
        right_sidebar.pack(side=tk.RIGHT, fill=tk.BOTH, padx=5, pady=5)
        right_sidebar.pack_propagate(False)
        right_sidebar.configure(width=600)

        self.props_frame = tk.Frame(
            right_sidebar,
            bg='white',
            bd=2,
            relief='solid'
        )
        self.props_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 2), padx=1, ipady=5)
        self.props_frame.pack_propagate(False)

        self.props_header = tk.Label(
            self.props_frame,
            text="Node Properties",
            font=('Arial', 12, 'bold'),
            bg='white'
        )
        self.props_header.pack(pady=5, fill=tk.X)

        self.props_content = tk.Frame(self.props_frame, bg='white')
        self.props_content.pack(fill=tk.BOTH, expand=True)

        separator = ttk.Separator(right_sidebar, orient='horizontal')
        separator.pack(fill=tk.X, pady=3)

        self.preview_frame = tk.Frame(
            right_sidebar,
            bg='white',
            bd=2,
            relief='solid'
        )
        self.preview_frame.pack(fill=tk.BOTH, expand=True, pady=(2, 0), padx=1, ipady=5)
        self.preview_frame.pack_propagate(False)

        self._clear_props() 

        self.preview_header = tk.Label(
            self.preview_frame,
            text="Pipeline Result",
            font=('Arial', 12, 'bold'),
            bg='white',
            anchor='center' 
        )
        self.preview_header.pack(pady=5, fill=tk.X, padx=5)

        self.preview_content = tk.Frame(self.preview_frame, bg='white')
        self.preview_content.pack(fill=tk.BOTH, expand=True)

        self.empty_preview_label = tk.Label(
            self.preview_content,
            text="Run pipeline to view results",
            wraplength=300,
            fg="#666666",
            bg='white',
            justify='center'
        )
        self.empty_preview_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        log_frame = ttk.Frame(self)
        log_frame.pack(side=tk.BOTTOM, fill=tk.X, expand=False)
        self.log = tk.Text(log_frame, height=10, background='#F0F0F0')  # светло-серый фон
        self.log.pack(fill=tk.BOTH, expand=True)

        status = ttk.Frame(self)
        status.pack(side=tk.BOTTOM, fill=tk.X)
        scale_label = ttk.Label(status, textvariable=self.scale_var)
        scale_label.pack(side=tk.LEFT, padx=5, pady=2)
    
        grid_check = ttk.Checkbutton(
            status,
            text="Grid",
            variable=self.grid_var,
            command=self.toggle_grid
        )
        grid_check.pack(side=tk.LEFT, padx=5, pady=2)

        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<ButtonPress-3>", self.start_pan)
        self.canvas.bind("<B3-Motion>", self.do_pan)
        self.canvas.bind("<MouseWheel>", self.do_zoom)
        self.canvas.bind("<ButtonRelease-3>", lambda e: self.canvas.config(cursor=""))

    def _clear_preview(self):
        for widget in self.preview_content.winfo_children():
            widget.destroy()
        if self.current_canvas:
            self.current_canvas.get_tk_widget().destroy()
            self.current_canvas = None

    def _show_text(self, parent, text):
        txt_frame = ttk.Frame(parent)
        txt_frame.pack(fill=tk.BOTH, expand=True)
    
        text_widget = tk.Text(txt_frame, wrap=tk.WORD)
        vsb = ttk.Scrollbar(txt_frame, command=text_widget.yview)
        text_widget.configure(yscrollcommand=vsb.set)
    
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        text_widget.insert(tk.END, text)

    def start_pan(self, event):
        self.canvas.scan_mark(event.x, event.y)
        self.canvas.config(cursor="fleur")

    def do_pan(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)
        self._update_grid()

    def _handle_canvas_resize(self, event):
        self._update_grid()

    def do_zoom(self, event):
        old_scale = self.scale_factor
        self.scale_factor *= 1.1 if event.delta > 0 else 0.9
        self.scale_factor = max (0.5, min(3.0, self.scale_factor))
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        self.canvas.scale('all', x, y, 1/old_scale, 1/old_scale)
        self.canvas.scale('all', x, y, self.scale_factor, self.scale_factor)
        for node in self.nodes.values():
            node.update_font_scale(self.scale_factor)
        self._update_scale_display()
        self._update_grid()

    def _update_scale_display(self):
        self.scale_var.set(f"{int(self.scale_factor * 100)}%")
        self._update_grid()

    def toggle_grid(self):
        self.grid_visible = self.grid_var.get()
        self.snap_to_grid = self.grid_visible
        self._update_grid()
        self.log.insert(tk.END, f"Grid {'on' if self.grid_visible else 'off'}\n")

    def _create_tooltip(self, widget, text):
        from tkinter import Toplevel, Label
        widget.bind("<Enter>", lambda e: self._show_tooltip(widget, text))
        widget.bind("<Leave>", lambda e: self._hide_tooltip())

    def _show_tooltip(self, widget, text):
        x = widget.winfo_rootx() + 20
        y = widget.winfo_rooty() + 20
        self.tooltip = tk.Toplevel(self)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(self.tooltip, text=text, background="#ffffe0", relief="solid", borderwidth=1)
        label.pack()

    def _hide_tooltip(self):
        if hasattr(self, 'tooltip'):
            self.tooltip.destroy()

    def _update_grid(self):
        for line in self.grid_lines:
            self.canvas.delete(line)
        self.grid_lines.clear()
        if self.grid_visible and self.canvas:
            x_start = self.canvas.canvasx(0)
            y_start = self.canvas.canvasy(0)
            x_end = x_start + self.canvas.winfo_width()
            y_end = y_start + self.canvas.winfo_height()
            grid_size = self.visible_grid_size
            first_x = (x_start // grid_size) * grid_size
            first_y = (y_start // grid_size) * grid_size
            x = first_x
            while x <= x_end:
                line = self.canvas.create_line(x, y_start, x, y_end, fill="#e0e0e0", tags=("grid"))
                self.grid_lines.append(line)
                x += grid_size
            y = first_y
            while y <= y_end:
                line = self.canvas.create_line(x_start, y, x_end, y, fill="#e0e0e0", tags=("grid"))
                self.grid_lines.append(line)
                y += grid_size
            self.canvas.tag_lower("grid")

    def save_scheme(self):
        path = filedialog.asksaveasfilename(defaultextension='.json', filetypes=[('JSON files','*.json')])
        if not path: return
        data = {'nodes': [], 'edges': []}
        for n in self.nodes.values():
            x0,y0,x1,y1 = self.canvas.coords(n.rect)
            cx,cy = (x0+x1)/2,(y0+y1)/2
            data['nodes'].append({'id':n.id,'type':n.type,'name':n.name,'properties':n.properties,'x':cx,'y':cy})
        for src,dst,_ in self.edges:
            data['edges'].append({'src':src,'dst':dst})
        try:
            with open(path,'w') as f: json.dump(data,f,indent=2)
        except Exception as e:
            messagebox.showerror("Error",f"Could not save file: {e}")

    def load_scheme(self):
        path = filedialog.askopenfilename(filetypes=[('JSON files','*.json')])
        if not path: return
        try:
            with open(path,'r') as f: data=json.load(f)
        except Exception as e:
            messagebox.showerror("Error",f"Could not load file: {e}"); return
        for n in list(self.nodes.values()): self.delete_node(n)
        for _,_,line in list(self.edges): self.canvas.delete(line)
        self.edges.clear(); self.nodes.clear(); self._clear_props(); self.selected_node=None; self.selected_edge=None
        for nd in data.get('nodes',[]):
            n = Node(self.canvas, nd['x'], nd['y'], self, node_id=nd['id'], node_type=nd['type'])
            n.update_font_scale(self.scale_factor)
            n.name=nd.get('name',n.type)
            self.canvas.itemconfig(n.text,text=n.name)
            n.properties=nd.get('properties',{})
            self.nodes[n.id]=n
        for ed in data.get('edges',[]):
            n1=self.nodes.get(ed['src']); n2=self.nodes.get(ed['dst'])
            if n1 and n2: self.create_edge(n1,n2)

    def open_type_selector(self):
        self.disable_modes()
        dlg=tk.Toplevel(self); dlg.title("Select Node Type"); dlg.resizable(False,False)
        ttk.Label(dlg,text="Choose node type:",font=("Arial",12)).pack(pady=(10,5))
        lb=tk.Listbox(dlg,height=len(NODE_LIBRARY))
        for t in NODE_LIBRARY: lb.insert(tk.END,t)
        lb.pack(fill=tk.BOTH,expand=True,padx=70)
        def onok():
            sel=lb.curselection()
            if sel:
                self.new_node_type=lb.get(sel[0]); self.add_mode=True; dlg.destroy()
        ttk.Button(dlg,text="OK",command=onok).pack(pady=10)
        dlg.grab_set(); dlg.transient(self)

    def on_canvas_click(self,event):
        if self.add_mode and self.new_node_type:
            n = Node(self.canvas, event.x, event.y, self, node_type=self.new_node_type)
            self.nodes[n.id] = n
            self.add_mode = False
            self.new_node_type = None
            return "break"
        items=self.canvas.find_withtag('current')
        if not items:
            self._deselect_all()

    def enable_connect(self): self.disable_modes(); self.connect_mode=True; self.edge_start=None

    def disable_modes(self):
        self.add_mode = False
        self.connect_mode = False
        self.new_node_type = None
        if self.edge_start:
            self.edge_start.highlight(False)
            self.edge_start = None

    def handle_connection(self, node):
        if not self.connect_mode:
            return
        
        if not self.edge_start:
            self.edge_start = node
            node.highlight(True)
        else:
            # Проверка на существующее соединение
            existing = any(
                e for e in self.edges 
                if (e[0] == self.edge_start.id and e[1] == node.id) or 
                   (e[0] == node.id and e[1] == self.edge_start.id)
            )
            if existing:
                messagebox.showerror("Error", "Connection already exists")
                self.edge_start.highlight(False)
                self.edge_start = None
                return
            
            self.create_edge(self.edge_start, node)
            self.connect_mode = False
            self.edge_start.highlight(False)
            self.edge_start = None

    def create_edge(self, n1, n2):
        x1a, y1a, x1b, y1b = self.canvas.coords(n1.rect)
        x2a, y2a, x2b, y2b = self.canvas.coords(n2.rect)
    
        center_x1 = (x1a + x1b) / 2
        center_y1 = (y1a + y1b) / 2

        # Определяем конечную точку для Merge-ноды
        if n2.type == "Merge":
            existing_inputs = len([e for e in self.edges if e[1] == n2.id])
            if existing_inputs >= 2:
                messagebox.showerror("Error", "Merge node can only have two inputs")
                return
            port_number = existing_inputs + 1
            port_tag = f"{n2.id}&&in_port_{port_number}"  # Тег включает ID ноды
            port_id = self.canvas.find_withtag(port_tag)  # Теперь находит порт
            if port_id:
                port_coords = self.canvas.coords(port_id)
                end_x = (port_coords[0] + port_coords[2]) / 2
                end_y = (port_coords[1] + port_coords[3]) / 2
            else:
                # Резервный вариант (если порт не найден)
                end_x = x2a
                end_y = (y2a + y2b) / 2
            line_tags = ("connection", f"merge_port_{port_number}")
        else:
            # Логика для других нод
            center_x2 = (x2a + x2b) / 2
            center_y2 = (y2a + y2b) / 2
            if center_x2 > center_x1:
                end_x = x2a
            else:
                end_x = x2b
            end_y = center_y2
            line_tags = ("connection",)

        # Определяем начальную точку
        if n2.type == "Merge" or (n2.type != "Merge" and center_x2 > center_x1):
            start_x = x1b
        else:
            start_x = x1a

        # Создаём линию
        line_coords = [
            start_x, center_y1,
            (start_x + end_x)/2, center_y1,
            (start_x + end_x)/2, end_y,
            end_x, end_y
        ]

        line = self.canvas.create_line(
            *line_coords,
            arrow=tk.LAST,
            width=2,
            smooth=True,
            splinesteps=5,
            tags=line_tags
        )
    
        self.canvas.tag_bind(line, "<Button-1>", self.on_edge_click)
        self.edges.append((n1.id, n2.id, line))

    def on_edge_click(self,event):
        lid=self.canvas.find_withtag('current')[0]
        self._deselect_all(); self.selected_edge=lid
        self.canvas.itemconfig(lid,fill="red",width=3)

    def delete_selected(self):
        if self.selected_node: self.delete_node(self.selected_node)
        elif self.selected_edge:
            lid=self.selected_edge; self.canvas.delete(lid)
            self.edges=[e for e in self.edges if e[2]!=lid]

    def delete_node(self, node):
        for src, dst, line in self.edges[:]:
            if node.id in (src, dst):
                self.canvas.delete(line)
                self.edges.remove((src, dst, line))
        self.canvas.delete(node.id)
        del self.nodes[node.id]
        self._clear_props()
        self.selected_node = None

    def rename_node(self,node):
        new=simpledialog.askstring("Rename Node","New name:",initialvalue=node.name)
        if new:
            old=node.name
            def do(): node.name=new; self.canvas.itemconfig(node.text,text=new)
            def undo(): node.name=old; self.canvas.itemconfig(node.text,text=old)
            self.history.execute(do,undo)

    def select_node(self, node):
        self._deselect_all()
        node.highlight(True)
        self.selected_node = node
        self._show_props(node)
        self.canvas.update_idletasks()

    def _deselect_all(self):
        if self.selected_node:
            self.selected_node.highlight(False)
            self.selected_node = None
        if self.selected_edge:
            self.canvas.itemconfig(self.selected_edge, fill="black", width=2)
            self.selected_edge = None
        self._clear_props()

    def _clear_props(self):
        for widget in self.props_content.winfo_children():
            widget.destroy()
    
        self.empty_props_label = tk.Label(
            self.props_content, 
            text="Select a node to view properties",
            wraplength=300,
            fg="#666666",
            bg='white',
            justify='center' 
        )
        self.empty_props_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
    
        self.props_content.update_idletasks()

    def _show_props(self, node):
        def create_property_widget(parent, prop_def, current_value):
            frame = tk.Frame(parent, bg='white')
            frame.pack(fill=tk.X, pady=2, anchor='w')

            lbl = tk.Label(
                frame,
                text=prop_def['label'] + ":",
                bg='white',
                font=('Arial', 10),
                width=20,
                anchor='w'
            )
            lbl.pack(side=tk.LEFT, padx=5)

            control_frame = tk.Frame(frame, bg='white')
            control_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

            prop_type = prop_def.get('type', 'text')
        
            if prop_type == 'dropdown':
                values = []
                # Сначала проверяем наличие опций в NODE_LIBRARY
                if 'options' in prop_def:
                    values = prop_def['options']
                # Если опции не заданы, проверяем источник данных
                elif prop_def.get('source') == 'input_columns':
                    # Обрабатываем случай множественного ввода (Merge-нода)
                    if isinstance(node.input_data, list) and node.input_data:
                        # Берем колонки из первого входного DataFrame
                        first_input = node.input_data[0]
                        if isinstance(first_input.data, pd.DataFrame):
                            values = first_input.data.columns.tolist()
                    # Обрабатываем случай одиночного ввода
                    elif node.input_data and isinstance(node.input_data.data, pd.DataFrame):
                        values = node.input_data.data.columns.tolist()
                var = tk.StringVar(value=current_value)
                cb = ttk.Combobox(
                    control_frame,
                    textvariable=var,
                    values=values,
                    state="readonly",
                    width=25
                )
                cb.pack(side=tk.LEFT, fill=tk.X, expand=True)
                var.trace_add('write', lambda *a: node.properties.update({
                    prop_def['name']: var.get()
                }))

            elif prop_type == 'int':
                var = tk.StringVar(value=str(current_value))
                validate = (control_frame.register(lambda s: s.isdigit() or s == ""), '%P')
                entry = ttk.Entry(
                    control_frame,
                    textvariable=var,
                    validate='key',
                    validatecommand=validate,
                    width=28
                )
                entry.pack(side=tk.LEFT)
                var.trace_add('write', lambda *a: node.properties.update({
                    prop_def['name']: int(var.get()) if var.get().isdigit() else prop_def.get('default', 0)
                }))

            elif prop_type == 'color':
                default_color = prop_def.get('default', '#FFFFFF')
                current_value = current_value if current_value else default_color
    
                var = tk.StringVar(value=current_value)
                color_frame = tk.Frame(control_frame, bg='white')
                color_frame.pack(side=tk.LEFT)
    
                btn = ttk.Button(
                    color_frame,
                    text="■",
                    width=3,
                    command=lambda: self._choose_color(var)
                )
                btn.pack(side=tk.LEFT)
    
                preview = tk.Label(
                    color_frame,
                    bg=var.get() or default_color,
                    width=6,
                    relief='sunken',
                    borderwidth=2
                )
                preview.pack(side=tk.LEFT, padx=5)

                def update_color(*args):
                    color = var.get() or default_color
                    preview.config(bg=color)
                    node.properties.update({prop_def['name']: color})
    
                var.trace_add('write', update_color)

            elif prop_type == 'file':
                var = tk.StringVar(value=current_value)
                entry = ttk.Entry(
                    control_frame,
                    textvariable=var,
                    width=20
                )
                entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            
                ttk.Button(
                    control_frame,
                    text="...",
                    width=3,
                    command=lambda: self._choose_file(var, prop_def)
                ).pack(side=tk.LEFT, padx=5)
                var.trace_add('write', lambda *a: node.properties.update({
                    prop_def['name']: var.get()
                }))

            elif prop_type == 'text':
                var = tk.StringVar(value=current_value)
                entry = ttk.Entry(
                    control_frame,
                    textvariable=var,
                    width=28
                )
                entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
                var.trace_add('write', lambda *a: node.properties.update({
                    prop_def['name']: var.get()
                }))

            elif prop_type == 'script':
                txt = tk.Text(control_frame, height=6, width=40)
                txt.insert('1.0', current_value)
                txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                txt.bind('<KeyRelease>', lambda e: node.properties.update({
                    prop_def['name']: txt.get('1.0','end-1c')
                }))

            return frame

        self._clear_props()
        content_frame = tk.Frame(self.props_content, bg='white')
        content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        type_frame = tk.Frame(content_frame, bg='white')
        type_frame.pack(fill=tk.X, pady=2)
        tk.Label(
            type_frame,
            text="Type:",
            bg='white',
            font=('Arial', 10),
            width=20,
            anchor='w'
        ).pack(side=tk.LEFT, padx=5)
        tk.Label(
            type_frame,
            text=node.type,
            bg='white',
            font=('Arial', 10),
            fg="#333333"
        ).pack(side=tk.LEFT)

        name_frame = tk.Frame(content_frame, bg='white')
        name_frame.pack(fill=tk.X, pady=2)
        tk.Label(
            name_frame,
            text="Name:",
            bg='white',
            font=('Arial', 10),
            width=20,
            anchor='w'
        ).pack(side=tk.LEFT, padx=5)
    
        name_var = tk.StringVar(value=node.name)
        name_entry = ttk.Entry(
            name_frame,
            textvariable=name_var,
            width=28,
            font=('Arial', 10)
        )
        name_entry.pack(side=tk.LEFT)
        name_var.trace_add('write', lambda *a: (
            setattr(node, 'name', name_var.get()),
            self.canvas.itemconfig(node.text, text=name_var.get())
        ))

        for prop_def in NODE_LIBRARY[node.type]['properties']:
            current_value = node.properties.get(
                prop_def['name'], 
                prop_def.get('default', '')
            )
            create_property_widget(content_frame, prop_def, current_value)

        if node.type in ['Histogram', 'Plot']:
            btn_frame = tk.Frame(content_frame, bg='white')
            btn_frame.pack(fill=tk.X, pady=10)
            ttk.Button(
                btn_frame,
                text="Preview",
                command=lambda: self._preview_node(node)
            ).pack(side=tk.LEFT, padx=20)

    def _choose_color(self, var):
        color = colorchooser.askcolor()[1]
        if color:
            var.set(color)

    def _choose_file(self, var, prop_def):
        filetypes = [("All files", "*.*")]
        path = filedialog.askopenfilename(filetypes=filetypes)
        if path:
            var.set(path)

    def _preview_node(self, node):
        try:
            result = node.execute()
            self.show_data_preview(result.data)
        except Exception as e:
            messagebox.showerror("Preview Error", str(e))

    def update_edges(self, moved_node):
        for edge in self.edges:
            src_id, dst_id, line = edge
            if src_id == moved_node.id or dst_id == moved_node.id:
                self._update_line(src_id, dst_id, line)

    def _update_line(self, id1, id2, line):
        n1, n2 = self.nodes[id1], self.nodes[id2]
        x1a, y1a, x1b, y1b = self.canvas.coords(n1.rect)
        x2a, y2a, x2b, y2b = self.canvas.coords(n2.rect)
    
        center_x1 = (x1a + x1b) / 2
        center_y1 = (y1a + y1b) / 2

        if n2.type == "Merge":
            # Получаем номер порта из тегов линии
            tags = self.canvas.gettags(line)
            port_tag = next((t for t in tags if t.startswith("merge_port_")), None)
            if port_tag:
                port_number = port_tag.split("_")[-1]
                port_id = self.canvas.find_withtag(f"{n2.id}&&in_port_{port_number}")
                if port_id:
                    port_coords = self.canvas.coords(port_id)
                    end_x = (port_coords[0] + port_coords[2]) / 2
                    end_y = (port_coords[1] + port_coords[3]) / 2
                else:
                    # Резервный вариант
                    end_x = x2a
                    end_y = (y2a + y2b) / 2
            else:
                end_x = x2a
                end_y = (y2a + y2b) / 2
        else:
            center_x2 = (x2a + x2b) / 2
            center_y2 = (y2a + y2b) / 2
            if center_x2 > center_x1:
                end_x = x2a
            else:
                end_x = x2b
            end_y = center_y2

        # Определяем начальную точку
        if n2.type == "Merge" or (n2.type != "Merge" and ( (x2a + x2b)/2 > center_x1 )):
            start_x = x1b
        else:
            start_x = x1a

        new_coords = [
            start_x, center_y1,
            (start_x + end_x)/2, center_y1,
            (start_x + end_x)/2, end_y,
            end_x, end_y
        ]
    
        self.canvas.coords(line, *new_coords)

    def run_pipeline(self):
        self.log.delete(1.0, tk.END)
        self.log.insert(tk.END, "Starting pipeline...\n")
        try:
            self.runner.run()
            self.log.insert(tk.END, "Pipeline completed successfully\n")
        except Exception as e:
            self.log.insert(tk.END, f"Error: {str(e)}\n")
            messagebox.showerror("Execution Error", str(e))

    def pause_pipeline(self): self.log.insert(tk.END,"Paused\n")

    def stop_pipeline(self):
        self.runner.stop()
    
        self.progress["value"] = 0
    
        for node in self.nodes.values():
            node.canvas.itemconfig(node.rect, fill="#AFEEEE") 
    
        self._reset_data_preview()

    def _reset_data_preview(self):
        """Восстанавливает начальное состояние превью"""
        for widget in self.preview_content.winfo_children():
            widget.destroy()
        self.empty_preview_label = tk.Label(
            self.preview_content, 
            text="Run pipeline to view results",
            wraplength=300,
            fg="#666666",
            bg='white',
            justify='center'
        )
        self.empty_preview_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

    def _show_dataframe_preview(self, df):
        self.preview_tree.delete(*self.preview_tree.get_children())
        self.preview_tree["columns"] = list(df.columns)
    
        self.preview_tree.column("#0", width=0, stretch=tk.NO) 
        for col in df.columns:
            self.preview_tree.column(col, anchor=tk.W, width=100, minwidth=50)
            self.preview_tree.heading(col, text=col, anchor=tk.W)
    
        for _, row in df.head(50).iterrows():
            self.preview_tree.insert("", "end", values=list(row))
    
        self.preview_frame.grid_columnconfigure(0, weight=1)
        self.preview_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def show_data_preview(self, data):
        self.current_data = data  # Сохраняем данные для экспорта
        for widget in self.preview_content.winfo_children():
            widget.destroy()
        if isinstance(data, pd.DataFrame):
            self._show_dataframe(self.preview_content, data)
            # Добавляем панель с кнопками экспорта
            export_frame = tk.Frame(self.preview_content, bg='white')
            export_frame.pack(fill=tk.X, pady=5)
            ttk.Button(export_frame, text="Export to Notepad", 
                      command=self.export_result_to_notepad).pack(side=tk.LEFT, padx=5)
            ttk.Button(export_frame, text="Export to Excel", 
                      command=self.export_result_to_excel).pack(side=tk.LEFT, padx=5)
        elif isinstance(data, Figure):
            self._show_matplotlib(self.preview_content, data)
            # Новая панель экспорта для графиков
            export_frame = tk.Frame(self.preview_content, bg='white')
            export_frame.pack(fill=tk.X, pady=5)
            ttk.Button(export_frame, text="Export to PDF", 
                      command=lambda: self.export_figure('pdf')).pack(side=tk.LEFT, padx=5)
            ttk.Button(export_frame, text="Export to PNG", 
                      command=lambda: self.export_figure('png')).pack(side=tk.LEFT, padx=5)
        else:
            self._show_text(self.preview_content, str(data))

    def export_figure(self, format_type):
        if not hasattr(self, 'current_canvas'):
            messagebox.showerror("Error", "No figure available to export")
            return
    
        figure = self.current_canvas.figure
        if not figure:
            messagebox.showerror("Error", "No figure available to export")
            return
    
        filepath = filedialog.asksaveasfilename(
            defaultextension=f".{format_type}",
            filetypes=[(f"{format_type.upper()} files", f"*.{format_type}")]
        )
        if not filepath:
            return
    
        try:
            if format_type == 'pdf':
                with PdfPages(filepath) as pdf:
                    pdf.savefig(figure, bbox_inches='tight')
            elif format_type == 'png':
                figure.savefig(filepath, format='png', bbox_inches='tight', dpi=300)
            messagebox.showinfo("Success", f"Figure successfully exported to {filepath}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def export_result_to_notepad(self):
        self._export_result(app='notepad')

    def export_result_to_excel(self):
        self._export_result(app='excel')

    def _export_result(self, app='notepad'):
        if not isinstance(self.current_data, pd.DataFrame):
            messagebox.showerror("Error", "No CSV data available")
            return
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")]
        )
        if not filepath:
            return
        try:
            self.current_data.to_csv(filepath, index=False)
            if app == 'notepad':
                if os.name == 'nt':
                    subprocess.run(['notepad.exe', filepath], check=True)
                else:
                    subprocess.run(['gedit', filepath], check=True)
            elif app == 'excel':
                if os.name == 'nt':
                    os.startfile(filepath)
                else:
                    subprocess.run(['open', '-a', 'Microsoft Excel', filepath], check=True)
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def _show_dataframe(self, parent, df):
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill=tk.BOTH, expand=True)
    
        tree = ttk.Treeview(tree_frame, show='headings')
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
    
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    
        # Настройка колонок
        tree["columns"] = list(df.columns)
        for col in df.columns:
            tree.heading(col, text=col)
            tree.column(col, width=100, anchor=tk.W, stretch=True)
    
        # Заполнение данными
        for _, row in df.head(50).iterrows():
            tree.insert("", "end", values=tuple(row))
    
        # Размещение элементов
        tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
    
        # Настройка грид-менеджера
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(1, weight=0)
        tree_frame.grid_rowconfigure(1, weight=0)
    
        # Функция проверки необходимости скроллбара
        def check_scrollbar():
            tree.update_idletasks()
            vsb_pos = tree.yview()
            if vsb_pos[1] == 1.0:
                vsb.grid_remove()
            else:
                vsb.grid()
    
        # Привязка к событиям
        tree.bind('<Configure>', lambda e: check_scrollbar())
        check_scrollbar()  # Проверка при создании

    def _show_matplotlib(self, parent, figure):
        canvas = FigureCanvasTkAgg(figure, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.current_canvas = canvas