import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import subprocess
import sys
from pathlib import Path
import os
import threading

REPO_ROOT = Path(__file__).parent
CONFIG = REPO_ROOT / 'pipeline_config.yaml'
SCRIPT_DIR = REPO_ROOT / "analysis_scripts"
ASSETS = REPO_ROOT / "assets"

try:
    import yaml
except Exception:
    yaml = None

class PipelineGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('EVOKE - Evoked Orofacial Behavior Analysis')
        self.geometry('650x540')
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TLabelframe.Label",
                font=("Segoe UI", 12, "bold"))
        
        self.create_widgets()

    def create_widgets(self):
        pad = {'padx': 2, 'pady': 2}
        banner = ttk.Frame(self)
        banner.grid(row=0, column=0, columnspan=4, sticky="ew", pady=10)
        # ---- Load logo ----
        logo_path = ASSETS / "evoke_logo.png"
        img = Image.open(logo_path)

        # resize (tweak as needed)
        img = img.resize((270,90))
        self.logo_img = ImageTk.PhotoImage(img)

        logo_label = ttk.Label(banner, image=self.logo_img)
        logo_label.grid(row=0, column=0, rowspan=2, padx=10)
        
        # ---- Title ----
        title = ttk.Label(
            banner,
            text="Author: Darian Mohsenin",
            font=("Segoe UI", 10, "bold")
        )
        title.grid(row=0, column=2, padx=(150, 0), sticky="w")

        # ---- Subtitle ----
        subtitle = ttk.Label(
            banner,
            text="University of California, San Francisco",
            font=("Segoe UI", 10)
        )
        subtitle.grid(row=1, column=2, padx=(125, 0), pady=(0, 50), sticky="w")

        # --- SECTION 1: GLOBAL PROJECT SETTINGS ---
        settings_frame = ttk.LabelFrame(self, text="Project Selection", padding=10)
        settings_frame.grid(column=0, row=2, columnspan=4, sticky='ew', padx=10, pady=5)

        ttk.Label(settings_frame, text='Project:').grid(column=0, row=0, sticky='w', **pad)
        self.project_var = tk.StringVar(value='TN')
        ttk.Combobox(settings_frame, textvariable=self.project_var, values=['TN','FMO'], width=8, state='readonly').grid(column=1, row=0, sticky='w')

        ttk.Label(settings_frame, text='Experiment ID:').grid(column=2, row=0, sticky='w', **pad)
        self.exp_entry = ttk.Entry(settings_frame, width=10)
        self.exp_entry.grid(column=3, row=0, sticky='w')

        # --- SECTION 2: GROUPED PHASES ---
        phase_frame = ttk.LabelFrame(self, text="Pipeline Phases (Grouped)", padding=10)
        phase_frame.grid(column=0, row=3, columnspan=4, sticky='ew', padx=10, pady=5)

        ttk.Button(phase_frame, text='File Transfer (Steps 1-2)', command=self.on_run_pre).grid(column=0, row=0, **pad)
        ttk.Button(phase_frame, text='Manual Frame Correction (Step 3)', command=self.on_run_step3).grid(column=1, row=0, **pad)
        ttk.Button(phase_frame, text='Evoked Analysis (Steps 4-8)', command=self.on_run_post).grid(column=2, row=0, **pad)

        # --- SECTION 3: INDIVIDUAL STEPS ---
        steps_frame = ttk.LabelFrame(self, text="Individual Steps", padding=10)
        steps_frame.grid(column=0, row=4, columnspan=4, sticky='ew', padx=10, pady=5)

        ttk.Button(steps_frame, text='Step 1: Transfer', 
                   command=lambda: self._run_single_script('Step1_transfer.py')).grid(column=0, row=0, **pad)
        ttk.Button(steps_frame, text='Step 2: Compile', 
                   command=lambda: self._run_single_script('Step2_data_compiler.py')).grid(column=1, row=0, **pad)
        ttk.Button(steps_frame, text='Step 3: Frame Correction', 
                   command=self.on_run_step3).grid(column=2, row=0, **pad)

        ttk.Button(steps_frame, text='Step 4: Clip Trim', 
                   command=lambda: self._run_single_script('Step4_clip_trim.py')).grid(column=0, row=1, **pad)
        ttk.Button(steps_frame, text='Step 5: DLC Label', 
                   command=lambda: self._run_single_script('Step5_DLC_labelling.py')).grid(column=1, row=1, **pad)
        ttk.Button(steps_frame, text='Step 6: Metrics', 
                   command=lambda: self._run_single_script('Step6_metrics.py')).grid(column=2, row=1, **pad)

        ttk.Button(steps_frame, text='Step 7: Experiment .csv compiler', 
                   command=lambda: self._run_single_script('Step7_experiment_compiler.py')).grid(column=0, row=2, **pad)
        ttk.Button(steps_frame, text='Step 8: Features', 
                   command=lambda: self._run_single_script('Step8_features.py')).grid(column=1, row=2, **pad)

        # --- SECTION 4: UTILITIES & STATUS ---
        ttk.Button(self, text='Open Config YAML', command=self.open_config_file).grid(column=0, row=5, sticky='w', padx=10, pady=10)
        
        self.status = ttk.Label(self, text='Ready', foreground="blue")
        self.status.grid(column=0, row=6, columnspan=4, sticky='w', padx=10, pady=5)

    def _run_batch_scripts(self, script_list):
        """Runs a list of scripts sequentially in one background thread."""
        project = self.project_var.get()
        expnum = self.exp_entry.get().strip()
        
        if not expnum:
            messagebox.showerror('Missing Exp ID', 'Please enter an Experiment ID.')
            return

        proj_map = {'TN': '1', 'FMO': '2'}
        env = os.environ.copy()
        env['EVOKED_PIPELINE_PROJECT'] = proj_map.get(project, '1')
        env['EVOKED_PIPELINE_EXPID'] = expnum

        def run_thread():
            for script_name in script_list:
                script_path = SCRIPT_DIR / script_name
                if not script_path.exists():
                    self.status.config(text=f'Error: {script_name} missing', foreground="red")
                    return # Stop the batch if a file is missing

                try:
                    self.status.config(text=f'Running {script_name}...', foreground="orange")
                    # Log terminal prints to a .txt file for debugging
                    log_dir = REPO_ROOT / "logs" / project
                    log_dir.mkdir(parents=True, exist_ok=True)

                    log_path = log_dir / f"Exp{expnum}_evoked_analysis_log.txt"
                    with open(log_path, "a") as log_file:
                        subprocess.run(
                            [sys.executable, "-u", str(script_path)],
                            env=env,
                            stdout=log_file,
                            stderr=log_file,
                            text=True
                        )
                    
                except subprocess.CalledProcessError:
                    self.status.config(text=f'Failed at {script_name}', foreground="red")
                    return # Stop the batch if a script fails

            self.status.config(text=f'Batch Finished Successfully', foreground="green")

        threading.Thread(target=run_thread, daemon=True).start()

    def _run_single_script(self, script_name):
        """Helper to run a specific script with env variables and background waiting"""
        project = self.project_var.get()
        expnum = self.exp_entry.get().strip()
        
        if not expnum:
            messagebox.showerror('Missing Exp ID', 'Please enter an Experiment ID.')
            return

        proj_map = {'TN': '1', 'FMO': '2'}
        env = os.environ.copy()
        env['EVOKED_PIPELINE_PROJECT'] = proj_map.get(project, '1')
        env['EVOKED_PIPELINE_EXPID'] = expnum

        script_path = SCRIPT_DIR / script_name
        if not script_path.exists():
            messagebox.showerror('File Not Found', f'Could not find {script_name}')
            return

        # Start the script in a background thread to keep UI responsive
        def run_thread():
            try:
                self.status.config(text=f'Running {script_name}...', foreground="orange")

                log_dir = REPO_ROOT / "logs" / project
                log_dir.mkdir(parents=True, exist_ok=True)

                log_path = log_dir / f"Exp{expnum}_evoked_analysis_log.txt"
                
                # MANUAL SCRIPT 3 live terminal
                if script_name == "Step3_FrameCorrection.py":
                    subprocess.Popen(
                    f'start cmd /k "{sys.executable} {script_path}"',
                    shell=True,
                    env=env
                )

                else:
                    with open(log_path, "a") as log_file:
                        log_file.write(f"\n===== Running {script_name} =====\n")

                        subprocess.run(
                            [sys.executable, "-u", str(script_path)],
                            env=env,
                            stdout=log_file,
                            stderr=log_file,
                            text=True
                        )

                        log_file.write(f"===== Finished {script_name} =====\n")

                self.status.config(text=f'Finished {script_name}', foreground="green")

            except subprocess.CalledProcessError:
                self.status.config(text=f'Failed {script_name}', foreground="red")
            except Exception:
                self.status.config(text='Launch failed', foreground="red")

        threading.Thread(target=run_thread, daemon=True).start()
    
    def on_run_pre(self):
        self._run_batch_scripts(['Step1_transfer.py', 'Step2_data_compiler.py'])

    def on_run_post(self):
        scripts = [
            'Step4_clip_trim.py', 'Step5_DLC_labelling.py',
            'Step6_metrics.py', 'Step7_experiment_compiler.py',
            'Step8_features.py'
        ]
        self._run_batch_scripts(scripts)

    def on_run_step3(self):
        self._run_single_script('Step3_FrameCorrection.py')

    def open_config_file(self):
        try:
            if sys.platform.startswith('win'):
                os.startfile(CONFIG)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', CONFIG])
            else:
                subprocess.Popen(['xdg-open', CONFIG])
        except Exception as e:
            messagebox.showerror('Open failed', str(e))

if __name__ == '__main__':
    app = PipelineGUI()
    app.mainloop()