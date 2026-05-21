#!/usr/bin/env tcsh
# =============================================================================
# run_pipeline.csh — Master pipeline runner
# Reads subjects from subjects.csv and runs all enabled processing steps.
# =============================================================================
# Usage: tcsh run_pipeline.csh [config_file] [csv_file]
# =============================================================================

set script_dir = `dirname $0`
set script_dir = `cd "$script_dir" && pwd`

# Default files
set config_file = "${script_dir}/config.cfg"
set csv_file    = "${script_dir}/subjects.csv"

# Override from arguments
if ($#argv >= 1) set config_file = "$1"
if ($#argv >= 2) set csv_file    = "$2"

# --- Load Configuration ---
if (! -f "$config_file") then
    echo "ERROR: Config file not found: $config_file"
    exit 1
endif
source "$config_file"

# --- Validate ---
if (! -f "$csv_file") then
    echo "ERROR: CSV file not found: $csv_file"
    exit 1
endif

set template_dir = "${script_dir}/scripts/templates"
if (! -d "$template_dir") then
    echo "ERROR: Template scripts not found: $template_dir"
    exit 1
endif

# --- Create log directory ---
if (! -d "$log_dir") then
    mkdir -p "$log_dir"
endif

set timestamp = `date +%Y%m%d_%H%M%S`
set master_log = "${log_dir}/pipeline_${timestamp}.log"

echo "============================================================" | tee "$master_log"
echo "  AFNI Preprocessing Pipeline" | tee -a "$master_log"
echo "  Started: `date`" | tee -a "$master_log"
echo "  Config:  $config_file" | tee -a "$master_log"
echo "  CSV:     $csv_file" | tee -a "$master_log"
echo "============================================================" | tee -a "$master_log"

# --- Count subjects ---
set total_subjects = `grep -v '^#' "$csv_file" | grep -v '^$' | wc -l | tr -d ' '`
echo "  Subjects to process: $total_subjects" | tee -a "$master_log"
echo "" | tee -a "$master_log"

set subj_num = 0
set success_count = 0
set error_count = 0

# --- Process each subject ---
foreach line (`grep -v '^#' "$csv_file" | grep -v '^$'`)
    @ subj_num++

    # Parse CSV line
    set subj_id          = `echo "$line" | cut -d',' -f1`
    set session          = `echo "$line" | cut -d',' -f2`
    set dcm_folder       = `echo "$line" | cut -d',' -f3`
    set csv_num_runs     = `echo "$line" | cut -d',' -f4`
    set csv_motion       = `echo "$line" | cut -d',' -f5`
    set csv_skip_steps   = `echo "$line" | cut -d',' -f6`

    # Use per-subject overrides or fall back to config defaults
    set motion_thresh = "$default_motion_threshold"
    if ("$csv_motion" != "") set motion_thresh = "$csv_motion"

    echo "------------------------------------------------------------" | tee -a "$master_log"
    echo "  Subject ${subj_num}/${total_subjects}: ${subj_id} (session: ${session})" | tee -a "$master_log"
    echo "  Folder: ${dcm_folder}" | tee -a "$master_log"
    echo "------------------------------------------------------------" | tee -a "$master_log"

    # Create per-subject error log
    set subj_log = "${log_dir}/subject_${subj_id}_${timestamp}.log"

    # Validate subject folder
    if (! -d "$dcm_folder") then
        echo "  ERROR: Subject folder not found: $dcm_folder" | tee -a "$master_log" "$subj_log"
        @ error_count++
        continue
    endif

    set subj_error = 0

    # Helper function to check if step should be skipped
    # (implemented inline since tcsh doesn't have functions like bash)

    # --- Step 001a: DICOM to NIfTI ---
    if ($run_step_001a == 1) then
        echo "$csv_skip_steps" | grep -q "001a"
        if ($status != 0) then
            echo "  [${subj_num}/${total_subjects}] Running Step 001a: DICOM to NIfTI..." | tee -a "$master_log"
            tcsh "${template_dir}/001a_dcm2niix.csh" "$dcm_folder" |& tee -a "$subj_log"
            if ($status != 0) then
                echo "  ERROR in Step 001a for ${subj_id}" | tee -a "$master_log" "$subj_log"
                set subj_error = 1
            endif
        else
            echo "  [${subj_num}/${total_subjects}] Skipping Step 001a (per CSV skip_steps)" | tee -a "$master_log"
        endif
    endif

    # --- Step 001c: Rename Files ---
    if ($run_step_001c == 1 && $subj_error == 0) then
        echo "$csv_skip_steps" | grep -q "001c"
        if ($status != 0) then
            echo "  [${subj_num}/${total_subjects}] Running Step 001c: Rename Files..." | tee -a "$master_log"
            tcsh "${template_dir}/001c_rename_files.csh" "$dcm_folder" "$subj_id" |& tee -a "$subj_log"
            if ($status != 0) then
                echo "  ERROR in Step 001c for ${subj_id}" | tee -a "$master_log" "$subj_log"
                set subj_error = 1
            endif
        else
            echo "  [${subj_num}/${total_subjects}] Skipping Step 001c (per CSV)" | tee -a "$master_log"
        endif
    endif

    # --- Auto-detect number of runs ---
    set num_runs = "$csv_num_runs"
    if ("$num_runs" == "0" || "$num_runs" == "") then
        set fpath_detect = "${dcm_folder}/PreprocessedData"
        set num_runs = 0
        set i = 1
        while ($i <= 10)
            # Check for defaced or original functional files
            if (-f "${fpath_detect}/func_run${i}_df+orig.nii.gz" || \
                -f "${fpath_detect}/func_run${i}_df+orig.nii"   || \
                -f "${fpath_detect}/func_run${i}+orig.nii.gz"   || \
                -f "${fpath_detect}/func_run${i}+orig.nii") then
                set num_runs = $i
            else
                break
            endif
            @ i++
        end
        if ($num_runs == 0) set num_runs = 1
        echo "  Auto-detected ${num_runs} functional run(s)" | tee -a "$master_log"
    endif

    # --- Step 002: Deface/Reface ---
    if ($run_step_002 == 1 && $subj_error == 0) then
        echo "$csv_skip_steps" | grep -q "002"
        if ($status != 0) then
            echo "  [${subj_num}/${total_subjects}] Running Step 002: Deface/Reface..." | tee -a "$master_log"
            tcsh "${template_dir}/002_batch_defaceMRI.csh" "$dcm_folder" "$num_runs" |& tee -a "$subj_log"
            if ($status != 0) then
                echo "  ERROR in Step 002 for ${subj_id}" | tee -a "$master_log" "$subj_log"
                set subj_error = 1
            endif
        else
            echo "  [${subj_num}/${total_subjects}] Skipping Step 002 (per CSV)" | tee -a "$master_log"
        endif
    endif

    # --- Step 003: FreeSurfer ---
    if ($run_step_003 == 1 && $subj_error == 0) then
        echo "$csv_skip_steps" | grep -q "003"
        if ($status != 0) then
            echo "  [${subj_num}/${total_subjects}] Running Step 003: FreeSurfer recon-all..." | tee -a "$master_log"
            tcsh "${template_dir}/003_FreeSurfer_recon.csh" "$dcm_folder" "$subj_id" "$freesurfer_home" |& tee -a "$subj_log"
            if ($status != 0) then
                echo "  ERROR in Step 003 for ${subj_id}" | tee -a "$master_log" "$subj_log"
                set subj_error = 1
            endif
        else
            echo "  [${subj_num}/${total_subjects}] Skipping Step 003 (per CSV)" | tee -a "$master_log"
        endif
    endif

    # --- Step 003b: SUMA ---
    if ($run_step_003b == 1 && $subj_error == 0) then
        echo "$csv_skip_steps" | grep -q "003b"
        if ($status != 0) then
            set gui_flag = "--no-gui"
            if ($launch_suma_gui == 1) set gui_flag = ""

            echo "  [${subj_num}/${total_subjects}] Running Step 003b: SUMA conversion..." | tee -a "$master_log"
            tcsh "${template_dir}/003b_FreeSurferQA_SUMA.csh" "$dcm_folder" "$subj_id" "$freesurfer_home" $gui_flag |& tee -a "$subj_log"
            if ($status != 0) then
                echo "  ERROR in Step 003b for ${subj_id}" | tee -a "$master_log" "$subj_log"
                set subj_error = 1
            endif
        else
            echo "  [${subj_num}/${total_subjects}] Skipping Step 003b (per CSV)" | tee -a "$master_log"
        endif
    endif

    # --- Step 004: afni_proc.py ---
    if ($run_step_004 == 1 && $subj_error == 0) then
        echo "$csv_skip_steps" | grep -q "004"
        if ($status != 0) then
            echo "  [${subj_num}/${total_subjects}] Running Step 004: afni_proc.py..." | tee -a "$master_log"
            tcsh "${template_dir}/004_createAP_struct_rf.csh" \
                "$dcm_folder" "$subj_id" "$num_runs" \
                "$motion_thresh" "$default_outlier_threshold" \
                "$default_polort" "$default_bandpass_low" "$default_bandpass_high" \
                "$default_blur_size" "$default_tpattern" "$default_template" \
                "$auto_execute_proc" |& tee -a "$subj_log"
            if ($status != 0) then
                echo "  ERROR in Step 004 for ${subj_id}" | tee -a "$master_log" "$subj_log"
                set subj_error = 1
            endif
        else
            echo "  [${subj_num}/${total_subjects}] Skipping Step 004 (per CSV)" | tee -a "$master_log"
        endif
    endif

    # --- Step 005: AFNI to NIfTI ---
    if ($run_step_005 == 1 && $subj_error == 0) then
        echo "$csv_skip_steps" | grep -q "005"
        if ($status != 0) then
            echo "  [${subj_num}/${total_subjects}] Running Step 005: AFNI to NIfTI..." | tee -a "$master_log"
            tcsh "${template_dir}/005_afni2nifti.csh" "$dcm_folder" "$subj_id" "$num_runs" "0" |& tee -a "$subj_log"
            if ($status != 0) then
                echo "  ERROR in Step 005 for ${subj_id}" | tee -a "$master_log" "$subj_log"
                set subj_error = 1
            endif
        else
            echo "  [${subj_num}/${total_subjects}] Skipping Step 005 (per CSV)" | tee -a "$master_log"
        endif
    endif

    # --- Subject Summary ---
    if ($subj_error == 0) then
        @ success_count++
        echo "  SUBJECT ${subj_id}: ALL STEPS COMPLETED SUCCESSFULLY" | tee -a "$master_log"
    else
        @ error_count++
        echo "  SUBJECT ${subj_id}: COMPLETED WITH ERRORS (see ${subj_log})" | tee -a "$master_log"
    endif
    echo "" | tee -a "$master_log"
end

# --- Pipeline Summary ---
echo "============================================================" | tee -a "$master_log"
echo "  Pipeline Complete: `date`" | tee -a "$master_log"
echo "  Successful: ${success_count}/${total_subjects}" | tee -a "$master_log"
echo "  Errors:     ${error_count}/${total_subjects}" | tee -a "$master_log"
echo "  Log:        ${master_log}" | tee -a "$master_log"
echo "============================================================" | tee -a "$master_log"
