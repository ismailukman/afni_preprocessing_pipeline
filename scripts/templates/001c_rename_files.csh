#!/usr/bin/env tcsh
# =============================================================================
# 001c_rename_files.csh — Rename dcm2niix output to standardized format
# Dynamically identifies structural (nv=1) vs functional (nv>1) files
# Usage: tcsh 001c_rename_files.csh <dcm_folder> <subj_id>
# =============================================================================

if ($#argv < 2) then
    echo "Usage: $0 <dcm_folder> <subj_id>"
    exit 1
endif

set dcmFolder = "$1"
set subj_id   = "$2"
set fpath     = "${dcmFolder}/PreprocessedData"

echo "=== Step 001c: Rename Files to Standard Format ==="
echo "  Subject: ${subj_id}"
echo "  Path:    ${fpath}"

if (! -d "$fpath") then
    echo "ERROR: PreprocessedData directory not found: ${fpath}"
    exit 1
endif

# Collect NIfTI files (tcsh-safe: no 2>/dev/null)
set nifti_files = ()
foreach ext_pat (nii.gz nii)
    set matches = (`find "$fpath" -maxdepth 1 -name "*.${ext_pat}" -type f`)
    if ($#matches > 0) then
        set nifti_files = ($nifti_files $matches)
    endif
end

set nifti_count = $#nifti_files

if ($nifti_count == 0) then
    echo "WARNING: No NIfTI files found in ${fpath}"
    exit 1
endif

echo "  Found ${nifti_count} NIfTI file(s)"

# Identify structural vs functional using 3dinfo -nv
set func_count = 0
set struct_count = 0
foreach f ($nifti_files)
    set base = `basename "$f"`

    # Skip already-renamed files
    if ("$base" =~ func_run*) then
        echo "  Skipping already-renamed: $base"
        continue
    endif
    if ("$base" =~ struct*) then
        echo "  Skipping already-renamed: $base"
        continue
    endif
    # Skip defaced/mask files
    if ("$base" =~ df_*) continue
    if ("$base" =~ *_df_*) continue
    if ("$base" =~ *_mask*) continue
    if ("$base" =~ *_rf.*) continue
    if ("$base" =~ *.face.*) continue

    # Get number of volumes (tcsh-safe redirect; filter AFNI *+ warnings)
    set nv = `3dinfo -nv "$f" |& grep -E '^[0-9]'`
    set tr_val = `3dinfo -tr "$f" |& grep -E '^[0-9]'`

    # Validate nv is a number
    if ("$nv" == "" || "$nv" == "0") then
        echo "  WARNING: Cannot read nv for $base — skipping"
        continue
    endif

    # Determine extension
    set ext = "nii.gz"
    if ("$base" =~ *.nii && ! ("$base" =~ *.nii.gz)) set ext = "nii"

    # Derive json source path
    set json_src = `echo "$f" | sed 's/\.nii\.gz$/.json/' | sed 's/\.nii$/.json/'`

    if ($nv > 1) then
        # Functional scan (multiple volumes)
        @ func_count++
        set dest = "${fpath}/func_run${func_count}+orig.${ext}"
        echo "  Functional: $base -> func_run${func_count}+orig.${ext} (nv=${nv}, TR=${tr_val}s)"
        mv "$f" "$dest"
        if (-f "$json_src") then
            mv "$json_src" "${fpath}/func_run${func_count}+orig.json"
        endif
    else
        # Structural scan (single volume)
        @ struct_count++
        if ($struct_count == 1) then
            set dest = "${fpath}/struct+orig.${ext}"
        else
            set dest = "${fpath}/struct${struct_count}+orig.${ext}"
        endif
        echo "  Structural: $base -> `basename $dest` (nv=${nv})"
        mv "$f" "$dest"
        if (-f "$json_src") then
            if ($struct_count == 1) then
                mv "$json_src" "${fpath}/struct+orig.json"
            else
                mv "$json_src" "${fpath}/struct${struct_count}+orig.json"
            endif
        endif
    endif
end

# Verify TR values for renamed functional runs
set func_renamed = (`find "$fpath" -maxdepth 1 -name "func_run*+orig.nii*" -type f`)
foreach f ($func_renamed)
    set tr_check = `3dinfo -tr "$f" |& grep -v ERROR`
    echo "  Verified TR for `basename $f`: ${tr_check}s"
end

echo "  Renamed: ${func_count} functional run(s), ${struct_count} structural file(s)"
echo "=== Step 001c: COMPLETE ==="
