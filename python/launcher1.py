import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
import urllib.request
import zipfile
import subprocess
import json
import threading
from pathlib import Path
import ctypes
import webbrowser
import uuid
import time
import re
from urllib.parse import urlencode

# 配置信息

SERVER_URL = f""
UPDATE_PATH = r""
BAT_FILE = r""
ODD_BAT_FILE = r""
VERSION_FILE = ""
UPDATE_ZIP = ""
AUTH_API = ""
APP_ID = "" 

# 设备码文件
DEVICE_CODE_FILE = ""

def is_admin():
    """检查是否以管理员权限运行"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    """以管理员权限重新运行程序"""
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1
    )

def get_device_id():
    """获取或生成设备ID"""
    # 尝试从文件读取设备ID
    if os.path.exists(DEVICE_CODE_FILE):
        try:
            with open(DEVICE_CODE_FILE, 'r') as f:
                return f.read().strip()
        except:
            pass
    
    # 生成新的设备ID (UUID)
    device_id = str(uuid.uuid4())
    
    # 保存到文件
    try:
        with open(DEVICE_CODE_FILE, 'w') as f:
            f.write(device_id)
    except:
        pass
    
    return device_id

def parse_json_response(response_text):
    """尝试解析可能的JSON响应，处理格式问题"""
    try:
        # 尝试直接解析
        return json.loads(response_text)
    except json.JSONDecodeError as e:
        # 尝试修复常见的JSON格式问题
        try:
            # 尝试提取JSON对象部分
            match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if match:
                fixed_json = match.group(0)
                return json.loads(fixed_json)
        except:
            pass
        
        # 尝试移除可能的HTML标签
        try:
            clean_text = re.sub(r'<[^>]+>', '', response_text)
            return json.loads(clean_text)
        except:
            pass
        
        # 尝试移除可能的BOM字符
        try:
            if response_text.startswith('\ufeff'):
                return json.loads(response_text[1:])
        except:
            pass
        
        # 所有尝试都失败，抛出原始异常
        raise e

class GameLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("maimai启动器")
        self.root.geometry("600x400")  # 增加窗口高度以容纳新元素
        self.root.resizable(False, False)
        
        # 检查管理员权限
        if not is_admin():
            messagebox.showwarning(
                "权限提示", 
                "启动器需要管理员权限来运行ODD程序。\n请允许UAC提示以继续。"
            )
            run_as_admin()
            sys.exit(0)
        
        # 初始化验证状态
        self.auth_data = None
        self.is_authenticated = False
        self.device_id = get_device_id()  # 获取设备ID
        
        # 创建UI
        self.create_widgets()
        
        # 初始化路径
        self.base_dir = Path(os.getcwd())
        self.update_dir = self.base_dir / UPDATE_PATH
        self.version_file = self.base_dir / VERSION_FILE
        self.bat_file = self.base_dir / BAT_FILE
        self.odd_bat_file = self.base_dir / ODD_BAT_FILE
        
        # 加载本地版本信息
        self.local_version = self.load_local_version()
        
        # 显示卡密输入窗口
        self.show_auth_window()
    
    def create_widgets(self):
        # 标题
        title_frame = tk.Frame(self.root)
        title_frame.pack(pady=10)
        tk.Label(title_frame, text="maimai启动器", font=("Arial", 16, "bold")).pack()
        
        # 权限提示
        tk.Label(
            title_frame, 
            text="(已获得管理员权限)", 
            font=("Arial", 8), 
            fg="green"
        ).pack()
        
        # 验证状态
        self.auth_status = tk.StringVar(value="请输入卡密进行验证")
        auth_label = tk.Label(self.root, textvariable=self.auth_status, font=("Arial", 10), fg="blue")
        auth_label.pack(pady=5)
        
        # 版本信息
        self.version_label = tk.Label(self.root, text="版本: 加载中...", font=("Arial", 10))
        self.version_label.pack(pady=5)
        
        # 进度条
        progress_frame = tk.Frame(self.root)
        progress_frame.pack(fill=tk.X, padx=20, pady=10)
        self.progress = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL, length=500, mode='determinate')
        self.progress.pack()
        
        # 状态信息
        self.status_var = tk.StringVar(value="等待验证...")
        status_label = tk.Label(self.root, textvariable=self.status_var, font=("Arial", 10))
        status_label.pack(pady=5)
        
        # 按钮
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=10)
        
        # 第一行按钮
        button_row1 = tk.Frame(button_frame)
        button_row1.pack(pady=5)
        
        self.start_btn = tk.Button(button_row1, text="启动游戏", width=15, 
                                  command=self.start_game, state=tk.DISABLED)
        self.start_btn.pack(side=tk.LEFT, padx=10)
        
        self.odd_btn = tk.Button(button_row1, text="启动ODD", width=15, 
                                command=self.start_odd, state=tk.DISABLED)
        self.odd_btn.pack(side=tk.LEFT, padx=10)
        
        # 第二行按钮
        button_row2 = tk.Frame(button_frame)
        button_row2.pack(pady=5)
        
        self.update_btn = tk.Button(button_row2, text="强制更新", width=15, 
                                   command=self.force_update, state=tk.DISABLED)
        self.update_btn.pack(side=tk.LEFT, padx=10)
        
        self.logout_btn = tk.Button(button_row2, text="查看日志", width=15, 
                                   command=self.show_logs, state=tk.DISABLED)
        self.logout_btn.pack(side=tk.LEFT, padx=10)
        
        # 第三行按钮 - 网络验证相关
        button_row3 = tk.Frame(button_frame)
        button_row3.pack(pady=5)
        
        self.buy_btn = tk.Button(button_row3, text="购买卡密", width=15, 
                                command=self.open_buy_page)
        self.buy_btn.pack(side=tk.LEFT, padx=10)
        
        self.retry_btn = tk.Button(button_row3, text="重新验证", width=15, 
                                  command=self.show_auth_window)
        self.retry_btn.pack(side=tk.LEFT, padx=10)
        
        # 第四行 - VIP信息
        self.vip_info = tk.StringVar(value="验证状态: 未验证")
        vip_label = tk.Label(button_frame, textvariable=self.vip_info, font=("Arial", 10), fg="purple")
        vip_label.pack(pady=10)

    def show_auth_window(self):
        """显示卡密验证窗口"""
        auth_win = tk.Toplevel(self.root)
        auth_win.title("卡密验证")
        auth_win.geometry("400x200")
        auth_win.resizable(False, False)
        auth_win.grab_set()  # 模态窗口
        
        # 居中显示
        auth_win.update_idletasks()
        width = auth_win.winfo_width()
        height = auth_win.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        auth_win.geometry(f'+{x}+{y}')
        
        # 内容框架
        content_frame = tk.Frame(auth_win)
        content_frame.pack(pady=20, padx=20, fill=tk.BOTH, expand=True)
        
        # 设备ID显示
        tk.Label(content_frame, text=f"设备ID: {self.device_id}", font=("Arial", 9)).pack(anchor="w", pady=5)
        
        # 卡密输入
        tk.Label(content_frame, text="请输入卡密:", font=("Arial", 10)).pack(anchor="w", pady=5)
        
        self.kami_entry = tk.Entry(content_frame, width=30, font=("Arial", 10))
        self.kami_entry.pack(fill=tk.X, pady=5)
        self.kami_entry.focus_set()
        
        # 状态标签
        self.auth_result = tk.StringVar(value="")
        result_label = tk.Label(content_frame, textvariable=self.auth_result, font=("Arial", 9), fg="red")
        result_label.pack(pady=5)
        
        # 按钮框架
        btn_frame = tk.Frame(content_frame)
        btn_frame.pack(pady=10)
        
        # 验证按钮
        auth_btn = tk.Button(btn_frame, text="验证卡密", width=15, 
                            command=lambda: self.perform_network_authentication(auth_win))
        auth_btn.pack(side=tk.LEFT, padx=10)
        
        # 关闭按钮
        close_btn = tk.Button(btn_frame, text="关闭", width=15, 
                             command=auth_win.destroy)
        close_btn.pack(side=tk.LEFT, padx=10)
        
        # 绑定回车键
        auth_win.bind('<Return>', lambda event: self.perform_network_authentication(auth_win))
    
    def perform_network_authentication(self, auth_win=None):
        """执行网络验证"""
        kami = self.kami_entry.get().strip()
        if not kami:
            self.auth_result.set("卡密不能为空")
            return
        
        self.auth_result.set("正在验证...")
        
        # 禁用输入和按钮
        self.kami_entry.config(state=tk.DISABLED)
        if auth_win:
            for widget in auth_win.winfo_children():
                if isinstance(widget, tk.Button):
                    widget.config(state=tk.DISABLED)
        
        threading.Thread(target=self._authentication_thread, args=(kami, auth_win), daemon=True).start()
    
    def _authentication_thread(self, kami, auth_win=None):
        """验证线程 - 仅使用必需的四个参数"""
        try:
            self.auth_status.set("正在连接验证服务器...")
            
            # 准备请求参数 - 只使用必需的四个参数
            params = {
                "api": "kmlogon",  # 接口名称
                "app": APP_ID,      # 应用ID
                "kami": kami,       # 卡密
                "markcode": self.device_id  # 设备码
            }
            
            # 构建请求URL (使用urlencode确保正确编码)
            url = f"{AUTH_API}?{urlencode(params)}"
            print("请求URL:", url)  # 调试输出
            
            # 发送请求
            with urllib.request.urlopen(url, timeout=15) as response:
                raw_data = response.read().decode('utf-8')
                
                # 打印原始响应用于调试
                print("原始响应数据:", raw_data[:500] + ("..." if len(raw_data) > 500 else ""))
                
                # 使用自定义JSON解析器
                data = parse_json_response(raw_data)
            
            # 检查返回状态
            if data.get("code") != 200:
                error_msg = self.get_error_message(data.get("code"))
                self.auth_result.set(f"验证失败: {error_msg}")
                self.auth_status.set(f"验证失败: {error_msg}")
                return
            
            # 解析返回数据
            self.auth_data = data.get("msg", {})
            
            # 更新VIP信息
            vip_expiry = self.auth_data.get("vip", "未知")
            self.vip_info.set(f"验证状态: 有效期至 {vip_expiry}")
            
            # 验证成功
            self.is_authenticated = True
            self.auth_status.set("验证成功!")
            self.activate_buttons()
            
            # 关闭验证窗口
            if auth_win:
                auth_win.destroy()
            
            # 检查更新
            self.check_for_updates()
        
        except urllib.error.HTTPError as e:
            error_msg = f"HTTP错误: {e.code} {e.reason}"
            self.auth_result.set(error_msg)
            self.auth_status.set(error_msg)
        except urllib.error.URLError as e:
            error_msg = f"网络错误: {str(e.reason)}"
            self.auth_result.set(error_msg)
            self.auth_status.set(error_msg)
        except json.JSONDecodeError as e:
            error_msg = f"JSON解析错误: {str(e)}"
            self.auth_result.set(error_msg)
            self.auth_status.set(error_msg)
        except Exception as e:
            error_msg = f"验证失败: {str(e)}"
            self.auth_result.set(error_msg)
            self.auth_status.set(error_msg)
        finally:
            # 重新启用输入和按钮
            if auth_win:
                self.kami_entry.config(state=tk.NORMAL)
                for widget in auth_win.winfo_children():
                    if isinstance(widget, tk.Button):
                        widget.config(state=tk.NORMAL)
    
    def get_error_message(self, error_code):
        """根据错误码返回错误信息"""
        error_messages = {
            "101": "应用不存在",
            "102": "应用已关闭",
            "171": "接口维护中",
            "172": "接口未添加或不存在",
            "104": "签名为空",
            "105": "数据过期",
            "106": "签名有误",
            "148": "卡密为空",
            "149": "卡密不存在",
            "151": "卡密禁用",
            "169": "IP不一致"
        }
        return error_messages.get(str(error_code), f"未知错误 (代码: {error_code})")
    
    def activate_buttons(self):
        """激活功能按钮"""
        self.start_btn.config(state=tk.NORMAL)
        self.odd_btn.config(state=tk.NORMAL)
        self.update_btn.config(state=tk.NORMAL)
        self.logout_btn.config(state=tk.NORMAL)
    
    def open_buy_page(self):
        """打开购买页面"""
        webbrowser.open("https://m.tb.cn/h.hYesG5B?tk=qva9Vs7587S")  # 替换为实际的购买页面
    
    def load_local_version(self):
        """加载本地版本信息"""
        version_data = {"version": "0.0.0", "files": {}}
        
        if self.version_file.exists():
            try:
                with open(self.version_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return version_data

    def save_local_version(self, version_data):
        """保存本地版本信息"""
        with open(self.version_file, 'w', encoding='utf-8') as f:
            json.dump(version_data, f, indent=2)

    def get_remote_version(self):
        """获取服务器版本信息"""
        try:
            with urllib.request.urlopen(f"{SERVER_URL}{VERSION_FILE}") as response:
                raw_data = response.read().decode('utf-8')
                return parse_json_response(raw_data)
        except Exception as e:
            self.status_var.set(f"无法获取服务器版本: {str(e)}")
            return None

    def check_for_updates(self):
        """检查更新"""
        if not self.is_authenticated:
            self.status_var.set("请先完成验证")
            return
            
        threading.Thread(target=self._check_updates_thread, daemon=True).start()

    def _check_updates_thread(self):
        """更新检查线程"""
        self.start_btn.config(state=tk.DISABLED)
        self.update_btn.config(state=tk.DISABLED)
        
        remote_version = self.get_remote_version()
        if not remote_version:
            self.status_var.set("连接服务器失败")
            self.start_btn.config(state=tk.NORMAL)
            self.update_btn.config(state=tk.NORMAL)
            return
        
        # 比较版本
        if remote_version["version"] == self.local_version["version"]:
            self.status_var.set("游戏已是最新版本")
            self.version_label.config(text=f"版本: v{self.local_version['version']}")
            self.start_btn.config(state=tk.NORMAL)
            self.update_btn.config(state=tk.NORMAL)
        else:
            self.status_var.set(f"发现新版本 v{remote_version['version']}")
            self.update_game(remote_version)

    def update_game(self, remote_version=None):
        """执行更新"""
        if not self.is_authenticated:
            self.status_var.set("请先完成验证")
            return
            
        if not remote_version:
            remote_version = self.get_remote_version()
            if not remote_version:
                self.status_var.set("无法获取更新信息")
                return
        
        self.start_btn.config(state=tk.DISABLED)
        self.update_btn.config(state=tk.DISABLED)
        self.odd_btn.config(state=tk.DISABLED)
        
        threading.Thread(target=self._update_thread, args=(remote_version,), daemon=True).start()

    def force_update(self):
        """强制更新"""
        self.status_var.set("开始强制更新...")
        self.update_game()

    def _update_thread(self, remote_version):
        """更新线程"""
        try:
            # 创建更新目录
            self.update_dir.mkdir(parents=True, exist_ok=True)
            
            # 下载更新包
            self.status_var.set("正在下载更新...")
            zip_path = self.base_dir / UPDATE_ZIP
            
            def update_progress(count, block_size, total_size):
                percent = int(count * block_size * 100 / total_size)
                self.progress['value'] = percent
                self.status_var.set(f"下载中: {percent}%")
                self.root.update_idletasks()
            
            urllib.request.urlretrieve(
                f"{SERVER_URL}{UPDATE_ZIP}",
                zip_path,
                reporthook=update_progress
            )
            
            # 解压更新包
            self.status_var.set("正在解压文件...")
            self.progress['value'] = 0
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                total_files = len(zip_ref.infolist())
                for i, file in enumerate(zip_ref.infolist()):
                    if file.filename.endswith('/'):
                        continue
                    
                    percent = int(i * 100 / total_files)
                    self.progress['value'] = percent
                    self.status_var.set(f"解压中: {file.filename}")
                    self.root.update_idletasks()
                    
                    zip_ref.extract(file, self.update_dir)
            
            # 更新版本信息
            self.local_version = remote_version
            self.save_local_version(remote_version)
            
            self.status_var.set("更新完成!")
            self.version_label.config(text=f"版本: v{self.local_version['version']}")
            self.progress['value'] = 100
            
            # 删除临时文件
            if zip_path.exists():
                os.remove(zip_path)
            
            messagebox.showinfo("更新完成", "游戏已成功更新到最新版本!")
            
        except Exception as e:
            self.status_var.set(f"更新失败: {str(e)}")
            messagebox.showerror("更新错误", f"更新过程中发生错误:\n{str(e)}")
        finally:
            self.start_btn.config(state=tk.NORMAL)
            self.update_btn.config(state=tk.NORMAL)
            self.odd_btn.config(state=tk.NORMAL)

    def start_game(self):
        """启动游戏"""
        if not self.is_authenticated:
            messagebox.showwarning("未验证", "请先完成网络验证")
            return
            
        if not self.bat_file.exists():
            messagebox.showerror("错误", f"找不到启动文件: {BAT_FILE}")
            return
        
        try:
            bat_dir = os.path.dirname(self.bat_file)
            subprocess.Popen(
                [self.bat_file], 
                cwd=bat_dir,
                shell=True
            )
            self.root.after(1000, self.root.destroy)
        except Exception as e:
            messagebox.showerror("启动失败", f"无法启动游戏: {str(e)}")

    def start_odd(self):
        """启动ODD程序"""
        if not self.is_authenticated:
            messagebox.showwarning("未验证", "请先完成网络验证")
            return
            
        if not self.odd_bat_file.exists():
            messagebox.showerror("错误", f"找不到ODD启动文件: {ODD_BAT_FILE}")
            return
        
        try:
            # 使用runas命令确保管理员权限
            bat_dir = os.path.dirname(self.odd_bat_file)
            subprocess.Popen(
                [self.odd_bat_file], 
                cwd=bat_dir,
                shell=True
            )
            messagebox.showinfo("启动成功", "ODD程序正在运行中...")
        except Exception as e:
            messagebox.showerror("启动失败", f"无法启动ODD程序: {str(e)}")

    def show_logs(self):
        """显示更新日志"""
        if not self.is_authenticated:
            messagebox.showwarning("未验证", "请先完成网络验证")
            return
            
        changelog = self.local_version.get("changelog", "暂无更新日志")
        
        log_window = tk.Toplevel(self.root)
        log_window.title("更新日志")
        log_window.geometry("600x450")
        
        text_frame = tk.Frame(log_window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        text_area = tk.Text(text_frame, wrap=tk.WORD, yscrollcommand=scrollbar.set, font=("Arial", 10))
        text_area.pack(fill=tk.BOTH, expand=True)
        text_area.insert(tk.END, changelog)
        text_area.config(state=tk.DISABLED)
        
        scrollbar.config(command=text_area.yview)

if __name__ == "__main__":
    # 检查管理员权限
    if not is_admin():
        # 创建临时窗口显示提示
        root = tk.Tk()
        root.withdraw()  # 隐藏主窗口
        messagebox.showinfo(
            "权限提升", 
            "启动器需要管理员权限运行，请允许UAC提示。"
        )
        run_as_admin()
        root.destroy()
        sys.exit(0)
    
    root = tk.Tk()
    app = GameLauncher(root)
    root.mainloop()