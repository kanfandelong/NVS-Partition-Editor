import os
import sys
import csv
import time
import json
import base64
import tempfile
import subprocess
import io
import argparse
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox

# 必须子模块直接导入
import nvs_parser as nvs_parser
import nvs_logger as nvs_logger
import nvs_partition_gen as nvs_gen_mod

class NVS_Editor:
    def __init__(self, master):
        self.master = master
        master.title("NVS Partition Editor by 看番の龙")
        master.geometry("1000x600")
        
        # 设置工具路径（保留但不再用于命令行调用）
        self.nvs_tool = r".\nvs_tool.py"
        self.nvs_gen = r".\nvs_partition_gen.py"
        
        # 初始化数据
        self.partition_size = 0x5000
        self.current_file = None
        self.nvs_data = []
        self.namespace_map = {}  # 存储命名空间映射 {namespace_index: namespace_name}
        
        # 创建菜单栏
        self.menu_bar = tk.Menu(master)
        self.file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.file_menu.add_command(label="打开NVS分区", command=self.open_partition)
        self.file_menu.add_command(label="生成NVS分区", command=self.save_partition)
        self.file_menu.add_separator()
        # 导入导出CSV菜单项
        self.file_menu.add_command(label="导入CSV", command=self.import_from_csv)
        self.file_menu.add_command(label="导出CSV", command=self.export_to_csv)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="退出", command=master.quit)
        self.menu_bar.add_cascade(label="文件", menu=self.file_menu)

        # 添加帮助菜单，包含关于对话框
        self.help_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.help_menu.add_command(label="关于", command=self.show_about)
        self.menu_bar.add_cascade(label="帮助", menu=self.help_menu)

        master.config(menu=self.menu_bar)
        
        # 创建工具栏
        self.toolbar = ttk.Frame(master)
        self.toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        self.add_btn = ttk.Button(self.toolbar, text="添加条目", command=self.add_entry)
        self.add_btn.pack(side=tk.LEFT, padx=2)
        
        self.edit_btn = ttk.Button(self.toolbar, text="编辑条目", command=self.edit_entry)
        self.edit_btn.pack(side=tk.LEFT, padx=2)
        
        self.del_btn = ttk.Button(self.toolbar, text="删除条目", command=self.delete_entry)
        self.del_btn.pack(side=tk.LEFT, padx=2)

        # 排序控件
        ttk.Label(self.toolbar, text="排序依据:").pack(side=tk.LEFT, padx=(10,2))
        self.sort_field_var = tk.StringVar(value="键名")
        self.sort_field = ttk.Combobox(self.toolbar, textvariable=self.sort_field_var, state="readonly", width=12)
        self.sort_field["values"] = ("键名", "命名空间", "类型", "值")
        self.sort_field.pack(side=tk.LEFT, padx=2)
        # 选择变化自动触发排序
        self.sort_field.bind("<<ComboboxSelected>>", lambda e: self.sort_entries())

        self.sort_order_asc = True
        self.sort_order_btn = ttk.Button(self.toolbar, text="升序", width=6, command=lambda: self._toggle_sort_order())
        self.sort_order_btn.pack(side=tk.LEFT, padx=2)

        # 添加搜索框（右侧）
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(self.toolbar, textvariable=self.search_var, width=20)
        self.search_entry.pack(side=tk.LEFT, padx=5)
        # 当搜索内容变化时实时过滤列表
        self.search_entry.bind("<KeyRelease>", lambda e: self._apply_filter_and_sort())

        # self.sort_btn = ttk.Button(self.toolbar, text="排序", command=lambda: self.sort_entries())
        # self.sort_btn.pack(side=tk.LEFT, padx=2)
        
        # 创建主显示区域
        self.tree_frame = ttk.Frame(master)
        self.tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 创建树状视图
        columns = ("Key", "Namespace", "Type", "Value")
        self.tree = ttk.Treeview(self.tree_frame, columns=columns, show="headings")
        self.tree.heading("#0", text="nvs")
        self.tree.heading("Key", text="键名")
        self.tree.heading("Namespace", text="命名空间")
        self.tree.heading("Type", text="类型")
        self.tree.heading("Value", text="值")
        
        self.tree.column("#0", width=150)
        self.tree.column("Key", width=100)
        self.tree.column("Namespace", width=50)
        self.tree.column("Type", width=50)
        self.tree.column("Value", width=400)
        
        # 添加滚动条
        self.scrollbar = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(fill=tk.BOTH, expand=True)
        
        # 状态栏
        self.status = tk.StringVar()
        self.status.set("就绪")
        self.status_bar = ttk.Label(master, textvariable=self.status, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 绑定事件
        self.tree.bind("<Double-1>", self.on_double_click)

        # 直接赋值为已导入模块
        self.nvs_parser = nvs_parser
        self.nvs_logger = nvs_logger
        self.nvs_gen_mod = nvs_gen_mod

    def show_about(self):
        """显示程序的详细信息。"""
        info = (
            "NVS Partition Editor\n"
            "版本: 2026-02-26\n"
            "作者: 看番の龙\n"
            "GitHub: https://github.com/kanfandelong/NVS-Partition-Editor\n"
            "此工具用于编辑 ESP-IDF NVS 分区，支持 CSV 导入/导出以及分区生成。"
        )
        messagebox.showinfo(title="关于 NVS Partition Editor", message=info)

    def open_partition(self):
        file_path = filedialog.askopenfilename(
            title="打开NVS分区文件",
            filetypes=[("Binary Files", "*.bin"), ("All Files", "*.*")]
        )
        if not file_path:
            return
        
        try:
            json_file = None
            # 获取分区大小
            self.partition_size = os.path.getsize(file_path)
            self.status.set(f"解析分区: {file_path}...")
            self.master.update()
            
            # 直接使用已导入的模块
            with open(file_path, 'rb') as f:
                partition = f.read()
            nvs_obj = self.nvs_parser.NVS_Partition(os.path.basename(file_path), bytearray(partition))
            buf = io.StringIO()
            old_stdout = sys.stdout
            try:
                sys.stdout = buf
                self.nvs_logger.print_json(nvs_obj)
            finally:
                sys.stdout = old_stdout
            json_text = buf.getvalue()
            try:
                data = json.loads(json_text)
            except json.JSONDecodeError as e:
                raise ValueError(f"JSON解析错误: {e}\n原始内容片段:\n{json_text[:500]}...")
        except Exception:
            messagebox.showerror("错误", "解析分区文件失败，请检查文件格式和内容")
            self.status.set("错误")
            return

        # 处理并显示数据
        self.nvs_data = []
        self.namespace_map = {}  # 重置命名空间映射
        self.tree.delete(*self.tree.get_children())
        
        # 首先处理命名空间条目
        if "pages" in data:
            for page in data["pages"]:
                if "entries" in page:
                    for entry in page["entries"]:
                        if entry.get("state") == "Written" and entry.get("key") and entry.get("metadata", {}).get("namespace") == 0:
                            # 这是命名空间定义条目
                            namespace_name = entry["key"]
                            namespace_index = entry["data"]["value"]
                            self.namespace_map[namespace_index] = namespace_name
        
        # 然后处理所有条目
        if "pages" in data:
            for page in data["pages"]:
                if "entries" in page:
                    for entry in page["entries"]:
                        if entry.get("state") == "Written" and entry.get("key") and entry.get("metadata", {}).get("namespace") != 0:
                            # 这是普通数据条目
                            self._process_entry(entry)
        
        # 在加载完所有条目后自动按当前设置排序并刷新视图
        try:
            self.sort_entries()
        except Exception:
            pass

        self.current_file = file_path
        self.status.set(f"共加载: {file_path} | 条目数: {len(self.nvs_data)}")
        # 仅当临时 json_file 存在时删除
        try:
            if json_file and os.path.exists(json_file):
                os.unlink(json_file)
        except Exception:
            pass
    
    def import_from_csv(self):
        """从CSV文件导入数据，遵循官方命名空间分组规则"""
        self.current_file = None
        file_path = filedialog.askopenfilename(
            title="选择CSV文件",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if not file_path:
            return

        try:
            # 清空现有数据
            self.nvs_data = []
            self.namespace_map = {}
            self.tree.delete(*self.tree.get_children())

            current_namespace = "default"
            current_namespace_index = 1
            namespace_counter = 1

            with open(file_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                # reader.fieldnames 可能为 None，需先检查
                if not reader.fieldnames or not {'key', 'type', 'encoding', 'value'}.issubset(reader.fieldnames):
                    raise ValueError("CSV文件必须包含key,type,encoding,value列")

                for row in reader:
                    if row['type'].strip().lower() == 'namespace':
                        # 处理命名空间定义
                        current_namespace = row['key']
                        if current_namespace not in self.namespace_map.values():
                            current_namespace_index = namespace_counter
                            self.namespace_map[current_namespace_index] = current_namespace
                            namespace_counter += 1
                        else:
                            # 找到已有命名空间的索引
                            for idx, name in self.namespace_map.items():
                                if name == current_namespace:
                                    current_namespace_index = idx
                                    break
                        continue

                    # 处理数据条目
                    entry = {
                        "key": row['key'],
                        "namespace": current_namespace,
                        "namespace_index": current_namespace_index,
                        "type": row['encoding'],
                        "value": row['value'],
                        "raw": {}
                    }
                    self.nvs_data.append(entry)

                    # 添加到树状视图
                    display_value = row['value']
                    if len(display_value) > 100:
                        display_value = display_value[:100] + "..."
                        self.tree.insert("", "end", text=entry["key"],
                                    values=(entry["key"], current_namespace, row['encoding'], display_value),
                                    tags=(str(current_namespace_index),))

            self.status.set(f"已从CSV导入: {file_path} | 条目数: {len(self.nvs_data)}")
            # 导入完成后自动排序
            try:
                self.sort_entries()
            except Exception:
                pass
            messagebox.showinfo("成功", "CSV文件导入成功")
        except Exception as e:
            messagebox.showerror("错误", f"导入CSV失败:\n{str(e)}")
            # 避免将长错误信息显示在状态栏
            self.status.set("错误")

    def export_to_csv(self):
        """导出数据到CSV文件，遵循官方命名空间分组规则"""
        TYPE_MAPPING = {
            # 标准类型
            'u8': 'u8',
            'i8': 'i8',
            'uint8_t': 'u8',
            'int8_t': 'i8',
            'u16': 'u16',
            'i16': 'i16',
            'uint16_t': 'u16',
            'int16_t': 'i16',
            'u32': 'u32',
            'i32': 'i32',
            'uint32_t': 'u32',
            'int32_t': 'i32',
            'u64': 'u64',
            'i64': 'i64',
            'uint64_t': 'u64',
            'int64_t': 'i64',
            'string': 'string',
            'blob': 'hex2bin',
            'hex2bin': 'hex2bin',
            'blob_data': 'hex2bin',
            'binary': 'binary',
            'base64': 'base64'
        }
        if not self.nvs_data:
            messagebox.showwarning("导出", "没有数据可导出")
            return

        file_path = filedialog.asksaveasfilename(
            title="保存CSV文件",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            defaultextension=".csv"
        )
        if not file_path:
            return

        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['key', 'type', 'encoding', 'value'])

                # 按命名空间分组数据
                namespace_entries = {}
                for entry in self.nvs_data:
                    ns = entry["namespace"]
                    if ns not in namespace_entries:
                        namespace_entries[ns] = []
                    namespace_entries[ns].append(entry)

                # 写入数据，确保命名空间条目在前
                for ns, entries in namespace_entries.items():
                    # 写入命名空间定义(跳过默认命名空间)
                    if ns != "default":
                        writer.writerow([ns, 'namespace', '', ''])
                    
                    # 写入该命名空间下的所有条目
                    for entry in entries:
                        writer.writerow([
                            entry['key'],
                            'data',
                            TYPE_MAPPING.get(entry['type'], ""),
                            entry['value']
                        ])

            self.status.set(f"已导出到CSV: {file_path}")
            messagebox.showinfo("成功", "CSV文件导出成功")
        except Exception as e:
            messagebox.showerror("错误", f"导出CSV失败:\n{str(e)}")
            # 避免将长错误信息显示在状态栏
            self.status.set("错误")
    def _process_entry(self, entry):
        """处理单个NVS条目并添加到树状视图"""
        if not isinstance(entry, dict):
            return
            
        key = entry.get("key", "")
        if not key:
            return
            
        namespace_index = entry.get("metadata", {}).get("namespace", 0)
        namespace = self.namespace_map.get(namespace_index, f"ns_{namespace_index}")
        
        entry_type = entry.get("metadata", {}).get("type", "unknown")
        value = entry.get("data", {}).get("value", "")

        display_value = str(value)

        if entry_type == "blob_index":
            print("跳过blob_index")
            print(f"key:{key} namespace:{namespace} value:{value}")
            self.status.set(f"跳过blob_index {key}...")
            self.master.update()
            return
        # if entry_type == "blob_data":
        #     self.status.set(f"跳过blob_data {key}...")
        #     return
        
        # 特殊处理 blob_data 和 string 类型
        if entry_type in ["blob_data", "string"] and "children" in entry:
            # 处理子条目中的实际数据
            try:
                # 收集所有子条目的原始数据
                raw_data = b''
                for child in entry.get("children", []):
                    # 解码 base64 格式的原始数据
                    child_raw = child.get("raw", "")
                    if child_raw:
                        # 移除填充字符并解码
                        child_raw = child_raw.rstrip('=')
                        raw_data += base64.b64decode(child_raw + '=' * (4 - len(child_raw) % 4))
                        # print(raw_data)
                
                # 根据类型处理数据
                if entry_type == "string":
                    # 字符串类型：转换为UTF-8字符串
                    display_value = raw_data.decode('utf-8', errors='ignore').rstrip('\x00')
                    value = display_value
                else:  # blob_data
                    try:
                        display_value = raw_data.decode('utf-8', errors='strict')
                        value = raw_data
                    except UnicodeDecodeError:
                        # 如果失败，转为十六进制表示
                        
                        hex_str = raw_data.hex()
                        # 尝试提取可能的UTF-8部分
                        value = f"{hex_str}"
                        try:
                            # 从十六进制中提取非FFFF部分
                            clean_hex = hex_str.split('ffffffff')[0]  # 去除填充
                            display_value = bytes.fromhex(clean_hex).decode('utf-8')
                        except:
                            display_value = f"{hex_str}"
                    
            except Exception as e:
                print(f"处理子条目数据失败: {str(e)}")
                value = "<二进制数据解码失败>"
                
        elif isinstance(value, (int, float)):
            value = str(value)
        
        # 存储条目数据
        item_data = {
            "key": key,
            "namespace": namespace,
            "namespace_index": namespace_index,
            "type": entry_type,
            "value": value,
            "raw": entry
        }
        self.nvs_data.append(item_data)
        
        # 截断长值用于显示
        if len(display_value) > 100:
            display_value = display_value[:100] + "..."
        self.status.set(f"加载 {key}...")
        self.master.update()
        # time.sleep(0.01)
        # 添加到树状视图
        self.tree.insert("", "end", text=key, 
                            values=(key, namespace, entry_type, display_value),
                            tags=(str(namespace_index),))

    def save_partition(self):

        if not self.nvs_data:
            messagebox.showwarning("保存", "没有数据可保存")
            return
            
        # 如果没有打开文件，要求用户输入分区大小
        if not self.current_file:
            # 创建一个简单的对话框获取分区大小
            size_dialog = tk.Toplevel(self.master)
            size_dialog.title("输入分区大小")
            size_dialog.geometry("300x150")
            
            ttk.Label(size_dialog, text="NVS分区大小 (十六进制):").pack(pady=10)
            
            size_entry = ttk.Entry(size_dialog)
            size_entry.pack(pady=5)
            size_entry.insert(0, "0x5000")  # 默认值
            
            def on_ok():
                try:
                    size_str = size_entry.get().strip()
                    if size_str.startswith("0x"):
                        self.partition_size = int(size_str, 16)
                    else:
                        self.partition_size = int(size_str)
                    size_dialog.destroy()
                    self._do_save()  # 继续保存流程
                except ValueError:
                    messagebox.showerror("错误", "请输入有效的十六进制或十进制数字")
            
            ttk.Button(size_dialog, text="确定", command=on_ok).pack(pady=10)
            
            # 将对话框居中到主窗口
            try:
                size_dialog.update_idletasks()
                parent_x = self.master.winfo_rootx()
                parent_y = self.master.winfo_rooty()
                parent_w = self.master.winfo_width()
                parent_h = self.master.winfo_height()
                win_w = 300
                win_h = 150
                x = parent_x + (parent_w - win_w) // 2
                y = parent_y + (parent_h - win_h) // 2
                size_dialog.geometry(f"{win_w}x{win_h}+{x}+{y}")
            except Exception:
                pass

            # 使对话框模态
            size_dialog.transient(self.master)
            size_dialog.grab_set()
            size_dialog.wait_window()
        else:
            self._do_save()

    def _do_save(self):
        """实际的保存逻辑"""
                # 类型映射表
        TYPE_MAPPING = {
            # 标准类型
            'u8': 'u8',
            'i8': 'i8',
            'uint8_t': 'u8',
            'int8_t': 'i8',
            'u16': 'u16',
            'i16': 'i16',
            'uint16_t': 'u16',
            'int16_t': 'i16',
            'u32': 'u32',
            'i32': 'i32',
            'uint32_t': 'u32',
            'int32_t': 'i32',
            'u64': 'u64',
            'i64': 'i64',
            'uint64_t': 'u64',
            'int64_t': 'i64',
            'string': 'string',
            'blob': 'hex2bin',
            'hex2bin': 'hex2bin',
            'blob_data': 'hex2bin',
            'binary': 'binary',
            'base64': 'base64'
        }
        save_path = filedialog.asksaveasfilename(
            title="保存NVS分区",
            filetypes=[("Binary Files", "*.bin"), ("All Files", "*.*")],
            defaultextension=".bin"
        )
        if not save_path:
            return
        
        try:
            self.status.set("生成CSV数据...")
            self.master.update()
            csv_file = None
            # 使用 csv.writer 生成临时 CSV，保证必要的引用和转义，避免键中包含逗号导致的格式问题
            with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False, newline='', encoding='utf-8') as tmpfile:
                csv_file = tmpfile.name
                writer = csv.writer(tmpfile, quoting=csv.QUOTE_MINIMAL)
                writer.writerow(["key", "type", "encoding", "value"])

                namespace_entries = {}
                for entry in self.nvs_data:
                    ns_name = entry["namespace"]
                    if ns_name not in namespace_entries:
                        namespace_entries[ns_name] = []
                    namespace_entries[ns_name].append(entry)

                for ns_name, entries in namespace_entries.items():
                    if ns_name != "ns_0":
                        writer.writerow([ns_name, 'namespace', '', ''])

                    for entry in entries:
                        key = entry["key"]
                        original_type = entry["type"].lower()
                        value = entry["value"]

                        data_type = "data"
                        encoding = TYPE_MAPPING.get(original_type, "")

                        if not encoding:
                            print(f"警告: 未知类型 '{original_type}'，默认使用hex2bin")
                            encoding = "hex2bin"

                        # 处理 hex2bin 字段格式
                        if encoding == "hex2bin" and isinstance(value, (bytes, bytearray)):
                            # 将字节转换为大写十六进制字符串
                            value = bytes(value).hex().upper()
                        elif encoding == "hex2bin" and isinstance(value, str):
                            value = value.upper()
                            if len(value) % 2 != 0:
                                value = "0" + value

                        # 确保写入 CSV 的都是字符串或可序列化类型
                        try:
                            writer.writerow([key, data_type, encoding, value])
                        except Exception:
                            # 作为最后手段，转换为字符串再写入
                            writer.writerow([str(key), data_type, encoding, str(value)])

                        self.status.set(f"写入 {key} 到csv ...")
                        self.master.update()

            print("打印csv表格")
            # 使用 UTF-8 编码读取临时 CSV，避免在默认 GBK 编码下出现解码错误
            with open(csv_file, 'r', encoding='utf-8') as f:
                print(f.read())  # 查看生成的CSV

            # 生成分区文件
            self.status.set("生成新分区...")
            self.master.update()
            
            # 直接使用已导入的生成模块
            gen_args = argparse.Namespace(
                input=csv_file,
                output=save_path,
                size=str(self.partition_size),
                version=2,
                outdir=os.getcwd(),
            )
            try:
                self.nvs_gen_mod.generate(gen_args)
            except SystemExit as e:
                raise Exception(f"生成函数异常退出: {e}")
            except Exception as e:
                raise

            self.current_file = save_path  # 更新当前文件路径
            self.status.set(f"成功保存到: {save_path}")
            messagebox.showinfo("成功", "NVS分区已成功保存")
            
        except Exception as e:
            messagebox.showerror("错误", f"保存分区失败:\n{str(e)}")
            print(f"保存分区失败: {str(e)}")
            # 避免将长错误信息显示到状态栏，详细信息在弹窗中已显示
            self.status.set("错误")
        finally:
            try:
                if os.path.exists(csv_file):
                    os.unlink(csv_file)
            except:
                pass

    def add_entry(self):
        # 获取所有命名空间作为选项
        namespace_options = list(set(entry["namespace"] for entry in self.nvs_data))
        if not namespace_options:
            namespace_options = ["default"]
            
        dialog = EntryDialog(self.master, "添加新条目", namespace_options)
        if dialog.result:
            new_entry = {
                "key": dialog.key,
                "namespace": dialog.namespace,
                "namespace_index": self._get_namespace_index(dialog.namespace),
                "type": dialog.data_type,
                "value": dialog.value,
                "raw": {}
            }
            
            # 检查是否已存在
            for item in self.tree.get_children():
                if (self.tree.item(item, "text") == dialog.key and 
                    self.tree.item(item, "values")[1] == dialog.namespace):
                    messagebox.showwarning("添加", "该名在指定命名空间中已存在!")
                    return
            
            # 添加显示值（截断长字符串）
            display_value = dialog.value
            if len(display_value) > 100:
                display_value = display_value[:100] + "..."
            
            self.nvs_data.append(new_entry)
            self.tree.insert("", "end", text=dialog.key, 
                            values=(dialog.key, dialog.namespace, dialog.data_type, display_value),
                            tags=(str(self._get_namespace_index(dialog.namespace)),))
            # 新增后自动排序
            try:
                self.sort_entries()
            except Exception:
                pass
            self.status.set(f"已添加条目: {dialog.namespace}:{dialog.key}")

    def _toggle_sort_order(self):
        """切换排序顺序（升序/降序）"""
        self.sort_order_asc = not getattr(self, 'sort_order_asc', True)
        self.sort_order_btn.config(text=("升序" if self.sort_order_asc else "降序"))
        # 切换顺序后自动排序
        self.sort_entries()

    def sort_entries(self):
        """按用户选择的字段对数据排序并刷新树视图（同时考虑搜索过滤）"""
        if not self.nvs_data:
            self.status.set("没有数据可排序")
            return

        field = self.sort_field_var.get()

        # 定义字段到访问器的映射
        field_map = {
            "键名": lambda e: (str(e.get('key') or '')).lower(),
            "命名空间": lambda e: (str(e.get('namespace') or '')).lower(),
            "类型": lambda e: (str(e.get('type') or '')).lower(),
            "值": lambda e: (str(e.get('value') or '')).lower(),
        }

        # 过滤：如果搜索框有内容，仅保留包含搜索关键字的条目（任意字段匹配）
        search_text = self.search_var.get().strip().lower() if hasattr(self, 'search_var') else ''
        if search_text:
            filtered = []
            for e in self.nvs_data:
                if (search_text in str(e.get('key') or '').lower() or
                    search_text in str(e.get('namespace') or '').lower() or
                    search_text in str(e.get('type') or '').lower() or
                    search_text in str(e.get('value') or '').lower()):
                    filtered.append(e)
        else:
            filtered = list(self.nvs_data)

        # 构造优先级列表：用户选择的字段权重最高，其余字段按固定顺序作为次要键
        remaining = [f for f in ("键名", "命名空间", "类型", "值") if f != field]
        priority_fields = [field] + remaining

        def multi_key(e):
            try:
                return tuple(field_map[f](e) for f in priority_fields)
            except Exception:
                return (str(e.get('key') or '').lower(),)

        sorted_list = sorted(filtered, key=multi_key, reverse=not self.sort_order_asc)

        # 刷新树视图
        self.tree.delete(*self.tree.get_children())
        for entry in sorted_list:
            display_value = entry.get('value', '')
            try:
                display_value = str(display_value)
            except Exception:
                display_value = repr(display_value)
            if len(display_value) > 100:
                display_value = display_value[:100] + "..."
            self.tree.insert("", "end", text=entry.get('key', ''),
                             values=(entry.get('key', ''), entry.get('namespace', ''), entry.get('type', ''), display_value),
                             tags=(str(entry.get('namespace_index', '')),))

        # 不修改原始 self.nvs_data，保持完整数据用于保存等操作
        self.status.set(f"已按 '{field}' 排序 ({'升序' if self.sort_order_asc else '降序'})")

    def _apply_filter_and_sort(self):
        """在搜索框内容变化时调用，重新应用过滤并排序显示"""
        # 直接复用 sort_entries 的逻辑即可
        self.sort_entries()

    def _get_namespace_index(self, namespace_name):
        """获取命名空间的索引值"""
        for ns_index, ns_name in self.namespace_map.items():
            if ns_name == namespace_name:
                return ns_index
        # 如果找不到，返回一个新的索引（大于现有最大索引）
        max_index = max(self.namespace_map.keys()) if self.namespace_map else 0
        new_index = max_index + 1
        self.namespace_map[new_index] = namespace_name
        return new_index

    def edit_entry(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("编辑", "请先选择一个条目")
            return
            
        item = selected[0]
        key = self.tree.item(item, "values")[0]
        current_namespace = self.tree.item(item, "values")[1]
        current_type = self.tree.item(item, "values")[2]
        
        # 查找原始数据（完整值）
        full_value = ""
        for entry in self.nvs_data:
            if entry["key"] == key and entry["namespace"] == current_namespace:
                full_value = entry["value"]
                break
        
        # 获取所有命名空间作为选项
        namespace_options = list(set(entry["namespace"] for entry in self.nvs_data))
        
        # 显示编辑对话框
        dialog = EntryDialog(
            self.master, "编辑条目",
            namespace_options,
            f"{current_namespace}:{key}", 
            current_namespace,
            current_type, 
            full_value
        )
        
        if dialog.result:
            # 更新数据
            for idx, entry in enumerate(self.nvs_data):
                if entry["key"] == key and entry["namespace"] == current_namespace:
                    self.nvs_data[idx]["key"] = dialog.key
                    self.nvs_data[idx]["namespace"] = dialog.namespace
                    self.nvs_data[idx]["namespace_index"] = self._get_namespace_index(dialog.namespace)
                    self.nvs_data[idx]["type"] = dialog.data_type
                    self.nvs_data[idx]["value"] = dialog.value
                    
                    # 更新显示值（截断长字符串）
                    display_value = dialog.value
                    if len(display_value) > 100:
                        display_value = display_value[:100] + "..."
                    
                    # 更新树状视图
                    self.tree.item(item, 
                                 text=dialog.key,
                                 values=(dialog.key, dialog.namespace, dialog.data_type, display_value),
                                 tags=(str(self._get_namespace_index(dialog.namespace)),))
                    # 编辑后自动排序
                    try:
                        self.sort_entries()
                    except Exception:
                        pass
                    self.status.set(f"已更新条目: {dialog.namespace}:{dialog.key}")
                    break

    def delete_entry(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("删除", "请先选择一个条目")
            return
            
        item = selected[0]
        key = self.tree.item(item, "values")[0]
        namespace = self.tree.item(item, "values")[1]
        
        if messagebox.askyesno("确认", f"确定要删除 '{namespace}:{key}' 吗?"):
            # 从数据中移除
            self.nvs_data = [e for e in self.nvs_data 
                           if not (e["key"] == key and e["namespace"] == namespace)]
            
            # 从树状视图中移除
            self.tree.delete(item)
            # 删除后自动排序
            try:
                self.sort_entries()
            except Exception:
                pass
            self.status.set(f"已删除条目: {namespace}:{key}")

    def on_double_click(self, event):
        self.edit_entry()

class EntryDialog(tk.Toplevel):
    def __init__(self, parent, title, namespace_options, ns_key="", current_namespace="", data_type="", value=""):
        super().__init__(parent)
        self.title(title)
        self.geometry("600x500")  # 增大窗口尺寸以容纳新组件
        self.result = False
        
        # 解析传入的ns_key
        if ns_key:
            try:
                parts = ns_key.split(":", 1)
                if len(parts) == 2:
                    current_namespace, key = parts
                else:
                    key = ns_key
            except ValueError:
                current_namespace, key = "", ns_key
        else:
            key = ""
        
        # 创建表单
        ttk.Label(self, text="命名空间:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.ns_var = tk.StringVar(value=current_namespace or (namespace_options[0] if namespace_options else ""))
        self.ns_combo = ttk.Combobox(self, textvariable=self.ns_var, values=namespace_options)
        if not namespace_options:
            self.ns_combo.config(state="disabled")
        self.ns_combo.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        
        ttk.Label(self, text="键名:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.key_entry = ttk.Entry(self)
        self.key_entry.grid(row=1, column=1, padx=5, pady=5, sticky=tk.EW)
        self.key_entry.insert(0, key)
        
        ttk.Label(self, text="数据类型:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.type_var = tk.StringVar(value=data_type or "string")
        type_combo = ttk.Combobox(self, textvariable=self.type_var, state="readonly")
        type_combo["values"] = ("u8", "i8", "u16", "i16", "u32", "i32", "u64", "i64", "string", "blob_data", "hex2bin", "base64", "binary")
        type_combo.grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)
        
        # 绑定数据类型变化事件
        self.type_var.trace_add("write", self._on_type_changed)
        
        ttk.Label(self, text="值:").grid(row=3, column=0, padx=5, pady=5, sticky=tk.NW)
        self.value_text = tk.Text(self, wrap=tk.WORD, height=10)
        self.value_text.grid(row=3, column=1, padx=5, pady=5, sticky=tk.NSEW)
        self.value_text.insert("1.0", value)
        
        # 添加ASCII解码显示区域
        ttk.Label(self, text="ASCII解码:").grid(row=4, column=0, padx=5, pady=5, sticky=tk.NW)
        self.ascii_display = tk.Text(self, wrap=tk.WORD, height=5, state=tk.DISABLED, bg="#f0f0f0")
        self.ascii_display.grid(row=4, column=1, padx=5, pady=5, sticky=tk.NSEW)
        
        # 绑定值变化事件
        self.value_text.bind("<KeyRelease>", self._update_ascii_preview)
        
        # 初始更新ASCII预览
        self._update_ascii_preview()

        # 统一文本控件字体为主界面默认字体，避免与 ttk 控件风格不一致
        try:
            default_font = tkfont.nametofont('TkDefaultFont')
            self.value_text.config(font=default_font)
            self.ascii_display.config(font=default_font)
        except Exception:
            pass
        
        # 按钮框架
        button_frame = ttk.Frame(self)
        button_frame.grid(row=5, column=0, columnspan=2, pady=10)
        
        ttk.Button(button_frame, text="确定", command=self.on_ok).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="取消", command=self.destroy).pack(side=tk.RIGHT)
        
        # 配置网格权重
        self.columnconfigure(1, weight=1)
        self.rowconfigure(3, weight=1)
        self.rowconfigure(4, weight=0)  # ASCII显示区域不需要太大
        
        # 将对话框居中到父窗口
        try:
            self.update_idletasks()
            parent_x = parent.winfo_rootx()
            parent_y = parent.winfo_rooty()
            parent_w = parent.winfo_width()
            parent_h = parent.winfo_height()
            win_w = 600
            win_h = 500
            x = parent_x + (parent_w - win_w) // 2
            y = parent_y + (parent_h - win_h) // 2
            self.geometry(f"{win_w}x{win_h}+{x}+{y}")
        except Exception:
            pass

        self.grab_set()
        self.transient(parent)
        self.wait_window()
    
    def _on_type_changed(self, *args):
        """当数据类型变化时更新ASCII预览"""
        self._update_ascii_preview()
    
    def _update_ascii_preview(self, event=None):
        """更新ASCII解码预览"""
        current_type = self.type_var.get()
        value = self.value_text.get("1.0", tk.END).strip()
        
        # 清空显示
        self.ascii_display.config(state=tk.NORMAL)
        self.ascii_display.delete("1.0", tk.END)
        
        # 显示ASCII解码
        if (current_type == "hex2bin" or current_type == "blob_data") and value:
            try:
                # 确保十六进制字符串长度为偶数
                if len(value) % 2 != 0:
                    value = "0" + value
                
                # 转换为字节
                bytes_data = bytes.fromhex(value)
                
                # 尝试解码为ASCII
                try:
                    ascii_str = bytes_data.decode('ascii', errors='strict')
                    display_text = f"ASCII解码结果:\n{ascii_str}"
                except UnicodeDecodeError:
                    # 如果不能完全解码为ASCII，显示可打印的部分
                    printable = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in bytes_data)
                    display_text = f"部分可打印字符 (不可见字符显示为'.'):\n{printable}"
                
                self.ascii_display.insert("1.0", display_text)
                
            except ValueError as e:
                self.ascii_display.insert("1.0", f"十六进制数据无效: {str(e)}")
            except Exception as e:
                self.ascii_display.insert("1.0", f"解码错误: {str(e)}")
        
        self.ascii_display.config(state=tk.DISABLED)
    
    def on_ok(self):
        self.namespace = self.ns_var.get().strip()
        self.key = self.key_entry.get().strip()
        self.data_type = self.type_var.get()
        self.value = self.value_text.get("1.0", tk.END).strip()
        
        if not self.key:
            messagebox.showwarning("输入错误", "键名不能为空")
            return
        
        if not self.namespace:
            messagebox.showwarning("输入错误", "命名空间不能为空")
            return
        
        # 验证blob数据
        if self.data_type == "hex2bin":
            try:
                # 确保十六进制字符串长度为偶数
                if len(self.value) % 2 != 0:
                    self.value = "0" + self.value
                    
                # 验证是否为有效十六进制
                bytes.fromhex(self.value)
            except ValueError:
                messagebox.showwarning("输入错误", "Hex数据必须是有效的十六进制字符串")
                return
        
        # 验证整数类型
        elif self.data_type.startswith(("u", "i")):
            try:
                int(self.value)
            except ValueError:
                messagebox.showwarning("输入错误", f"{self.data_type} 类型需要整数值")
                return
        
        self.result = True
        self.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = NVS_Editor(root)
    root.mainloop()