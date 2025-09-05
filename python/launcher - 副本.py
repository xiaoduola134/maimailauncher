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
import shutil
import ssl
from bs4 import BeautifulSoup
import http.cookiejar
import random
import logging
import traceback

# 设置日志记录
logging.basicConfig(
    filename='launcher.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

SERVER_IP = ""  
SERVER_URL = f"https://{SERVER_IP}/"  
UPDATE_PATH = r""
BAT_FILE = r""
ODD_BAT_FILE = r""
VERSION_FILE = ""
UPDATE_ZIP = ""
AUTH_API = ""
APP_ID = ""  

DEVICE_CODE_FILE = ""
LICENSE_FILE = ""  
LAUNCHER_UPDATE_FILE = ""
LAUNCHER_EXE_NAME = ""  

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36 Edg/92.0.902.55"
]

COOKIE_JAR = http.cookiejar.CookieJar()
COOKIE_PROCESSOR = urllib.request.HTTPCookieProcessor(COOKIE_JAR)
HTTPS_HANDLER = urllib.request.HTTPSHandler(context=ssl.create_default_context())

OPENER = urllib.request.build_opener(COOKIE_PROCESSOR, HTTPS_HANDLER)
urllib.request.install_opener(OPENER)

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1
    )

def get_device_id():
    if os.path.exists(DEVICE_CODE_FILE):
        try:
            with open(DEVICE_CODE_FILE, 'r') as f:
                return f.read().strip()
        except Exception as e:
            logger.error(f"读取设备ID失败: {str(e)}")
    
    device_id = str(uuid.uuid4())
    
    try:
        with open(DEVICE_CODE_FILE, 'w') as f:
            f.write(device_id)
    except Exception as e:
        logger.error(f"保存设备ID失败: {str(e)}")
    
    return device_id

def save_license(kami, device_id, vip_expiry):
    license_data = {
        "kami": kami,
        "device_id": device_id,
        "vip_expiry": vip_expiry,
        "timestamp": int(time.time())
    }
    try:
        with open(LICENSE_FILE, 'w') as f:
            json.dump(license_data, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"保存许可证失败: {str(e)}")
        return False

def load_license():
    if not os.path.exists(LICENSE_FILE):
        return None
    
    try:
        with open(LICENSE_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"加载许可证失败: {str(e)}")
    return None

def parse_json_response(response_text):
    try:
        return json.loads(response_text)
    except json.JSONDecodeError as e:
        try:
            # 尝试提取可能的JSON部分
            match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if match:
                fixed_json = match.group(0)
                return json.loads(fixed_json)
        except:
            pass
        
        try:
            # 尝试移除HTML标签
            clean_text = re.sub(r'<[^>]+>', '', response_text)
            return json.loads(clean_text)
        except:
            pass
        
        try:
            # 尝试移除BOM
            if response_text.startswith('\ufeff'):
                return json.loads(response_text[1:])
        except:
            pass
        
        logger.error(f"JSON解析失败: {str(e)}")
        raise e

def make_request(url, max_retries=3, timeout=15):
    retry_count = 0
    headers = {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0'
    }
    
    while retry_count < max_retries:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                content = response.read().decode('utf-8')
                
                # 处理Cloudflare挑战
                if "Cloudflare" in content and "challenge-form" in content:
                    logger.info("遇到Cloudflare挑战，尝试解决...")
                    soup = BeautifulSoup(content, 'html.parser')
                    jschl_vc = soup.find('input', {'name': 'jschl_vc'})['value']
                    pass_field = soup.find('input', {'name': 'pass'})['value']
                    
                    script = soup.find('script').text
                    match = re.search(r"setTimeout\(function\(\){\s*(var s,t,o,p,b,r,e,a,k,i,n,g,f.+?\r?\n[\s\S]+?a\.value\s*=.+?)\r?\n", script)
                    if not match:
                        raise Exception("找不到Cloudflare挑战脚本")
                    
                    js_answer = match.group(1)
                    js_answer = re.sub(r"a\.value\s*=\s*(parseInt\(.+?\)).+", r"\1", js_answer)
                    js_answer = re.sub(r"\s{3,}[a-z](?: = |\.).+", "", js_answer)
                    
                    try:
                        answer = eval(js_answer)
                    except Exception as e:
                        logger.warning(f"计算Cloudflare答案失败: {str(e)}")
                        match = re.search(r"parseInt\((.+?)\)", js_answer)
                        if match:
                            answer = int(match.group(1))
                        else:
                            answer = 0
                    
                    host = urllib.parse.urlparse(url).netloc
                    time.sleep(5)  # Cloudflare需要等待
                    
                    challenge_url = f"https://{host}/cdn-cgi/l/chk_jschl"
                    params = {
                        'jschl_vc': jschl_vc,
                        'pass': pass_field,
                        'jschl_answer': str(answer)
                    }
                    challenge_url += "?" + urllib.parse.urlencode(params)
                    
                    req = urllib.request.Request(challenge_url, headers=headers)
                    response = urllib.request.urlopen(req, timeout=timeout)
                    
                    # 更新cookie
                    for cookie in COOKIE_JAR:
                        if cookie.name.startswith('__cf'):
                            headers['Cookie'] = f"{cookie.name}={cookie.value}"
                    
                    retry_count += 1
                    continue
                
                return content
        except urllib.error.HTTPError as e:
            if e.code == 503 and 'Cloudflare' in e.headers.get('Server', ''):
                logger.info("遇到Cloudflare 503错误，重试...")
                time.sleep(3)
                retry_count += 1
                continue
            else:
                logger.error(f"HTTP错误: {e.code} {e.reason}")
                raise
        except Exception as e:
            logger.error(f"请求失败: {str(e)}")
            retry_count += 1
            time.sleep(2)
    
    raise Exception(f"请求失败，重试 {max_retries} 次后仍然无法连接")

class GameLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("maimai启动器")
        self.root.geometry("600x400") 
        self.root.resizable(False, False)
        
        # 设置关闭窗口事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # 检查管理员权限
        if not is_admin():
            self.show_admin_warning()
            return
        
        self.auth_data = None
        self.is_authenticated = False
        self.device_id = get_device_id()
        self.license_info = load_license()
        self.auth_win = None  # 添加对验证窗口的引用
        
        self.create_widgets()
        
        self.base_dir = Path(os.getcwd())
        self.update_dir = self.base_dir / UPDATE_PATH
        self.version_file = self.base_dir / VERSION_FILE
        self.bat_file = self.base_dir / BAT_FILE
        self.odd_bat_file = self.base_dir / ODD_BAT_FILE
        
        self.local_version = self.load_local_version()
        self.version_label.config(text=f"版本: v{self.local_version.get('version', '0.0.0')}")
        
        # 尝试自动验证
        if self.license_info:
            self.auth_status.set("尝试自动验证...")
            threading.Thread(target=self.try_auto_authentication, daemon=True).start()
        else:
            self.show_auth_window()
    
    def show_admin_warning(self):
        messagebox.showwarning(
            "权限提示", 
            "启动器需要管理员权限来运行ODD程序。\n请允许UAC提示以继续。"
        )
        run_as_admin()
        self.root.destroy()
    
    def create_widgets(self):
        title_frame = tk.Frame(self.root)
        title_frame.pack(pady=10)
        tk.Label(title_frame, text="maimai启动器", font=("Arial", 16, "bold")).pack()
        
        tk.Label(
            title_frame, 
            text="(已获得管理员权限)", 
            font=("Arial", 8), 
            fg="green"
        ).pack()
        
        # 状态显示
        self.auth_status = tk.StringVar(value="正在初始化...")
        auth_label = tk.Label(self.root, textvariable=self.auth_status, font=("Arial", 10), fg="blue")
        auth_label.pack(pady=5)
        
        self.version_label = tk.Label(self.root, text="版本: 加载中...", font=("Arial", 10))
        self.version_label.pack(pady=5)
        
        # 进度条
        progress_frame = tk.Frame(self.root)
        progress_frame.pack(fill=tk.X, padx=20, pady=10)
        self.progress = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL, length=500, mode='determinate')
        self.progress.pack()
        
        self.status_var = tk.StringVar(value="等待验证...")
        status_label = tk.Label(self.root, textvariable=self.status_var, font=("Arial", 10))
        status_label.pack(pady=5)
        
        # 按钮区域
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
        
        # 第三行按钮
        button_row3 = tk.Frame(button_frame)
        button_row3.pack(pady=5)
        
        self.buy_btn = tk.Button(button_row3, text="购买卡密", width=15, 
                                command=self.open_buy_page)
        self.buy_btn.pack(side=tk.LEFT, padx=10)
        
        self.retry_btn = tk.Button(button_row3, text="重新验证", width=15, 
                                  command=self.show_auth_window)
        self.retry_btn.pack(side=tk.LEFT, padx=10)
        
        # VIP信息和清除按钮
        self.vip_info = tk.StringVar(value="VIP状态: 未验证")
        vip_label = tk.Label(button_frame, textvariable=self.vip_info, font=("Arial", 10), fg="purple")
        vip_label.pack(pady=10)
        
        self.license_btn = tk.Button(button_frame, text="清除卡密", width=15, 
                                    command=self.clear_license, state=tk.DISABLED)
        self.license_btn.pack(pady=10)

    def try_auto_authentication(self):
        try:
            logger.info("尝试自动验证...")
            if not self.license_info:
                self.update_ui(lambda: self.auth_status.set("无保存的卡密信息"))
                self.update_ui(self.show_auth_window)
                return
                
            kami = self.license_info.get("kami", "")
            saved_device_id = self.license_info.get("device_id", "")
            vip_expiry = self.license_info.get("vip_expiry", "")
            
            if saved_device_id != self.device_id:
                self.update_ui(lambda: self.auth_status.set("设备ID变化，需要重新验证"))
                self.update_ui(self.show_auth_window)
                return
                
            if vip_expiry and str(vip_expiry).isdigit():
                expiry_time = int(vip_expiry)
                if time.time() > expiry_time:
                    self.update_ui(lambda: self.auth_status.set("卡密已过期，请重新验证"))
                    self.update_ui(self.show_auth_window)
                    return
            
            self.update_ui(lambda: self.auth_status.set("使用保存的卡密进行验证..."))
            self._authentication_thread(kami, None)
        except Exception as e:
            logger.error(f"自动验证失败: {str(e)}")
            self.update_ui(lambda: self.auth_status.set(f"自动验证失败: {str(e)}"))
            self.update_ui(self.show_auth_window)

    def show_auth_window(self):
        logger.info("显示验证窗口")
        # 如果验证窗口已存在，则先关闭
        if self.auth_win and self.auth_win.winfo_exists():
            self.auth_win.destroy()
        
        self.auth_win = tk.Toplevel(self.root)
        self.auth_win.title("卡密验证")
        self.auth_win.geometry("400x250")  
        self.auth_win.resizable(False, False)
        self.auth_win.grab_set()
        
        # 居中窗口
        self.auth_win.update_idletasks()
        width = self.auth_win.winfo_width()
        height = self.auth_win.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.auth_win.geometry(f'+{x}+{y}')
        
        # 设置关闭事件
        self.auth_win.protocol("WM_DELETE_WINDOW", self.on_auth_win_close)
        
        content_frame = tk.Frame(self.auth_win)
        content_frame.pack(pady=20, padx=20, fill=tk.BOTH, expand=True)
        
        # 显示设备ID
        tk.Label(content_frame, text=f"设备ID: {self.device_id}", font=("Arial", 9)).pack(anchor="w", pady=5)
        
        # 卡密输入框
        tk.Label(content_frame, text="请输入卡密:", font=("Arial", 10)).pack(anchor="w", pady=5)
        self.kami_entry = tk.Entry(content_frame, width=30, font=("Arial", 10))
        self.kami_entry.pack(fill=tk.X, pady=5)
        self.kami_entry.focus_set()
        
        # 预填充保存的卡密
        if self.license_info:
            kami = self.license_info.get("kami", "")
            if kami:
                self.kami_entry.insert(0, kami)
        
        # 记住卡密选项
        self.save_license_var = tk.BooleanVar(value=True)
        save_check = tk.Checkbutton(
            content_frame, 
            text="记住卡密信息", 
            variable=self.save_license_var,
            font=("Arial", 9))
        save_check.pack(anchor="w", pady=5)
        
        # 验证结果
        self.auth_result = tk.StringVar(value="")
        result_label = tk.Label(content_frame, textvariable=self.auth_result, font=("Arial", 9), fg="red")
        result_label.pack(pady=5)
        
        # 按钮区域
        btn_frame = tk.Frame(content_frame)
        btn_frame.pack(pady=10)
        
        auth_btn = tk.Button(btn_frame, text="验证卡密", width=15, 
                            command=lambda: self.perform_network_authentication(self.auth_win))
        auth_btn.pack(side=tk.LEFT, padx=10)
        
        close_btn = tk.Button(btn_frame, text="关闭", width=15, 
                             command=self.on_auth_win_close)
        close_btn.pack(side=tk.LEFT, padx=10)
        
        # 回车键绑定
        self.auth_win.bind('<Return>', lambda event: self.perform_network_authentication(self.auth_win))
    
    def on_auth_win_close(self):
        """处理验证窗口关闭事件"""
        if self.auth_win and self.auth_win.winfo_exists():
            self.auth_win.destroy()
        self.auth_win = None
    
    def perform_network_authentication(self, auth_win=None):
        kami = self.kami_entry.get().strip()
        if not kami:
            self.auth_result.set("卡密不能为空")
            return
        
        self.auth_result.set("正在验证...")
        
        # 禁用输入框和按钮
        self.kami_entry.config(state=tk.DISABLED)
        if auth_win:
            for widget in auth_win.winfo_children():
                if isinstance(widget, tk.Button):
                    widget.config(state=tk.DISABLED)
        
        threading.Thread(target=self._authentication_thread, args=(kami, auth_win), daemon=True).start()
    
        
        # 启动验证线程
        threading.Thread(target=self._authentication_thread, args=(kami, auth_win), daemon=True).start()
    
    def update_ui(self, func):
        """在主线程安全地更新UI"""
        self.root.after(0, func)
    
    def _authentication_thread(self, kami, auth_win=None):
        try:
            logger.info(f"开始验证卡密: {kami}")
            self.update_ui(lambda: self.auth_status.set("正在连接验证服务器..."))
            
            # 构建验证请求
            params = {
                "api": "kmlogon",
                "app": APP_ID,
                "kami": kami,
                "markcode": self.device_id
            }
            
            url = f"{AUTH_API}?{urlencode(params)}"
            logger.debug(f"验证URL: {url}")
            
            try:
                # 发送验证请求
                raw_data = make_request(url)
                logger.debug(f"验证响应: {raw_data[:200]}...")
                data = parse_json_response(raw_data)
            except Exception as e:
                # 主请求失败，尝试备用请求
                logger.warning(f"主验证请求失败: {str(e)}")
                try:
                    headers = {'User-Agent': random.choice(USER_AGENTS)}
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req, timeout=15) as response:
                        raw_data = response.read().decode('utf-8')
                        logger.debug(f"备用验证响应: {raw_data[:200]}...")
                        data = parse_json_response(raw_data)
                except Exception as e2:
                    error_msg = f"验证失败: {str(e)} (备用方法也失败: {str(e2)})"
                    logger.error(error_msg)
                    self.update_ui(lambda: self.auth_result.set(error_msg))
                    self.update_ui(lambda: self.auth_status.set(error_msg))
                    return
            
            # 检查验证结果
            if data.get("code") != 200:
                error_msg = self.get_error_message(data.get("code"))
                logger.error(f"验证失败: {error_msg}")
                self.update_ui(lambda: self.auth_result.set(f"验证失败: {error_msg}"))
                self.update_ui(lambda: self.auth_status.set(f"验证失败: {error_msg}"))
                return
            
            # 验证成功
            self.auth_data = data.get("msg", {})
            vip_expiry = self.auth_data.get("vip", "未知")
            logger.info(f"验证成功! VIP有效期: {vip_expiry}")
            
            # 更新UI状态
            self.update_ui(lambda: self.vip_info.set(f"VIP状态: 有效期至 {vip_expiry}"))
            self.update_ui(lambda: setattr(self, 'is_authenticated', True))
            self.update_ui(lambda: self.auth_status.set("验证成功!"))
            self.update_ui(self.activate_buttons)
            
            # 保存许可证信息
            if self.auth_win and self.save_license_var.get():
                save_success = save_license(kami, self.device_id, vip_expiry)
                if save_success:
                    self.update_ui(lambda: self.auth_result.set("卡密信息已保存"))
                    self.update_ui(lambda: self.license_btn.config(state=tk.NORMAL))
            
            # 关闭验证窗口
            if self.auth_win:
                self.update_ui(lambda: self.on_auth_win_close())
            
            # 检查更新
            self.update_ui(self.check_for_updates)
        
        except urllib.error.HTTPError as e:
            error_msg = f"HTTP错误: {e.code} {e.reason}"
            logger.error(error_msg)
            self.update_ui(lambda: self.auth_result.set(error_msg))
            self.update_ui(lambda: self.auth_status.set(error_msg))
        except urllib.error.URLError as e:
            error_msg = f"网络错误: {str(e.reason)}"
            logger.error(error_msg)
            self.update_ui(lambda: self.auth_result.set(error_msg))
            self.update_ui(lambda: self.auth_status.set(error_msg))
        except json.JSONDecodeError as e:
            error_msg = f"JSON解析错误: {str(e)}"
            logger.error(error_msg)
            self.update_ui(lambda: self.auth_result.set(error_msg))
            self.update_ui(lambda: self.auth_status.set(error_msg))
        except Exception as e:
            error_msg = f"验证失败: {str(e)}"
            logger.error(error_msg)
            self.update_ui(lambda: self.auth_result.set(error_msg))
            self.update_ui(lambda: self.auth_status.set(error_msg))
        finally:
            # 安全恢复UI状态 - 只操作主窗口的UI
            self.update_ui(lambda: self.restore_auth_win_ui())

    def restore_auth_win_ui(self):
        """安全恢复验证窗口的UI状态"""
        try:
            # 检查验证窗口是否存在且有效
            if self.auth_win and self.auth_win.winfo_exists():
                # 恢复输入框
                self.kami_entry.config(state=tk.NORMAL)
                
                # 恢复按钮
                for widget in self.auth_win.winfo_children():
                    if isinstance(widget, tk.Button):
                        widget.config(state=tk.NORMAL)
        except tk.TclError as e:
            # 忽略无效窗口错误
            logger.warning(f"恢复验证窗口UI时忽略错误: {str(e)}")
        except Exception as e:
            logger.error(f"恢复验证窗口UI时出错: {str(e)}")

    def activate_buttons(self):
        """激活所有功能按钮"""
        try:
            logger.info("激活功能按钮")
            self.start_btn.config(state=tk.NORMAL)
            self.odd_btn.config(state=tk.NORMAL)
            self.update_btn.config(state=tk.NORMAL)
            self.logout_btn.config(state=tk.NORMAL)
            self.license_btn.config(state=tk.NORMAL)
            self.root.update_idletasks()  # 强制刷新UI
        except Exception as e:
            logger.error(f"激活按钮时出错: {str(e)}")
    
    def clear_license(self):
        try:
            if os.path.exists(LICENSE_FILE):
                os.remove(LICENSE_FILE)
            self.license_info = None
            self.license_btn.config(state=tk.DISABLED)
            self.auth_status.set("卡密信息已清除")
            messagebox.showinfo("成功", "保存的卡密信息已清除")
            logger.info("卡密信息已清除")
        except Exception as e:
            messagebox.showerror("错误", f"清除卡密失败: {str(e)}")
            logger.error(f"清除卡密失败: {str(e)}")
    
    def get_error_message(self, error_code):
        """根据错误代码返回错误消息"""
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
    
    def open_buy_page(self):
        webbrowser.open("https://m.tb.cn/h.hYesG5B?tk=qva9Vs7587S")
        logger.info("打开购买页面")
    
    def load_local_version(self):
        """加载本地版本信息"""
        version_data = {"version": "0.0.0", "files": {}}
        
        if self.version_file.exists():
            try:
                with open(self.version_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载本地版本失败: {str(e)}")
        return version_data

    def save_local_version(self, version_data):
        """保存本地版本信息"""
        try:
            with open(self.version_file, 'w', encoding='utf-8') as f:
                json.dump(version_data, f, indent=2)
        except Exception as e:
            logger.error(f"保存本地版本失败: {str(e)}")

    def get_remote_version(self):
        """获取远程版本信息"""
        try:
            url = f"{SERVER_URL}{VERSION_FILE}"
            raw_data = make_request(url)
            return parse_json_response(raw_data)
        except Exception as e:
            self.update_ui(lambda: self.status_var.set(f"无法获取服务器版本: {str(e)}"))
            logger.error(f"获取远程版本失败: {str(e)}")
            return None

    def check_for_updates(self):
        """检查更新"""
        if not self.is_authenticated:
            self.update_ui(lambda: self.status_var.set("请先完成验证"))
            return
            
        threading.Thread(target=self._check_updates_thread, daemon=True).start()

    def _check_updates_thread(self):
        """检查更新线程"""
        logger.info("开始检查更新")
        self.update_ui(lambda: self.start_btn.config(state=tk.DISABLED))
        self.update_ui(lambda: self.update_btn.config(state=tk.DISABLED))
        self.update_ui(lambda: self.status_var.set("正在检查更新..."))
        
        remote_version = self.get_remote_version()
        if not remote_version:
            self.update_ui(lambda: self.status_var.set("连接服务器失败"))
            # 恢复按钮状态
            self.update_ui(lambda: self.start_btn.config(state=tk.NORMAL))
            self.update_ui(lambda: self.update_btn.config(state=tk.NORMAL))
            return
        
        if remote_version["version"] == self.local_version["version"]:
            self.update_ui(lambda: self.status_var.set("游戏已是最新版本"))
            self.update_ui(lambda: self.version_label.config(text=f"版本: v{self.local_version['version']}"))
            # 恢复按钮状态
            self.update_ui(lambda: self.start_btn.config(state=tk.NORMAL))
            self.update_ui(lambda: self.update_btn.config(state=tk.NORMAL))
        else:
            self.update_ui(lambda: self.status_var.set(f"发现新版本 v{remote_version['version']}"))
            self.update_game(remote_version)
        
        # 检查启动器更新
        self.check_launcher_update()
    
    def check_launcher_update(self):
        """检查启动器更新"""
        try:
            launcher_version_url = f"{SERVER_URL}launcher_version.json"
            raw_data = make_request(launcher_version_url)
            launcher_data = parse_json_response(raw_data)
            
            current_version = getattr(sys, '_MEIPASS', os.getcwd())
            if launcher_data.get("version") != current_version:
                self.update_ui(lambda: self.status_var.set("发现启动器更新，正在下载..."))
                self.update_launcher()
        except Exception as e:
            logger.error(f"检查启动器更新失败: {str(e)}")
        finally:
            # 确保无论是否更新启动器都恢复按钮状态
            self.update_ui(lambda: self.start_btn.config(state=tk.NORMAL))
            self.update_ui(lambda: self.update_btn.config(state=tk.NORMAL))
    
    def update_launcher(self):
        """更新启动器"""
        try:
            logger.info("开始更新启动器")
            launcher_update_url = f"{SERVER_URL}{LAUNCHER_UPDATE_FILE}"
            update_zip_path = os.path.join(os.getcwd(), LAUNCHER_UPDATE_FILE)
            
            def update_progress(count, block_size, total_size):
                percent = int(count * block_size * 100 / total_size)
                self.update_ui(lambda: self.status_var.set(f"下载启动器更新: {percent}%"))
            
            headers = {'User-Agent': random.choice(USER_AGENTS)}
            req = urllib.request.Request(launcher_update_url, headers=headers)
            
            with urllib.request.urlopen(req) as response:
                total_size = int(response.headers.get('Content-Length', 0))
                block_size = 8192
                count = 0
                with open(update_zip_path, 'wb') as f:
                    while True:
                        buffer = response.read(block_size)
                        if not buffer:
                            break
                        f.write(buffer)
                        count += len(buffer)
                        update_progress(count, 1, total_size)
            
            temp_dir = os.path.join(os.getcwd(), "temp_launcher_update")
            os.makedirs(temp_dir, exist_ok=True)
            
            with zipfile.ZipFile(update_zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            new_launcher_path = None
            for root, dirs, files in os.walk(temp_dir):
                if LAUNCHER_EXE_NAME in files:
                    new_launcher_path = os.path.join(root, LAUNCHER_EXE_NAME)
                    break
            
            if new_launcher_path:
                current_launcher_path = sys.executable
                shutil.copy2(new_launcher_path, current_launcher_path)
                
                shutil.rmtree(temp_dir)
                os.remove(update_zip_path)
                
                self.update_ui(lambda: self.status_var.set("启动器更新完成，请重新启动"))
                messagebox.showinfo("更新成功", "启动器已成功更新，请重新启动应用")
                logger.info("启动器更新完成")
            else:
                self.update_ui(lambda: self.status_var.set("未找到启动器更新文件"))
                logger.warning("未找到启动器更新文件")
        
        except Exception as e:
            self.update_ui(lambda: self.status_var.set(f"启动器更新失败: {str(e)}"))
            logger.error(f"启动器更新失败: {str(e)}")
        finally:
            # 确保更新完成后恢复按钮状态
            self.update_ui(lambda: self.start_btn.config(state=tk.NORMAL))
            self.update_ui(lambda: self.update_btn.config(state=tk.NORMAL))

    def update_game(self, remote_version=None):
        """更新游戏"""
        if not self.is_authenticated:
            self.update_ui(lambda: self.status_var.set("请先完成验证"))
            return
            
        if not remote_version:
            remote_version = self.get_remote_version()
            if not remote_version:
                self.update_ui(lambda: self.status_var.set("无法获取更新信息"))
                return
        
        self.update_ui(lambda: self.start_btn.config(state=tk.DISABLED))
        self.update_ui(lambda: self.update_btn.config(state=tk.DISABLED))
        self.update_ui(lambda: self.odd_btn.config(state=tk.DISABLED))
        
        threading.Thread(target=self._update_thread, args=(remote_version,), daemon=True).start()

    def force_update(self):
        """强制更新"""
        self.update_ui(lambda: self.status_var.set("开始强制更新..."))
        self.update_game()

    def _update_thread(self, remote_version):
        """更新线程"""
        try:
            logger.info(f"开始更新游戏到版本: {remote_version['version']}")
            self.update_dir.mkdir(parents=True, exist_ok=True)
            
            self.update_ui(lambda: self.status_var.set("正在下载更新..."))
            zip_path = self.base_dir / UPDATE_ZIP
            
            def update_progress(count, block_size, total_size):
                percent = int(count * block_size * 100 / total_size)
                self.update_ui(lambda: self.progress.config(value=percent))
                self.update_ui(lambda: self.status_var.set(f"下载中: {percent}%"))
            
            update_url = f"{SERVER_URL}{UPDATE_ZIP}"
            headers = {'User-Agent': random.choice(USER_AGENTS)}
            req = urllib.request.Request(update_url, headers=headers)
            
            with urllib.request.urlopen(req) as response:
                total_size = int(response.headers.get('Content-Length', 0))
                block_size = 8192
                count = 0
                with open(zip_path, 'wb') as f:
                    while True:
                        buffer = response.read(block_size)
                        if not buffer:
                            break
                        f.write(buffer)
                        count += len(buffer)
                        update_progress(count, 1, total_size)
            
            self.update_ui(lambda: self.status_var.set("正在解压文件..."))
            self.update_ui(lambda: self.progress.config(value=0))
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                total_files = len(zip_ref.infolist())
                for i, file in enumerate(zip_ref.infolist()):
                    if file.filename.endswith('/'):
                        continue
                    
                    percent = int(i * 100 / total_files)
                    self.update_ui(lambda: self.progress.config(value=percent))
                    self.update_ui(lambda: self.status_var.set(f"解压中: {file.filename}"))
                    
                    zip_ref.extract(file, self.update_dir)
            
            self.local_version = remote_version
            self.save_local_version(remote_version)
            
            self.update_ui(lambda: self.status_var.set("更新完成!"))
            self.update_ui(lambda: self.version_label.config(text=f"版本: v{self.local_version['version']}"))
            self.update_ui(lambda: self.progress.config(value=100))
            
            if zip_path.exists():
                os.remove(zip_path)
            
            self.update_ui(lambda: messagebox.showinfo("更新完成", "游戏已成功更新到最新版本!"))
            logger.info("游戏更新完成")
            
        except Exception as e:
            self.update_ui(lambda: self.status_var.set(f"更新失败: {str(e)}"))
            self.update_ui(lambda: messagebox.showerror("更新错误", f"更新过程中发生错误:\n{str(e)}"))
            logger.error(f"更新失败: {str(e)}")
        finally:
            self.update_ui(lambda: self.start_btn.config(state=tk.NORMAL))
            self.update_ui(lambda: self.update_btn.config(state=tk.NORMAL))
            self.update_ui(lambda: self.odd_btn.config(state=tk.NORMAL))

    def start_game(self):
        """启动游戏"""
        if not self.is_authenticated:
            messagebox.showwarning("未验证", "请先完成网络验证")
            return
            
        if not self.bat_file.exists():
            messagebox.showerror("错误", f"找不到启动文件: {BAT_FILE}")
            return
        
        try:
            logger.info("启动游戏")
            bat_dir = os.path.dirname(self.bat_file)
            subprocess.Popen(
                [self.bat_file], 
                cwd=bat_dir,
                shell=True
            )
            self.root.after(1000, self.root.destroy)
        except Exception as e:
            messagebox.showerror("启动失败", f"无法启动游戏: {str(e)}")
            logger.error(f"启动游戏失败: {str(e)}")

    def start_odd(self):
        """启动ODD"""
        if not self.is_authenticated:
            messagebox.showwarning("未验证", "请先完成网络验证")
            return
            
        if not self.odd_bat_file.exists():
            messagebox.showerror("错误", f"找不到ODD启动文件: {ODD_BAT_FILE}")
            return
        
        try:
            logger.info("启动ODD")
            bat_dir = os.path.dirname(self.odd_bat_file)
            subprocess.Popen(
                [self.odd_bat_file], 
                cwd=bat_dir,
                shell=True
            )
            messagebox.showinfo("启动成功", "ODD程序正在运行中...")
        except Exception as e:
            messagebox.showerror("启动失败", f"无法启动ODD程序: {str(e)}")
            logger.error(f"启动ODD失败: {str(e)}")

    def show_logs(self):
        """显示更新日志"""
        if not self.is_authenticated:
            messagebox.showwarning("未验证", "请先完成网络验证")
            return
            
        changelog = self.local_version.get("changelog", "暂无更新日志")
        logger.info("显示更新日志")
        
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
    
    def on_close(self):
        """处理主窗口关闭事件"""
        self.root.destroy()
        logger.info("启动器已关闭")

if __name__ == "__main__":
    # 检查管理员权限
    if not is_admin():
        # 创建临时根窗口
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(
            "权限提升", 
            "启动器需要管理员权限运行，请允许UAC提示。"
        )
        run_as_admin()
        root.destroy()
        sys.exit(0)
    
    # 创建主窗口
    root = tk.Tk()
    try:
        app = GameLauncher(root)
        root.mainloop()
    except Exception as e:
        logger.error(f"启动器崩溃: {str(e)}\n{traceback.format_exc()}")
        messagebox.showerror("严重错误", f"启动器遇到意外错误:\n{str(e)}")