import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk
import subprocess
import sys
from pathlib import Path
import os
import threading
import re

REPO_ROOT = Path(__file__).parent
CONFIG = REPO_ROOT / 'pipeline_config.yaml'
SCRIPT_DIR = REPO_ROOT / "analysis_scripts"
ASSETS = REPO_ROOT / "assets"

PROJECT_CONFIG_KEYS = {'TN': 1, 'FMO': 2}
PROJECT_FOLDER_NAMES = {'TN': 'TN_project', 'FMO': 'FMO_project'}
PROJECT_METADATA_FILES = {
    'TN': 'OPexperiment_metadata.csv',
    'FMO': 'TMJexperiment_metadata.csv',
}


def set_windows_app_identity():
    """Give EVOKE its own taskbar identity instead of Python's generic one."""
    if not sys.platform.startswith('win'):
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            'UCSF.EVOKE.BehaviorAnalysisPipeline'
        )
    except (AttributeError, OSError):
        # The window can still launch if an older Windows version lacks this API.
        pass


def initialize_project_data_root(selected_root, project, config_path=CONFIG):
    """Create one project's data tree and point its YAML settings at it."""
    if yaml is None:
        raise RuntimeError('PyYAML is required to update pipeline_config.yaml.')
    if project not in PROJECT_CONFIG_KEYS:
        raise ValueError(f'Unknown project: {project}')

    selected_root = Path(selected_root).expanduser().resolve()
    project_root = selected_root / PROJECT_FOLDER_NAMES[project]
    paths = {
        'evoked_root': project_root / 'data' / 'evoked' / 'raw_files',
        'spontaneous_root': project_root / 'data' / 'spontaneous' / 'raw_files',
        'metadata_path': project_root / 'data' / PROJECT_METADATA_FILES[project],
        'evoked_processed_root': project_root / 'data' / 'evoked' / 'processed_files',
        'evoked_analysis_root': project_root / 'analysis' / 'evoked' / 'large_csv_files',
        'evoked_summary_root': project_root / 'analysis' / 'evoked' / 'summary_csv_files',
    }

    # metadata_path is a future CSV file; create its parent, not an empty CSV.
    for key, path in paths.items():
        (path.parent if key == 'metadata_path' else path).mkdir(parents=True, exist_ok=True)

    with open(config_path, 'r', encoding='utf-8') as config_file:
        config_text = config_file.read()
    config_data = yaml.safe_load(config_text) or {}
    projects = config_data.get('projects', {})
    project_key = PROJECT_CONFIG_KEYS[project]
    project_config = projects.get(project_key) or projects.get(str(project_key))
    if project_config is None:
        raise KeyError(f'Project {project_key} is missing from {config_path}.')

    # Replace only this project's values so comments and hand-edited settings survive.
    project_header = re.search(rf'(?m)^  {project_key}:\s*$', config_text)
    if project_header is None:
        raise KeyError(f'Project {project_key} block is missing from {config_path}.')
    next_project = re.search(r'(?m)^  [^ #\r\n][^:\r\n]*:\s*$', config_text[project_header.end():])
    block_end = (
        project_header.end() + next_project.start()
        if next_project is not None
        else len(config_text)
    )
    project_block = config_text[project_header.end():block_end]
    for key, path in paths.items():
        pattern = rf'(?m)^(    {re.escape(key)}:)\s*.*$'
        project_block, count = re.subn(
            pattern,
            lambda match, value=path.as_posix(): f'{match.group(1)} "{value}"',
            project_block,
        )
        if count != 1:
            raise KeyError(f'Expected one {key} entry in project {project_key}; found {count}.')

    updated_text = config_text[:project_header.end()] + project_block + config_text[block_end:]
    yaml.safe_load(updated_text)  # Do not write malformed YAML.
    with open(config_path, 'w', encoding='utf-8') as config_file:
        config_file.write(updated_text)

    return project_root, paths

try:
    import yaml
except Exception:
    yaml = None

class PipelineGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('EVOKE - Evoked Orofacial Behavior Analysis')
        icon_path = ASSETS / 'evoke.png'
        self.icon_img = tk.PhotoImage(file=str(icon_path))
        self.iconphoto(True, self.icon_img)
        self.geometry('650x580')
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Header.TFrame", background="#efbee7")
        style.configure("Header.TLabel", background="#efbee7")
        style.configure(
            "Section.TLabelframe.Label",
            background="#ec769a",
            font=("Segoe UI", 10, "bold"),
        )
        
        self.create_widgets()

    def create_widgets(self):
        pad = {'padx': 2, 'pady': 2}
        banner = ttk.Frame(self, style="Header.TFrame")
        banner.grid(row=0, column=0, columnspan=4, sticky="ew", pady=10)
        # ---- Load logo ----
        logo_path = ASSETS / "evoke_logo.png"
        img = Image.open(logo_path)

        # resize (tweak as needed)
        img = img.resize((270,90))
        self.logo_img = ImageTk.PhotoImage(img)

        logo_label = ttk.Label(banner, image=self.logo_img, style="Header.TLabel")
        logo_label.grid(row=0, column=0, rowspan=2, padx=10)
        
        # ---- Title ----
        title = ttk.Label(
            banner,
            text="Author: Darian Mohsenin",
            style="Header.TLabel",
            font=("Segoe UI", 10, "bold")
        )
        title.grid(row=0, column=2, padx=(180, 0), sticky="w")

        # ---- Subtitle ----
        subtitle = ttk.Label(
            banner,
            text="University of California, San Francisco",
            style="Header.TLabel",
            font=("Segoe UI", 10)
        )
        subtitle.grid(row=1, column=2, padx=(125, 0), pady=(0, 50), sticky="w")

        # --- SECTION 1: GLOBAL PROJECT SETTINGS ---
        settings_frame = ttk.LabelFrame(
            self, text="Project Selection", padding=10, style="Section.TLabelframe"
        )
        settings_frame.grid(column=0, row=2, columnspan=4, sticky='ew', padx=10, pady=5)

        ttk.Label(settings_frame, text='Project:').grid(column=0, row=0, sticky='w', **pad)
        self.project_var = tk.StringVar(value='TN')
        ttk.Combobox(settings_frame, textvariable=self.project_var, values=['TN','FMO'], width=8, state='readonly').grid(column=1, row=0, sticky='w')

        ttk.Label(settings_frame, text='Experiment ID:').grid(column=2, row=0, sticky='w', **pad)
        self.exp_entry = ttk.Entry(settings_frame, width=10)
        self.exp_entry.grid(column=3, row=0, sticky='w')

        ttk.Button(
            settings_frame,
            text="Initialize Data Root",
            command=self.setup_data_root,
        ).grid(column=4, row=0, padx=(220, 0), sticky='w')


        # --- SECTION 2: GROUPED PHASES ---
        phase_frame = ttk.LabelFrame(
            self, text="Pipeline Phases (Grouped)", padding=10,
            style="Section.TLabelframe"
        )
        phase_frame.grid(column=0, row=3, columnspan=4, sticky='ew', padx=10, pady=5)

        ttk.Button(phase_frame, text='File Transfer (Steps 1-2)', command=self.on_run_pre).grid(column=0, row=0, **pad)
        ttk.Button(phase_frame, text='Manual Frame Correction (Step 3)', command=self.on_run_step3).grid(column=1, row=0, **pad)
        ttk.Button(phase_frame, text='Evoked Analysis (Steps 4-8)', command=self.on_run_post).grid(column=2, row=0, **pad)

        # --- SECTION 3: INDIVIDUAL STEPS ---
        steps_frame = ttk.LabelFrame(
            self, text="Individual Steps", padding=10, style="Section.TLabelframe"
        )
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

        # --- SECTION 4: FOLDERS & CONFIGURATION ---
        folders_frame = ttk.LabelFrame(
            self,
            text="Folders and Configuration",
            padding=10,
            style="Section.TLabelframe",
        )
        folders_frame.grid(
            column=0, row=5, columnspan=4, sticky='ew', padx=10, pady=5
        )
        ttk.Button(
            folders_frame, text='Open Config YAML', command=self.open_config_file
        ).grid(column=0, row=0, **pad)
        ttk.Button(
            folders_frame, text='Open Output Folder', command=self.open_output_folder
        ).grid(column=1, row=0, **pad)
        ttk.Button(
            folders_frame, text='Open Log Folder', command=self.open_log_folder
        ).grid(column=2, row=0, **pad)
        
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

    def setup_data_root(self):
        project = self.project_var.get()
        selected_root = filedialog.askdirectory(
            parent=self,
            title=f'Select the folder that will contain {PROJECT_FOLDER_NAMES[project]}',
            mustexist=True,
        )
        if not selected_root:
            return

        try:
            project_root, _ = initialize_project_data_root(selected_root, project)
        except Exception as exc:
            self.status.config(text='Data root initialization failed', foreground='red')
            messagebox.showerror('Initialization failed', str(exc), parent=self)
            return

        self.status.config(
            text=f'{project} data root initialized: {project_root}',
            foreground='green',
        )
        messagebox.showinfo(
            'Data root initialized',
            f'Created the {project} folder structure at:\n{project_root}\n\n'
            'pipeline_config.yaml has been updated.',
            parent=self,
        )

    def open_config_file(self):
        self._open_path(CONFIG, 'configuration file')

    def open_output_folder(self):
        if yaml is None:
            messagebox.showerror('Open failed', 'PyYAML is not installed.', parent=self)
            return
        try:
            with open(CONFIG, 'r', encoding='utf-8') as config_file:
                config_data = yaml.safe_load(config_file) or {}
            project_key = PROJECT_CONFIG_KEYS[self.project_var.get()]
            projects = config_data.get('projects', {})
            project_config = (
                projects.get(project_key) or projects.get(str(project_key)) or {}
            )
            output_path = project_config.get('evoked_summary_root')
            if not output_path:
                raise KeyError('evoked_summary_root is not configured for this project.')
            self._open_path(Path(output_path), 'output folder')
        except Exception as exc:
            messagebox.showerror('Open failed', str(exc), parent=self)

    def open_log_folder(self):
        log_path = REPO_ROOT / 'logs' / self.project_var.get()
        log_path.mkdir(parents=True, exist_ok=True)
        self._open_path(log_path, 'log folder')

    def _open_path(self, path, description):
        path = Path(path)
        if not path.exists():
            messagebox.showerror(
                'Open failed',
                f'The {description} does not exist:\n{path}',
                parent=self,
            )
            return
        try:
            if sys.platform.startswith('win'):
                os.startfile(path)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', str(path)])
            else:
                subprocess.Popen(['xdg-open', str(path)])
        except Exception as exc:
            messagebox.showerror('Open failed', str(exc), parent=self)

if __name__ == '__main__':
    set_windows_app_identity()
    app = PipelineGUI()
    app.mainloop()
