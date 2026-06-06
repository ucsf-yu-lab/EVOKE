import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import os
import pandas as pd
from config import get_processed_evoked_root, get_evoked_analysis_root

# Script Authors:    Darian Mohsenin
# Date: 3/23/2026

# About:
# Concatenates kinematic data from all mice/trials into a single long read csv for analysis
# ====================================================================
# Update Log:
# 3/15/2026: Updated input/ouput selection/file paths to work for other orofacial pain studies going on in the lab
# 3/23/2026: Added authorship, date, authorship, & update log to formalize script

# ====================================================================
# SCRIPT BELOW

# ====================================================================
# FIND EXPERIMENT FOLDER
# ====================================================================
def get_project_paths_auto(project_type):
    """Fetches input and output roots from config without interactive input."""
    input_base = str(get_processed_evoked_root(project_type) or '')
    output_dir = str(get_evoked_analysis_root(project_type) or '')
    return input_base, output_dir


def find_experiment_folder(base_dir: str, number_input: str):
    """
    Searches a base directory for a folder that starts with 'Exp' + number_input.
    Returns the full folder name if a unique match is found, otherwise returns None.
    """
    prefix = f"Exp{number_input}"
    
    matches = []
    
    # Check if the base directory exists
    if not os.path.isdir(base_dir):
        print(f"Error: Base directory does not exist at {base_dir}")
        return None
        
    for item in os.listdir(base_dir):
        if os.path.isdir(os.path.join(base_dir, item)) and item.startswith(prefix):
            matches.append(item)
            
    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        print(f"ERROR: Found multiple folders starting with '{prefix}'. Please be more specific.")
        return None
    else:
        print(f"ERROR: No folder found starting with '{prefix}' in {base_dir}")
        return None


def get_experiment_folder_path(INPUT_BASE_DIR):
    """
    Prompts the user for a 3-digit Experiment ID, finds the corresponding 
    experiment folder within the hardcoded INPUT_BASE_DIR, and returns 
    the full, normalized path to that folder.
    Returns the string 'QUIT' if the user chooses to exit.
    Returns None on error or if no folder is found.
    """
    print(f"\nSearching for experiment folder in: {INPUT_BASE_DIR}")
    
    # 1. Get User Input for Experiment ID
    number_input = input("Enter the 3-digit Experiment ID (e.g., '001'), or type 'done'/'q' to quit: ").strip().lower()
    
    if number_input in ['done', 'q']:
        return "QUIT"
    
    if not number_input.isdigit() or len(number_input) < 1:
        print("Invalid input. Please enter a numerical Experiment ID or 'done'.")
        return None

    # Pad with leading zeros if necessary (e.g., '1' becomes '001')
    exp_id = number_input.zfill(3)

    # 2. Find the Experiment Folder
    folder_name = find_experiment_folder(INPUT_BASE_DIR, exp_id)
    
    if folder_name:
        # 3. Construct the full path
        full_exp_path = os.path.normpath(os.path.join(INPUT_BASE_DIR, folder_name))
        print(f"Found folder: {folder_name}")
        return full_exp_path
    else:
        # Error message is handled within find_experiment_folder
        return None



# ====================================================================
# MAIN
# ====================================================================
def main():
    print("="*40)
    print("Step 7: DeepLabCut Mega-CSV Compiler")
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
            
            number_input = input("Enter 3-digit Experiment ID (e.g., 001): ").strip()
            exp_id = number_input.zfill(3)
            interactive = True
        except Exception as e:
            print(f"Input error: {e}")
            return

    # 2. Find and Validate Folder
    root_dir = os.path.normpath(os.path.join(INPUT_BASE_DIR, find_experiment_folder(INPUT_BASE_DIR, exp_id)))
    if not os.path.exists(root_dir):
        print(f"Error: Experiment folder not found for ID {exp_id}")
        return

    # 3. Extract Metadata from Folder Name
    # Expects: Exp001_2026-03-23_Treatment_Cage1 etc.
    folder_name = os.path.basename(root_dir)
    parts = folder_name.split('_')
    
    experiment_ID = parts[0] if len(parts) > 0 else exp_id
    date = parts[1] if len(parts) > 1 else "UnknownDate"
    treatment = parts[3] if len(parts) > 3 else "UnknownTreatment"
    cage_ID = parts[4] if len(parts) > 4 else "UnknownCage"
    
    protocol_number = 306 
    all_data = []

    print(f"Compiling trials for Experiment: {experiment_ID}...")

    # 4. The "Long-Read" Compilation Loop
    # This crawls your subject/trial/cleaned_csvs structure
    for subject_id in os.listdir(root_dir):
        subject_path = os.path.join(root_dir, subject_id)
        if not os.path.isdir(subject_path): continue

        for stimulus_folder in os.listdir(subject_path):
            stimulus_path = os.path.join(subject_path, stimulus_folder)
            cleaned_path = os.path.join(stimulus_path, 'dlc_outputs', 'cleaned_csvs')
            
            if not os.path.isdir(cleaned_path): continue

            for body_part_folder in os.listdir(cleaned_path):
                if not body_part_folder.endswith('_metrics_median'): continue
                
                body_path = os.path.join(cleaned_path, body_part_folder)
                body_part = body_part_folder.replace('_metrics_median', '')

                for file in os.listdir(body_path):
                    if not file.endswith('.csv'): continue
                    
                    file_path = os.path.join(body_path, file)
                    
                    try:
                        # Parsing filename: MouseID_Trial_1_Left...
                        f_parts = file.split('_')
                        trial = f_parts[2] if len(f_parts) >= 3 else "NA"
                        side = f_parts[3] if len(f_parts) >= 4 else "NA"

                        df = pd.read_csv(file_path)
                        if df.empty: continue

                        # Reshaping to Long Format
                        # We identify common columns to pivot
                        for col in ['speed_mm_s', 'acceleration_mm_s2', 'is_active']:
                            if col in df.columns:
                                temp = pd.DataFrame({
                                    'protocol_number': protocol_number,
                                    'experiment_ID': experiment_ID,
                                    'treatment': treatment,
                                    'date': date,
                                    'cage_ID': cage_ID,
                                    'unique_ID': subject_id,
                                    'body_part': body_part,
                                    'stimulus': stimulus_folder,
                                    'side_of_stimulation': side,
                                    'trial': trial,
                                    'frame': df['frame'],
                                    'variable': col,
                                    'value_1': df[col],
                                    'value_2': None,
                                    'likelihood': df.get('likelihood', None)
                                })
                                all_data.append(temp)
                        
                        # Special handling for paired X/Y (Position and Velocity)
                        if 'x_mm' in df.columns and 'y_mm' in df.columns:
                            pos = pd.DataFrame({
                                'protocol_number': protocol_number, 'experiment_ID': experiment_ID,
                                'treatment': treatment, 'date': date, 'cage_ID': cage_ID,
                                'unique_ID': subject_id, 'body_part': body_part, 'stimulus': stimulus_folder,
                                'side_of_stimulation': side, 'trial': trial, 'frame': df['frame'],
                                'variable': 'position', 'value_1': df['x_mm'], 'value_2': df['y_mm'],
                                'likelihood': df.get('likelihood', None)
                            })
                            all_data.append(pos)

                    except Exception as e:
                        print(f"Skip {file}: {e}")

    # 5. Final Concatenation & Save
    if all_data:
        result_df = pd.concat(all_data, ignore_index=True)
        output_filename = os.path.join(OUTPUT_DIR, f"{experiment_ID}_{date}_{cage_ID}_{treatment}.csv")
        
        # Ensure output directory exists
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        result_df.to_csv(output_filename, index=False)
        print(f"\nSUCCESS! Mega CSV saved to:\n{output_filename}")
    else:
        print("No data found to compile.")

    if interactive:
        run_again = input("\nCompile another? (yes/no): ").strip().lower()
        if run_again == 'yes': main()

if __name__ == "__main__":
    main()