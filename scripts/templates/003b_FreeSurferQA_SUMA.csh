#!/usr/bin/env tcsh
# =============================================================================
# 003b_FreeSurferQA_SUMA.csh — Convert FreeSurfer to SUMA format
# Usage: tcsh 003b_FreeSurferQA_SUMA.csh <dcm_folder> <subj_id> <freesurfer_home> [--no-gui]
#
# If --no-gui is passed, only the SUMA conversion runs (no interactive QA).
# =============================================================================

if ($#argv < 3) then
    echo "Usage: $0 <dcm_folder> <subj_id> <freesurfer_home> [--no-gui]"
    exit 1
endif

set dcmFolder      = "$1"
set subj_id        = "$2"
set freesurfer_dir = "$3"
set fpath          = "${dcmFolder}/PreprocessedData"
set launch_gui     = 1

# Check for --no-gui flag
if ($#argv >= 4) then
    if ("$4" == "--no-gui") set launch_gui = 0
endif

echo "=== Step 003b: SUMA Conversion ==="
echo "  Subject: ${subj_id}"
echo "  GUI QA:  ${launch_gui}"

# Set up FreeSurfer environment
setenv FREESURFER_HOME "${freesurfer_dir}"
source "${FREESURFER_HOME}/SetUpFreeSurfer.csh"
setenv SUBJECTS_DIR "${fpath}"

# Check if SUMA directory already exists
if (-d "${fpath}/${subj_id}/SUMA") then
    echo "  SUMA directory already exists."
    if (! -f "${fpath}/${subj_id}/SUMA/${subj_id}_both.spec") then
        echo "  But spec file missing — re-running @SUMA_Make_Spec_FS..."
    else
        echo "  SUMA conversion already done."
        if ($launch_gui == 0) then
            echo "=== Step 003b: SKIPPED (already done, GUI disabled) ==="
            exit 0
        endif
    endif
endif

# Run SUMA conversion
@SUMA_Make_Spec_FS -NIFTI -fspath "${fpath}/${subj_id}/" -sid "$subj_id"

if ($status != 0) then
    echo "ERROR: @SUMA_Make_Spec_FS failed for ${subj_id}"
    exit 1
endif

# Verify key SUMA outputs exist
if (! -f "${fpath}/${subj_id}/SUMA/${subj_id}_both.spec") then
    echo "ERROR: SUMA conversion did not produce ${subj_id}_both.spec"
    exit 1
endif

# Optionally launch GUI for manual QA
if ($launch_gui == 1) then
    echo ""
    echo "  Launching AFNI + SUMA for visual QA..."
    echo "  Close AFNI/SUMA windows when done to continue pipeline."
    afni -niml &
    suma -spec "${fpath}/${subj_id}/SUMA/${subj_id}_both.spec" \
         -sv "${fpath}/${subj_id}/SUMA/${subj_id}_SurfVol.nii"
else
    echo "  GUI QA skipped (--no-gui mode)"
endif

echo "=== Step 003b: COMPLETE ==="
