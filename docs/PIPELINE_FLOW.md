# AFNI Pipeline Processing Flow - Version 1.3.3

## Overview
This document explains how the pipeline maintains consistency across all processing steps by using:
1. **Intelligent scan type detection** - Uses AFNI 3dinfo to identify structural vs functional scans
2. **Priority-based file search** - Ensures each step uses output from previous steps

---

## Intelligent Scan Type Detection (NEW in v1.3.3)

### The Problem
Pipeline couldn't identify structural vs functional scans when files had unfamiliar or non-standard names.

### The Solution
Instead of relying only on filename patterns, the pipeline now uses **AFNI's 3dinfo** to inspect file headers and determine scan type based on image properties.

### Detection Criteria

**Structural Scans (T1w)**:
- Number of volumes (nv) = 1 (single 3D volume)
- TR < 0.5 seconds (or TR = 0)
- Examples: MPRAGE, T1-weighted anatomical

**Functional Scans (BOLD)**:
- Number of volumes (nv) > 1 (4D time series)
- TR ≥ 0.5 seconds (typically 1-3s for fMRI)
- Examples: resting-state, task fMRI

### Two-Stage Detection Strategy

**Stage 1: Fast Pattern Matching**
- Tries common naming conventions first
- Examples: `*T1*.nii`, `*bold*.nii`, `*rest*.nii`
- Fast and works for standard BIDS/AFNI formats

**Stage 2: Intelligent Scanning (Fallback)**
- If pattern matching fails, scans ALL .nii/.nii.gz files
- Uses `3dinfo -nv` and `3dinfo -tr` to inspect each file
- Identifies scan type based on header information
- Works with ANY filename!

### Example Log Output

```
Attempting to auto-detect scan parameters...
No functional file found by pattern, scanning all NIfTI files...
  90-MPRAGE.nii.gz: STRUCTURAL (nv=1, TR=0.0s)
  AN-90-resting.nii.gz: FUNCTIONAL (nv=150, TR=2.0s)
✓ Identified functional scan: AN-90-resting.nii.gz
Inspecting file: AN-90-resting.nii.gz
Detected TR: 2.0s
Detected timepoints: 150
```

### Benefits

1. **Universal Compatibility**: Works with any naming convention
2. **No Manual Renaming**: Process files as-is
3. **100% Accurate**: Based on actual image properties, not guesses
4. **Robust Fallback**: Pattern matching for speed, 3dinfo for reliability

---

## Pipeline Step Flow

### Step 1: DICOM to NIfTI Conversion (001a_dcm2niix)
**Input**: DICOM files from subject folder
**Output**: NIfTI files (.nii or .nii.gz)
**Skip Logic**: Skipped if any .nii or .nii.gz files already exist

### Step 2: Rename Files (001c_rename_files)
**Input**: NIfTI files from Step 1 (or pre-existing)
**Output**: BIDS-formatted files:
- `{subject_id}_T1w.nii.gz`
- `{subject_id}_task-rest_run-01_bold.nii.gz`

**Skip Logic**: Skipped if BIDS-formatted files already exist

### Step 3: Defacing (002_batch_defaceMRI)
**Input**: BIDS-formatted files from Step 2
**Output**: Defaced files:
- `func_run1_df+orig.nii.gz`
- `anat_df+orig.nii.gz`
- Or: `{subject_id}_T1w_df.nii.gz`, `{subject_id}_task-rest_run-01_bold_df.nii.gz`

**Skip Logic**: Skipped if defaced files (*_df.nii.gz) already exist

### Step 4: FreeSurfer Reconstruction (003_FreeSurfer_recon)
**Input**: Structural file (preferably defaced from Step 3)
**Output**: FreeSurfer directory with reconstruction data
**Skip Logic**: Skipped if FreeSurfer/subject_id/mri/brainmask.mgz exists

### Step 5: Create Processing Script (004_createAP_struct_rf)
**Input**: Functional and structural files (preferably defaced from Step 3)
**Output**: `proc.{subject_id}` script
**Parameters Detected**: TR, timepoints, number of runs

### Step 6: Execute Processing Script (004_execute_proc)
**Input**: `proc.{subject_id}` script from Step 5
**Output**: Preprocessed functional data

---

## Priority-Based File Search

### Key Innovation (v1.3.2)
The pipeline now uses **priority-based file search** to ensure each step uses the output from the previous step.

### Search Priority Order

#### For Functional Files (`_find_functional_file()`):
1. **Priority 1 - Defaced files** (most processed):
   - `func_run{i}_df+orig.nii.gz`
   - `func_run{i}_df.nii.gz`
   - `{subject_id}_task-*_run-0{i}_bold_df.nii.gz`
   - `*_df.nii.gz`

2. **Priority 2 - BIDS-formatted files**:
   - `{subject_id}_task-*_run-0{i}_bold.nii.gz`
   - `{subject_id}_task-*_bold.nii.gz`

3. **Priority 3 - Original/generic files**:
   - `func_run{i}.nii.gz`
   - `*rest*.nii.gz`
   - `*resting*.nii.gz`
   - `*bold*.nii.gz`

#### For Structural Files (`_find_structural_file()`):
1. **Priority 1 - Defaced T1w files**:
   - `{subject_id}_T1w_df.nii.gz`
   - `anat_df+orig.nii.gz`
   - `*T1*_df.nii.gz`
   - `*MPRAGE*_df.nii.gz`

2. **Priority 2 - BIDS-formatted T1w files**:
   - `{subject_id}_T1w.nii.gz`

3. **Priority 3 - Original structural files**:
   - `anat.nii.gz`
   - `*T1*.nii.gz`
   - `*MPRAGE*.nii.gz`
   - `*anat*.nii.gz`

#### For Run Counting (`_count_runs()`):
Uses the same priority order as functional files, but counts sequential runs (1, 2, 3, ...).

---

## Example Scenarios

### Scenario 1: Starting with DICOM files
```
1. DICOM Conversion: DICOM → *.nii
2. Rename: *.nii → {subject}_task-rest_run-01_bold.nii.gz
3. Defacing: {subject}_task-rest_run-01_bold.nii.gz → func_run1_df+orig.nii.gz
4. FreeSurfer: Uses anat_df+orig.nii.gz (defaced)
5. Create Proc: Detects parameters from func_run1_df+orig.nii.gz
6. Execute Proc: Uses defaced files
```

### Scenario 2: Starting with NIfTI files (BIDS format)
```
1. DICOM Conversion: SKIPPED (NIfTI files already exist)
2. Rename: SKIPPED (already in BIDS format)
3. Defacing: {subject}_task-rest_run-01_bold.nii.gz → func_run1_df+orig.nii.gz
4. FreeSurfer: Uses anat_df+orig.nii.gz (defaced)
5. Create Proc: Detects parameters from func_run1_df+orig.nii.gz
6. Execute Proc: Uses defaced files
```

### Scenario 3: Resuming after partial processing
```
1. DICOM Conversion: SKIPPED (NIfTI exists)
2. Rename: SKIPPED (BIDS files exist)
3. Defacing: SKIPPED (defaced files exist)
4. FreeSurfer: SKIPPED (reconstruction complete)
5. Create Proc: Detects parameters from func_run1_df+orig.nii.gz
6. Execute Proc: Uses defaced files
```

---

## Benefits of Priority-Based Search

1. **Consistency Across Steps**: Each step automatically uses the most processed version of files available

2. **Flexible Workflow**: Can start from any processing state (DICOM, NIfTI, BIDS, defaced)

3. **Intelligent Skipping**: Automatically skips already-completed steps

4. **Correct Parameter Detection**: Always detects parameters from the latest processed files

5. **Subject-Specific Processing**: Each subject can be at different processing stages

---

## Code Implementation

### Key Methods in `pipeline_manager.py`

```python
def _find_functional_file(subject: Subject) -> Optional[Path]:
    """Find functional file, prioritizing most-processed first"""
    # Search order: defaced → BIDS → generic

def _find_structural_file(subject: Subject) -> Optional[Path]:
    """Find structural file, prioritizing most-processed first"""
    # Search order: defaced T1w → BIDS T1w → generic

def _count_runs(subject: Subject) -> int:
    """Count runs from most-processed files available"""
    # Search order: defaced → BIDS → generic

def _should_skip_script(subject: Subject, script: ScriptInfo) -> bool:
    """Check if script output already exists"""
    # Checks for expected output files
```

---

## Troubleshooting

### Issue: Pipeline uses wrong file version
**Solution**: The priority search ensures the most processed version is always used. Check that output files have the expected naming patterns.

### Issue: Parameter detection fails
**Solution**: The `_find_functional_file()` method searches all known patterns. Check that at least one functional file exists in PreprocessedData.

### Issue: Step incorrectly skipped
**Solution**: The skip logic checks for specific output files. If output exists but is corrupted, delete it and re-run.

---

## Version History

- **v1.3.3**: Added intelligent scan type detection using 3dinfo (header-based)
- **v1.3.2**: Implemented priority-based file search for consistency
- **v1.3.1**: Fixed UnboundLocalError in pattern matching
- **v1.3.0**: Added intelligent script skipping
- **v1.2.0**: Added auto-detected parameters display
- **v1.0.0**: Initial release

---

**Last Updated**: December 11, 2024
**Author**: Lukman E Ismaila Ph.D
**Version**: 1.3.3
**Status**: Production Ready ✅
