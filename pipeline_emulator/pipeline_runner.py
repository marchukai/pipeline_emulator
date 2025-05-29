import threading
import queue
from collections import deque
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

class PipelineRunner:
    def __init__(self, app):
        self.app = app
        self.running = False
        self.execution_queue = queue.Queue()
        self.last_node = None
        self.node_execution_order = []
        self.current_progress = 0
        self._stop_requested = False

    def build_execution_order(self):
        in_degree = {node_id: 0 for node_id in self.app.nodes}
        graph = {node_id: [] for node_id in self.app.nodes}
        
        for src, dst, _ in self.app.edges:
            graph[src].append(dst)
            in_degree[dst] += 1

        queue = deque([node_id for node_id, degree in in_degree.items() if degree == 0])
        execution_order = []
        
        while queue:
            node_id = queue.popleft()
            execution_order.append(node_id)
            
            for neighbor in graph[node_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        self.node_execution_order = [self.app.nodes[node_id] for node_id in execution_order]
        self.app.progress["maximum"] = len(execution_order)

    def execute_node(self, node):
        if self._stop_requested:
            return

        try:
            self.app.after(0, self._update_node_visual, node, "executing")
        
            input_data = []
            for src, dst, _ in self.app.edges:
                if dst == node.id:
                    input_data.append(self.app.nodes[src].output_data)
        
            node.input_data = input_data[0] if len(input_data) == 1 else input_data
            result = node.execute()
        
            node.output_data = result
            self.last_node = node
            self.current_progress += 1
        
            self.app.after(0, self._update_progress)
            self.app.after(0, self._update_node_visual, node, "completed")

        except Exception as e:
            self.app.after(0, self._handle_error, node, e)
            return 

    def run(self):
        if self.running:
            return

        self.running = True
        self._stop_requested = False
        self.last_node = None
        self.current_progress = 0
        self.build_execution_order()
        
        threading.Thread(target=self._run_pipeline, daemon=True).start()

    def _run_pipeline(self):
        try:
            for node in self.node_execution_order:
                if self._stop_requested:
                    break
                
                self.execute_node(node)
                
            self.app.after(0, self._finalize_execution)
            
        finally:
            self.running = False

    def _update_node_visual(self, node, status):
        color = {
            "executing": "#F4A460",  
            "completed": "#90EE90",
            "error": "#F08080"      
        }.get(status, "#00FA9A")
        
        node.canvas.itemconfig(node.rect, fill=color)
        self.app.canvas.update_idletasks()

    def _update_progress(self):
        self.app.progress["value"] = self.current_progress

    def _handle_error(self, node, error):
        self._update_node_visual(node, "error")
        self.app.log.insert(tk.END, f"Error in {node.name}: {str(error)}\n")
        self.stop()

    def _finalize_execution(self):
        if self.last_node and self.last_node.output_data:
            self.app.show_data_preview(self.last_node.output_data.data)
        self.running = False
        self.app.log.insert(tk.END, "Pipeline execution completed\n")

    def stop(self):
        self._stop_requested = True
        self.running = False