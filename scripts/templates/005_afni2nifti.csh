#!/usr/bin/env tcsh
# =============================================================================
# 005_afni2nifti.csh — Convert AFNI output to NIfTI and gzip
# Usage: tcsh 005_afni2nifti.csh <dcm_folder> <subj_id> <num_runs> [timepoints_per_run]
#
# If timepoints_per_run is 0 or not given, it's auto-detected from the data.
# =============================================================================

if ($#argv < 3) then
    echo "Usage: $0 <dcm_folder> <subj_id> <num_runs> [timepoints_per_run]"
    exit 1
endif

set dcmFolder = "$1"
set subj_id   = "$2"
set num_runs  = "$3"
set tpts_arg  = "0"
if ($#argv >= 4) set tpts_arg = "$4"

set fpath     = "${dcmFolder}/PreprocessedData"
set subj      = "${subj_id}"
set out_fpath = "${fpath}/${subj}/output_${subj}"

echo "=== Step 005: AFNI to NIfTI Conversion ==="
echo "  Subject: ${subj_id}"
echo "  Runs:    ${num_runs}"
echo "  Output:  ${out_fpath}"

if (! -d "$out_fpath") then
    echo "ERROR: Output directory not found: ${out_fpath}"
    exit 1
endif

# --- Auto-detect total timepoints from fanaticor dataset ---
set total_tpts = 0
set fanaticor_file = "${out_fpath}/errts.${subj}.fanaticor+tlrc"
if (-f "${fanaticor_file}.HEAD" || -f "${fanaticor_file}.BRIK" || -f "${fanaticor_file}.BRIK.gz") then
    set total_tpts = `3dinfo -nv "${fanaticor_file}" |& grep -v ERROR`
    echo "  Total timepoints (fanaticor): ${total_tpts}"
endif

# Determine timepoints per run
set tpts_per_run = $tpts_arg
if ($tpts_per_run == 0 && $total_tpts > 0 && $num_runs > 0) then
    @ tpts_per_run = $total_tpts / $num_runs
    echo "  Auto-detected timepoints per run: ${tpts_per_run}"
else if ($tpts_per_run > 0) then
    echo "  Timepoints per run (user specified): ${tpts_per_run}"
endif

if ($tpts_per_run <= 0) then
    echo "ERROR: Cannot determine timepoints per run"
    exit 1
endif

# Convert each run
set run = 1
while ($run <= $num_runs)
    @ start_idx = ($run - 1) * $tpts_per_run
    @ end_idx   = $start_idx + $tpts_per_run - 1

    echo "  Run ${run}: timepoints [${start_idx}..${end_idx}]"

    # errts fanaticor
    if (-f "${fanaticor_file}.HEAD" || -f "${fanaticor_file}.BRIK" || -f "${fanaticor_file}.BRIK.gz") then
        set out_prefix = "${out_fpath}/errts.${subj}.r0${run}.fanaticor+tlrc"
        3dAFNItoNIFTI -prefix "$out_prefix" "${fanaticor_file}[${start_idx}..${end_idx}]"
        if (-f "${out_prefix}.nii") gzip "${out_prefix}.nii"
    endif

    # errts tproject
    set tproject_file = "${out_fpath}/errts.${subj}.tproject+tlrc"
    if (-f "${tproject_file}.HEAD" || -f "${tproject_file}.BRIK" || -f "${tproject_file}.BRIK.gz") then
        set out_prefix = "${out_fpath}/errts.${subj}.r0${run}.tproject+tlrc"
        3dAFNItoNIFTI -prefix "$out_prefix" "${tproject_file}[${start_idx}..${end_idx}]"
        if (-f "${out_prefix}.nii") gzip "${out_prefix}.nii"
    endif

    # pb05 scale (per-run files already exist)
    set scale_file = "${out_fpath}/pb05.${subj}.r0${run}.scale+tlrc"
    if (-f "${scale_file}.HEAD" || -f "${scale_file}.BRIK" || -f "${scale_file}.BRIK.gz") then
        set out_prefix = "${out_fpath}/pb05.${subj}.r0${run}.scale+tlrc"
        3dAFNItoNIFTI -prefix "$out_prefix" "$scale_file"
        if (-f "${out_prefix}.nii") gzip "${out_prefix}.nii"
    endif

    @ run++
end

echo "=== Step 005: COMPLETE ==="
