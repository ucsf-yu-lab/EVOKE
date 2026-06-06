import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import pandas as pd
import tkinter as tk
from tkinter import filedialog
from config import get_evoked_root
import os
import re

# Script Authors:    Darian Mohsenin
# Date: 3/23/2026

# About:
# Takes both csv files (digital & analog) from Saleae logic analyzer to pull out stimulus delivery events
# ====================================================================
# Update Log:
# 3/23/2026: Added authorship, date, authorship, & update log to formalize script
# 4/08/2026: Added TN or TMJ project selection to speed up file search

# ====================================================================
# SCRIPT BELOW

# ====================================================================
# COMBINE DIGITAL & ANALOG FILES, EXTRACT STIMULUS-DELIVERY EVENTS
# ====================================================================

# ====================================================================
# PROJECT & PATH AUTO-DETECTION
# ====================================================================
def get_automated_paths():
    # 1. Pull project selection from GUI environment variable
    project_env = os.environ.get('EVOKED_PIPELINE_PROJECT')
    if project_env:
        project_type = int(project_env)
    else:
        # Fallback for manual runs
        project_type = int(input("Project (1 or 2): ").strip())

    # 2. Get the base directory from config
    input_base = Path(get_evoked_root(project_type))

    # 3. Pull Experiment ID from GUI environment variable
    exp_id = os.environ.get('EVOKED_PIPELINE_EXPID')
    
    # If we have an ExpID, we can find the specific folder automatically
    if exp_id:
        # Search for the folder that starts with "Exp" + your ID
        matching_folders = [f for f in input_base.iterdir() if f.is_dir() and f.name.startswith(f"Exp{exp_id}")]
        if matching_folders:
            return matching_folders[0] # Return the first matching experiment folder
    
    # Fallback to manual folder selection if auto-detection fails
    root = tk.Tk()
    root.withdraw()
    return Path(filedialog.askdirectory(title="Select Experiment Folder", initialdir=input_base))


# Code for converting voltage readings of the stimulus potentiometer into actual stimulus values
def voltage_to_stimulus(voltage):
    """Convert voltage to stimulus type"""
    try:
        v = float(voltage)
        if v < 0 or v <= 0.759:
            return "0.02g"
        elif 0.76 <= v <= 1.59:
            return "0.04g"
        elif 1.6 <= v <= 2.39:
            return "0.07g"
        elif 2.4 <= v <= 3.29:
            return "0.16g"
        elif 3.3 <= v <= 4.09:
            return "Air Puff"
        elif v >= 4.1:
            return "Other"
    except:
        return "Invalid"

# Code for processing the hit columns
def process_hits_column(frames_df, analog_df, hit_col, output_dir, round_id=""):
    frames = frames_df[frames_df['Frame'] == 1].copy()
    frames['Frame'] = range(1, len(frames) + 1)

    merged = pd.merge_asof(
        frames.sort_values('Time [s]'),
        analog_df.sort_values('Time [s]'),
        left_on='Time [s]',
        right_on='Time [s]',
        direction='nearest'
    )

    merged['Stimulus'] = merged['Stimulus'].apply(voltage_to_stimulus)
    merged['Stimulus'] = merged['Stimulus'].replace('', pd.NA).ffill().fillna('Invalid')
    merged.rename(columns={hit_col: 'Hit_Raw'}, inplace=True)

    merged['Hit'] = 0
    hit_counter = 0
    previous_stimulus = None
    previous_hit = 0

    for index, row in merged.iterrows():
        current_stimulus = row['Stimulus']
        current_hit_raw = row['Hit_Raw']

        if current_stimulus != previous_stimulus:
            hit_counter = 0
        elif current_hit_raw == 1 and previous_hit == 0:
            hit_counter += 1

        merged.at[index, 'Hit'] = hit_counter
        previous_stimulus = current_stimulus
        previous_hit = current_hit_raw

    output_cols = ['Time [s]', 'Hit', 'Frame', 'Stimulus']
    final_rows = []
    previous_hit_value = None

    for index, row in merged.iterrows():
        if row['Hit'] != previous_hit_value and row['Hit'] > 0:
            final_rows.append(row)
            previous_hit_value = row['Hit']

    # Save new file of corrected 'Hits' (integer) & 'Stimulus' (string)
    final_output = pd.DataFrame(final_rows, columns=output_cols)
    
    if round_id:
        output_file_name = f"Compiled-Saleae-Data-{hit_col}_{round_id}.csv"
    else:
        output_file_name = f"Compiled-Saleae-Data-{hit_col}.csv"
        
    output_file_path = os.path.join(output_dir, output_file_name)
    
    try:
        final_output.to_csv(output_file_path, index=False)
        print(f"Results saved to: {output_file_path}")
    except Exception as e:
        print(f"An error occurred while saving {hit_col} output file: {e}")


# ====================================================================
# MAIN
# ====================================================================
def main():
    print("Saleae Digital & Analog Data Compiler (Automated)")
    print("="*40)

    exp_folder = get_automated_paths()
    print(f"Working in: {exp_folder}")

    # Find all digital files
    digital_files = list(exp_folder.glob("*digital*.csv"))

    if not digital_files:
        print("No digital CSV files found in this folder.")
        return

    for digital_path in digital_files:
        # Extract the round identifier (e.g., 'round1' or 'r1')
        basename = digital_path.name
        match = re.search(r'(round\d+|r\d+)', basename, re.IGNORECASE)
        
        if not match:
            print(f"Skipping {basename}: Could not determine round number.")
            continue
            
        round_str = match.group(1).lower().replace('round', 'r') # Normalize to 'r1'
        round_id = match.group(1) # Keep original for output naming
        
        # Look for the matching analog file in the same folder
        # This searches for anything containing 'analog' and the same round ID
        analog_matches = [f for f in exp_folder.glob("*analog*.csv") 
                         if round_str in f.name.lower().replace('round', 'r')]

        if not analog_matches:
            print(f"Warning: Could not find matching analog file for {basename}")
            continue

        analog_path = analog_matches[0]
        print(f"\n--- Pairing Found ---")
        print(f"Digital: {digital_path.name}")
        print(f"Analog:  {analog_path.name}")

        try:
            digital_df = pd.read_csv(digital_path)
            analog_df = pd.read_csv(analog_path)
            
            # Use your existing processing logic
            output_dir = exp_folder
            analog_df['Stimulus'] = analog_df['Stimulus'].ffill()
            hit_columns = [col for col in digital_df.columns if col.startswith("Hits_b")]

            for hit_col in hit_columns:
                print(f"Processing {hit_col}...")
                process_hits_column(digital_df.copy(), analog_df.copy(), hit_col, output_dir, round_id)

        except Exception as e:
            print(f"Error processing round {round_id}: {e}")

    print("\n" + "="*40)
    print("All detected pairings have been processed!")

if __name__ == "__main__":
    main()