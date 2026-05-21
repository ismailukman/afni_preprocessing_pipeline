#!/usr/bin/env tcsh
# 006_get_motion_files.csh - Extract motion parameter files
# Usage: ./006_get_motion_files.csh <dcmFolder> <subj_id> <num_runs>

# Parse arguments
if ($#argv < 3) then
    echo "ERROR: Missing required arguments"
    echo "Usage: $0 <dcmFolder> <subj_id> <num_runs>"
    exit 1
endif

set dcmFolder = "$argv[1]"
set subj_id = "$argv[2]"
set num_runs = "$argv[3]"
set fpath = "${dcmFolder}/PreprocessedData"

set base_path = "${fpath}/${subj_id}/output_${subj_id}"
set output_path = "${fpath}/${subj_id}/motion_files"

echo "=========================================="
echo "Script 006: Get Motion Files"
echo "=========================================="
echo "Subject ID: ${subj_id}"
echo "Number of runs: ${num_runs}"
echo "Source directory: ${base_path}"
echo "Output directory: ${output_path}"

if (! -d "${base_path}") then
    echo "ERROR: Processing output directory not found: ${base_path}"
    exit 1
endif

# Create output folder if needed
if (! -d $output_path) then
    echo "Creating motion files directory..."
    mkdir -p $output_path
endif

# Build file list based on number of runs
set file_list = ()
@ i = 1
while ($i <= $num_runs)
    set file_list = ($file_list "dfile.r0${i}.1D")
    @ i++
end

# Copy and rename motion files
echo ""
echo "Copying motion files..."

foreach f ($file_list)
    set src = "${base_path}/${f}"
    set new_name = "${subj_id}_${f}"
    set dest = "${output_path}/${new_name}"

    if (-e $src) then
        cp $src $dest
        echo "  ✓ Copied: $f → $new_name"
    else
        echo "  ⚠ File not found: $src"
    endif
end

# Get timepoint information
if (-e "${base_path}/errts.${subj_id}.fanaticor+tlrc.HEAD") then
    set ntpts = `3dinfo -nv "${base_path}/errts.${subj_id}.fanaticor+tlrc"`
    echo ""
    echo "Total timepoints: $ntpts"
else
    echo ""
    echo "Note: Could not determine total timepoints (errts file not found)"
endif

echo ""
echo "✓ Motion files extraction completed"
exit 0
