#!/usr/bin/env tcsh
# =============================================================================
# 004_createAP_struct_rf.csh — Generate and optionally execute afni_proc.py
# Usage: tcsh 004_createAP_struct_rf.csh <dcm_folder> <subj_id> <num_runs> \
#        [motion_thresh] [outlier_thresh] [polort] [bp_low] [bp_high] \
#        [blur_size] [tpattern] [template] [auto_execute]
#
# TR is AUTO-DETECTED from functional data — never hard-coded.
# =============================================================================

if ($#argv < 3) then
    echo "Usage: $0 <dcm_folder> <subj_id> <num_runs> [motion_thresh] [outlier_thresh] [polort] [bp_low] [bp_high] [blur_size] [tpattern] [template] [auto_execute]"
    exit 1
endif

set dcmFolder        = "$1"
set subj_id          = "$2"
set num_runs         = "$3"

# Defaults (can be overridden by arguments)
set motion_thresh    = "0.4"
set outlier_thresh   = "0.1"
set polort           = "2"
set bp_low           = "0.01"
set bp_high          = "0.1"
set blur_size        = "6"
set tpattern         = "seq+z"
set template         = "MNI152_2009_template_SSW.nii.gz"
set auto_execute     = "1"

# Parse optional arguments
if ($#argv >= 4  && "$4"  != "") set motion_thresh  = "$4"
if ($#argv >= 5  && "$5"  != "") set outlier_thresh = "$5"
if ($#argv >= 6  && "$6"  != "") set polort         = "$6"
if ($#argv >= 7  && "$7"  != "") set bp_low         = "$7"
if ($#argv >= 8  && "$8"  != "") set bp_high        = "$8"
if ($#argv >= 9  && "$9"  != "") set blur_size      = "$9"
if ($#argv >= 10 && "$10" != "") set tpattern       = "$10"
if ($#argv >= 11 && "$11" != "") set template       = "$11"
if ($#argv >= 12 && "$12" != "") set auto_execute   = "$12"

set fpath     = "${dcmFolder}/PreprocessedData"
set subj      = "${subj_id}"
set anatsubj  = "${subj}"
set outputDir = "${fpath}/${subj}/output_${subj}"
set sdir      = "${fpath}/${subj}/SUMA"

echo "=== Step 004: Create afni_proc.py Processing Script ==="
echo "  Subject:          ${subj_id}"
echo "  Runs:             ${num_runs}"
echo "  Motion threshold: ${motion_thresh}"
echo "  Blur size:        ${blur_size} mm"
echo "  Template:         ${template}"

# Create the subject directory if needed
if (! -d "${fpath}/${subj}") then
    mkdir -p "${fpath}/${subj}"
endif

# --- Auto-detect TR from functional data ---
set tr_val = ""
set func_file = ""

# Find the first functional file (defaced preferred)
foreach pattern (func_run1_df+orig.nii.gz func_run1_df+orig.nii func_run1_df.nii.gz func_run1_df.nii func_run1+orig.nii.gz func_run1+orig.nii)
    if (-f "${fpath}/${pattern}") then
        set func_file = "${fpath}/${pattern}"
        break
    endif
    # Also check inside subject dir
    if (-f "${fpath}/${subj}/${pattern}") then
        set func_file = "${fpath}/${subj}/${pattern}"
        break
    endif
end

if ("$func_file" == "") then
    # Fallback: search for any functional file
    set func_files = ()
    foreach pat (func bold rest)
        set _m = (`find "$fpath" -maxdepth 1 -name "*${pat}*" -type f`)
        if ($#_m > 0) set func_files = ($func_files $_m)
    end
    if ($#func_files > 0) then
        set func_file = "$func_files[1]"
    endif
endif

if ("$func_file" != "") then
    set tr_val = `3dinfo -tr "$func_file" |& grep -v ERROR`
    echo "  AUTO-DETECTED TR: ${tr_val}s (from `basename $func_file`)"
else
    echo "  WARNING: Could not find functional file for TR detection."
    echo "  Falling back to TR=2.0s"
    set tr_val = "2.0"
endif

# Move functional files into subject directory if needed
set run = 1
set dataIn = ()
while ($run <= $num_runs)
    # Check for defaced files first, then originals
    foreach pattern (func_run${run}_df+orig.nii.gz func_run${run}_df+orig.nii func_run${run}_df.nii.gz func_run${run}_df.nii func_run${run}+orig.nii.gz func_run${run}+orig.nii)
        if (-f "${fpath}/${pattern}" && ! -f "${fpath}/${subj}/${pattern}") then
            echo "  Moving ${pattern} into subject directory..."
            mv "${fpath}/${pattern}" "${fpath}/${subj}/${pattern}"
        endif
        if (-f "${fpath}/${subj}/${pattern}") then
            # Prefer _df files
            if ("$pattern" =~ *_df*) then
                set dataIn = ($dataIn "${fpath}/${subj}/${pattern}")
                break
            else
                # Only use non-df if no df version already added for this run
                set already_added = 0
                foreach d ($dataIn)
                    if ("$d" =~ *run${run}*) set already_added = 1
                end
                if ($already_added == 0) set dataIn = ($dataIn "${fpath}/${subj}/${pattern}")
                break
            endif
        endif
    end
    @ run++
end

if ($#dataIn == 0) then
    echo "ERROR: No functional data files found for any run"
    exit 1
endif

echo "  Functional data: $dataIn"

# Create white matter and ventricle masks
# Use pre-existing SUMA masks if available, otherwise create from aparc+aseg
set vent_mask = ""
set wm_mask = ""

# Priority 1: Pre-existing fs_ap masks from @SUMA_Make_Spec_FS
if (-f "${sdir}/fs_ap_latvent.nii.gz") then
    set vent_mask = "${sdir}/fs_ap_latvent.nii.gz"
    echo "  Using existing ventricle mask: fs_ap_latvent.nii.gz"
endif
if (-f "${sdir}/fs_ap_wm.nii.gz") then
    set wm_mask = "${sdir}/fs_ap_wm.nii.gz"
    echo "  Using existing WM mask: fs_ap_wm.nii.gz"
endif

# Priority 2: Previously created subject-named masks
if ("$vent_mask" == "" && -f "${sdir}/${anatsubj}_vent.nii") then
    set vent_mask = "${sdir}/${anatsubj}_vent.nii"
endif
if ("$wm_mask" == "" && -f "${sdir}/${anatsubj}_WM.nii") then
    set wm_mask = "${sdir}/${anatsubj}_WM.nii"
endif

# Priority 3: Create from aparc+aseg (.nii or .nii.gz)
if ("$vent_mask" == "" || "$wm_mask" == "") then
    set aseg_file = ""
    if (-f "${sdir}/aparc+aseg.nii") then
        set aseg_file = "${sdir}/aparc+aseg.nii"
    else if (-f "${sdir}/aparc+aseg.nii.gz") then
        set aseg_file = "${sdir}/aparc+aseg.nii.gz"
    endif

    if ("$aseg_file" != "") then
        if ("$vent_mask" == "") then
            echo "  Creating ventricle mask from $aseg_file..."
            3dcalc -a "$aseg_file" -datum byte \
                   -prefix "${sdir}/${anatsubj}_vent.nii" \
                   -expr 'amongst(a,4,43)'
            set vent_mask = "${sdir}/${anatsubj}_vent.nii"
        endif
        if ("$wm_mask" == "") then
            echo "  Creating white matter mask from $aseg_file..."
            3dcalc -a "$aseg_file" -datum byte \
                   -prefix "${sdir}/${anatsubj}_WM.nii" \
                   -expr 'amongst(a,2,7,16,41,46,251,252,253,254,255)'
            set wm_mask = "${sdir}/${anatsubj}_WM.nii"
        endif
    else
        echo "WARNING: No aparc+aseg found and no pre-existing masks — ventricle/WM ROIs will be missing"
    endif
endif

echo "  Ventricle mask: $vent_mask"
echo "  WM mask: $wm_mask"

# Verify required SUMA files exist before building afni_proc.py command
if (! -f "${sdir}/brain.finalsurfs.nii.gz") then
    echo "ERROR: Required SUMA file not found: ${sdir}/brain.finalsurfs.nii.gz"
    echo "  FreeSurfer recon-all or @SUMA_Make_Spec_FS may have failed."
    exit 1
endif

# Build the afni_proc.py command
echo "  Generating afni_proc.py script: proc.${anatsubj}"

afni_proc.py -subj_id ${subj} \
    -script "${fpath}/proc.${anatsubj}" -scr_overwrite \
    -blocks despike tshift align tlrc volreg blur mask scale regress \
    -radial_correlate_blocks tcat volreg \
    -out_dir "$outputDir" \
    -copy_anat "${sdir}/brain.finalsurfs.nii.gz" \
    -anat_has_skull no \
    -anat_follower anat_w_skull anat "${sdir}/${anatsubj}_SurfVol.nii" \
    -anat_follower_ROI aaseg anat "${sdir}/aparc.a2009s+aseg.nii.gz" \
    -anat_follower_ROI aeseg epi "${sdir}/aparc.a2009s+aseg.nii.gz" \
    -anat_follower_ROI FSVente epi "$vent_mask" \
    -anat_follower_ROI FSWe epi "$wm_mask" \
    -anat_follower_erode FSVente FSWe \
    -dsets $dataIn \
    -tcat_remove_first_trs 0 \
    -tshift_opts_ts -tpattern ${tpattern} -TR ${tr_val}s \
    -align_opts_aea -cost lpc+ZZ -ginormous_move -check_flip \
    -tlrc_base "${template}" \
    -tlrc_NL_warp \
    -volreg_align_to MIN_OUTLIER \
    -volreg_align_e2a \
    -volreg_tlrc_warp \
    -mask_segment_anat yes \
    -mask_segment_erode yes \
    -mask_epi_anat yes \
    -blur_size ${blur_size} \
    -regress_motion_per_run \
    -regress_ROI_PC FSVente 3 \
    -regress_ROI_PC_per_run FSVente \
    -regress_make_corr_vols aeseg FSVente \
    -regress_anaticor_fast \
    -regress_anaticor_label FSWe \
    -regress_censor_motion ${motion_thresh} \
    -regress_censor_outliers ${outlier_thresh} \
    -regress_polort ${polort} \
    -regress_bandpass ${bp_low} ${bp_high} \
    -regress_apply_mot_types demean deriv \
    -regress_est_blur_epits \
    -regress_est_blur_errts \
    -html_review_style pythonic

if ($status != 0) then
    echo "ERROR: afni_proc.py failed to generate processing script"
    exit 1
endif

echo "  Processing script generated: ${fpath}/proc.${anatsubj}"

# Auto-execute or prompt
if ("$auto_execute" == "1") then
    echo ""
    echo "  Auto-executing processing script..."
    tcsh -xef "${fpath}/proc.${anatsubj}" |& tee "${fpath}/output.proc.${anatsubj}.txt"
    if ($status != 0) then
        echo "ERROR: Processing script execution failed"
        exit 1
    endif
else
    echo ""
    echo "  Processing script generated at: ${fpath}/proc.${anatsubj}"
    echo "  To execute manually: tcsh -xef ${fpath}/proc.${anatsubj}"
    echo -n "  Execute now? (y/n): "
    set answer = $<
    if ("$answer" == "y" || "$answer" == "Y") then
        tcsh -xef "${fpath}/proc.${anatsubj}" |& tee "${fpath}/output.proc.${anatsubj}.txt"
    else
        echo "  Skipping execution."
    endif
endif

echo "=== Step 004: COMPLETE ==="
