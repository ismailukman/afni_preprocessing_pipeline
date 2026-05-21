#!/usr/bin/env tcsh
# 005_afni2nifti_v2.csh - Convert AFNI output to NIfTI format
# Usage: ./005_afni2nifti_v2.csh <dcmFolder> <subj_id> <num_runs> <timepoints_per_run>

# Parse arguments
if ($#argv < 4) then
    echo "ERROR: Missing required arguments"
    echo "Usage: $0 <dcmFolder> <subj_id> <num_runs> <timepoints_per_run>"
    exit 1
endif

set dcmFolder = "$argv[1]"
set subj_id = "$argv[2]"
set num_runs = "$argv[3]"
set tpts_per_run = "$argv[4]"
set fpath = "${dcmFolder}/PreprocessedData"
set subj = "${subj_id}"

set out_fpath = "${fpath}/${subj}/output_${subj}/"

echo "=========================================="
echo "Script 005: AFNI to NIfTI Conversion"
echo "=========================================="
echo "Subject ID: ${subj_id}"
echo "Number of runs: ${num_runs}"
echo "Timepoints per run: ${tpts_per_run}"
echo "Output directory: ${out_fpath}"

if (! -d "${out_fpath}") then
    echo "ERROR: Output directory not found: ${out_fpath}"
    echo "Please run the processing script (proc.${subj}) first"
    exit 1
endif

# Convert errts files (fanaticor and tproject) for each run
echo ""
echo "Converting errts files..."

@ run = 1
@ start_tp = 0
while ($run <= $num_runs)
    @ end_tp = $start_tp + $tpts_per_run - 1

    echo "Run ${run}: timepoints ${start_tp}..${end_tp}"

    # Convert fanaticor
    if (-e "${out_fpath}/errts.${subj}.fanaticor+tlrc.HEAD") then
        3dAFNItoNIFTI -prefix "${out_fpath}/errts.${subj}.r0${run}.fanaticor+tlrc" \
            "${out_fpath}/errts.${subj}.fanaticor+tlrc[${start_tp}..${end_tp}]"

        if (-e "${out_fpath}/errts.${subj}.r0${run}.fanaticor+tlrc.nii") then
            gzip "${out_fpath}/errts.${subj}.r0${run}.fanaticor+tlrc.nii"
            echo "  ✓ errts run ${run} fanaticor converted"
        endif
    endif

    # Convert tproject
    if (-e "${out_fpath}/errts.${subj}.tproject+tlrc.HEAD") then
        3dAFNItoNIFTI -prefix "${out_fpath}/errts.${subj}.r0${run}.tproject+tlrc" \
            "${out_fpath}/errts.${subj}.tproject+tlrc[${start_tp}..${end_tp}]"

        if (-e "${out_fpath}/errts.${subj}.r0${run}.tproject+tlrc.nii") then
            gzip "${out_fpath}/errts.${subj}.r0${run}.tproject+tlrc.nii"
            echo "  ✓ errts run ${run} tproject converted"
        endif
    endif

    @ start_tp = $end_tp + 1
    @ run++
end

# Convert pb05 scale files for each run
echo ""
echo "Converting pb05 scale files..."

@ run = 1
while ($run <= $num_runs)
    if (-e "${out_fpath}/pb05.${subj}.r0${run}.scale+tlrc.HEAD") then
        3dAFNItoNIFTI -prefix "${out_fpath}/pb05.${subj}.r0${run}.scale+tlrc" \
            "${out_fpath}/pb05.${subj}.r0${run}.scale+tlrc"

        if (-e "${out_fpath}/pb05.${subj}.r0${run}.scale+tlrc.nii") then
            gzip "${out_fpath}/pb05.${subj}.r0${run}.scale+tlrc.nii"
            echo "  ✓ pb05 run ${run} scale converted"
        endif
    endif

    @ run++
end

echo ""
echo "✓ AFNI to NIfTI conversion completed"
exit 0
