"""Configuration management for the AFNI preprocessing pipeline"""
import json
import platform
from pathlib import Path
from typing import Dict, Any, List


class ConfigManager:
    """Manages application configuration and persistence"""

    @staticmethod
    def get_platform_defaults():
        """Get platform-specific default paths"""
        system = platform.system()

        if system == "Darwin":  # macOS
            fs_home = "/Applications/freesurfer/7.1.1"
        elif system == "Linux":
            # Try common Linux locations
            for path in ["/usr/local/freesurfer", str(Path.home() / "freesurfer"), "/opt/freesurfer"]:
                if Path(path).exists():
                    fs_home = path
                    break
            else:
                fs_home = "/usr/local/freesurfer"
        elif system == "Windows":
            fs_home = "C:\\Program Files\\freesurfer"
        else:
            fs_home = str(Path.home() / "freesurfer")

        return {
            "freesurfer_home": fs_home
        }

    DEFAULT_CONFIG = {
        "freesurfer_home": "",  # Will be set platform-specifically
        "execution_mode": "auto",  # auto, step-by-step, semi-auto
        "stop_on_error": False,
        "skip_interactive": True,
        "parallel_subjects": False,
        "num_parallel": 1,
        "keep_intermediate": True,
        "enabled_scripts": {
            "001a_dcm2niix": True,
            "001c_rename_files": True,
            "002_batch_defaceMRI": True,
            "003_FreeSurfer_recon": True,
            "003b_FreeSurferQA_SUMA": True,
            "004_createAP_struct_rf": True,
            "004_execute_proc": True,
            "005_afni2nifti": True,
            "006_get_motion_files": True,
        },
        "last_parent_dir": "",
        "last_subjects": [],
        "window_geometry": {},
    }

    def __init__(self, config_file=None):
        if config_file:
            self.config_file = Path(config_file)
        else:
            config_dir = Path.home() / ".afni_gui_preprocessing"
            config_dir.mkdir(parents=True, exist_ok=True)
            self.config_file = config_dir / "config.json"

        # Set platform-specific defaults
        platform_defaults = self.get_platform_defaults()
        self.DEFAULT_CONFIG.update(platform_defaults)

        self.config = self.load_config()

    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file or create default"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                # Merge with defaults to ensure all keys exist
                config = self.DEFAULT_CONFIG.copy()
                config.update(loaded_config)
                return config
            except Exception as e:
                print(f"Error loading config: {e}")
                return self.DEFAULT_CONFIG.copy()
        else:
            return self.DEFAULT_CONFIG.copy()

    def save_config(self):
        """Save current configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key: str, default=None):
        """Get configuration value"""
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        """Set configuration value"""
        self.config[key] = value

    def get_enabled_scripts(self) -> List[str]:
        """Get list of enabled script names"""
        enabled = self.config.get("enabled_scripts", {})
        return [name for name, is_enabled in enabled.items() if is_enabled]

    def is_script_enabled(self, script_name: str) -> bool:
        """Check if a script is enabled"""
        return self.config.get("enabled_scripts", {}).get(script_name, True)

    def set_script_enabled(self, script_name: str, enabled: bool):
        """Enable or disable a script"""
        if "enabled_scripts" not in self.config:
            self.config["enabled_scripts"] = {}
        self.config["enabled_scripts"][script_name] = enabled

    def reset_to_defaults(self):
        """Reset configuration to defaults"""
        self.config = self.DEFAULT_CONFIG.copy()
        self.save_config()
