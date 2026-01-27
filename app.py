import customtkinter as ctk
import os
import threading
import asyncio
import discord
import webbrowser
import sys
import requests
import ctypes
import subprocess
import base64
import platform
from datetime import datetime
from discord import app_commands
from discord.ext import commands
import obsws_python as obs

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.backends import default_backend
except ImportError:
    pass

if sys.platform == "win32":
    kernel32 = ctypes.WinDLL('kernel32')
    user32 = ctypes.WinDLL('user32')
    hWnd = kernel32.GetConsoleWindow()
    if hWnd:
        user32.ShowWindow(hWnd, 0)

try:
    import pystray
    from pystray import MenuItem as item
    from PIL import Image, ImageDraw
except ImportError:
    pass

def is_admin():
    try:
        if sys.platform == 'win32':
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        else:
            return os.getuid() == 0
    except AttributeError:
        return False

def elevate_privileges():
    if is_admin():
        return

    if sys.platform == 'win32':
        if getattr(sys, 'frozen', False):
            path = sys.executable
            args = " ".join(sys.argv[1:])
        else:
            path = sys.executable
            args = f'"{sys.argv[0]}" ' + " ".join(sys.argv[1:])
        
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", path, args, None, 1
        )
        sys.exit(0)
    else:
        try:
            args = ['sudo', sys.executable] + sys.argv
            os.execvpe('sudo', args, os.environ)
        except Exception:
            print("Failed to elevate privileges. Please run the script as root/sudo.")
            sys.exit(1)

APP_NAME = "StreamCast"
VERSION = "v1.1.4"
VERSION_URL = "https://stream-cast.netlify.app/version.txt"
UPDATE_URL = "https://stream-cast.netlify.app/"
CURRENT_YEAR = datetime.now().year
COPYRIGHT = f"© {CURRENT_YEAR} Niels Coert. All rights reserved."

# Editable Safety Tips list for easy future updates
SAFETY_TIPS = [
    "ℹ️ Tip: Place the bot only in a Discord channel dedicated to staff to avoid unauthorized use.",
]

# Set the appearance mode and default color theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class SecretManager:
    def __init__(self):
        self._key = self._generate_hardware_bound_key()

    def _get_hardware_id(self):
        try:
            if sys.platform == "win32":
                import winreg
                registry = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
                key = winreg.OpenKey(registry, r"SOFTWARE\Microsoft\Cryptography")
                machine_id = winreg.QueryValueEx(key, "MachineGuid")[0]
                return machine_id.encode()
            else:
                return (platform.node() + platform.processor()).encode()
        except:
            return b"streamcast-static-salt-fallback-unique-id"

    def _generate_hardware_bound_key(self):
        salt = b'streamcast_secure_v1_salt'
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(self._get_hardware_id()))
        return key

    def encrypt_file(self, file_path):
        if not os.path.exists(file_path):
            return
        
        f = Fernet(self._key)
        with open(file_path, "rb") as file:
            file_data = file.read()
        
        encrypted_data = f.encrypt(file_data)
        with open(file_path, "wb") as file:
            file.write(encrypted_data)

    def decrypt_content(self, file_path):
        if not os.path.exists(file_path):
            return ""
        
        f = Fernet(self._key)
        with open(file_path, "rb") as file:
            encrypted_data = file.read()
        
        try:
            decrypted_data = f.decrypt(encrypted_data)
            return decrypted_data.decode("utf-8")
        except Exception:
            try:
                return encrypted_data.decode("utf-8")
            except:
                return ""

class ContentWindow(ctk.CTkToplevel):
    def __init__(self, master, title, content_text, extra_content_callback=None):
        super().__init__(master)
        self.title(title)
        self.geometry("550x600")
        self.attributes("-topmost", True)
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text=title)
        self.scroll_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        content_lbl = ctk.CTkLabel(
            self.scroll_frame, 
            text=content_text, 
            justify="left", 
            wraplength=480, 
            font=ctk.CTkFont(size=13)
        )
        content_lbl.pack(padx=15, pady=15)

        if extra_content_callback:
            extra_content_callback(self.scroll_frame)

        self.close_button = ctk.CTkButton(self, text="Close", command=self.destroy)
        self.close_button.grid(row=1, column=0, pady=15)

class AboutWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title(f"About {APP_NAME}")
        self.geometry("450x580")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        
        self.grid_columnconfigure(0, weight=1)
        
        self.logo_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=60))
        self.logo_label.pack(pady=(30, 0))
        
        self.title_label = ctk.CTkLabel(self, text=APP_NAME, font=ctk.CTkFont(size=24, weight="bold"))
        self.title_label.pack()
        
        self.ver_label = ctk.CTkLabel(self, text=f"Version {VERSION}", text_color="gray")
        self.ver_label.pack(pady=(0, 20))

        self.nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.nav_frame.pack(fill="x", padx=40)
        
        self.create_nav_item("", "User Guide", self.open_user_guide)
        self.create_nav_item("", "Terms of Service", self.open_tos)
        self.create_nav_item("", "Privacy Policy", self.open_privacy)
        self.create_nav_item("", "Acknowledgements", self.open_credits)

        self.reset_btn = ctk.CTkButton(
            self, 
            text=" Delete & Reset App", 
            command=self.confirm_reset, 
            fg_color="#990000", 
            hover_color="#cc0000",
            height=35
        )
        self.reset_btn.pack(pady=(20, 0))

        self.copyright_label = ctk.CTkLabel(self, text=COPYRIGHT, font=ctk.CTkFont(size=10), text_color="gray50")
        self.copyright_label.pack(side="bottom", pady=15)

    def create_nav_item(self, icon, text, command):
        btn = ctk.CTkButton(
            self.nav_frame, 
            text=f"{icon}  {text}", 
            command=command, 
            anchor="w", 
            fg_color="gray25", 
            hover_color="gray35",
            height=40
        )
        btn.pack(fill="x", pady=5)

    def confirm_reset(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Confirm Reset")
        dialog.geometry("400x200")
        dialog.resizable(False, False)
        dialog.attributes("-topmost", True)
        dialog.grid_columnconfigure((0, 1), weight=1)

        msg = ctk.CTkLabel(
            dialog, 
            text="Are you sure you want to delete all settings?\n\nThis will remove your Bot Token, OBS Password,\nand Moderator list. The app will restart.",
            wraplength=350
        )
        msg.grid(row=0, column=0, columnspan=2, pady=20, padx=20)

        cancel_btn = ctk.CTkButton(dialog, text="Cancel", command=dialog.destroy, fg_color="gray30")
        cancel_btn.grid(row=1, column=0, padx=10, pady=10, sticky="ew")

        confirm_btn = ctk.CTkButton(dialog, text="Yes, Reset", command=self.perform_reset, fg_color="#990000", hover_color="#cc0000")
        confirm_btn.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

    def perform_reset(self):
        if os.path.exists(".env"):
            try:
                os.remove(".env")
            except Exception as e:
                print(f"Error deleting .env: {e}")
        
        os.execl(sys.executable, sys.executable, *sys.argv)

    def open_user_guide(self):
        content = (
            "USER GUIDE\n\n"
            "1. OUR PURPOSE\n"
            f"We designed {APP_NAME} as a bridge between Discord and OBS. Our tool allows you to delegate production tasks "
            "(like switching scenes) to your trusted Discord moderators so you can focus on your gameplay or content.\n\n"
            "2. HOW OUR BOT WORKS\n"
            "The app runs a Discord bot on your local computer. When a moderator uses a command in Discord, "
            "our bot sends a signal to your local OBS via the WebSocket connection to execute the action.\n\n"
            "3. AVAILABLE COMMANDS\n"
            "• /switch [scene_name]: Changes the current OBS scene. Auto-completes with your available scenes.\n"
            "• /start_stream: Starts the OBS stream if it's not already running.\n"
            "• /stop_stream: Stops the OBS stream if it's currently active.\n"
            "• /addmod [@user]: (Owner Only) Adds a user as a moderator.\n"
            "• /remmod [@user]: (Owner Only) Removes a user from the moderator list.\n"
            "• /listmod: Lists all current moderators and their status.\n\n"
            "4. PERMISSIONS\n"
            "• Owner: The Discord Server Owner has full control by default. They can add or remove moderators.\n"
            "• Moderator: Users added via /addmod can use the /switch command. They cannot modify other moderators.\n\n"
            "5. STREAM CONTROL\n"
            "• Use '/start_stream' to begin your stream when you're ready to go live. The bot will check if a stream is already running.\n"
            "• Use '/stop_stream' to end your stream when you're done. The bot will verify the stream status first.\n\n"
            "6. SCENE SWITCHING\n"
            "When using the '/switch' command, a list of your current OBS scenes will appear as suggestions. "
            "Simply select one and the bot will update your stream layout instantly. The bot caches your scene list "
            "for quick access, and you can refresh it by starting to type the scene name.\n\n"
            "7. TROUBLESHOOTING\n"
            "• If scenes don't appear in the autocomplete, ensure OBS is running with WebSocket server enabled.\n"
            "• If you get permission errors, verify the user has been properly added as a moderator with /addmod.\n"
            "• The bot needs 'Send Messages' and 'View Channel' permissions in your Discord server."
        )

        def add_safety_tips(parent_frame):
            tips_frame = ctk.CTkFrame(parent_frame, fg_color="gray20", corner_radius=10)
            tips_frame.pack(fill="x", padx=15, pady=(0, 15))
            
            for tip in SAFETY_TIPS:
                tip_lbl = ctk.CTkLabel(
                    tips_frame, 
                    text=tip, 
                    justify="left", 
                    wraplength=440, 
                    font=ctk.CTkFont(size=12, slant="italic"),
                    text_color="#3b8ed0" 
                )
                tip_lbl.pack(padx=10, pady=10)

        ContentWindow(self, "User Guide", content, extra_content_callback=add_safety_tips)

    def open_tos(self):
        content = (
            "TERMS OF SERVICE\n\n"
            "1. ACCEPTANCE OF TERMS\n"
            f"By accessing or using {APP_NAME} (the Software), you agree to be bound by these Terms of Service. "
            "If you do not agree to these terms, please do not use the Software.\n\n"
            "2. LICENSE GRANT\n"
            f"We grant you a limited, non-exclusive, non-transferable license to use {APP_NAME} for personal "
            "or community streaming management purposes in accordance with these terms.\n\n"
            "3. USER RESPONSIBILITIES\n"
            "• You are responsible for all activities that occur under your Discord bot account.\n"
            "• You must ensure that your use of the Software complies with all applicable laws and regulations.\n"
            "• You are responsible for maintaining the confidentiality of your OBS WebSocket password and Discord bot token.\n\n"
            "4. PROHIBITED USES\n"
            "You agree not to use the Software to:\n"
            "• Harass, abuse, or harm others\n"
            "• Gain unauthorized access to OBS instances you don't own or have permission to manage\n"
            "• Disrupt or interfere with the security or accessibility of the Software\n"
            "• Use the Software for any illegal or unauthorized purpose\n\n"
            "5. LIMITATION OF LIABILITY\n"
            f"To the maximum extent permitted by law, {APP_NAME} and its developers shall not be liable for any "
            "indirect, incidental, special, consequential, or punitive damages, or any loss of profits or revenues, "
            "whether incurred directly or indirectly, or any loss of data, use, goodwill, or other intangible losses, "
            "resulting from your access to or use of the Software.\n\n"
            "6. DISCLAIMER OF WARRANTIES\n"
            "The Software is provided as is without warranties of any kind, whether express or implied, "
            "including but not limited to implied warranties of merchantability, fitness for a particular purpose, "
            "or non-infringement.\n\n"
            "7. CHANGES TO TERMS\n"
            f"We reserve the right to modify these terms at any time. Your continued use of {APP_NAME} after such "
            "changes constitutes your acceptance of the new terms."
        )
        ContentWindow(self, "Terms of Service", content)

    def open_privacy(self):
        content = (
            "PRIVACY POLICY\n\n"
            "1. INFORMATION WE COLLECT\n"
            f"{APP_NAME} handles the following types of information:\n\n"
            "• Discord Bot Token: Required to authenticate with Discord's API.\n"
            "• OBS WebSocket Password: Required to communicate with your local OBS instance.\n"
            "• Moderator Information: User IDs and names of Discord users granted moderator permissions.\n\n"
            "2. HOW WE USE YOUR INFORMATION\n"
            "• Your Discord Bot Token is used exclusively to authenticate with Discord's API.\n"
            "• Your OBS WebSocket Password is used only to establish a connection with your local OBS instance.\n"
            "• Moderator information is used to control access to the bot's functionality.\n\n"
            "3. DATA STORAGE AND SECURITY\n"
            "• All sensitive information is stored securely in an encrypted .env file in the application directory.\n"
            "• The encryption key is dynamically derived from your local hardware and cannot be extracted manually.\n"
            "• No data is transmitted to our servers or any third parties.\n"
            "• We recommend the following security practices:\n"
            "  - Keep your .env file secure and never share it publicly\n"
            "  - Use strong, unique passwords for your OBS WebSocket connection\n"
            "  - Only grant moderator permissions to trusted users\n\n"
            "4. DATA DELETION\n"
            "You can delete all stored data by:\n"
            "• Deleting the .env file from the application directory\n"
            "• Using the /remmod command to remove moderator permissions\n\n"
            "5. CHILDREN'S PRIVACY\n"
            f"{APP_NAME} is not intended for use by children under the age of 13. We do not knowingly collect "
            "personal information from children under 13. If we learn we have collected personal information from "
            "a child under 13, we will take steps to delete the information as soon as possible.\n\n"
            "6. CHANGES TO THIS POLICY\n"
            "We may update our Privacy Policy from time to time. We will notify you of any changes by posting the new "
            "Privacy Policy in the application. You are advised to review this Privacy Policy periodically for any changes."
        )
        ContentWindow(self, "Privacy Policy", content)

    def open_credits(self):
        win = ContentWindow(self, "Acknowledgements", 
            "• Discord Dev Portal\n"
            "• Niels Coert\n"
            "• OBS Project"
        )
        
        link_frame = ctk.CTkFrame(win.scroll_frame, fg_color="transparent")
        link_frame.pack(pady=10)
        
        links = [
            ("StreamCast", "https://stream-cast.netlify.app"),
            ("OBS Project", "https://obsproject.com"),
            ("Discord Devs", "https://discord.com/developers"),
            ("GitHub Repo", "https://github.com/The-BitWalker/StreamCast")
        ]
        
        for name, url in links:
            l_btn = ctk.CTkButton(link_frame, text=name, width=100, command=lambda u=url: webbrowser.open(u))
            l_btn.pack(side="left", padx=5, pady=5)

class SetupGuideWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Setup Instructions")
        self.geometry("650x600")
        self.attributes("-topmost", True)
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="Step-by-Step Setup")
        self.scroll_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.display_setup_guide()

        self.close_button = ctk.CTkButton(self, text="Got it!", command=self.destroy, width=200)
        self.close_button.grid(row=1, column=0, pady=15)

    def add_step(self, title, text, link=None, is_warning=False):
        frame = ctk.CTkFrame(self.scroll_frame, fg_color="gray20" if is_warning else "transparent")
        frame.pack(fill="x", pady=8, padx=5)
        
        title_color = "#ff4444" if is_warning else "#3b8ed0"
        title_prefix = " " if is_warning else ""
        
        title_lbl = ctk.CTkLabel(frame, text=f"{title_prefix}{title}", font=ctk.CTkFont(size=16, weight="bold"), text_color=title_color)
        title_lbl.pack(anchor="w", padx=10, pady=(5, 2))
        
        content_lbl = ctk.CTkLabel(frame, text=text, justify="left", wraplength=550, font=ctk.CTkFont(size=13))
        content_lbl.pack(anchor="w", pady=(0, 10 if link else 5), padx=10)
        
        if link:
            link_lbl = ctk.CTkLabel(frame, text=" Click here for official instructions", text_color="#1f538d", cursor="hand2", font=ctk.CTkFont(size=13, underline=True))
            link_lbl.pack(anchor="w", padx=10, pady=(0, 10))
            link_lbl.bind("<Button-1>", lambda e: webbrowser.open(link))

    def display_setup_guide(self):
        self.add_step("What is this?", f"We built {APP_NAME} to let your Discord moderators control your OBS scenes. It connects your Discord server to your streaming software safely.")
        self.add_step("1. Create Your Bot", "A Discord Bot is like a virtual assistant for your server. Create one in our recommended portal.", "https://discord.com/developers/applications")
        self.add_step("2. Get Your Secret Token", "In the Bot section, click 'Reset Token' to see your password. Keep it secret!")
        self.add_step("3. Invite the Bot", "Go to OAuth2 -> URL Generator. Check 'bot' and 'applications.commands'.")
        self.add_step("4. Install OBS WebSocket", "OBS 28+ has this built-in. Check Tools -> WebSocket Server Settings.", "https://obsproject.com/forum/resources/obs-websocket-remote-control-of-obs-studio-from-websockets.466/")
        self.add_step("SECURITY WARNING", "Never share your Bot Token or OBS Password with anyone.", is_warning=True)

class ControlPanel(ctk.CTkToplevel):
    def __init__(self, master, token, obs_password):
        super().__init__(master)
        self.token = token
        self.obs_password = obs_password
        
        self.title(f"{APP_NAME} - Active")
        self.geometry("400x380")
        self.resizable(False, False)
        
        self.after(10, self.center_window)
        
        self.grid_columnconfigure(0, weight=1)

        self.header_label = ctk.CTkLabel(self, text="StreamCast", font=ctk.CTkFont(size=20, weight="bold"))
        self.header_label.pack(pady=(30, 10))

        self.bot_identity_label = ctk.CTkLabel(self, text="Bot: Not Connected", font=ctk.CTkFont(size=14, weight="bold"), text_color="gray")
        self.bot_identity_label.pack(pady=5)

        self.status_label = ctk.CTkLabel(self, text="Status: Connecting...", text_color="orange", font=ctk.CTkFont(size=13))
        self.status_label.pack(pady=5)

        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.pack(pady=20)

        self.about_btn = ctk.CTkButton(self.btn_frame, text=" About & Info", command=self.open_about, fg_color="#1f538d", width=160)
        self.about_btn.pack(pady=5)

        self.protocol("WM_DELETE_WINDOW", self.hide_window)

        self.bot = None
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.start_async_loop, daemon=True).start()

        self.tray_icon = None
        threading.Thread(target=self.setup_tray, daemon=True).start()

    def create_tray_image(self):
        width = 64
        height = 64
        image = Image.new('RGB', (width, height), color=(31, 83, 141)) # Blue background
        dc = ImageDraw.Draw(image)
        dc.rectangle([width // 4, height // 4, width * 3 // 4, height * 3 // 4], fill=(255, 255, 255))
        return image

    def setup_tray(self):
        menu = (
            item('Restore Window', self.show_window, default=True),
            item('Quit Completely', self.quit_application)
        )
        self.tray_icon = pystray.Icon("StreamCast", self.create_tray_image(), "StreamCast - Active", menu)
        self.tray_icon.run()

    def hide_window(self):
        self.withdraw()

    def show_window(self, icon=None, item=None):
        self.deiconify()
        self.lift()
        self.focus_force()

    def quit_application(self, icon=None, item=None):
        if self.tray_icon:
            self.tray_icon.stop()
        self.master.destroy()
        sys.exit(0)

    def center_window(self):
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

    def open_about(self):
        AboutWindow(self)

    def start_async_loop(self):
        asyncio.set_event_loop(self.loop)
        intents = discord.Intents.default()

        class StreamBot(commands.Bot):
            def __init__(self, obs_pwd, moderators=None):
                super().__init__(command_prefix="!", intents=intents)
                self.obs_password = obs_pwd
                self.moderator_ids = set()
                self.moderator_names = {}
                self.scene_cache = []
                if moderators:
                    for mod_id, name in moderators.items():
                        self.moderator_ids.add(int(mod_id))
                        self.moderator_names[int(mod_id)] = name

            async def setup_hook(self):
                await self.tree.sync()

            def is_owner_or_mod(self, interaction: discord.Interaction):
                is_owner = interaction.user.id == interaction.guild.owner_id
                is_mod = interaction.user.id in self.moderator_ids
                return is_owner or is_mod

            def get_obs_scenes(self):
                try:
                    client = obs.ReqClient(host='localhost', port=4455, password=self.obs_password)
                    resp = client.get_scene_list()
                    scenes = [s['sceneName'] for s in resp.scenes]
                    self.scene_cache = scenes
                    return scenes
                except Exception:
                    return []

        moderators = {}
        if os.path.exists(".env"):
            try:
                decrypted_content = self.master.secret_mgr.decrypt_content(".env")
                lines = decrypted_content.splitlines()
                for line in lines:
                    if line.startswith("MODERATORS=") and "=" in line:
                        mods_str = line.split("=", 1)[1].strip()
                        if mods_str:
                            for mod_pair in mods_str.split(","):
                                if ":" in mod_pair:
                                    mod_id, mod_name = mod_pair.split(":", 1)
                                    moderators[mod_id] = mod_name
            except Exception:
                pass

        self.bot = StreamBot(self.obs_password, moderators)

        @self.bot.tree.command(name="addmod", description="Promote a user to moderator (Owner Only)")
        async def addmod(interaction: discord.Interaction, user: discord.Member):
            if interaction.user.id != interaction.guild.owner_id:
                await interaction.response.send_message(" This command is restricted to the Server Owner.", ephemeral=True)
                return

            self.bot.moderator_ids.add(user.id)
            self.bot.moderator_names[user.id] = user.display_name
            
            current_mods = []
            for mid, mname in self.bot.moderator_names.items():
                current_mods.append((mid, mname))
            self.master.save_to_env(self.token, self.obs_password, current_mods)
            
            await interaction.response.send_message(f" {user.mention} is now a StreamCast Moderator.", ephemeral=False)

        @self.bot.tree.command(name="remmod", description="Remove moderator privileges (Owner Only)")
        async def remmod(interaction: discord.Interaction, user: discord.Member):
            if interaction.user.id != interaction.guild.owner_id:
                await interaction.response.send_message(" This command is restricted to the Server Owner.", ephemeral=True)
                return

            if user.id in self.bot.moderator_ids:
                self.bot.moderator_ids.remove(user.id)
                self.bot.moderator_names.pop(user.id, None)
                
                current_mods = []
                for mid, mname in self.bot.moderator_names.items():
                    current_mods.append((mid, mname))
                self.master.save_to_env(self.token, self.obs_password, current_mods)
                
                await interaction.response.send_message(f" {user.display_name} has been removed from moderators.", ephemeral=False)
            else:
                await interaction.response.send_message("User is not a moderator.", ephemeral=True)

        @self.bot.tree.command(name="listmod", description="Show all StreamCast moderators")
        async def listmod(interaction: discord.Interaction):
            if not self.bot.moderator_ids:
                await interaction.response.send_message("No moderators have been added yet.", ephemeral=True)
                return
            
            mod_list = "\n".join([f"• {name}" for name in self.bot.moderator_names.values()])
            embed = discord.Embed(title="StreamCast Moderators", description=mod_list, color=discord.Color.blue())
            await interaction.response.send_message(embed=embed)

        @self.bot.tree.command(name="switch", description="Change the active OBS scene")
        @app_commands.describe(scene="The name of the scene to switch to")
        async def switch(interaction: discord.Interaction, scene: str):
            if not self.bot.is_owner_or_mod(interaction):
                await interaction.response.send_message(" You don't have permission to control the stream.", ephemeral=True)
                return

            try:
                client = obs.ReqClient(host='localhost', port=4455, password=self.obs_password)
                client.set_current_program_scene(scene)
                await interaction.response.send_message(f" Successfully switched to: **{scene}**")
            except Exception as e:
                await interaction.response.send_message(f" Failed to switch scene. Is OBS WebSocket active? Error: {e}", ephemeral=True)

        @switch.autocomplete('scene')
        async def scene_autocomplete(interaction: discord.Interaction, current: str):
            if not self.bot.scene_cache:
                self.bot.get_obs_scenes()
            
            return [
                app_commands.Choice(name=scene, value=scene)
                for scene in self.bot.scene_cache if current.lower() in scene.lower()
            ][:25]

        @self.bot.tree.command(name="start_stream", description="Starts the OBS live stream")
        async def start_stream(interaction: discord.Interaction):
            if not self.bot.is_owner_or_mod(interaction):
                await interaction.response.send_message(" Permission denied.", ephemeral=True)
                return
            
            try:
                client = obs.ReqClient(host='localhost', port=4455, password=self.obs_password)
                status = client.get_stream_status()
                if status.output_active:
                    await interaction.response.send_message(" Stream is already live!")
                else:
                    client.start_stream()
                    await interaction.response.send_message(" Starting the stream...")
            except Exception as e:
                await interaction.response.send_message(f" Error communicating with OBS: {e}", ephemeral=True)

        @self.bot.tree.command(name="stop_stream", description="Stops the active OBS live stream")
        async def stop_stream(interaction: discord.Interaction):
            if not self.bot.is_owner_or_mod(interaction):
                await interaction.response.send_message(" Permission denied.", ephemeral=True)
                return
            
            try:
                client = obs.ReqClient(host='localhost', port=4455, password=self.obs_password)
                status = client.get_stream_status()
                if not status.output_active:
                    await interaction.response.send_message(" No active stream detected.")
                else:
                    client.stop_stream()
                    await interaction.response.send_message(" Stream stopped.")
            except Exception as e:
                await interaction.response.send_message(f" Error communicating with OBS: {e}", ephemeral=True)

        @self.bot.event
        async def on_ready():
            self.status_label.configure(text="Status: Online & Listening", text_color="green")
            self.bot_identity_label.configure(text=f"Bot: {self.bot.user.name}", text_color="white")
            print(f"Logged in as {self.bot.user}")

        async def run_bot():
            try:
                await self.bot.start(self.token)
            except discord.LoginFailure:
                self.status_label.configure(text="Status: Invalid Bot Token", text_color="#ff4444")
            except Exception as e:
                self.status_label.configure(text=f"Status: Error - {e}", text_color="#ff4444")

        self.loop.run_until_complete(run_bot())

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.secret_mgr = SecretManager()
        
        self.title(f"{APP_NAME} {VERSION}")
        self.geometry("500x520")
        self.resizable(False, False)
        
        self.center_window()

        self.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(self, text=APP_NAME, font=ctk.CTkFont(size=28, weight="bold"))
        self.title_label.pack(pady=(40, 5))

        self.tagline_label = ctk.CTkLabel(self, text="Remote Scene Control via Discord", font=ctk.CTkFont(size=14), text_color="gray")
        self.tagline_label.pack(pady=(0, 30))

        self.input_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.input_frame.pack(padx=50, fill="x")

        self.discord_label = ctk.CTkLabel(self.input_frame, text="Discord Bot Token:", font=ctk.CTkFont(size=13, weight="bold"))
        self.discord_label.pack(anchor="w", pady=(10, 5))
        self.discord_entry = ctk.CTkEntry(self.input_frame, placeholder_text="MTE0MzIx...", show="*", height=35)
        self.discord_entry.pack(fill="x")

        self.obs_label = ctk.CTkLabel(self.input_frame, text="OBS WebSocket Password:", font=ctk.CTkFont(size=13, weight="bold"))
        self.obs_label.pack(anchor="w", pady=(15, 5))
        self.obs_entry = ctk.CTkEntry(self.input_frame, placeholder_text="YourPassword123", show="*", height=35)
        self.obs_entry.pack(fill="x")

        self.message_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=12))
        self.message_label.pack(pady=10)

        self.submit_button = ctk.CTkButton(self, text="Start StreamCast", command=self.submit_event, font=ctk.CTkFont(size=14, weight="bold"), height=40)
        self.submit_button.pack(pady=10)

        self.guide_button = ctk.CTkButton(self, text="How to get these?", command=self.open_guide, fg_color="gray25", hover_color="gray35")
        self.guide_button.pack(pady=5)

        self.info_button = ctk.CTkButton(self, text="About & Privacy", command=self.open_about, fg_color="transparent", text_color="gray", hover_color="gray20")
        self.info_button.pack(side="bottom", pady=15)

        self.stored_token = ""
        self.stored_obs_pwd = ""
        self.load_from_env()

        threading.Thread(target=self.check_for_updates, daemon=True).start()

    def center_window(self):
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

    def check_for_updates(self):
        try:
            r = requests.get(VERSION_URL, timeout=5)
            if r.status_code == 200:
                remote_ver = r.text.strip()
                if remote_ver != VERSION:
                    self.after(2000, lambda: self.show_update_notice(remote_ver))
        except Exception:
            pass

    def show_update_notice(self, new_ver):
        notice = ctk.CTkToplevel(self)
        notice.title("Update Available")
        notice.geometry("350x180")
        notice.attributes("-topmost", True)
        
        lbl = ctk.CTkLabel(notice, text=f"A new version is available: {new_ver}\n(Current: {VERSION})", wraplength=300)
        lbl.pack(pady=20)
        
        btn = ctk.CTkButton(notice, text="Download Update", command=lambda: webbrowser.open(UPDATE_URL))
        btn.pack(pady=10)

    def open_guide(self):
        SetupGuideWindow(self)

    def open_about(self):
        AboutWindow(self)

    def load_from_env(self):
        if os.path.exists(".env"):
            try:
                decrypted_content = self.secret_mgr.decrypt_content(".env")
                lines = decrypted_content.splitlines()
                env_vars = {}
                for line in lines:
                    if "=" in line:
                        k, v = line.split("=", 1)
                        env_vars[k.strip()] = v.strip()
                
                self.stored_token = env_vars.get("DISCORD_TOKEN", "")
                self.stored_obs_pwd = env_vars.get("OBS_PASSWORD", "")
                
                if self.stored_token:
                    self.discord_entry.insert(0, self.stored_token)
                if self.stored_obs_pwd:
                    self.obs_entry.insert(0, self.stored_obs_pwd)
                
                if self.stored_token:
                    self.message_label.configure(text="Stored credentials found. Starting...", text_color="gray")
                    self.after(100, self.open_control_panel)
            except Exception:
                pass

    def save_to_env(self, token, password, moderators=None):
        try:
            with open(".env", "w", encoding="utf-8") as f:
                f.write(f"DISCORD_TOKEN={token}\nOBS_PASSWORD={password}\n")
                if moderators is not None:
                    mods_str = ",".join([f"{mod_id}:{name}" for mod_id, name in moderators])
                    f.write(f"MODERATORS={mods_str}\n")
            
            self.secret_mgr.encrypt_file(".env")
            return True
        except IOError:
            return False

    def open_control_panel(self):
        self.withdraw()
        self.control_panel = ControlPanel(self, self.stored_token, self.stored_obs_pwd)

    def submit_event(self):
        d_token = self.discord_entry.get().strip()
        o_pwd = self.obs_entry.get().strip()
        if not d_token:
            self.message_label.configure(text="Error: Discord Token is required!", text_color="#ff4444")
            return
        if self.save_to_env(d_token, o_pwd):
            self.stored_token, self.stored_obs_pwd = d_token, o_pwd
            self.message_label.configure(text="Success! Starting host...", text_color="green")
            self.after(500, self.open_control_panel)
        else:
            self.message_label.configure(text="Error: Could not save .env file", text_color="#ff4444")

if __name__ == "__main__":
    elevate_privileges()
    
    app = App()
    app.mainloop()