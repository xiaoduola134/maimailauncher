import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
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
import hashlib
import socket
import ssl

# 配置信息
SERVER_URL = f""
UPDATE_PATH = r""
BAT_FILE = r""
ODD_BAT_FILE = r""
HOSTS_BAT = r"" 
VERSION_FILE = ""
UPDATE_ZIP = ""
LAUNCHER_VERSION_FILE = ""
AUTH_API = ""
APP_ID = ""
LAUNCHER_VERSION = "1.0.3"  
DEVICE_CODE_FILE = r""
LAUNCHER_UPDATE_BAT = ""
ANNOUNCEMENT_FILE = ""  
CARD_FILE = r"P" 

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
    
    # 获取MAC地址并哈希
    def get_mac_address():
        mac = uuid.getnode()
        mac_address = ':'.join(['{:02x}'.format((mac >> i) & 0xff) for i in range(0, 48, 8)])
        return mac_address
    
    def hash_mac_address(mac_address):
        sha256_hash = hashlib.sha256(mac_address.encode()).hexdigest()
        return sha256_hash
    
    # 生成新的设备ID (基于MAC地址的哈希)
    mac_address = get_mac_address()
    device_id = hash_mac_address(mac_address)
    
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
        self.root.title(f"maimai启动器 v{LAUNCHER_VERSION}")
        self.root.geometry("800x450")  # 增加窗口宽度以容纳右侧公告
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
        self.hosts_bat = self.base_dir / HOSTS_BAT  # hosts批处理文件
        self.launcher_version_file = self.base_dir / LAUNCHER_VERSION_FILE
        self.launcher_update_bat = self.base_dir / LAUNCHER_UPDATE_BAT
        # 修改点1：将卡密文件路径更改为 Package/CARD.txt
        self.card_file = self.base_dir / CARD_FILE  # 卡密存储文件（已更改路径）
        
        # 加载本地版本信息
        self.local_version = self.load_local_version()
        
        # 尝试加载保存的卡密
        self.saved_kami = self.load_saved_kami()
        
        # 获取公告内容
        self.fetch_announcement()
        
        # 如果存在保存的卡密，则自动验证
        if self.saved_kami:
            self.auth_status.set("正在使用保存的卡密进行验证...")
            self.perform_network_authentication(self.saved_kami, remember=True)
        else:
            # 显示卡密输入窗口
            self.show_auth_window()
    
    def load_saved_kami(self):
        """加载保存的卡密"""
        try:
            # 确保目录存在
            self.card_file.parent.mkdir(parents=True, exist_ok=True)
            
            if self.card_file.exists():
                with open(self.card_file, 'r') as f:
                    return f.read().strip()
        except Exception as e:
            print(f"加载保存的卡密失败: {str(e)}")
        return None
    
    def save_kami(self, kami):
        """保存卡密到文件"""
        try:
            with open(self.card_file, 'w') as f:
                f.write(kami)
            return True
        except Exception as e:
            print(f"保存卡密失败: {str(e)}")
            return False
    
    def clear_saved_kami(self):
        """清除保存的卡密"""
        try:
            if self.card_file.exists():
                os.remove(self.card_file)
            return True
        except Exception as e:
            print(f"清除卡密失败: {str(e)}")
            return False
    
    def fetch_announcement(self):
        """获取公告内容"""
        threading.Thread(target=self._fetch_announcement_thread, daemon=True).start()
    
    def _fetch_announcement_thread(self):
        """获取公告内容的线程"""
        try:
            # 创建自定义的HTTPS处理程序
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # 设置超时时间
            socket.setdefaulttimeout(15)
            
            # 公告URL
            announcement_url = f"{SERVER_URL}/g/{ANNOUNCEMENT_FILE}"
            
            # 发送请求
            request = urllib.request.Request(announcement_url)
            request.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
            
            with urllib.request.urlopen(request, context=ssl_context) as response:
                raw_data = response.read().decode('utf-8')
                announcement_data = parse_json_response(raw_data)
                
                # 更新UI显示公告
                self.root.after(0, lambda: self.update_announcement(announcement_data))
                
        except Exception as e:
            print(f"获取公告失败: {str(e)}")
            # 显示默认公告
            default_announcement = {
                "title": "公告",
                "content": "无法连接到服务器获取最新公告。\n请检查网络连接或稍后再试。",
                "date": time.strftime("%Y-%m-%d")
            }
            self.root.after(0, lambda: self.update_announcement(default_announcement))
    
    def update_announcement(self, announcement_data):
        """更新公告显示 - 只显示公告内容"""
        # 清空现有内容
        self.announcement_text.config(state=tk.NORMAL)
        self.announcement_text.delete(1.0, tk.END)
        
        # 添加标题
        title = announcement_data.get("title", "公告")
        date = announcement_data.get("date", time.strftime("%Y-%m-%d"))
        self.announcement_text.tag_configure("title", font=("Arial", 12, "bold"), foreground="blue")
        self.announcement_text.insert(tk.END, f"{title}\n", "title")
        self.announcement_text.insert(tk.END, f"发布日期: {date}\n\n", ("title",))
        
        # 添加内容
        content = announcement_data.get("content", "暂无公告内容。")
        self.announcement_text.tag_configure("content", font=("Arial", 10))
        self.announcement_text.insert(tk.END, content, "content")
        
        # 禁用编辑
        self.announcement_text.config(state=tk.DISABLED)
    
    def show_auth_window(self):
        """显示卡密验证窗口"""
        self.auth_win = tk.Toplevel(self.root)
        self.auth_win.title(f"卡密验证")
        self.auth_win.geometry("400x250")  # 增加高度以容纳"记住卡密"复选框
        self.auth_win.resizable(False, False)
        self.auth_win.grab_set()  # 模态窗口
        
        # 居中显示
        self.auth_win.update_idletasks()
        width = self.auth_win.winfo_width()
        height = self.auth_win.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.auth_win.geometry(f'+{x}+{y}')
        
        # 内容框架
        content_frame = tk.Frame(self.auth_win)
        content_frame.pack(pady=20, padx=20, fill=tk.BOTH, expand=True)
        
        # 设备ID显示
        tk.Label(content_frame, text=f"设备ID: {self.device_id}", font=("Arial", 9)).pack(anchor="w", pady=5)
        
        # 卡密输入
        tk.Label(content_frame, text="请输入卡密:", font=("Arial", 10)).pack(anchor="w", pady=5)
        
        self.kami_entry = tk.Entry(content_frame, width=30, font=("Arial", 10))
        self.kami_entry.pack(fill=tk.X, pady=5)
        self.kami_entry.focus_set()
        
        # 如果之前保存过卡密，自动填充
        if self.saved_kami:
            self.kami_entry.insert(0, self.saved_kami)
        
        # "记住卡密"复选框
        self.remember_var = tk.BooleanVar(value=True)  # 默认选中
        remember_check = tk.Checkbutton(
            content_frame, 
            text="记住卡密 (下次自动验证)",
            variable=self.remember_var,
            font=("Arial", 9)
        )
        remember_check.pack(anchor="w", pady=5)
        
        # 状态标签
        self.auth_result = tk.StringVar(value="")
        result_label = tk.Label(content_frame, textvariable=self.auth_result, font=("Arial", 9), fg="red")
        result_label.pack(pady=5)
        
        # 按钮框架
        btn_frame = tk.Frame(content_frame)
        btn_frame.pack(pady=10)
        
        # 验证按钮
        auth_btn = tk.Button(btn_frame, text="验证卡密", width=15, 
                            command=lambda: self.perform_network_authentication(
                                self.kami_entry.get().strip(), 
                                self.remember_var.get(),
                                self.auth_win
                            ))
        auth_btn.pack(side=tk.LEFT, padx=10)
        
        # 清除卡密按钮
        clear_btn = tk.Button(btn_frame, text="清除卡密", width=15, 
                             command=self.clear_kami)
        clear_btn.pack(side=tk.LEFT, padx=10)
        
        # 绑定回车键
        self.auth_win.bind('<Return>', lambda event: self.perform_network_authentication(
            self.kami_entry.get().strip(), 
            self.remember_var.get(),
            self.auth_win
        ))
    
    def clear_kami(self):
        """清除保存的卡密"""
        if self.clear_saved_kami():
            self.saved_kami = None
            self.auth_result.set("已清除保存的卡密")
            # 清除后重新获取公告
            self.fetch_announcement()
        else:
            self.auth_result.set("清除卡密失败")
    
    def perform_network_authentication(self, kami, remember=True, auth_win=None):
        """执行网络验证"""
        if not kami:
            if auth_win:
                self.auth_result.set("卡密不能为空")
            else:
                self.auth_status.set("卡密不能为空")
            return
        
        if auth_win:
            self.auth_result.set("正在验证...")
        else:
            self.auth_status.set("正在验证...")
        
        # 禁用输入和按钮
        if auth_win:
            self.kami_entry.config(state=tk.DISABLED)
            for widget in auth_win.winfo_children():
                if isinstance(widget, tk.Button):
                    widget.config(state=tk.DISABLED)
        
        threading.Thread(target=self._authentication_thread, args=(kami, remember, auth_win), daemon=True).start()
    
    def _authentication_thread(self, kami, remember, auth_win=None):
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
            
            # 创建自定义的HTTPS处理程序
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # 设置超时时间
            socket.setdefaulttimeout(15)
            
            # 发送请求
            request = urllib.request.Request(url)
            request.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
            
            with urllib.request.urlopen(request, context=ssl_context) as response:
                raw_data = response.read().decode('utf-8')
                
                # 打印原始响应用于调试
                print("原始响应数据:", raw_data[:500] + ("..." if len(raw_data) > 500 else ""))
                
                # 使用自定义JSON解析器
                data = parse_json_response(raw_data)
            
            # 检查返回状态
            if data.get("code") != 200:
                error_msg = self.get_error_message(data.get("code"))
                if auth_win:
                    self.auth_result.set(f"验证失败: {error_msg}")
                self.auth_status.set(f"验证失败: {error_msg}")
                
                # 验证失败时清除保存的卡密（如果存在）
                if self.saved_kami:
                    self.clear_saved_kami()
                    self.saved_kami = None
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
            
            # 保存卡密（如果需要）
            if remember:
                if self.save_kami(kami):
                    self.saved_kami = kami
                    if auth_win:
                        self.auth_result.set("验证成功并保存卡密")
                    else:
                        self.auth_status.set("验证成功并保存卡密")
                else:
                    if auth_win:
                        self.auth_result.set("验证成功但保存卡密失败")
                    else:
                        self.auth_status.set("验证成功但保存卡密失败")
            else:
                # 如果不记住卡密，清除之前保存的
                if self.saved_kami:
                    self.clear_saved_kami()
                    self.saved_kami = None
                if auth_win:
                    self.auth_result.set("验证成功（未保存卡密）")
                else:
                    self.auth_status.set("验证成功（未保存卡密）")
            
            # 关闭验证窗口
            if auth_win and auth_win.winfo_exists():
                auth_win.destroy()
            
            # 检查更新
            self.check_for_updates()
            
            # 检查启动器更新
            self.check_launcher_update()
        
        except urllib.error.HTTPError as e:
            error_msg = f"HTTP错误: {e.code} {e.reason}"
            if auth_win:
                self.auth_result.set(error_msg)
            self.auth_status.set(error_msg)
            
            # 验证失败时清除保存的卡密（如果存在）
            if self.saved_kami:
                self.clear_saved_kami()
                self.saved_kami = None
        except urllib.error.URLError as e:
            error_msg = f"网络错误: {str(e.reason)}"
            if auth_win:
                self.auth_result.set(error_msg)
            self.auth_status.set(error_msg)
            
            # 验证失败时清除保存的卡密（如果存在）
            if self.saved_kami:
                self.clear_saved_kami()
                self.saved_kami = None
        except json.JSONDecodeError as e:
            error_msg = f"JSON解析错误: {str(e)}"
            if auth_win:
                self.auth_result.set(error_msg)
            self.auth_status.set(error_msg)
            
            # 验证失败时清除保存的卡密（如果存在）
            if self.saved_kami:
                self.clear_saved_kami()
                self.saved_kami = None
        except Exception as e:
            error_msg = f"验证失败: {str(e)}"
            if auth_win:
                self.auth_result.set(error_msg)
            self.auth_status.set(error_msg)
            
            # 验证失败时清除保存的卡密（如果存在）
            if self.saved_kami:
                self.clear_saved_kami()
                self.saved_kami = None
        
        # 重新启用输入和按钮 - 仅在窗口仍然存在时
        if auth_win and auth_win.winfo_exists():
            try:
                self.kami_entry.config(state=tk.NORMAL)
                for widget in auth_win.winfo_children():
                    if isinstance(widget, tk.Button):
                        widget.config(state=tk.NORMAL)
            except tk.TclError:
                # 忽略窗口已被销毁时的错误
                pass
    
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
            "150": "卡密已使用",
            "151": "卡密禁用",
            "169": "IP不一致"
        }
        return error_messages.get(str(error_code), f"未知错误 (代码: {error_code})")
    
    def activate_buttons(self):
        """激活功能按钮"""
        self.start_btn.config(state=tk.NORMAL)
        self.odd_btn.config(state=tk.NORMAL)
        self.update_btn.config(state=tk.NORMAL)
        self.modify_hosts_btn.config(state=tk.NORMAL)
    
    def open_buy_page(self):
        """打开购买页面"""
        webbrowser.open("https://m.tb.cn/h.hYesG5B?tk=qva9Vs7587S")  # 替换为实际的购买页面
    
    def create_widgets(self):
        # 主框架 - 分割左右区域
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 左侧功能区域
        left_frame = tk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 右侧公告区域
        right_frame = tk.LabelFrame(main_frame, text="最新公告", font=("Arial", 10, "bold"))
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(10, 0), pady=5)
        right_frame.config(width=250)  # 固定宽度
        
        # 公告内容区域
        announcement_container = tk.Frame(right_frame)
        announcement_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 添加滚动条
        scrollbar = tk.Scrollbar(announcement_container)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 公告文本区域
        self.announcement_text = tk.Text(
            announcement_container, 
            wrap=tk.WORD, 
            yscrollcommand=scrollbar.set,
            font=("Arial", 10),
            padx=5,
            pady=5,
            height=15
        )
        self.announcement_text.pack(fill=tk.BOTH, expand=True)
        
        # 配置滚动条
        scrollbar.config(command=self.announcement_text.yview)
        
        # 添加初始公告内容
        self.announcement_text.insert(tk.END, "正在加载公告...\n")
        self.announcement_text.config(state=tk.DISABLED)
        
        # 左侧功能区域内容
        # 标题
        title_frame = tk.Frame(left_frame)
        title_frame.pack(pady=10)
        tk.Label(title_frame, text=f"maimai启动器",  # 添加版本号
                font=("Arial", 16, "bold")).pack()
        
        # 权限提示
        tk.Label(
            title_frame, 
            text="(已获得管理员权限)", 
            font=("Arial", 8), 
            fg="green"
        ).pack()
        
        # 验证状态
        self.auth_status = tk.StringVar(value="请输入卡密进行验证")
        auth_label = tk.Label(left_frame, textvariable=self.auth_status, font=("Arial", 10), fg="blue")
        auth_label.pack(pady=5)
        
        # 版本信息
        self.version_label = tk.Label(left_frame, text="版本: 加载中...", font=("Arial", 10))
        self.version_label.pack(pady=5)
        
        # 进度条
        progress_frame = tk.Frame(left_frame)
        progress_frame.pack(fill=tk.X, padx=20, pady=10)
        self.progress = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL, length=500, mode='determinate')
        self.progress.pack()
        
        # 状态信息
        self.status_var = tk.StringVar(value="等待验证...")
        status_label = tk.Label(left_frame, textvariable=self.status_var, font=("Arial", 10))
        status_label.pack(pady=5)
        
        # 按钮
        button_frame = tk.Frame(left_frame)
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
        
        # 修改：将"查看日志"按钮改为"修改hosts"按钮
        self.modify_hosts_btn = tk.Button(button_row2, text="修改hosts", width=15, 
                                   command=self.modify_hosts, state=tk.DISABLED)
        self.modify_hosts_btn.pack(side=tk.LEFT, padx=10)
        
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
        
        # 在右下角添加闲鱼信息
        xianyu_frame = tk.Frame(self.root)
        xianyu_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        
        # 使用一个空标签占据左侧空间，使文本靠右
        tk.Label(xianyu_frame, text="", width=1).pack(side=tk.LEFT, expand=True)
        
        # 添加闲鱼信息文本
        xianyu_label = tk.Label(
            xianyu_frame, 
            text="闲鱼:多啦多啦", 
            font=("Arial", 8),
            fg="gray"
        )
        xianyu_label.pack(side=tk.RIGHT, padx=(0, 10))
    
    def modify_hosts(self):
        """修改hosts文件"""
        if not self.is_authenticated:
            messagebox.showwarning("未验证", "请先完成网络验证")
            return
            
        if not self.hosts_bat.exists():
            messagebox.showerror("错误", f"找不到hosts修改文件: {HOSTS_BAT}")
            return
        
        try:
            # 使用管理员权限运行hosts.bat
            bat_dir = os.path.dirname(self.hosts_bat)
            subprocess.Popen(
                [self.hosts_bat], 
                cwd=bat_dir,
                shell=True
            )
            messagebox.showinfo("操作成功", "hosts文件修改命令已执行，请查看命令行窗口确认结果。")
        except Exception as e:
            messagebox.showerror("操作失败", f"无法修改hosts文件: {str(e)}")
    
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
            # 创建自定义的HTTPS处理程序
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # 设置超时时间
            socket.setdefaulttimeout(15)
            
            # 发送请求
            request = urllib.request.Request(f"{SERVER_URL}{VERSION_FILE}")
            request.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
            
            with urllib.request.urlopen(request, context=ssl_context) as response:
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
        self.modify_hosts_btn.config(state=tk.DISABLED)
        
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
            
            # 创建自定义的HTTPS处理程序
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # 设置超时时间
            socket.setdefaulttimeout(30)
            
            # 下载URL
            download_url = f"{SERVER_URL}/update/{UPDATE_ZIP}"
            
            # 创建请求
            request = urllib.request.Request(download_url)
            request.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
            
            # 打开连接
            with urllib.request.urlopen(request, context=ssl_context) as response:
                # 获取文件大小
                total_size = int(response.headers.get('content-length', 0))
                block_size = 1024 * 8  # 8KB blocks
                count = 0
                
                # 打开文件准备写入
                with open(zip_path, 'wb') as f:
                    while True:
                        # 读取数据块
                        chunk = response.read(block_size)
                        if not chunk:
                            break
                        
                        # 写入文件
                        f.write(chunk)
                        
                        # 更新进度
                        count += 1
                        if total_size > 0:
                            percent = min(100, int(count * block_size * 100 / total_size))
                            self.progress['value'] = percent
                            self.status_var.set(f"下载中: {percent}%")
                            self.root.update_idletasks()
            
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
            self.modify_hosts_btn.config(state=tk.NORMAL)

    def check_launcher_update(self):
        """检查启动器更新"""
        if not self.is_authenticated:
            return
            
        threading.Thread(target=self._check_launcher_update_thread, daemon=True).start()

    def _check_launcher_update_thread(self):
        """检查启动器更新线程"""
        try:
            # 获取远程启动器版本信息
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            socket.setdefaulttimeout(15)
            
            # 发送请求
            request = urllib.request.Request(f"{SERVER_URL}{LAUNCHER_VERSION_FILE}")
            request.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
            
            with urllib.request.urlopen(request, context=ssl_context) as response:
                raw_data = response.read().decode('utf-8')
                remote_data = parse_json_response(raw_data)
                
            # 比较版本
            remote_version = remote_data.get("version")
            download_url = remote_data.get("url")
            
            if not remote_version or not download_url:
                print("无效的启动器版本信息")
                return
                
            # 版本号比较
            current_parts = list(map(int, LAUNCHER_VERSION.split('.')))
            remote_parts = list(map(int, remote_version.split('.')))
            
            # 确保版本号长度一致
            max_len = max(len(current_parts), len(remote_parts))
            current_parts += [0] * (max_len - len(current_parts))
            remote_parts += [0] * (max_len - len(remote_parts))
            
            # 比较每个部分
            for i in range(max_len):
                if remote_parts[i] > current_parts[i]:
                    # 发现新版本
                    self.root.after(0, lambda: self.prompt_launcher_update(remote_version, download_url))
                    return
                elif remote_parts[i] < current_parts[i]:
                    # 当前版本更高
                    return
            
            print("启动器已是最新版本")
        except Exception as e:
            print(f"检查启动器更新失败: {str(e)}")

    def prompt_launcher_update(self, remote_version, download_url):
        """提示用户更新启动器"""
        if not messagebox.askyesno("启动器更新", 
                                  f"发现新版本启动器 v{remote_version}\n是否立即更新?"):
            return
            
        # 开始更新
        self.status_var.set("正在更新启动器...")
        self.progress['value'] = 0
        threading.Thread(target=self._update_launcher_thread, 
                         args=(download_url,), daemon=True).start()

    def _update_launcher_thread(self, download_url):
        """启动器更新线程"""
        try:
            # 下载新启动器
            self.status_var.set("正在下载新启动器...")
            new_launcher_path = self.base_dir / "launcher_new.exe"
            
            # 创建自定义的HTTPS处理程序
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # 设置超时时间
            socket.setdefaulttimeout(30)
            
            # 创建请求
            request = urllib.request.Request(download_url)
            request.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
            
            # 打开连接
            with urllib.request.urlopen(request, context=ssl_context) as response:
                # 获取文件大小
                total_size = int(response.headers.get('content-length', 0))
                block_size = 1024 * 8  # 8KB blocks
                count = 0
                
                # 打开文件准备写入
                with open(new_launcher_path, 'wb') as f:
                    while True:
                        # 读取数据块
                        chunk = response.read(block_size)
                        if not chunk:
                            break
                        
                        # 写入文件
                        f.write(chunk)
                        
                        # 更新进度
                        count += 1
                        if total_size > 0:
                            percent = min(100, int(count * block_size * 100 / total_size))
                            self.progress['value'] = percent
                            self.status_var.set(f"下载启动器: {percent}%")
                            self.root.update_idletasks()
            
            # 创建更新批处理脚本
            bat_content = f"""
@echo off
echo 正在更新启动器...
timeout /t 3 /nobreak >nul
taskkill /F /IM "{os.path.basename(sys.executable)}" >nul 2>&1
move /Y "{new_launcher_path}" "{sys.executable}" >nul
echo 启动新版本...
start "" "{sys.executable}"
del "%~f0"
"""
            with open(self.launcher_update_bat, 'w') as f:
                f.write(bat_content)
            
            # 运行批处理脚本
            subprocess.Popen([self.launcher_update_bat], shell=True)
            
            # 退出当前程序
            self.root.destroy()
            sys.exit(0)
            
        except Exception as e:
            self.status_var.set(f"启动器更新失败: {str(e)}")
            messagebox.showerror("更新失败", f"启动器更新失败:\n{str(e)}")
            self.progress['value'] = 0

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
            # 修改点2：移除关闭窗口的代码，使启动器保持运行
            # 原代码：self.root.after(1000, self.root.destroy)
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