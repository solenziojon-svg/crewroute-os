import os
import shutil

# Define the target structure
structure = {
    "agents": [
        "crewroute_agents.py",
        "photo_audit_agent.py",
        "focus_mode_agent.py",
        "solo_pilot_agent.py"
    ],
    "core": [
        "empire_ai_nexus.py",
        "empire_moat.py",
        "empire_status.py",
        "empire_report.py",
        "empire_logging.py"
    ],
    "cjs": [
        "cjs_operating_hub.py",
        "crewroute_daily_engine.py"
    ],
    "utils": [
        "alerts.py",
        "telegram_bot.py"
    ]
}

# Folders that should just exist (even if empty)
folders_to_create = ["prompts", "schema"]

def reorganize():
    print("Starting reorganization...\n")

    # Create main folders
    for folder in structure.keys():
        os.makedirs(folder, exist_ok=True)
        print(f"Created folder: {folder}")

    for folder in folders_to_create:
        os.makedirs(folder, exist_ok=True)
        print(f"Created folder: {folder}")

    # Move files
    for target_folder, files in structure.items():
        for file in files:
            if os.path.exists(file):
                try:
                    shutil.move(file, os.path.join(target_folder, file))
                    print(f"Moved: {file} → {target_folder}/")
                except Exception as e:
                    print(f"Error moving {file}: {e}")
            else:
                print(f"File not found (skipped): {file}")

    print("\n✅ Reorganization complete!")
    print("Note: You may need to update some import statements inside the files.")

if __name__ == "__main__":
    reorganize()