import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import deeplabcut as dlc
import os
import pandas as pd
from tqdm import tqdm
import glob
from typing import Optional
from config import get_dlc_project_path, get_processed_evoked_root, get_spontaneous_root

# Script Authors:    Darian Mohsenin
# Date: 3/23/2026

# About:
# Batch DeepLabCut(DLC) labelling script
# ====================================================================


# Run this with deeplabcut environment!!!!!!!!!!!

# ----- USER CONFIGURATION -----
# ====================================================================

ROOT = Path(__file__).resolve().parents[1]  # project root
os.chdir(ROOT)
# DeepLabCut project path (points to dlc model within project folder)
DLC_PROJECT_PATH = get_dlc_project_path()
CONFIG_FILE = os.path.join(DLC_PROJECT_PATH, 'config.yaml')

# DeepLabCut analysis parameters
CREATE_NEW_VIDEO = True
PCUTOFF = 0.0  # Set to 0 so all model predictions are displayed
VIDEO_EXTENSIONS = ('.mp4', '.mov', '.avi') # Can add more extensions if needed, analysis was completed with .avi files

# ====================================================================



# ====================================================================
# FIND EXPERIMENT FOLDER
# ====================================================================

def get_project_paths(project_type):
    """Returns base directories based on project type without interactive input."""
    # This uses your config.py helpers to get the right folders automatically
    evoked_root = str(get_processed_evoked_root(project_type) or '')
    spont_root = str(get_spontaneous_root(project_type) or '')
    
    return evoked_root, spont_root

def find_experiment_folder(base_dir: str, number_input: str) -> Optional[str]:
    """Finds a folder starting with ExpXXX where XXX is number_input."""
    prefix = f"Exp{number_input}"
    matches = []

    if not os.path.isdir(base_dir):
        print(f"Error: Base directory does not exist at {base_dir}")
        return None

    for item in os.listdir(base_dir):
        full_path = os.path.join(base_dir, item)
        if os.path.isdir(full_path) and item.startswith(prefix):
            matches.append(item)

    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        print(f"ERROR: Multiple folders found starting with '{prefix}': {matches}")
        return None
    else:
        print(f"ERROR: No folder found starting with '{prefix}' in {base_dir}")
        return None


def find_videos_recursive(exp_dir):
    """Recursively finds all video files, case-insensitive."""
    video_files = []
    for root, _, files in os.walk(exp_dir):
        for file in files:
            if file.lower().endswith(tuple(ext.lower() for ext in VIDEO_EXTENSIONS)):
                full_path = os.path.join(root, file)
                video_files.append(full_path)
    return video_files


# ====================================================================
# DEEPLABCUT ANALYSIS SCRIPT
# ====================================================================

def analyze_videos_and_create_csv(exp_dir, config_file, create_new_video, pcutoff):
    """Analyzes videos with DLC and converts h5 outputs to CSV."""
    exp_dir = os.path.normpath(exp_dir)
    print(f"\nSearching for videos in: {exp_dir}")

    video_files = find_videos_recursive(exp_dir)

    if not video_files:
        print(f"No videos found in {exp_dir}. Check folder contents and file extensions.")
        return

    print(f"Found {len(video_files)} video(s):")
    for v in video_files:
        print(f"  {v}")

    for video_path in tqdm(video_files, desc=f"Analyzing videos in {os.path.basename(exp_dir)}"):
        try:
            video_dir = os.path.dirname(video_path)
            file = os.path.basename(video_path)
            video_type = os.path.splitext(file)[1][1:]

            print(f"\nAnalyzing video: {video_path} (type: {video_type})")
            dlc.analyze_videos(config_file, [video_path], videotype=video_type, shuffle=3)

            if create_new_video:
                dlc.create_labeled_video(config_file, [video_path], videotype=video_type, pcutoff=pcutoff, shuffle=3)

            # Convert .h5 to CSV
            video_name = os.path.splitext(file)[0]
            h5_files = glob.glob(os.path.join(video_dir, f"{video_name}*DLC*.h5"))

            if h5_files:
                h5_file = h5_files[0]
                try:
                    data = pd.read_hdf(h5_file)
                    csv_file = os.path.join(video_dir, f"{video_name}_dlc_output.csv")
                    data.to_csv(csv_file)
                    print(f"  CSV created: {csv_file}")
                except Exception as e:
                    print(f"  Error reading .h5 or creating CSV for {video_path}: {e}")
            else:
                print(f"  Warning: .h5 file not found for {video_path} after analysis.")

        except Exception as e:
            print(f"  Error analyzing {video_path}: {e}")


# ====================================================================
# MAIN
# ====================================================================

def main():
    """Main workflow for DLC video analysis."""
    if not os.path.exists(CONFIG_FILE):
        print(f"Error: DLC config file not found at {CONFIG_FILE}")
        return

    # 1. Check for Pipeline Environment Variables
    env_proj = os.environ.get('EVOKED_PIPELINE_PROJECT')
    env_expid = os.environ.get('EVOKED_PIPELINE_EXPID')

    if env_proj and env_expid:
        # --- PIPELINE MODE (No Inputs) ---
        project_type = int(env_proj)
        exp_id = env_expid.zfill(3)
        interactive = False
    else:
        # --- MANUAL MODE (Interactive) ---
        print("DeepLabCut Batch Labelling Tool")
        print("="*40)
        proj_input = input("Project: TN (1) or TMJ (2): ").strip()
        if not proj_input: return
        project_type = int(proj_input)
        
        number_input = input("Enter 3-digit Experiment ID (e.g., 001): ").strip()
        exp_id = number_input.zfill(3)
        interactive = True

    # 2. Setup Paths
    evoked_base, spont_base = get_project_paths(project_type)
    
    # Logic: Analyze processed evoked clips
    input_base_dir = evoked_base

    if not input_base_dir:
        print(f"Error: Could not determine base directory for project {project_type}")
        return

    # 3. Find experiment folder
    folder_name = find_experiment_folder(input_base_dir, exp_id)
    if folder_name:
        exp_dir = os.path.join(input_base_dir, folder_name)
        print(f"\nProcessing: {folder_name}")
        
        # 4. Run the DLC analysis
        analyze_videos_and_create_csv(exp_dir, CONFIG_FILE, CREATE_NEW_VIDEO, PCUTOFF)
        print("\nAnalysis complete.")
    
    # 5. Handle "Run Again" only in interactive mode
    if interactive:
        run_again = input("\nRun another experiment? (yes/no): ").strip().lower()
        if run_again == 'yes':
            main() # Restart the loop manually

if __name__ == "__main__":
    main()