import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import pandas as pd
import numpy as np
import os
from config import get_evoked_analysis_root, get_evoked_root

# Script Authors:    Darian Mohsenin
# Date: 3/23/2026

# About:
# Extract behavior features from the long read csv file
# ====================================================================
# Update Log:
# 3/15/2026: Updated input/ouput selection/file paths to work for other orofacial pain studies going on in the lab
# 3/23/2026: Added authorship, date, authorship, & update log to formalize script

# ====================================================================
# SCRIPT BELOW

# ====================================================================
# USER CONFIGURATION
# ====================================================================
FPS = 62  # Match your video capture rate, MAKE SURE TO CHECK THIS!!
stim_frame = 2100  # 1050 or 2100 or 3600 (EARLIEST PROJECT DATA WAS 1050 or 3600!!) 

# Windows (in seconds converted to frames)
BASELINE_SEC = 2
POST_STIM_SEC = 2
AUC_WINDOW_SEC = 15
SNAP_WINDOW_SEC = 0.3 
ACTIVE_THRESH = 5 # mm/s
SIDE_ORDER = ['Right', 'Left']

# ====================================================================
# FIND EXPERIMENT FOLDER
# ====================================================================
def get_project_paths_auto(project_type):
    """Reads paths directly from pipeline_config.yaml based on project ID."""
    import yaml
    
    # Locate the config file relative to the script
    config_path = ROOT / "pipeline_config.yaml"
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Access the 'projects' dictionary
    project_cfg = config.get('projects', {}).get(project_type, {})
    
    if not project_cfg:
        # Fallback to the 'processed_roots' key if 'projects' isn't used
        project_cfg = config.get('processed_roots', {}).get(project_type, {})

    input_dir = project_cfg.get('evoked_analysis_root')
    # Try to get the explicit summary root, otherwise use your old logic of going to the parent
    output_dir = project_cfg.get('evoked_summary_root')
    
    if not output_dir and input_dir:
        # Emergency fallback if summary_root isn't in YAML
        output_dir = os.path.join(os.path.dirname(input_dir), 'summary_csv_files')

    return input_dir, output_dir


def find_experiment_csv(base_dir: str, number_input: str):
    """
    Searches base_dir for a CSV file starting with 'Exp' + number_input.
    """
    prefix = f"Exp{number_input}"
    matches = []
    
    if not os.path.isdir(base_dir):
        print(f"Error: Directory does not exist: {base_dir}")
        return None
        
    for item in os.listdir(base_dir):
        # Change: Check if it's a file AND ends with .csv AND starts with our prefix
        if os.path.isfile(os.path.join(base_dir, item)):
            if item.startswith(prefix) and item.lower().endswith('.csv'):
                matches.append(item)
            
    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        print(f"ERROR: Multiple CSVs found for '{prefix}': {matches}")
        return None
    else:
        print(f"ERROR: No CSV file found starting with '{prefix}' in {base_dir}")
        return None

def get_experiment_csv_path(INPUT_BASE_DIR):
    """
    Prompts user for ID, finds the CSV, and returns the full path.
    """
    print(f"\nSearching for experiment CSV in: {INPUT_BASE_DIR}")
    
    number_input = input("Enter the 3-digit Experiment ID (e.g., '001'), or 'q' to quit: ").strip().lower()
    
    if number_input in ['done', 'q']:
        return "QUIT"
    
    # Pad to 3 digits (e.g., '1' -> '001')
    exp_id = number_input.zfill(3)

    file_name = find_experiment_csv(INPUT_BASE_DIR, exp_id)
    
    if file_name:
        full_path = os.path.normpath(os.path.join(INPUT_BASE_DIR, file_name))
        print(f"Found file: {file_name}")
        return full_path
    
    return None


# ====================================================================
# FEATURE CALCULATIONS
# ====================================================================
def calculate_features(group):
    group = group.sort_values('frame')
    
    # Pre-calculate derivative for acceleration
    speed = group['value_1']
    accel = speed.diff() * FPS
    

    group['t_rel'] = (group['frame'] - stim_frame) / FPS
    
    # 1. LATENCY TO RESPONSE
    baseline_data = group[(group['t_rel'] < 0) & (group['t_rel'] >= -BASELINE_SEC)]['value_1']
    thresh = baseline_data.mean() + (0.5 * baseline_data.std()) if len(baseline_data) > 0 else 5
        
    response_window = group[(group['t_rel'] >= 0) & (group['t_rel'] <= POST_STIM_SEC)]
    idx = response_window[response_window['value_1'] > thresh].index
    latency_ms = (response_window.loc[idx[0], 't_rel'] * 1000) if len(idx) > 0 else np.nan

    # 2. VIGOR METRICS (Slope and Accel)
    if not response_window['value_1'].dropna().empty:
        peak_idx = response_window['value_1'].dropna().idxmax()
        peak_speed = response_window['value_1'].max()
        time_to_peak_ms = response_window.loc[peak_idx, 't_rel'] * 1000
        
        # Vigor Slope (Peak Speed / Time to reach it)
        vigor_slope = peak_speed / (time_to_peak_ms / 1000) if time_to_peak_ms > 0 else 0
        max_accel = accel.loc[response_window.index].max()
    else:
        # If the whole 2s window is empty, it safely fills with NaN and MOVES ON
        peak_speed = vigor_slope = max_accel = np.nan

    # 3. SNAP SPEED (300ms Window)
    snap_data = group[(group['t_rel'] >= 0) & (group['t_rel'] <= SNAP_WINDOW_SEC)]
    snap_speed = snap_data['value_1'].max() if not snap_data.empty else np.nan

    # 4. TOTAL DISTANCE & ACTIVITY
    auc_window = group[(group['t_rel'] >= 0) & (group['t_rel'] <= AUC_WINDOW_SEC)]
    raw_dist = auc_window['value_1'].sum() * (1/FPS)
    coverage = auc_window['value_1'].notna().mean()
    total_dist_corrected = (raw_dist / coverage) if coverage > 0.1 else np.nan
    is_active = (auc_window['value_1'] > ACTIVE_THRESH).mean() * 100

    # 5. TRACKING CONFIDENCE (Average Likelihood)
    avg_likelihood = group['likelihood'].mean() if 'likelihood' in group.columns else np.nan


    return pd.Series({
        'latency_to_respond_ms': latency_ms,
        'head_snap_speed_300ms': snap_speed,
        'peak_speed_2s': peak_speed,
        'vigor_slope_mm_s2': vigor_slope,
        'max_accel_mm_s2': max_accel,
        'total_distance_mm': total_dist_corrected,
        'pct_time_active': is_active,
        'trial_tracking_quality': avg_likelihood
    })

# ====================================================================
# MAIN
# ====================================================================
def main():
    print("="*40)
    print("Step 8: Orofacial Feature Extraction")
    print("="*40)

    # 1. Check for Pipeline Environment Variables
    env_proj = os.environ.get('EVOKED_PIPELINE_PROJECT')
    env_expid = os.environ.get('EVOKED_PIPELINE_EXPID')

    if env_proj and env_expid:
        # --- PIPELINE MODE ---
        project_type = int(env_proj)
        exp_id = env_expid.zfill(3)
        INPUT_BASE_DIR, OUTPUT_DIR = get_project_paths_auto(project_type)
        interactive = False
    else:
        # --- MANUAL MODE ---
        try:
            proj_input = input("Project: TN (1) or TMJ (2): ").strip()
            if not proj_input: return
            project_type = int(proj_input)
            INPUT_BASE_DIR, OUTPUT_DIR = get_project_paths_auto(project_type)
            
            number_input = input("Enter 3-digit Experiment ID: ").strip()
            exp_id = number_input.zfill(3)
            interactive = True
        except Exception as e:
            print(f"Input error: {e}")
            return

    # 2. Find and Load the CSV
    csv_file = find_experiment_csv(INPUT_BASE_DIR, exp_id)
    if not csv_file:
        return
    
    input_path = os.path.join(INPUT_BASE_DIR, csv_file)
    print(f"Loading {csv_file}...")
    df = pd.read_csv(input_path)

    # 3. Extract Metadata from the DataFrame itself
    treatment = df['treatment'].iloc[0] if 'treatment' in df.columns else "Unknown"
    cage = df['cage_ID'].iloc[0] if 'cage_ID' in df.columns else "Unknown"
    date = df['date'].iloc[0] if 'date' in df.columns else "Unknown"
    exp_id_label = df['experiment_ID'].iloc[0] if 'experiment_ID' in df.columns else exp_id

    # 4. Feature Extraction Loop
    # Filtering specifically for 'nose' to track withdrawal kinetics
    df_nose = df[(df['body_part'] == 'nose') & (df['variable'] == 'speed_mm_s')].copy()

    if df_nose.empty:
        print("Warning: No 'nose' speed data found in this CSV!")
        return

    print(f"Calculating features for {exp_id_label}...")

    # Grouping by unique mouse/trial and applying the math
    trial_results = (df_nose.groupby(['unique_ID', 'treatment', 'trial', 'stimulus', 'side_of_stimulation'])
                        .apply(calculate_features, include_groups=False)
                        .reset_index())

    # Ensure clean sorting for GraphPad Prism compatibility
    trial_results['side_of_stimulation'] = pd.Categorical(
        trial_results['side_of_stimulation'], categories=SIDE_ORDER, ordered=True
    )
    trial_results = trial_results.sort_values(by=['side_of_stimulation', 'unique_ID', 'trial'])

    # 5. Save the Results
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    trial_fn = f"{exp_id_label}_{date}_{cage}_{treatment}_TrialSummary.csv"
    subject_fn = f"{exp_id_label}_{date}_{cage}_{treatment}_SubjectSummary.csv"

    trial_results.to_csv(os.path.join(OUTPUT_DIR, trial_fn), index=False)

    # Summary: Average across trials for each subject
    subject_summary = (trial_results.groupby(['unique_ID', 'treatment', 'stimulus', 'side_of_stimulation'], observed=True)
                        .agg({
                            'latency_to_respond_ms': 'mean',
                            'head_snap_speed_300ms': 'mean',
                            'peak_speed_2s': 'mean',
                            'vigor_slope_mm_s2': 'mean',
                            'max_accel_mm_s2': 'mean',
                            'total_distance_mm': 'mean',
                            'pct_time_active': 'mean',
                            'trial_tracking_quality': 'mean'
                        }).reset_index())

    subject_summary.to_csv(os.path.join(OUTPUT_DIR, subject_fn), index=False)

    print("\n" + "="*40)
    print(f"SUCCESS: Analysis complete for {exp_id_label}")
    print(f"Summary saved to: {OUTPUT_DIR}")
    print("="*40)

    if interactive:
        input("\nPress Enter to close...")

if __name__ == "__main__":
    main()