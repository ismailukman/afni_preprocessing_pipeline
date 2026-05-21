"""Pipeline manager for orchestrating the AFNI preprocessing workflow"""
import os
import subprocess
import shutil
from pathlib import Path
from typing import List, Dict, Optional
from PyQt6.QtCore import QObject, pyqtSignal
from .script_runner import ScriptRunner, DirectScriptRunner
from .config_manager import ConfigManager
from .logger import PipelineLogger


class Subject:
    """Represents a subject to be processed"""

    def __init__(self, path: Path, subject_id: str = None):
        self.path = Path(path)
        self.subject_id = subject_id or self.path.name
        self.status = {}  # script_name -> status
        self.tr = 2.0  # Default TR, to be auto-detected
        self.timepoints_per_run = 450  # Default, to be auto-detected

    def __str__(self):
        return self.subject_id


class ScriptInfo:
    """Information about a pipeline script"""

    def __init__(self, name: str, script_path: Optional[Path], description: str, estimated_time: str = "?"):
        self.name = name
        self.script_path = script_path
        if script_path is not None:
            self.script_path = Path(script_path)
        else:
            self.script_path = None
        self.description = description
        self.estimated_time = estimated_time

    def __str__(self):
        return f"{self.name}: {self.description}"


class PipelineManagerSignals(QObject):
    """Signals for pipeline manager"""
    status_updated = pyqtSignal(str, str, str)  # subject_id, script_name, status
    script_started = pyqtSignal(str, str)  # subject_id, script_name
    script_finished = pyqtSignal(str, str, bool)  # subject_id, script_name, success
    subject_started = pyqtSignal(str)  # subject_id
    subject_finished = pyqtSignal(str, bool)  # subject_id, success
    pipeline_started = pyqtSignal()
    pipeline_finished = pyqtSignal(bool)  # success
    progress_updated = pyqtSignal(int, int)  # current, total
    output_line = pyqtSignal(str, str)  # subject_id, line
    error_line = pyqtSignal(str, str)  # subject_id, line
    waiting_for_user = pyqtSignal(str, str)  # subject_id, script_name
    parameters_detected = pyqtSignal(float, int, int)  # tr, timepoints, num_runs


class PipelineManager(QObject):
    """Manages the execution of the preprocessing pipeline"""

    def __init__(self, config: ConfigManager, logger: PipelineLogger):
        super().__init__()
        self.config = config
        self.logger = logger
        self.signals = PipelineManagerSignals()

        self.subjects: List[Subject] = []
        self.current_subject: Optional[Subject] = None
        self.current_script: Optional[ScriptInfo] = None
        self.current_runner: Optional[ScriptRunner] = None

        self.is_running = False
        self.is_paused = False
        self.should_stop = False
        self.user_response = None

        # Define pipeline scripts
        base_path = Path(__file__).parent.parent / "scripts" / "templates"
        self.scripts = [
            ScriptInfo("001a_dcm2niix", base_path / "001a_dcm2niix.csh",
                      "Convert DICOM to NIfTI", "2-5 min"),
            ScriptInfo("001c_rename_files", base_path / "001c_rename_files.csh",
                      "Rename files to standard format", "< 1 min"),
            ScriptInfo("002_batch_defaceMRI", base_path / "002_batch_defaceMRI.csh",
                      "Deface functional & reface structural", "10-20 min"),
            ScriptInfo("003_FreeSurfer_recon", base_path / "003_FreeSurfer_recon.csh",
                      "FreeSurfer reconstruction", "3-8 hours"),
            ScriptInfo("003b_FreeSurferQA_SUMA", base_path / "003b_FreeSurferQA_SUMA.csh",
                      "Convert to SUMA format", "2-5 min"),
            ScriptInfo("004_createAP_struct_rf", base_path / "004_createAP_struct_rf.csh",
                      "Create preprocessing script", "1-2 min"),
            ScriptInfo("004_execute_proc", None,
                      "Execute preprocessing script", "30-60 min"),
            ScriptInfo("005_afni2nifti", base_path / "005_afni2nifti_v2.csh",
                      "Convert AFNI to NIfTI", "2-5 min"),
            ScriptInfo("006_get_motion_files", base_path / "006_get_motion_files.csh",
                      "Extract motion parameters", "< 1 min"),
        ]

    def set_subjects(self, subjects: List[Subject]):
        """Set the list of subjects to process"""
        self.subjects = subjects
        enabled_scripts = self.get_enabled_scripts()
        for subject in subjects:
            # Only initialize status for enabled scripts
            subject.status = {script.name: "pending" for script in enabled_scripts}

    def add_subjects(self, new_subjects: List[Subject]):
        """Append subjects to a running pipeline.  Skips IDs already queued.

        If the pipeline is idle (between subjects) when more are added, the
        normal ``_process_next_subject`` walk will pick them up automatically
        once the current subject finishes.
        """
        existing_ids = {s.subject_id for s in self.subjects}
        enabled_scripts = self.get_enabled_scripts()
        added = []
        for subject in new_subjects:
            if subject.subject_id in existing_ids:
                continue
            subject.status = {script.name: "pending" for script in enabled_scripts}
            self.subjects.append(subject)
            existing_ids.add(subject.subject_id)
            added.append(subject)
        if added:
            self.logger.info(
                f"Queued {len(added)} additional subject(s): "
                + ", ".join(s.subject_id for s in added)
            )
        return added

    def get_enabled_scripts(self) -> List[ScriptInfo]:
        """Get list of enabled scripts"""
        return [script for script in self.scripts if self.config.is_script_enabled(script.name)]

    def start_pipeline(self):
        """Start processing all subjects"""
        if not self.subjects:
            self.logger.error("No subjects to process")
            return

        self.is_running = True
        self.should_stop = False
        self.signals.pipeline_started.emit()
        self.logger.info("=" * 60)
        self.logger.info("Starting AFNI Preprocessing Pipeline")
        self.logger.info(f"Processing {len(self.subjects)} subject(s)")
        self.logger.info("=" * 60)

        self._process_next_subject()

    def _process_next_subject(self):
        """Process the next subject in the queue"""
        if self.should_stop:
            self._finish_pipeline(False)
            return

        # Find next pending subject (only check enabled scripts)
        enabled_scripts = self.get_enabled_scripts()
        for subject in self.subjects:
            # Check if any enabled script is still pending
            has_pending = any(subject.status.get(script.name) == "pending" for script in enabled_scripts)
            if has_pending:
                self.current_subject = subject
                self._process_subject(subject)
                return

        # All subjects processed
        self._finish_pipeline(True)

    def _process_subject(self, subject: Subject):
        """Process a single subject"""
        self.signals.subject_started.emit(subject.subject_id)
        self.logger.info(f"\n{'=' * 60}")
        self.logger.info(f"Processing subject: {subject.subject_id}")
        self.logger.info(f"{'=' * 60}")

        # Ensure PreprocessedData folder exists
        self._ensure_preprocessed_folder(subject)

        # Try to detect scan parameters early (if files already exist)
        self._detect_scan_parameters(subject)

        self._process_next_script(subject)

    def _process_next_script(self, subject: Subject):
        """Process the next script for a subject"""
        if self.should_stop:
            self.signals.subject_finished.emit(subject.subject_id, False)
            self._process_next_subject()
            return

        enabled_scripts = self.get_enabled_scripts()

        # Find next pending script
        for script in enabled_scripts:
            if subject.status.get(script.name) == "pending":
                self.current_script = script
                self._run_script(subject, script)
                return

        # All scripts completed for this subject
        success = not any(status == "error" for status in subject.status.values())
        self.signals.subject_finished.emit(subject.subject_id, success)
        self._process_next_subject()

    def _ensure_preprocessed_folder(self, subject: Subject):
        """Ensure PreprocessedData folder exists and contains NIfTI files.

        If PreprocessedData is empty, scan parent folder for NIfTI files,
        intelligently identify structural vs functional, and copy/rename them.
        """
        preprocessed_dir = subject.path / "PreprocessedData"

        # Create folder if it doesn't exist
        if not preprocessed_dir.exists():
            self.logger.info(f"Creating PreprocessedData folder: {preprocessed_dir}")
            try:
                preprocessed_dir.mkdir(parents=True, exist_ok=True)
                self.logger.info("✓ PreprocessedData folder created successfully")
            except Exception as e:
                self.logger.error(f"Failed to create PreprocessedData folder: {e}")
                return

        # Check if PreprocessedData has the required BIDS-formatted files
        required_structural = [
            preprocessed_dir / f"{subject.subject_id}_T1w.nii.gz",
            preprocessed_dir / f"{subject.subject_id}_T1w.nii",
        ]
        required_functional = [
            preprocessed_dir / f"{subject.subject_id}_task-rest_run-01_bold.nii.gz",
            preprocessed_dir / f"{subject.subject_id}_task-rest_run-01_bold.nii",
        ]

        has_structural = any(f.exists() for f in required_structural)
        has_functional = any(f.exists() for f in required_functional)

        if has_structural and has_functional:
            self.logger.info(f"✓ PreprocessedData contains required BIDS files")
            return

        if not has_structural:
            self.logger.info("Missing BIDS structural file, will search for it...")
        if not has_functional:
            self.logger.info("Missing BIDS functional file, will search for it...")

        # Scan BOTH parent folder AND PreprocessedData for NIfTI files
        self.logger.info("Scanning for NIfTI files to prepare...")

        # Collect all NIfTI files from both locations
        all_nifti_files = []

        # Scan parent folder
        parent_nifti = list(subject.path.glob("*.nii")) + list(subject.path.glob("*.nii.gz"))
        all_nifti_files.extend(parent_nifti)

        # Scan PreprocessedData (for files with wrong names)
        existing_nifti = list(preprocessed_dir.glob("*.nii")) + list(preprocessed_dir.glob("*.nii.gz"))
        all_nifti_files.extend(existing_nifti)

        if not all_nifti_files:
            self.logger.warning(f"No NIfTI files found in {subject.path} or PreprocessedData")
            return

        self.logger.info(f"Found {len(all_nifti_files)} NIfTI file(s) to scan")

        # Intelligently identify and prepare files
        structural_found = False
        functional_count = 0

        for nifti_file in all_nifti_files:
            # Skip files already in correct BIDS format
            if nifti_file.parent == preprocessed_dir:
                # Check if already in correct BIDS format
                if nifti_file.name.startswith(f"{subject.subject_id}_T1w"):
                    self.logger.info(f"  Skipping (already BIDS structural): {nifti_file.name}")
                    has_structural = True
                    continue
                elif nifti_file.name.startswith(f"{subject.subject_id}_task-rest_run-"):
                    self.logger.info(f"  Skipping (already BIDS functional): {nifti_file.name}")
                    continue

            # Determine scan type using 3dinfo
            if not has_structural and self._is_structural_scan(nifti_file):
                # Copy/rename structural file
                if str(nifti_file).endswith('.gz'):
                    dest_file = preprocessed_dir / f"{subject.subject_id}_T1w.nii.gz"
                else:
                    dest_file = preprocessed_dir / f"{subject.subject_id}_T1w.nii"

                if nifti_file.parent == preprocessed_dir:
                    # File is already in PreprocessedData, just rename it
                    self.logger.info(f"Renaming structural: {nifti_file.name} → {dest_file.name}")
                    nifti_file.rename(dest_file)
                else:
                    # File is in parent folder, copy it
                    self.logger.info(f"Copying structural: {nifti_file.name} → {dest_file.name}")
                    shutil.copy2(nifti_file, dest_file)

                # Compress if not already compressed
                if not str(dest_file).endswith('.gz'):
                    self.logger.info(f"Compressing {dest_file.name}...")
                    subprocess.run(['gzip', '-f', str(dest_file)], check=True)
                    self.logger.info(f"  → {dest_file.name}.gz")

                structural_found = True
                has_structural = True

            elif self._is_functional_scan(nifti_file):
                # Count existing BIDS functional runs to determine run number
                existing_runs = list(preprocessed_dir.glob(f"{subject.subject_id}_task-rest_run-*_bold.nii*"))
                functional_count = len(existing_runs) + 1

                # Copy/rename functional file
                if str(nifti_file).endswith('.gz'):
                    dest_file = preprocessed_dir / f"{subject.subject_id}_task-rest_run-{functional_count:02d}_bold.nii.gz"
                else:
                    dest_file = preprocessed_dir / f"{subject.subject_id}_task-rest_run-{functional_count:02d}_bold.nii"

                if nifti_file.parent == preprocessed_dir:
                    # File is already in PreprocessedData, just rename it
                    self.logger.info(f"Renaming functional: {nifti_file.name} → {dest_file.name}")
                    nifti_file.rename(dest_file)
                else:
                    # File is in parent folder, copy it
                    self.logger.info(f"Copying functional: {nifti_file.name} → {dest_file.name}")
                    shutil.copy2(nifti_file, dest_file)

                # Compress if not already compressed
                if not str(dest_file).endswith('.gz'):
                    self.logger.info(f"Compressing {dest_file.name}...")
                    subprocess.run(['gzip', '-f', str(dest_file)], check=True)
                    self.logger.info(f"  → {dest_file.name}.gz")

        if structural_found:
            self.logger.info(f"✓ Prepared {functional_count} functional + 1 structural file(s) in PreprocessedData")
        elif has_structural:
            self.logger.info(f"✓ BIDS structural file already exists")
        else:
            self.logger.warning("No structural scan found")

    def _is_functional_scan(self, nifti_file: Path) -> bool:
        """Determine if a NIfTI file is functional (BOLD) using 3dinfo.

        Criteria for functional:
        - Number of timepoints (nv) > 1 (time series)
        - TR > 0.5 seconds (typically 1-3s for fMRI)
        """
        try:
            # Get number of timepoints
            nv_result = subprocess.run(['3dinfo', '-nv', str(nifti_file)],
                                     capture_output=True, text=True, check=True)
            nv = int(nv_result.stdout.strip())

            # Get TR
            tr_result = subprocess.run(['3dinfo', '-tr', str(nifti_file)],
                                     capture_output=True, text=True, check=True)
            tr = float(tr_result.stdout.strip())

            # Functional scans typically have:
            # - Multiple volumes (nv > 1)
            # - TR > 0.5s (typical fMRI TR is 1-3s)
            is_functional = (nv > 1) and (tr >= 0.5)

            if is_functional:
                self.logger.info(f"  {nifti_file.name}: FUNCTIONAL (nv={nv}, TR={tr}s)")
            else:
                self.logger.info(f"  {nifti_file.name}: structural (nv={nv}, TR={tr}s)")

            return is_functional

        except (subprocess.CalledProcessError, ValueError, FileNotFoundError) as e:
            self.logger.warning(f"Could not determine scan type for {nifti_file.name}: {e}")
            # Fallback to filename pattern matching
            name_lower = nifti_file.name.lower()
            is_functional_name = any(kw in name_lower for kw in ['bold', 'func', 'rest', 'resting', 'epi'])
            return is_functional_name

    def _find_functional_file(self, subject: Subject) -> Optional[Path]:
        """Find a functional file dynamically, prioritizing most-processed files first.

        Strategy:
        1. First try common naming patterns (fast)
        2. If not found, scan all .nii/.nii.gz files and use 3dinfo to identify functional
        """
        preprocessed_dir = subject.path / "PreprocessedData"
        subj_id = subject.subject_id

        # Priority 1: Defaced files (most processed)
        defaced_patterns = [
            "func_run{i}_df+orig.nii.gz",
            "func_run{i}_df+orig.nii",
            "func_run{i}_df.nii.gz",
            "func_run{i}_df.nii",
            f"{subj_id}_task-*_run-0{{i}}_bold_df.nii.gz",
            f"{subj_id}_task-*_run-0{{i}}_bold_df.nii",
            "*_df.nii.gz",
            "*_df.nii",
        ]

        # Priority 2: BIDS-formatted files (renamed)
        bids_patterns = [
            f"{subj_id}_task-*_run-0{{i}}_bold.nii.gz",
            f"{subj_id}_task-*_run-0{{i}}_bold.nii",
            f"{subj_id}_task-*_bold.nii.gz",
            f"{subj_id}_task-*_bold.nii",
        ]

        # Priority 3: Generic functional files (original or various formats)
        generic_patterns = [
            "func_run{i}+orig.nii.gz",
            "func_run{i}+orig.nii",
            "func_run{i}.nii.gz",
            "func_run{i}.nii",
            "*rest*run{i}*+orig.nii.gz",
            "*rest*run{i}*+orig.nii",
            "*rest*run{i}*.nii.gz",
            "*rest*run{i}*.nii",
            "*resting*+orig.nii.gz",
            "*resting*+orig.nii",
            "*resting*.nii.gz",
            "*resting*.nii",
            "*rest*+orig.nii.gz",
            "*rest*+orig.nii",
            "*rest*.nii.gz",
            "*rest*.nii",
            "*bold*.nii.gz",
            "*bold*.nii",
            "*func*+orig.nii.gz",
            "*func*+orig.nii",
            "*func*.nii.gz",
            "*func*.nii",
        ]

        # First try pattern matching (fast)
        all_pattern_groups = [defaced_patterns, bids_patterns, generic_patterns]

        for pattern_group in all_pattern_groups:
            # Try with run numbers first
            for i in range(1, 10):
                for pattern_template in pattern_group:
                    if "{i}" in pattern_template:
                        pattern = pattern_template.replace("{i}", str(i))
                    else:
                        pattern = pattern_template

                    matches = list(preprocessed_dir.glob(pattern))
                    if matches:
                        self.logger.info(f"Found functional file by pattern: {matches[0].name}")
                        return matches[0]

            # Try without run numbers
            for pattern in pattern_group:
                if "{i}" not in pattern:
                    matches = list(preprocessed_dir.glob(pattern))
                    if matches:
                        self.logger.info(f"Found functional file by pattern: {matches[0].name}")
                        return matches[0]

        # If no pattern match, scan all NIfTI files and use 3dinfo to identify
        self.logger.info("No functional file found by pattern, scanning all NIfTI files...")
        all_nifti = list(preprocessed_dir.glob("*.nii")) + list(preprocessed_dir.glob("*.nii.gz"))

        for nifti_file in all_nifti:
            if self._is_functional_scan(nifti_file):
                self.logger.info(f"✓ Identified functional scan: {nifti_file.name}")
                return nifti_file

        return None

    def _is_structural_scan(self, nifti_file: Path) -> bool:
        """Determine if a NIfTI file is structural (T1w) using 3dinfo.

        Criteria for structural:
        - Number of timepoints (nv) = 1 (single volume)
        - TR = 0 or very small (< 0.5 seconds)
        - Not in typical functional naming patterns
        """
        try:
            # Get number of timepoints
            nv_result = subprocess.run(['3dinfo', '-nv', str(nifti_file)],
                                     capture_output=True, text=True, check=True)
            nv = int(nv_result.stdout.strip())

            # Get TR
            tr_result = subprocess.run(['3dinfo', '-tr', str(nifti_file)],
                                     capture_output=True, text=True, check=True)
            tr = float(tr_result.stdout.strip())

            # Structural scans typically have:
            # - Single volume (nv = 1)
            # - TR = 0 or very small (< 0.5s)
            is_structural = (nv == 1) and (tr < 0.5)

            if is_structural:
                self.logger.info(f"  {nifti_file.name}: STRUCTURAL (nv={nv}, TR={tr}s)")
            else:
                self.logger.info(f"  {nifti_file.name}: functional (nv={nv}, TR={tr}s)")

            return is_structural

        except (subprocess.CalledProcessError, ValueError, FileNotFoundError) as e:
            self.logger.warning(f"Could not determine scan type for {nifti_file.name}: {e}")
            # Fallback to filename pattern matching
            name_lower = nifti_file.name.lower()
            is_structural_name = any(kw in name_lower for kw in ['t1', 'mprage', 'anat', 'structural'])
            return is_structural_name

    def _find_structural_file(self, subject: Subject) -> Optional[Path]:
        """Find a structural (T1w) file dynamically, prioritizing most-processed files first.

        Strategy:
        1. First try common naming patterns (fast)
        2. If not found, scan all .nii/.nii.gz files and use 3dinfo to identify structural
        """
        preprocessed_dir = subject.path / "PreprocessedData"
        subj_id = subject.subject_id

        # Priority 1: Defaced structural files
        defaced_patterns = [
            f"{subj_id}_T1w_df.nii.gz",
            f"{subj_id}_T1w_df.nii",
            "anat_df+orig.nii.gz",
            "anat_df+orig.nii",
            "anat_df.nii.gz",
            "anat_df.nii",
            "*T1*_df.nii.gz",
            "*T1*_df.nii",
            "*MPRAGE*_df.nii.gz",
            "*MPRAGE*_df.nii",
        ]

        # Priority 2: BIDS-formatted T1w files
        bids_patterns = [
            f"{subj_id}_T1w.nii.gz",
            f"{subj_id}_T1w.nii",
        ]

        # Priority 3: Generic structural files
        generic_patterns = [
            "anat.nii.gz",
            "anat.nii",
            "*T1*.nii.gz",
            "*T1*.nii",
            "*MPRAGE*.nii.gz",
            "*MPRAGE*.nii",
            "*anat*.nii.gz",
            "*anat*.nii",
        ]

        # First try pattern matching (fast)
        all_pattern_groups = [defaced_patterns, bids_patterns, generic_patterns]

        for pattern_group in all_pattern_groups:
            for pattern in pattern_group:
                matches = list(preprocessed_dir.glob(pattern))
                if matches:
                    self.logger.info(f"Found structural file by pattern: {matches[0].name}")
                    return matches[0]

        # If no pattern match, scan all NIfTI files and use 3dinfo to identify
        self.logger.info("No structural file found by pattern, scanning all NIfTI files...")
        all_nifti = list(preprocessed_dir.glob("*.nii")) + list(preprocessed_dir.glob("*.nii.gz"))

        for nifti_file in all_nifti:
            if self._is_structural_scan(nifti_file):
                self.logger.info(f"✓ Identified structural scan: {nifti_file.name}")
                return nifti_file

        return None

    def _detect_scan_parameters(self, subject: Subject):
        """Auto-detect TR and timepoints from functional files."""
        self.logger.info("Attempting to auto-detect scan parameters...")

        # Find a functional file to inspect (prefer run 1)
        func_file = self._find_functional_file(subject)

        if not func_file:
            self.logger.warning("Could not find a functional file to auto-detect parameters. Using defaults.")
            return

        self.logger.info(f"Inspecting file: {func_file}")

        try:
            # Detect TR
            tr_result = subprocess.run(['3dinfo', '-tr', str(func_file)], capture_output=True, text=True, check=True)
            tr_value = float(tr_result.stdout.strip())
            subject.tr = tr_value
            self.logger.info(f"Detected TR: {subject.tr}s")

            # Detect number of timepoints (nv)
            nv_result = subprocess.run(['3dinfo', '-nv', str(func_file)], capture_output=True, text=True, check=True)
            nv_value = int(nv_result.stdout.strip())
            subject.timepoints_per_run = nv_value
            self.logger.info(f"Detected timepoints: {subject.timepoints_per_run}")

            # Count number of runs
            num_runs = self._count_runs(subject)
            self.logger.info(f"Detected runs: {num_runs}")

            # Emit signal with detected parameters
            self.signals.parameters_detected.emit(subject.tr, subject.timepoints_per_run, num_runs)

        except (subprocess.CalledProcessError, FileNotFoundError, ValueError) as e:
            self.logger.error(f"Failed to auto-detect scan parameters: {e}")
            self.logger.warning("Falling back to default values for TR and timepoints.")


    def _should_skip_script(self, subject: Subject, script: ScriptInfo) -> bool:
        """Check if a script should be skipped (already completed)"""
        preprocessed_dir = subject.path / "PreprocessedData"

        # Check for 001a: DICOM to NIfTI - skip if NIfTI files already exist
        if script.name == "001a_dcm2niix":
            # Look for existing NIfTI files
            nifti_patterns = [
                f"{subject.subject_id}_task-rest_run-*.nii.gz",
                f"{subject.subject_id}_task-rest_run-*.nii",
                f"{subject.subject_id}_T1w.nii.gz",
                f"{subject.subject_id}_T1w.nii",
                "*.nii.gz",
                "*.nii"
            ]
            for pattern in nifti_patterns:
                matches = list(preprocessed_dir.glob(pattern))
                if matches:
                    self.logger.info(f"✓ NIfTI files already exist, skipping DICOM conversion")
                    self.logger.info(f"  Found: {[f.name for f in matches[:3]]}")
                    return True

        # Check for 001c: Rename files - skip if files already properly named
        elif script.name == "001c_rename_files":
            expected_files = [
                preprocessed_dir / f"{subject.subject_id}_T1w.nii.gz",
                preprocessed_dir / f"{subject.subject_id}_T1w.nii",
                preprocessed_dir / f"{subject.subject_id}_task-rest_run-01_bold.nii.gz",
                preprocessed_dir / f"{subject.subject_id}_task-rest_run-01_bold.nii"
            ]
            if any(f.exists() for f in expected_files):
                self.logger.info(f"✓ Files already properly named, skipping rename")
                return True

        # Check for 002: Defacing - skip if defaced files exist
        elif script.name == "002_batch_defaceMRI":
            defaced_patterns = ["*_df.nii.gz", "*_df.nii", "*_df+orig.nii.gz"]
            for pattern in defaced_patterns:
                if list(preprocessed_dir.glob(pattern)):
                    self.logger.info(f"✓ Defaced files already exist, skipping defacing")
                    return True

        # Check for 003: FreeSurfer - skip if FreeSurfer output exists
        elif script.name == "003_FreeSurfer_recon":
            fs_dir = subject.path / "FreeSurfer" / subject.subject_id
            if fs_dir.exists() and (fs_dir / "mri" / "brainmask.mgz").exists():
                self.logger.info(f"✓ FreeSurfer reconstruction already complete, skipping")
                return True

        return False

    def _run_script(self, subject: Subject, script: ScriptInfo):
        """Run a single script for a subject"""
        self.logger.info(f"\n{'-' * 60}")
        self.logger.info(f"Running: {script.description}")
        self.logger.info(f"Estimated time: {script.estimated_time}")
        self.logger.info(f"{'-' * 60}")

        # Check if script should be skipped (already done)
        if self._should_skip_script(subject, script):
            subject.status[script.name] = "skipped"
            self.signals.status_updated.emit(subject.subject_id, script.name, "skipped")
            self.signals.script_finished.emit(subject.subject_id, script.name, True)
            self._process_next_script(subject)
            return

        # Re-detect parameters before creating the proc script (in case new files were created)
        if script.name == "004_createAP_struct_rf":
            self.logger.info("Re-checking scan parameters before creating processing script...")
            self._detect_scan_parameters(subject)

        subject.status[script.name] = "running"
        self.signals.script_started.emit(subject.subject_id, script.name)
        self.signals.status_updated.emit(subject.subject_id, script.name, "running")

        # Special handling for script 004_execute_proc
        if script.name == "004_execute_proc":
            self._run_proc_script(subject, script)
            return

        # Build arguments based on script
        args = self._build_script_args(subject, script)

        # Skip if interactive and configured to skip
        if script.name == "003b_FreeSurferQA_SUMA" and self.config.get("skip_interactive"):
            if "--no-gui" not in args:
                args.append("--no-gui")

        # Set up environment variables
        env_vars = {}
        if "FreeSurfer" in script.name or "SUMA" in script.name:
            env_vars["FREESURFER_HOME"] = self.config.get("freesurfer_home")

        # Create and run script runner
        self.current_runner = ScriptRunner(script.script_path, args, env_vars)
        self.current_runner.signals.output_line.connect(
            lambda line: self._handle_output(subject.subject_id, line)
        )
        self.current_runner.signals.error_line.connect(
            lambda line: self._handle_error(subject.subject_id, line)
        )
        self.current_runner.signals.finished.connect(
            lambda success, code: self._handle_script_finished(subject, script, success, code)
        )
        self.current_runner.start()

    def _run_proc_script(self, subject: Subject, script: ScriptInfo):
        """Run the generated proc script"""
        proc_script_path = subject.path / "PreprocessedData" / f"proc.{subject.subject_id}"

        if not proc_script_path.exists():
            self.logger.error(f"Proc script not found: {proc_script_path}")
            self._handle_script_finished(subject, script, False, 1)
            return

        self.current_runner = DirectScriptRunner(proc_script_path)
        self.current_runner.signals.output_line.connect(
            lambda line: self._handle_output(subject.subject_id, line)
        )
        self.current_runner.signals.error_line.connect(
            lambda line: self._handle_error(subject.subject_id, line)
        )
        self.current_runner.signals.finished.connect(
            lambda success, code: self._handle_script_finished(subject, script, success, code)
        )
        self.current_runner.start()

    def _build_script_args(self, subject: Subject, script: ScriptInfo) -> List[str]:
        """Build argument list for a script"""
        dcm_folder = str(subject.path)
        subj_id = subject.subject_id
        freesurfer_home = self.config.get("freesurfer_home")

        args_map = {
            "001a_dcm2niix": [dcm_folder],
            "001c_rename_files": [dcm_folder, subj_id],
            "002_batch_defaceMRI": [dcm_folder],
            "003_FreeSurfer_recon": [dcm_folder, subj_id, freesurfer_home],
            "003b_FreeSurferQA_SUMA": [dcm_folder, subj_id, freesurfer_home],
            "004_createAP_struct_rf": [dcm_folder, subj_id, str(self._count_runs(subject)), str(subject.tr)],
            "005_afni2nifti": [dcm_folder, subj_id, str(self._count_runs(subject)),
                             str(subject.timepoints_per_run)],
            "006_get_motion_files": [dcm_folder, subj_id, str(self._count_runs(subject))],
        }

        return args_map.get(script.name, [])

    def _count_runs(self, subject: Subject) -> int:
        """Count number of functional runs for a subject, prioritizing most-processed files.

        Search order (most processed to least):
        1. Defaced functional files
        2. BIDS-formatted functional files
        3. Original/generic functional files
        """
        preprocessed_dir = subject.path / "PreprocessedData"
        subj_id = subject.subject_id
        count = 0

        # Priority 1: Defaced files (most processed)
        defaced_patterns = [
            "func_run{i}_df+orig.nii.gz",
            "func_run{i}_df+orig.nii",
            "func_run{i}_df.nii.gz",
            "func_run{i}_df.nii",
            f"{subj_id}_task-*_run-0{{i}}_bold_df.nii.gz",
            f"{subj_id}_task-*_run-0{{i}}_bold_df.nii",
        ]

        # Priority 2: BIDS-formatted files
        bids_patterns = [
            f"{subj_id}_task-*_run-0{{i}}_bold.nii.gz",
            f"{subj_id}_task-*_run-0{{i}}_bold.nii",
        ]

        # Priority 3: Generic functional files
        generic_patterns = [
            "func_run{i}+orig.nii.gz",
            "func_run{i}+orig.nii",
            "func_run{i}.nii.gz",
            "func_run{i}.nii",
            "*rest*run{i}*+orig.nii.gz",
            "*rest*run{i}*+orig.nii",
            "*rest*run{i}*.nii.gz",
            "*rest*run{i}*.nii",
            "*_run{i}*+orig.nii.gz",
            "*_run{i}*+orig.nii",
            "*_run{i}*.nii.gz",
            "*_run{i}*.nii",
        ]

        # Search in priority order: defaced -> BIDS -> generic
        all_pattern_groups = [defaced_patterns, bids_patterns, generic_patterns]

        for pattern_group in all_pattern_groups:
            temp_count = 0
            for i in range(1, 10):  # Check up to 9 runs
                found = False
                for pattern_template in pattern_group:
                    if "{i}" in pattern_template:
                        pattern = pattern_template.replace("{i}", str(i))
                    else:
                        continue  # Skip non-run-specific patterns in sequential search

                    matches = list(preprocessed_dir.glob(pattern))
                    if matches:
                        temp_count += 1
                        found = True
                        break  # Found this run in this pattern group

                if not found:
                    break  # No more sequential runs in this pattern group

            # If we found runs in this pattern group, use that count
            if temp_count > 0:
                count = temp_count
                self.logger.info(f"Counted {count} runs from pattern group")
                return count

        # Fallback: Count all functional files without run numbers
        if count == 0:
            bids_files = list(preprocessed_dir.glob(f"{subj_id}_task-*_bold*.nii*"))
            rest_files = list(preprocessed_dir.glob("*rest*.nii*")) + list(preprocessed_dir.glob("*resting*.nii*"))
            count = max(len(bids_files), len(rest_files))

        # Last resort: Default to 1 if at least one functional file exists
        if count == 0:
            if self._find_functional_file(subject):
                count = 1
                self.logger.info("Defaulting to 1 run (single functional file found)")
            else:
                count = 2  # Default assumption if no files found yet
                self.logger.info("No functional files found, assuming 2 runs (default)")

        return count

    def _handle_output(self, subject_id: str, line: str):
        """Handle output line from script"""
        self.logger.info(line)
        self.signals.output_line.emit(subject_id, line)

    def _handle_error(self, subject_id: str, line: str):
        """Handle error line from script"""
        self.logger.warning(line)
        self.signals.error_line.emit(subject_id, line)

    def _handle_script_finished(self, subject: Subject, script: ScriptInfo, success: bool, return_code: int):
        """Handle script completion"""
        if success:
            self.logger.info(f"✓ {script.description} completed successfully")
            subject.status[script.name] = "completed"
            self.signals.status_updated.emit(subject.subject_id, script.name, "completed")
            self.signals.script_finished.emit(subject.subject_id, script.name, True)

            # Check for step-by-step mode
            if self.config.get("execution_mode") == "step-by-step":
                self.is_paused = True
                self.signals.waiting_for_user.emit(subject.subject_id, script.name)
                return  # Wait for user input

            # Continue to next script
            self._process_next_script(subject)

        else:
            self.logger.error(f"✗ {script.description} failed (exit code: {return_code})")
            subject.status[script.name] = "error"
            self.signals.status_updated.emit(subject.subject_id, script.name, "error")
            self.signals.script_finished.emit(subject.subject_id, script.name, False)

            # Check if we should stop on error
            if self.config.get("stop_on_error"):
                self.should_stop = True
                self.signals.subject_finished.emit(subject.subject_id, False)
                self._finish_pipeline(False)
            else:
                # Continue to next script
                self._process_next_script(subject)

    def continue_after_pause(self):
        """Continue execution after user confirmation"""
        if self.is_paused and self.current_subject:
            self.is_paused = False
            self._process_next_script(self.current_subject)

    def skip_current_script(self):
        """Skip the current script"""
        if self.current_subject and self.current_script:
            self.current_subject.status[self.current_script.name] = "skipped"
            self.signals.status_updated.emit(self.current_subject.subject_id, self.current_script.name, "skipped")
            self.is_paused = False
            self._process_next_script(self.current_subject)

    def stop_pipeline(self):
        """Stop the pipeline execution"""
        self.should_stop = True
        if self.current_runner:
            self.current_runner.stop()
        self.logger.warning("Pipeline stopped by user")

    def pause_pipeline(self):
        """Pause pipeline execution"""
        self.is_paused = True
        self.logger.info("Pipeline paused")

    def resume_pipeline(self):
        """Resume pipeline execution"""
        if self.is_paused:
            self.is_paused = False
            self.logger.info("Pipeline resumed")
            if self.current_subject:
                self._process_next_script(self.current_subject)

    def _finish_pipeline(self, success: bool):
        """Finish pipeline execution"""
        self.is_running = False
        self.signals.pipeline_finished.emit(success)

        if success:
            self.logger.info("\n" + "=" * 60)
            self.logger.info("Pipeline completed successfully!")
            self.logger.info("=" * 60)
        else:
            self.logger.warning("\n" + "=" * 60)
            self.logger.warning("Pipeline finished with errors")
            self.logger.warning("=" * 60)

    def get_progress(self) -> tuple:
        """Get current progress (completed, total)"""
        if not self.subjects:
            return (0, 0)

        enabled_scripts = self.get_enabled_scripts()
        total_steps = len(self.subjects) * len(enabled_scripts)
        completed_steps = 0

        for subject in self.subjects:
            for script in enabled_scripts:
                status = subject.status.get(script.name, "pending")
                if status in ["completed", "skipped"]:
                    completed_steps += 1

        return (completed_steps, total_steps)
