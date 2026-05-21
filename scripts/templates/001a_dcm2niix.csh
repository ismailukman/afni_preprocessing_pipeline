#!/usr/bin/env tcsh
# =============================================================================
# 001a_dcm2niix.csh — Convert DICOM/PAR-REC to NIfTI
# Usage: tcsh 001a_dcm2niix.csh <dcm_folder>
# =============================================================================

if ($#argv < 1) then
    echo "Usage: $0 <dcm_folder>"
    exit 1
endif

set dcmFolder = "$1"
set outputFolder = "${dcmFolder}/PreprocessedData"

# Create the output folder if it doesn't exist
if (! -d "${outputFolder}") then
    mkdir -p "${outputFolder}"
endif

echo "=== Step 001a: DICOM to NIfTI Conversion ==="
echo "  Input:  ${dcmFolder}"
echo "  Output: ${outputFolder}"

# Try dcm2niix_afni first, fall back to dcm2niix_main, then dcm2niix
set cmd_found = 0
foreach cmd (dcm2niix_afni dcm2niix_main dcm2niix)
    which $cmd >& /dev/null
    if ($status == 0) then
        echo "  Using: $cmd"
        $cmd -z y -o "${outputFolder}" "${dcmFolder}"
        set cmd_found = 1
        break
    endif
end

if ($cmd_found == 0) then
    echo "ERROR: No dcm2niix variant found. Install dcm2niix or AFNI."
    exit 1
endif

echo "=== Step 001a: COMPLETE ==="
