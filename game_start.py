import os
import time
import subprocess
import threading
from tkinter import messagebox


def start_game_process(app):
    exe = app.exec_path_var.get()
    args = app.exec_args_var.get()
    if not exe:
        messagebox.showwarning("Execution Pipeline", "No binary context path declared inside environment.")
        return
    
    try:
        exe_clean = os.path.normpath(exe.strip('"'))
        game_folder = os.path.dirname(exe_clean)
        bat_args = args.replace('%', '%%')
        
        bat_path = os.path.abspath("launch_game.bat")
        
        with open(bat_path, "w", encoding="utf-8") as bat_file:
            bat_file.write("@echo off\n")
            bat_file.write(f'cd /d "{game_folder}"\n')
            if bat_args:
                bat_file.write(f'start "" "{exe_clean}" {bat_args}\n')
            else:
                bat_file.write(f'start "" "{exe_clean}"\n')
        
        cmd = f'explorer "{bat_path}"'
        subprocess.Popen(cmd, shell=True)
        
        def cleanup_bat():
            time.sleep(1.5)
            try:
                if os.path.exists(bat_path):
                    os.remove(bat_path)
            except Exception:
                pass

        threading.Thread(target=cleanup_bat, daemon=True).start()
        
        app.status_var.set("Target game execution environment spawned via script wrapper.")
    except Exception as e:
        messagebox.showerror("Execution Pipeline Critical", f"Failed to instantiate target process tree:\n{e}")
        
        def cleanup_bat():
            time.sleep(1.5) # Odotetaan hetki että peli ehtii käynnistyä
            try:
                if os.path.exists(bat_path):
                    os.remove(bat_path)
            except Exception:
                pass # Jos tiedosto on vielä lukittu, jätetään se rauhaan

        threading.Thread(target=cleanup_bat, daemon=True).start()
        
        app.status_var.set("Target game execution environment spawned via script wrapper.")
    except Exception as e:
        messagebox.showerror("Execution Pipeline Critical", f"Failed to instantiate target process tree:\n{e}")