import os
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import uuid
import json
from collections import deque
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import pandas as pd 
from scapy.all import rdpcap
import pandas as pd
from protocols import PROTOCOL_MAP

from data_packet import DataPacket

NODE_LIBRARY = {
    "CSVReader": {
        "properties": [
            {
                "name": "filepath", 
                "type": "file", 
                "label": "File Path",
                "filetypes": [("CSV files", "*.csv")]
            }
        ],
        "ports": {"in": [], "out": ["data"]}
    },
    "PythonScript": {
        "properties": [
            {
                "name": "script", 
                "type": "script", 
                "label": "Script",
                "default": "output = input"
            }
        ],
        "ports": {"in": ["data"], "out": ["result"]}
    },
    "Filter": {
        "properties": [
            {
                "name": "condition", 
                "type": "text", 
                "label": "Filter Condition",
                "default": ""
            }
        ],
        "ports": {"in": ["data"], "out": ["filtered_data"]}
    },
    "Histogram": {
        "properties": [
            {
                "name": "column", 
                "type": "dropdown", 
                "label": "Column",
                "source": "input_columns"
            },
            {
                "name": "bins", 
                "type": "int", 
                "label": "Bins",
                "default": 10,
                "min": 1,
                "max": 1000
            },
            {
                "name": "color", 
                "type": "color", 
                "label": "Color",
                "default": "#4C72B0"
            },
            {
                "name": "title", 
                "type": "text", 
                "label": "Title",
                "default": "Histogram"
            }
        ],
        "ports": {"in": ["data"], "out": ["figure"]}
    },
    "PCAPReader": {
        "properties": [
            {
                "name": "filepath",
                "type": "file",
                "label": "PCAP File Path",
                "filetypes": [("PCAP files", "*.pcap")]
            }
        ],
        "ports": {"in": [], "out": ["network_data"]}
    },
    "TrafficAnalyzer": {
        "properties": [
            {
                "name": "metrics",
                "type": "dropdown",
                "label": "Metrics to Show",
                "options": ["Protocol Distribution", "Top Talkers", "Time Series"],
                "default": "Protocol Distribution"  # Значение по умолчанию
            }
        ],
        "ports": {"in": ["network_data"], "out": ["analysis_result"]}
    },
    "NetworkVisualizer": {
        "properties": [
            {
                "name": "chart_type",
                "type": "dropdown",
                "label": "Chart Type",
                "options": ["Bar", "Line", "Pie"],
                "default": "Bar"
            },
            {
                "name": "column",
                "type": "dropdown",
                "label": "Data Column",
                "source": "input_columns"
            }
        ],
        "ports": {"in": ["analysis_result"], "out": ["figure"]}
    },
    "AnomalyDetector": {
        "properties": [
            {
                "name": "threshold",
                "type": "int",
                "label": "Anomaly Threshold",
                "default": 1000
            }
        ],
        "ports": {"in": ["network_data"], "out": ["alerts"]}
    },
    "Merge": {
        "properties": [
            {
                "name": "merge_type",
                "type": "dropdown",
                "label": "Merge Type",
                "options": ["Concatenate", "Join"],
                "default": "Concatenate"
            },
            {
                "name": "join_key",
                "type": "dropdown",
                "label": "Join Key",
                "source": "input_columns",
                "default": ""
            }
        ],
        "ports": {"in": ["input1", "input2"], "out": ["merged_data"]}
    },
    "XYPlot": {
    "properties": [
        {
            "name": "x_column",
            "type": "dropdown",
            "label": "X Axis Column",
            "source": "input_columns"
        },
        {
            "name": "y_column",
            "type": "dropdown",
            "label": "Y Axis Column",
            "source": "input_columns"
        },
        {
            "name": "title",
            "type": "text",
            "label": "Plot Title",
            "default": "XY Plot"
        },
        {
            "name": "plot_type",
            "type": "dropdown",
            "label": "Plot Type",
            "options": ["Line", "Scatter", "Bar"],
            "default": "Line"
        },
        {
            "name": "color",
            "type": "color",
            "label": "Line/Marker Color",
            "default": "#1f77b4"
        }
    ],
    "ports": {"in": ["data"], "out": ["figure"]}
}
}

def snap(val, grid):
    return round(val / grid) * grid

class Node:
    def __init__(self, canvas, x, y, app, node_type="Default", node_id=None):
        self.canvas = canvas
        self.app = app 
        self.canvas = canvas
        self.id = node_id or str(uuid.uuid4())
        self.type = node_type
        self.name = node_type
        self.input_data = None
        self.output_data = None
        self.base_font_size = 10
        self._is_dragging = False
        self.properties = {}
        self.dragging = False
        self.canvas.bind("<Motion>", self.on_mouse_move)
        for prop in NODE_LIBRARY[self.type]['properties']:
            # Используем значение по умолчанию из NODE_LIBRARY
            default_value = prop.get('default', '')
            self.properties[prop['name']] = default_value
        self.ports = NODE_LIBRARY[self.type]["ports"]
        w, h = 120, 60
        x0, y0 = x - w/2, y - h/2
        if self.app.snap_to_grid:
            x0 = snap(x0, self.app.grid_size)
            y0 = snap(y0, self.app.grid_size)
        x1, y1 = x0 + w, y0 + h
        self.rect = canvas.create_rectangle(
            x0, y0, x1, y1, fill="#F0F8FF", 
            outline="#0a0a0a", width=1, tags=(self.id,))
        self.text = canvas.create_text(
            (x0 + x1)/2, (y0 + y1)/2, text=self.name,
            tags=(self.id,), font=("Arial", self.base_font_size))
        self._draw_ports(x0, y0, x1, y1)
        self._drag_data = {"x": 0, "y": 0}
        for ev in ("<ButtonPress-1>", "<B1-Motion>", "<ButtonRelease-1>", "<Button-3>"):
            handler = ev.strip('<>').lower().replace('-', '_')
            canvas.tag_bind(self.id, ev, getattr(self, handler))

        if node_type == "Filter":
            self.__class__ = FilterNode

        if node_type == "Histogram":
            self.__class__ = HistogramNode
            self.ports = NODE_LIBRARY["Histogram"]["ports"]

        if node_type == "Merge":
            self.__class__ = MergeNode
            self.ports = NODE_LIBRARY["Merge"]["ports"]

        if node_type == "XYPlot":
            self.__class__ = XYPlotNode
            self.ports = NODE_LIBRARY["XYPlot"]["ports"]

        if node_type == "PCAPReader":
            self.__class__ = PCAPReaderNode
        elif node_type == "TrafficAnalyzer":
            self.__class__ = TrafficAnalyzerNode
        elif node_type == "NetworkVisualizer":
            self.__class__ = NetworkVisualizerNode
        elif node_type == "AnomalyDetector":
            self.__class__ = AnomalyDetectorNode

    def _draw_ports(self, x0, y0, x1, y1):
        # Для входных портов
        in_ports = self.ports['in']
        in_count = len(in_ports)
        in_gap = (y1 - y0) / (in_count + 1) if in_count > 0 else 0
        for i in range(in_count):
            y = y0 + in_gap * (i + 1)
            port_tag = f"in_port_{i+1}"
            self.canvas.create_rectangle(
                x0-6, y-5, x0, y+5, 
                fill="#888", 
                tags=(self.id, f"{self.id}&&in_port_{i+1}")  # Уникальный тег
            )
        
        # Для выходных портов
        out_ports = self.ports['out']
        out_count = len(out_ports)
        out_gap = (y1 - y0) / (out_count + 1) if out_count > 0 else 0
        for i in range(out_count):
            y = y0 + out_gap * (i + 1)
            self.canvas.create_rectangle(
                x1, y-5, x1+6, y+5, 
                fill="#888", 
                tags=(self.id, f"out_port_{i+1}")
            )

    def highlight(self, active: bool):
        outline = "#000000" if active else "#000000"
        width = 2 if active else 1
        self.canvas.itemconfig(self.rect, outline=outline, width=width)

    def buttonpress_1(self, event):
        if self.app.connect_mode:
            self.app.handle_connection(self)
            return "break"
            
        self._is_dragging = True  # Устанавливаем флаг сразу
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        self._drag_data = {"x": x, "y": y}  # Сохраняем начальные координаты
        return "break"

    def on_mouse_move(self, event):
        if self.dragging:
            self.canvas.config(cursor="fleur")
        else:
            self.canvas.config(cursor="")

    def b1_motion(self, event):
        if not self._is_dragging:
            return
            
        current_x = self.canvas.canvasx(event.x)
        current_y = self.canvas.canvasy(event.y)
        
        # Вычисляем смещение относительно начальных координат
        dx = current_x - self._drag_data['x']
        dy = current_y - self._drag_data['y']
        
        # Ограничиваем минимальное перемещение
        if abs(dx) < 1 and abs(dy) < 1:
            return
            
        # Применяем смещение к ноде
        self.canvas.move(self.id, dx, dy)
        
        # Обновляем данные для следующего перемещения
        self._drag_data['x'] = current_x
        self._drag_data['y'] = current_y
        
        # Обновляем соединения
        self.app.update_edges(self)
        self.canvas.update_idletasks()  # Принудительное обновление интерфейса

    def buttonrelease_1(self, event):
        self.app.select_node(self)
        self._is_dragging = False
        self.app.update_edges(self)

    def button_3(self, event):
        menu = tk.Menu(self.canvas, tearoff=0)
        menu.add_command(label="Show Data", command=lambda: self.show_node_data())
        menu.add_command(label="Delete", command=lambda: self.app.delete_node(self))
        menu.add_command(label="Rename", command=lambda: self.app.rename_node(self))
        menu.add_separator()
        menu.add_command(label="Export to Notepad", command=lambda: self.export_to_notepad())
        menu.add_command(label="Export to Excel", command=lambda: self.export_to_excel())
        menu.post(event.x_root, event.y_root)

    def update_font_scale(self, scale_factor):
        scaled_size = max(6, int(self.base_font_size * scale_factor))
        self.canvas.itemconfig(self.text, font=("Arial", scaled_size))

    def export_to_csv(self, app='notepad'):
        if not hasattr(self, 'output_data') or not isinstance(self.output_data.data, pd.DataFrame):
            messagebox.showerror("Error", "No CSV data available in this node")
            return
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")]
        )
        if not filepath:
            return
        try:
            self.output_data.data.to_csv(filepath, index=False)
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
        except subprocess.CalledProcessError as e:
            messagebox.showerror("Error", f"Failed to open {app}: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")

    def export_to_notepad(self):
        self.export_to_csv(app='notepad')

    def export_to_excel(self):
        self.export_to_csv(app='excel')

    def execute(self):
        try:
            if self.type == "CSVReader":
                self.output_data = self._execute_csv_reader()
            elif self.type == "PythonScript":
                self.output_data = self._execute_python_script()
            else:
                self.output_data = self.input_data
                
            self.canvas.itemconfig(self.rect, fill="#00FA9A")
            return self.output_data
            
        except Exception as e:
            self.canvas.itemconfig(self.rect, fill="#FF0000")
            raise

    def _execute_csv_reader(self):
        filepath = self.properties.get('filepath', '')
        if not filepath:
            raise ValueError("File path not specified")
        try:
            df = pd.read_csv(filepath)
        
            # Преобразуем timestamp
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
        
            # Преобразуем числовые столбцы
            numeric_cols = ['frequency', 'signal_strength', 'noise_level', 'bit_error_rate']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
        
            return DataPacket(df)
        except Exception as e:
            raise ValueError(f"CSV reading error: {str(e)}")
        
    def _execute_python_script(self):
        script = self.properties.get('script', '')
        if not script:
            return self.input_data
            
        locals_dict = {'input': self.input_data, 'output': None}
        try:
            exec(script, {}, locals_dict)
        except Exception as e:
            raise RuntimeError(f"Script error: {str(e)}")
            
        return DataPacket(locals_dict.get('output'))

        
    def show_node_data(self):
        if not self.output_data:
            messagebox.showinfo("Info", "No data available")
            return
    
        top = tk.Toplevel()
        top.title(f"Data from {self.name}")
    
        if isinstance(self.output_data.data, pd.DataFrame):
            # Отображение DataFrame как таблицы
            tree = ttk.Treeview(top, show="headings")
            tree["columns"] = list(self.output_data.data.columns)
            for col in self.output_data.data.columns:
                tree.heading(col, text=col)
                tree.column(col, width=100)
            for _, row in self.output_data.data.head(50).iterrows():
                tree.insert("", "end", values=list(row))
        
            vsb = ttk.Scrollbar(top, orient="vertical", command=tree.yview)
            hsb = ttk.Scrollbar(top, orient="horizontal", command=tree.xview)
            tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
            tree.grid(row=0, column=0, sticky="nsew")
            vsb.grid(row=0, column=1, sticky="ns")
            hsb.grid(row=1, column=0, sticky="ew")
            top.grid_rowconfigure(0, weight=1)
            top.grid_columnconfigure(0, weight=1)
    
        elif isinstance(self.output_data.data, Figure):
            # Отображение matplotlib Figure
            canvas = FigureCanvasTkAgg(self.output_data.data, master=top)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            top.geometry("800x600")  # Устанавливаем размер окна для графика
    
        else:
            # Отображение других типов данных как текст
            text = tk.Text(top, wrap=tk.WORD)
            text.insert(tk.END, str(self.output_data.data))
            text.pack(fill=tk.BOTH, expand=True)

class FilterNode(Node):
    def execute(self):
        try:
            import pandas as pd
            df = self.input_data.data
            
            condition = self.properties.get('condition', '')
            if not condition:
                return self.input_data
                
            filtered_df = df.query(condition)
            
            return DataPacket(filtered_df)
            
        except Exception as e:
            raise ValueError(f"Filter error: {str(e)}")

class HistogramNode(Node):
    def execute(self):
        try:
            df = self.input_data.data
            if not isinstance(df, pd.DataFrame):
                raise ValueError("Input data must be a DataFrame")
                
            column = self.properties.get('column', '')
            bins = int(self.properties.get('bins', 10))
            color = self.properties.get('color', '#4C72B0')
            title = self.properties.get('title', 'Histogram')
            
            if not column:
                raise ValueError("Column not selected")
            if column not in df.columns:
                raise ValueError(f"Column '{column}' not found")
            if not pd.api.types.is_numeric_dtype(df[column]):
                raise ValueError(f"Column '{column}' must be numeric")

            fig = Figure(figsize=(6, 4))
            ax = fig.add_subplot(111)
            
            ax.hist(
                df[column].dropna(),
                bins=bins,
                edgecolor='white',
                color=color,
                alpha=0.7
            )
            
            ax.set_title(title)
            ax.set_xlabel(column)
            ax.set_ylabel("Frequency")
            ax.grid(linestyle='--', alpha=0.5)
            
            return DataPacket(fig)
            
        except Exception as e:
            raise ValueError(f"Histogram error: {str(e)}")

    def on_input_changed(self):
        if self.input_data and isinstance(self.input_data.data, pd.DataFrame):
            self.available_columns = self.input_data.data.columns.tolist()
        else:
            self.available_columns = []

class PCAPReaderNode(Node):
    def execute(self):
        try:
            filepath = self.properties.get('filepath', '')
            if not filepath:
                raise ValueError("PCAP file path not specified")
            packets = rdpcap(filepath)
            packet_data = []
            for pkt in packets:
                if 'IP' in pkt:
                    # Преобразуем timestamp в числовой формат
                    try:
                        ts = float(pkt.time)
                    except ValueError:
                        ts = 0.0  # Значение по умолчанию для некорректных данных
                    packet_data.append({
                        'timestamp': ts,
                        'src_ip': pkt['IP'].src,
                        'dst_ip': pkt['IP'].dst,
                        'protocol': pkt['IP'].proto,
                        'length': len(pkt)
                    })
            df = pd.DataFrame(packet_data)
            # Преобразуем в datetime с обработкой ошибок
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s', errors='coerce')
            return DataPacket(df)
        except Exception as e:
            raise ValueError(f"PCAP reading error: {str(e)}")

class TrafficAnalyzerNode(Node):
    def get_protocol_name(self, proto_num):
        return PROTOCOL_MAP.get(proto_num, f"Unknown ({proto_num})")
    def execute(self):
        try:
            df = self.input_data.data
            metric = self.properties.get('metrics', 'Protocol Distribution')
            
            if metric == "Protocol Distribution":
                df['protocol_name'] = df['protocol'].apply(self.get_protocol_name)
                result = df['protocol_name'].value_counts().reset_index()
                result.columns = ['Protocol', 'Count']
            
            elif metric == "Top Talkers":
                if 'src_ip' not in df.columns or 'dst_ip' not in df.columns:
                    raise ValueError("IP addresses not found in data")
                
                top_sources = df['src_ip'].value_counts().head(5).reset_index()
                top_sources.columns = ['IP', 'Count (Source)']
                top_dests = df['dst_ip'].value_counts().head(5).reset_index()
                top_dests.columns = ['IP', 'Count (Destination)']
                
                result = pd.merge(
                    top_sources, 
                    top_dests, 
                    on='IP', 
                    how='outer'
                ).fillna(0)
                result['Total'] = result['Count (Source)'] + result['Count (Destination)']
                result = result[['IP', 'Count (Source)', 'Count (Destination)']]
            
            elif metric == "Time Series":
                if 'timestamp' not in df.columns:
                    raise ValueError("Timestamp column not found")
                
                if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
                    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
                
                df = df.dropna(subset=['timestamp']).set_index('timestamp')
                
                # Агрегация данных
                result = df.resample('5S').agg(
                    Total_Packets=('length', 'count'),
                    Total_Length=('length', 'sum')
                ).reset_index()
                
                # Переименовываем колонки
                result.columns = ['timestamp', 'PacketCount', 'TotalLength']  # Используем строчные буквы
            
            else:
                raise ValueError(f"Unknown metric: {metric}")
            
            return DataPacket(result)
        except Exception as e:
            raise ValueError(f"Analysis error: {str(e)}")

class NetworkVisualizerNode(Node):
    def execute(self):
        try:
            data = self.input_data.data
            chart_type = self.properties.get('chart_type', 'Bar')
            column = self.properties.get('column', '')  # Выбранный столбец

            # Приводим имена колонок к нижнему регистру для единообразия
            data.columns = data.columns.str.lower()

            if chart_type == "Pie" and not column:
                raise ValueError("Select column for Pie chart")

            fig = Figure(figsize=(6, 4))
            ax = fig.add_subplot(111)

            if chart_type == "Bar":
                if not column:
                    raise ValueError("Select column for Bar chart")
                if column not in data.columns:
                    raise ValueError(f"Column '{column}' not found in data")
                # Строим bar chart только для выбранного столбца
                data[column].value_counts().plot(kind='bar', ax=ax, color='#4C72B0')
                ax.set_title(f"Bar Chart: {column}")
                ax.set_xlabel(column)
                ax.set_ylabel("Count")
            
            elif chart_type == "Line":
                if 'timestamp' not in data.columns:
                    raise ValueError("'timestamp' column not found in data")
                x_column = 'timestamp'
                y_column = column if column else data.columns.difference(['timestamp']).tolist()[0]
                ax.plot(data[x_column], data[y_column], color='#1f77b4', marker='o')
                ax.set_title(f"Line Chart: {y_column}")
                ax.set_xlabel("Time")
                ax.set_ylabel(y_column)
            
            elif chart_type == "Pie":
                if not column:
                    raise ValueError("Select column for Pie chart")
                if column not in data.columns:
                    raise ValueError(f"Column '{column}' not found in data")
                data[column].value_counts().plot.pie(ax=ax, autopct='%1.1f%%', colors=plt.cm.Paired.colors)
                ax.set_title(f"Pie Chart: {column}")
                ax.set_ylabel("")  # Убираем подпись оси Y
            
            else:
                raise ValueError(f"Unknown chart type: {chart_type}")

            ax.grid(linestyle='--', alpha=0.5)
            return DataPacket(fig)
        
        except Exception as e:
            raise ValueError(f"Visualization error: {str(e)}")

class AnomalyDetectorNode(Node):
    def execute(self):
        try:
            df = self.input_data.data
            threshold = int(self.properties.get('threshold', 1000))
            
            alerts = []
            # Простая логика обнаружения аномалий
            for idx, row in df.iterrows():
                if row['totallength'] > threshold:
                    alerts.append({
                        'timestamp': row['timestamp'],
                        'packetcount': row['packetcount'],
                        'totallength': row['totallength']
                    })
                    
            return DataPacket(pd.DataFrame(alerts))
            
        except Exception as e:
            raise ValueError(f"Anomaly detection error: {str(e)}")

class MergeNode(Node):
    def execute(self):
        try:
            # Получаем список входных DataPacket'ов
            inputs = self.input_data  # Теперь это список
            
            # Извлекаем DataFrame из каждого DataPacket
            dataframes = []
            for dp in inputs:
                if isinstance(dp, DataPacket) and isinstance(dp.data, pd.DataFrame):
                    dataframes.append(dp.data)
            
            if not dataframes:
                raise ValueError("No valid input data")
            
            merge_type = self.properties.get('merge_type', 'Concatenate')
            
            if merge_type == 'Concatenate':
                combined = pd.concat(dataframes, ignore_index=True)
            elif merge_type == 'Join':
                key = self.properties.get('join_key', '')
                if not key or key not in dataframes[0].columns:
                    raise ValueError(f"Invalid join key: {key}")
                combined = dataframes[0]
                for df in dataframes[1:]:
                    combined = combined.merge(df, on=key, how='outer')
            
            return DataPacket(combined)
        except Exception as e:
            raise ValueError(f"Merge error: {str(e)}")

class XYPlotNode(Node):
    def execute(self):
        try:
            df = self.input_data.data
            x_col = self.properties.get('x_column')
            y_col = self.properties.get('y_column')
            title = self.properties.get('title', 'XY Plot')
            plot_type = self.properties.get('plot_type', 'Line')
            color = self.properties.get('color', '#1f77b4')

            # Проверяем, что выбранные колонки существуют
            if x_col not in df.columns or y_col not in df.columns:
                raise ValueError("Selected columns not found in data")

            # Проверяем, что Y-колонка содержит числовые данные
            if not pd.api.types.is_numeric_dtype(df[y_col]):
                raise ValueError("Y column must be numeric")

            # Преобразуем X-колонку, если это временная метка
            if pd.api.types.is_datetime64_any_dtype(df[x_col]):
                df[x_col] = pd.to_datetime(df[x_col])  # Убедимся, что это datetime
                x_values = df[x_col]
            elif pd.api.types.is_numeric_dtype(df[x_col]):
                x_values = df[x_col]
            else:
                raise ValueError("X column must be numeric or datetime")

            # Создаем график
            fig = Figure(figsize=(6, 4))
            ax = fig.add_subplot(111)

            if plot_type == "Line":
                ax.plot(x_values, df[y_col], color=color, marker='o')
            elif plot_type == "Scatter":
                ax.scatter(x_values, df[y_col], color=color)
            elif plot_type == "Bar":
                ax.bar(x_values.astype(str) if not pd.api.types.is_numeric_dtype(x_values) else x_values, 
                       df[y_col], color=color)

            # Настройки графика
            ax.set_title(title)
            ax.set_xlabel(x_col)
            ax.set_ylabel(y_col)
            ax.grid(linestyle='--', alpha=0.5)

            return DataPacket(fig)

        except Exception as e:
            raise ValueError(f"Plotting error: {str(e)}")