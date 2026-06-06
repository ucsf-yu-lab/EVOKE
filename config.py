from pathlib import Path
import os
import yaml

# Find the YAML file sitting next to this script
CONFIG_PATH = Path(__file__).parent / "pipeline_config.yaml"

def load_full_config():
    if not CONFIG_PATH.exists():
        # If the YAML is missing, we can't run. 
        # This print will show up in your terminal.
        print(f"!!! FATAL ERROR: {CONFIG_PATH} not found !!!")
        return {}
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}

_CFG = load_full_config()

# --- 1. GLOBAL TOOL PATHS ---
def get_source_root():
    return Path(_CFG.get('source_root', ''))

def get_ffmpeg_path():
    return _CFG.get('ffmpeg_path')

def get_dlc_project_path():
    return _CFG.get('dlc_project_path')

def get_metrics_script_path():
    return _CFG.get('metrics_script_path')

# --- 2. PROJECT-SPECIFIC HELPERS ---
def get_project_val(project_type, key):
    """Internal helper to grab values from the 'projects' block."""
    projects = _CFG.get('projects', {})
    # Handles 1 vs "1"
    proj_data = projects.get(project_type) or projects.get(str(project_type))
    return proj_data.get(key) if proj_data else None

def get_evoked_root(project_type):
    val = get_project_val(project_type, 'evoked_root')
    return Path(val) if val else None

def get_processed_evoked_root(project_type):
    val = get_project_val(project_type, 'evoked_processed_root')
    return Path(val) if val else None

def get_spontaneous_root(project_type):
    val = get_project_val(project_type, 'spontaneous_root')
    return Path(val) if val else None

def get_metadata_path(project_type):
    val = get_project_val(project_type, 'metadata_path')
    return Path(val) if val else None

def get_evoked_analysis_root(project_type):
    val = get_project_val(project_type, 'evoked_analysis_root')
    return Path(val) if val else None

def get_evoked_summary_root(project_type):
    val = get_project_val(project_type, 'evoked_summary_root')
    return Path(val) if val else None

# --- 3. STEP-SPECIFIC SETTINGS ---
def get_trimming_defaults():
    t = _CFG.get('trimming', {})
    return {
        'before_seconds': float(t.get('before_seconds', 30.0)),
        'after_seconds': float(t.get('after_seconds', 30.0)),
        'default_fps': float(t.get('default_fps', 70.0))
    }