#!/usr/bin/env tcsh
# =============================================================================
# 002_batch_defaceMRI.csh — Deface functional and reface structural images
# Usage: tcsh 002_batch_defaceMRI.csh <dcm_folder> <num_runs>
# =============================================================================

if ($#argv < 1) then
    echo "Usage: $0 <dcm_folder> [num_runs]"
    exit 1
endif

set dcmFolder = "$1"
set srcFolder = "${dcmFolder}/PreprocessedData"

# Auto-detect number of runs if not provided
if ($#argv >= 2) then
    set num_runs = $2
else
    set num_runs = 0
    set i = 1
    while ($i <= 10)
        if (-f "${srcFolder}/func_run${i}+orig.nii.gz" || -f "${srcFolder}/func_run${i}+orig.nii") then
            set num_runs = $i
        else
            break
        endif
        @ i++
    end
    if ($num_runs == 0) then
        echo "WARNING: No functional runs found to deface"
        set num_runs = 0
    endif
endif

echo "=== Step 002: Deface/Reface MRI ==="
echo "  Source:  ${srcFolder}"
echo "  Runs:   ${num_runs}"

# Deface each functional run
set run = 1
while ($run <= $num_runs)
    set inFile = ""
    if (-f "${srcFolder}/func_run${run}+orig.nii.gz") then
        set inFile = "${srcFolder}/func_run${run}+orig.nii.gz"
    else if (-f "${srcFolder}/func_run${run}+orig.nii") then
        set inFile = "${srcFolder}/func_run${run}+orig.nii"
    endif

    if ("$inFile" != "") then
        set outFile_v1   = "${srcFolder}/df_func_run${run}_df_v1.nii.gz"
        set outFile_mask = "${srcFolder}/df_func_run${run}_df_mask.nii.gz"
        set outFile_df   = "${srcFolder}/func_run${run}_df+orig.nii.gz"

        echo "  Defacing functional run ${run}..."
        @afni_refacer_run -input "$inFile" -mode_deface -anonymize_output -prefix "$outFile_v1"
        3dcalc -a "$outFile_v1" -expr 'notzero(a)' -prefix "$outFile_mask" -datum float
        3dcalc -a "$inFile" -b "$outFile_mask" -expr 'a*b' -prefix "$outFile_df" -datum float

        # Clean up intermediate files
        rm -f "$outFile_v1" "$outFile_mask"
    endif
    @ run++
end

# Reface structural
set structFile = ""
if (-f "${srcFolder}/struct+orig.nii.gz") then
    set structFile = "${srcFolder}/struct+orig.nii.gz"
else if (-f "${srcFolder}/struct+orig.nii") then
    set structFile = "${srcFolder}/struct+orig.nii"
endif

if ("$structFile" != "") then
    set outFile_rf = "${srcFolder}/struct_rf.nii.gz"
    echo "  Refacing structural..."
    @afni_refacer_run -input "$structFile" -mode_reface -anonymize_output -prefix "$outFile_rf"
else
    echo "WARNING: No structural file found to reface"
endif

echo "=== Step 002: COMPLETE ==="
