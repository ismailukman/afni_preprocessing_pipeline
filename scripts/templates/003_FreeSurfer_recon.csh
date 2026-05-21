#!/usr/bin/env tcsh
# =============================================================================
# 003_FreeSurfer_recon.csh — FreeSurfer cortical reconstruction
# Usage: tcsh 003_FreeSurfer_recon.csh <dcm_folder> <subj_id> <freesurfer_home>
# =============================================================================

if ($#argv < 3) then
    echo "Usage: $0 <dcm_folder> <subj_id> <freesurfer_home>"
    exit 1
endif

set dcmFolder      = "$1"
set subj_id        = "$2"
set freesurfer_dir = "$3"
set fpath          = "${dcmFolder}/PreprocessedData"

echo "=== Step 003: FreeSurfer Reconstruction ==="
echo "  Subject:         ${subj_id}"
echo "  FreeSurfer Home: ${freesurfer_dir}"
echo "  SUBJECTS_DIR:    ${fpath}"

# Set up FreeSurfer environment
setenv FREESURFER_HOME "${freesurfer_dir}"
source "${FREESURFER_HOME}/SetUpFreeSurfer.csh"
setenv SUBJECTS_DIR "${fpath}"

# Find the structural file (prefer refaced)
set struct_file = ""
if (-f "${fpath}/struct_rf.nii.gz") then
    set struct_file = "${fpath}/struct_rf.nii.gz"
else if (-f "${fpath}/struct+orig.nii.gz") then
    set struct_file = "${fpath}/struct+orig.nii.gz"
else if (-f "${fpath}/struct+orig.nii") then
    set struct_file = "${fpath}/struct+orig.nii"
endif

if ("$struct_file" == "") then
    echo "ERROR: No structural file found in ${fpath}"
    exit 1
endif

echo "  Input structural: $struct_file"

# Check if FreeSurfer output already exists
if (-f "${fpath}/${subj_id}/mri/brainmask.mgz") then
    echo "  FreeSurfer output already exists. Skipping recon-all."
    echo "=== Step 003: SKIPPED (already done) ==="
    exit 0
endif

# Auto-detect logical cores so the OpenMP stages of recon-all (mri_ca_register,
# mri_em_register, talairach, etc.) use threads.  Leave 1 core for the system.
# -parallel handles left/right hemisphere stages; -openmp handles compute-heavy
# single-stage routines.  Together they typically take recon-all from 4-8 hrs
# to 1-3 hrs on a modern multicore machine.
set ncpu = 4
if (`uname` == "Darwin") then
    set ncpu = `sysctl -n hw.ncpu`
else
    which nproc >& /dev/null
    if ($status == 0) set ncpu = `nproc`
endif
@ nthreads = $ncpu - 1
if ($nthreads < 2) set nthreads = 2
echo "  Using -openmp ${nthreads} (detected ${ncpu} logical cores)"

setenv OMP_NUM_THREADS $nthreads
setenv FS_OMP_NUM_THREADS $nthreads     # FreeSurfer-specific env var

# Run recon-all
recon-all -all -s "${subj_id}" -i "$struct_file" -parallel -openmp $nthreads

if ($status != 0) then
    echo "ERROR: recon-all failed for ${subj_id}"
    exit 1
endif

# Verify key output exists
if (! -f "${fpath}/${subj_id}/mri/brainmask.mgz") then
    echo "ERROR: recon-all did not produce brainmask.mgz — reconstruction likely failed"
    exit 1
endif

echo "=== Step 003: COMPLETE ==="
