#!/usr/bin/env python
"""
__author__ = 'Shannon Buckley', 5/8/16

An un-released, refactored version of a post-processing 'pipeline' that combines various outputs from the WashU HCP pipeline to create dense time courses required for downstream analyses. 

Goal is to re-implement existing Matlab & Bash functionality into Pythonic script that takes user args and leverages only open-source languages & packages (e.g. octave).  
"""

import os
import sys
from os import path
import argparse
import subprocess
import shutil
from glob import glob
import config_fnl_preproc
from oct2py import Oct2Py
import time
from datetime import datetime

PROG = 'hcp_post-process_pipeline'
VERSION = '0.7.3'
last_modified_date = '7-19-16'
last_modified_by = 'Shannon B.'

program_desc = """%(prog)s v%(ver)s - last modified by %(mod_by)s on %(last_mod)s -
\n
FNL preproc takes data after the Human Connectome Pipeline completes its final stage ('Surf') and prepares outputs
needed for GUI_environments and Executive Summary.
Directories '/summary' and '/analyses_v2' are created within each SubjID/VISIT folder to gather post-processed products.
Additional outputs of FNL_preproc are found within 'MNINonLinear/Results/' and within each Resting-State sub-directory
therein.
""" % {'prog': PROG, 'ver': VERSION, 'mod_by': last_modified_by, 'last_mod': last_modified_date}

# TAKES 2 COMMAND LINE ARGS: subjectID & path to processed data directory (after HCP_pipeline)

# 1) SubjectID
# e.g. "ABCDPILOT_MSC02"

# 2) folder location of processed data containing unprocessed, T1w, T2w, REST#, MNINonLinear, Scripts
# e.g. /share_name/ROOT_DIR/processed/ABCD-Pilot/ABCDPILOT_MSC02/64ch_2p0/HCP_PIPELINE_NAME/ABCDPILOT_MSC02


# ~~~~~~~~~~~~~~~~ ARGPARSE ~~~~~~~~~~~~~~~~~~ #
def get_parser():

    parser = argparse.ArgumentParser(description=program_desc, prog=PROG, version=VERSION)

    parser.add_argument('-s', '--subject_ID', dest='subject_code', action='store', required=True,
                        help='''Expects subjID, e.g. ABCDPILOT_MSC02/''')

    parser.add_argument('-o', '--output_path', dest='output_path', action='store', required=True,
                        help='''Expects path to the main subject-code folder where all folders & files get created
                        during HCP. Should contain unprocessed, T1w, T2w, some REST folders, MNINonLinear, Scripts''')

    parser.add_argument('-p', '--project_config', dest='project_config', action='store',
                        help='Configure like -p <project> to force a different config...')

    parser.add_argument('-l', '--list', dest='list_path', action='store',
                        help='''Path to list-file of data to process. List-file should be a 2-column,
                        comma-separated values (.csv file) with contents: subjectID, output_folder for each row.''')

    return parser


# ~~~~~~~~~~~~~~~~ GET ENVIRONMENT TO LOAD CONFIGS ~~~~~~~~~~~~~~~~~~ #
def get_environment(output_folder):
    """
    Uses output folder path to infer the environment in which this script is ran. Kinda hacky.

    :param output_folder: user input (absolute path string)
    :return: environment (string) - either 'airc' or 'exacloud' for now
    """

    environment = ''

    if 'group_shares' in output_folder or output_folder.startswith('/scratch/'):
        environment = 'airc'
    elif 'exacloud' in output_folder:
        environment = 'exacloud'
    elif '/mnt/' in output_folder:
        environment = 'rushmore'

    return environment


# ~~~~~~~~~~~~~~~~ GET PROJECT SPECIFIC CONFIG ~~~~~~~~~~~~~~~~~~ #
def get_configs(env, project_name_from_config):
    """
    Takes an environmental binaries config dict and project name to provide more details in a tuple

    :parameter env: environment config (dict)
    :parameter project_name_from_config: project name (string)
    :return: tuple (environment binaries dict, project configs dict, image names list, mask thresholds dict
    """

    if 'airc' in env.lower():

        env_config = config_fnl_preproc.configured_environments['airc']

    elif 'exacloud' in env.lower():

        env_config = config_fnl_preproc.configured_environments['exacloud']

    elif 'rushmore' in env.lower():

        env_config = config_fnl_preproc.configured_environments['rushmore']

    else:

        print 'no configurations for that environment! we only do either "exacloud" or "airc".'
        print 'env was: %s' % env.lower()
        exit(1)

    if project_name_from_config in config_fnl_preproc.configured_projects.keys():

        project_config = config_fnl_preproc.configured_projects[project_name_from_config]

    else:
        print 'no configurations for that project! choices are...\n%s' % config_fnl_preproc.configured_projects.keys()
        exit(1)

    img_names = config_fnl_preproc.image_names

    mask_thresh_vals = config_fnl_preproc.mask_threshold_values_dict

    return env_config, project_config, img_names, mask_thresh_vals


# ~~~~~~~~~~~~~~~~ HELPER FUNCTIONS ~~~~~~~~~~~~~~~~ #
def infer_project_details_from_path(output_path, subject_code):
    """
    Uses output path and subject code (user inputs) to infer other info about project

    :parameter output_path: user input (absolute path string to HCP processed directory)
    :parameter subject_code: user input (string)
    :return: tuple (project_name, visit_ID, pipeline name)
    """

    path_parts = output_path.split('/')[1:]

    if path_parts[-1] == '':
        path_parts.pop()

    if path_parts[-1] == subject_code:
        path_parts.pop()

    pipeline_dir = path.join(path_parts[-1])

    pipe_name = path.basename(pipeline_dir)

    if 'HCP' not in pipe_name:
        print 'We only process data that went through an HCP pipeline! Please check your data or ask a developer.'
        exit()

    visit_dir = path.join(path_parts[-2])

    visitID = path.basename(visit_dir)

    project_name = path.join(path_parts[-4])

    return project_name, visitID, pipe_name


def submit_command(cmd):
    """
    Takes a command-line (string) and runs it in a sub-shell, collecting either errors or info (output) in logger.

    :parameter cmd: command-line (string) you might otherwise run in a shell terminal
    :return: output
    """

    proc = subprocess.Popen(
        cmd
        , shell=True
        , stdout=subprocess.PIPE
        , stderr=subprocess.PIPE
    )

    (output, error) = proc.communicate()

    if error:
        print 'error! %s' % error
    if output:
        print 'output: %s' % output

    return output


def check_complete_inputs(t1_path, regressor_path, t1_brain_path):
    """
    Report True of False if any of these critical inputs (paths) are missing. Report which to std out.

    :param t1_path:
    :param regressor_path:
    :param t1_brain_path:
    :return: Boolean
    """

    check_these_paths = [t1_path, regressor_path, t1_brain_path]

    missing_inputs = [input_path for input_path in check_these_paths if not path.exists(path.join(input_path))]

    if missing_inputs:

        print 'You are missing some inputs! \n%s' % '\n'.join(missing_inputs)

        return False

    else:

        return True


def remove_outputs(list_of_output_paths):
    """
    Takes a list of expected-output paths and removes them if they exist.

    :param list_of_output_paths: full paths
    :return: None
    """

    for output in list_of_output_paths:

        if path.exists(output):

            shutil.rmtree(output)


def check_final_outputs(path_to_subjdir, subjID):
    """
    Report True / False if any expected final outputs are found missing. Print which were not found.

    :param path_to_subjdir: user input
    :param subjID: user input
    :return: Boolean
    """

    missing_files = []

    expected_final_outputs = [

        'summary/all_FD.txt',
        'summary/DVARS_and_FD_CONCA.png',
        'summary/FD_dist.png',
        'analyses_v2/timecourses/Gordon_subcortical.csv',
        'analyses_v2/timecourses/Gordon.csv',
        'analyses_v2/timecourses/Power.csv',
        'analyses_v2/timecourses/Yeo.csv',
        'analyses_v2/matlab_code/FD.mat',
        'analyses_v2/matlab_code/motion_numbers.mat',
        'analyses_v2/matlab_code/power_2014_motion.mat'
    ]

    for out_file in expected_final_outputs:

        if 'REST1' in out_file:
            out_file.replace('%(subj_id)s', subjID)

        if not path.exists(path.join(path_to_subjdir, out_file)):

            missing_files.append(out_file)

    if missing_files:

        print 'You are missing these files! \n%s' % missing_files

        return False

    else:

        return True


# # Count from i to max scenes number, check for t2, create_image_from_template on scene i
# # OUTPUTS A BUNCH OF PNG FILES

def create_image_from_template(output_folder, scene_num, image_name, env_binaries):
    """
    takes a scene number, finds a template and uses wb_command to make an image

    :parameter output_folder: user input
    :parameter scene_num: established in main for-loop
    :parameter image_name:
    :parameter env_binaries: from config
    :return: None
    """
    temp_scene = path.join(output_folder, 'image_template_temp.scene')
    cmd = '%(wb_command)s -show-scene %(temp-scene)s %(scene-num)s %(out-path)s 900 800 > /dev/null 2>&1' % {

        'wb_command': path.join(env_binaries['wb_command']),
        'temp-scene': temp_scene,
        'scene-num' : scene_num,
        'out-path'  : path.join(output_folder, 'summary', '%s.png' % image_name)
    }

    submit_command(cmd)


def build_scene_from_template(t2_path, t1_path, rp_path, lp_path, rwm_path, lwm_path, output_folder):
    """
    Takes several paths and creates a .scene file incorporating them

    :parameter t2_path: e.g. ${OutputFolder}/MNINonLinear/T2w_restore.nii.gz
    :parameter t1_path: e.g. ${OutputFolder}/MNINonLinear/T1w_restore.nii.gz
    :parameter rp_path: right pial surface
    :parameter lp_path: left pial surface
    :parameter rwm_path: right white matter surface
    :parameter lwm_path: left white matter surface
    :parameter output_folder: user input
    :return: None
    """

    temp_scene = path.join(output_folder, 'image_template_temp.scene')

    shutil.copyfile(path.join(path.dirname(sys.argv[0]), 'templates', 'image_template_temp.scene'), temp_scene)

    path_list = [t2_path, t1_path, rp_path, lp_path, rwm_path, lwm_path]

    templates = ['T2_IMG', 'T1_IMG', 'RPIAL', 'LPIAL', 'RWHITE', 'LWHITE']

    new_list = zip(path_list, templates)
    # print 'new_list is: \n%s' % new_list

    for item in new_list:
        # replace templated pathnames and filenames in scene
            with open(temp_scene, 'rw') as f:

                text = f.read()

                string_to_replace = '%s_PATH' % item[1]

                text = text.replace(string_to_replace, item[0])

                filename = path.basename(item[0])

                other_string_to_replace = '%s_NAME'

                text = text.replace(other_string_to_replace, filename)

                f.close()

            # WRITE OUT THE NEW SCENE FILE
            new_scene = path.join(output_folder, 'image_template_temp.scene')

            with open(new_scene, 'w') as g:
                g.write(text)
                g.close()


def count_epi_series(path_to_data_dir):
    """
    Count all epi-series found within unprocessed/NIFTI (excluding SBRef)

    :parameter path_to_data_dir: unprocessed/NIFTI
    :return: tuple (epi_count<int>, list of raw-epi data found in given path)
    """

    raw_epi_list = [path.join(path_to_data_dir, rest) for rest in os.listdir(path_to_data_dir) if 'REST' in rest and 'SBRef' not in rest]
    epi_count = len(raw_epi_list)

    return epi_count, raw_epi_list


# CHECK EACH REST SERIES' DATA
def check_regressors_valid(epi_path, epi_results_path, env_binaries):
    """
    Uses configured path to regressors-checking script, reports whether 'valid' per file

    :parameter epi_path:
    :parameter epi_results_path:
    :parameter env_binaries:
    :return: boolean
    """

    regressors_path = path.join(epi_results_path, 'Movement_Regressors.txt')

    if not path.exists(regressors_path):
        print 'Missing the Movement_Regressors.txt file within %s' % path.join(epi_results_path, path.dirname(epi_path))
        sys.exit()

    invalid_files = []

    validity_test_cmd = "python %(path_to_movment_regressor_check_binary)s --fmri %(raw_epi)s --movmnt %(reg_path)s" % {

        'path_to_movment_regressor_check_binary'    : env_binaries['path_to_movement_regressor_check'],
        'raw_epi'                                   : epi_path,
        'reg_path'                                  : regressors_path
    }

    validty_test_result = submit_command(validity_test_cmd).strip('\n')
    #print '\nvalidty_test_result is: \n%s' % validty_test_result

    if validty_test_result == 'valid':

        #  if valid-files == True
        print '\nmovement regressor file is valid for %s...' % path.basename(epi_path)

    else:

        invalid_files.append(epi_path)
        # print '\nregressor_path is invalid. This is usually due to a random race condition within HCP. ' \
        #       '\n\tPlease rerun HCP vol!\n'

    if invalid_files:
        return False
    else:
        return True


# SETUP AND RUN SLICES (FSL) COMMAND TO MAKE .GIFS
# TODO: remove hard-coded atlas dependencies for a particular species?

def create_t1_atlas_gifs(atlas_path, t1_restore_brain_path, summary_dir, subjectID):
    """
    Takes paths to an atlas and t1_restore_brain and uses slices (FSL) to create and label .gifs

    :parameter atlas_path: absolute path to templates/MNI152_T1_1mm_brain.nii.gz
    :parameter t1_restore_brain_path: path to MNINonLinear/T1w_restore_brain.nii.gz
    :parameter summary_dir: /summary
    :parameter subjectID: user input
    :return: None
    """

    cmd_atlas_in_t1 = 'slices %(t1-path)s %(atlas-path)s -o %(summary-dir)s/%(subjID)s_atlas_in_t1.gif' % {
        't1-path'       : t1_restore_brain_path
        , 'atlas-path'  : atlas_path
        , 'summary-dir' : summary_dir
        , 'subjID'      : subjectID
    }
    cmd_t1_in_atlas = 'slices %(atlas-path)s %(t1-path)s -o %(summary-dir)s/%(subjID)s_t1_in_atlas.gif' % {
        't1-path'       : t1_restore_brain_path
        , 'atlas-path'  : atlas_path
        , 'summary-dir' : summary_dir
        , 'subjID'      : subjectID
    }
    submit_command(cmd_atlas_in_t1)
    submit_command(cmd_t1_in_atlas)


# RUN FSL FLIRT on t1_brain -> reg to t1 2mm isovoxel brain -> t1_brain_2mm_mni_space

def flirt_t1_to_mni_2mm(t1_brain_path, fsl_standard_path):
    """
    Uses FSL's fliter to register given t1-path to a 'standard' brain provided by FSL (2mm_mni_space)

    :parameter t1_brain_path: path to t1
    :parameter fsl_standard_path: path to FSL_DIR/data/standard/MNI152_T1_2mm_brain. FSL_DIR depends on env.
    :return: path to t1-registered-to-2mm-mni-space output file.
    """

    alt_t1_brain = t1_brain_path.replace('_brain.nii.gz', '_brain.2.nii.gz')

    cmd = 'flirt -in %(t1-brain-path)s -ref %(fsl-std)s -applyisoxfm 2 -out %(alt-t1-brain)s' % {
        't1-brain-path' : t1_brain_path
        , 'fsl-std'     : fsl_standard_path
        , 'alt-t1-brain': alt_t1_brain
    }

    submit_command(cmd)

    return path.join(alt_t1_brain)


# # BOOLEAN SWITCH FOR WHETHER OR NOT WE HAVE A T2?
def has_t2(output_folder):
    """
    Checks for path to T2w_restore.nii.gz within MNINonLinear, returns boolean.

    :parameter output_folder: user input
    :return: boolean
    """

    t2_path = path.join(output_folder, 'MNINonLinear', 'T2w_restore.nii.gz')

    if path.exists(t2_path):
        return True
    else:
        print '\nT2 not found, but not a problem!\n'
        return False


# PUSH TO EPI-FILE FOR-LOOP
def get_epi_series_info_from_file(epi_path, subject):
    """
    Infers some information from a given path to an epi-file (raw expected)

    :parameter epi_path:
    :parameter subject:
    :return: tuple (REST<num>, <num>)
    """

    resting_series_name = path.basename(epi_path).lstrip(subject + '_').rstrip('.nii.gz')

    rest_series_num = resting_series_name[4:]

    return resting_series_name, rest_series_num


def make_functional_registration_gifs(t1_2mm_path, subject_code, summary_dir, epi_result_path, rest_series_name):
    """
    Takes paths to epi and t1-data, calls slices (FSL) to create several .gifs used in Executive Summary.

    :parameter t1_2mm_path:
    :parameter subject_code:
    :parameter summary_dir:
    :parameter epi_result_path:
    :parameter rest_series_name: e.g. ('REST2', '2')
    :return: None
    """

    epi_result_path = path.join(epi_result_path)

    t1_space_cmd = 'slices %(t1-2mm-path)s %(epi-path)s -s 2 -o ' \
                   '%(summary-dir)s/%(subject-code)s_%(rest-series-num)s_in_t1.gif' % {

                        't1-2mm-path': t1_2mm_path
                        , 'epi-path' : epi_result_path
                        , 'summary-dir': summary_dir
                        , 'subject-code': subject_code
                        , 'rest-series-num': rest_series_name
                   }

    submit_command(t1_space_cmd)

    functional_space_cmd = 'slices %(epi-path)s %(t1-2mm-path)s -s 2 -o ' \
                           '%(summary-dir)s/%(subject-code)s_t1_in_%(rest-series-num)s.gif' % {

                                't1-2mm-path': t1_2mm_path
                                , 'epi-path' : epi_result_path
                                , 'summary-dir': summary_dir
                                , 'subject-code': subject_code
                                , 'rest-series-num': rest_series_name
                           }

    submit_command(functional_space_cmd)


# # START BUNCH OF CALLS TO FSL USING LONG LIST OF PASSED, POSITIONAL ARGS
def make_wm_mask(seg_brain_dir, seg_brain_file, project_config, subject):
    """
    Takes path to labeled template and thresholds for ventricles according to project-config values.

    :parameter seg_brain_dir: working dir for this step
    :parameter seg_brain_file: segmented brain to be used for thresholding into label components
    :parameter project_config: set of project-specific paths and variables
    :parameter subject: subject_ID -> passed on command-line
    :returns: path to eroded_wm mask
    """

    wm_mask_L = "L_wm_2mm_%s_mask.nii.gz" % subject
    wm_mask_R = "R_wm_2mm_%s_mask.nii.gz" % subject
    wm_mask = "wm_2mm_%s_mask.nii.gz" % subject

    wm_masks = [
        wm_mask_L
        , wm_mask_R
        , wm_mask
    ]

    wm_mask_eroded = "wm_2mm_%s_mask_eroded.nii.gz" % subject

    # USE THRESHOLDS FROM CONFIG TO CREATE MASKS, BEGINNING WITH LEFT-WM
    left_wm_cmd = 'fslmaths %(seg-brain-dir)s/%(seg-brain)s -thr %(wm-lt-L)s -uthr ' \
        '%(wm-ut-L)s %(seg-brain-dir)s/%(wm-mask-out)s' % {

            'seg-brain-dir' : seg_brain_dir
            , 'seg-brain'   : seg_brain_file
            , 'wm-lt-L'     : project_config['wm_lt_L']
            , 'wm-ut-L'     : project_config['wm_ut_L']
            , 'wm-mask-out' : wm_mask_L
        }

    submit_command(left_wm_cmd)

    # MAKE RIGHT-WM
    right_wm_cmd = 'fslmaths %(seg-brain-dir)s/%(seg-brain)s -thr %(wm-lt-R)s -uthr ' \
        '%(wm-ut-R)s %(seg-brain-dir)s/%(wm-mask-out)s' % {

            'seg-brain-dir' : seg_brain_dir
            , 'seg-brain'   : seg_brain_file
            , 'wm-lt-R'     : project_config['wm_lt_R']
            , 'wm-ut-R'     : project_config['wm_ut_R']
            , 'wm-mask-out' : wm_mask_R
        }

    submit_command(right_wm_cmd)

    # COMBINE L-R MASKS AND BINARIZE
    combine_lr_masks_cmd = 'fslmaths %(seg-brain-dir)s/%(wm-mask-r)s -add ' \
        '%(seg-brain-dir)s/%(wm-mask-l)s -bin %(seg-brain-dir)s/%(wm-mask)s' % {

            'seg-brain-dir' : seg_brain_dir
            , 'wm-mask-r'   : wm_mask_R
            , 'wm-mask-l'   : wm_mask_L
            , 'wm-mask'     : wm_mask
        }

    submit_command(combine_lr_masks_cmd)

    # ERODE THE FINAL MASK OUTPUT

    # TODO: revisit whether we want a hard-coded size 2 gaussian kernel here.

    erode_mask_cmd = 'fslmaths %(seg-brain-dir)s/%(wm-mask)s -kernel gauss 2 -ero ' \
        '%(seg-brain-dir)s/%(wm-mask-eroded)s' % {

            'seg-brain-dir'     : seg_brain_dir
            , 'wm-mask'         : wm_mask
            , 'wm-mask-eroded'  : wm_mask_eroded
        }

    submit_command(erode_mask_cmd)

    for each_file in wm_masks:

        file_to_remove = path.join(seg_brain_dir, each_file)

        if path.exists(file_to_remove):

            os.remove(file_to_remove)

    return path.join(seg_brain_dir, wm_mask_eroded)


def make_vent_mask(seg_brain_dir, seg_brain_file, project_config, subject):
    """
    Takes path to labeled template and thresholds for ventricles according to project-config values.

    :parameter seg_brain_dir: working dir for this step
    :parameter seg_brain_file: segmented brain to be used for thresholding into label components
    :parameter project_config: set of project-specific paths and variables
    :parameter subject: subject_ID -> passed on command-line
    :returns: path to vent_mask_eroded
    """

    vent_mask_L = "L_vent_2mm_%s_mask.nii.gz" % subject
    vent_mask_R = "R_vent_2mm_%s_mask.nii.gz" % subject
    vent_mask = "vent_2mm_%s_mask.nii.gz" % subject

    vent_masks = [

        vent_mask_L
        , vent_mask_R
        , vent_mask
    ]

    vent_mask_eroded = "vent_2mm_%s_mask_eroded.nii.gz" % subject

    left_vent_cmd = 'fslmaths %(seg-brain-dir)s/%(seg-brain)s -thr %(vent-lt-L)s -uthr ' \
        '%(vent-ut-L)s %(seg-brain-dir)s/%(vent-mask-out)s' % {

            'seg-brain-dir' : seg_brain_dir
            , 'seg-brain'   : seg_brain_file
            , 'vent-lt-L'     : project_config['vent_lt_L']
            , 'vent-ut-L'     : project_config['vent_ut_L']
            , 'vent-mask-out' : vent_mask_L
        }

    submit_command(left_vent_cmd)

    right_vent_cmd = 'fslmaths %(seg-brain-dir)s/%(seg-brain)s -thr %(vent-lt-R)s -uthr ' \
        '%(vent-ut-R)s %(seg-brain-dir)s/%(vent-mask-out)s' % {

            'seg-brain-dir'     : seg_brain_dir
            , 'seg-brain'       : seg_brain_file
            , 'vent-lt-R'       : project_config['vent_lt_R']
            , 'vent-ut-R'       : project_config['vent_ut_R']
            , 'vent-mask-out'   : vent_mask_R
        }

    submit_command(right_vent_cmd)

    combine_lr_masks_cmd = 'fslmaths %(seg-brain-dir)s/%(vent-mask-r)s -add ' \
        '%(seg-brain-dir)s/%(vent-mask-l)s -bin %(seg-brain-dir)s/%(vent-mask)s' % {

            'seg-brain-dir' : seg_brain_dir
            , 'vent-mask-r' : vent_mask_R
            , 'vent-mask-l' : vent_mask_L
            , 'vent-mask'   : vent_mask
        }

    submit_command(combine_lr_masks_cmd)

    erode_vent_cmd = 'fslmaths  %(seg-brain-dir)s/%(vent-mask)s -kernel gauss 2 -ero ' \
        '%(seg-brain-dir)s/%(vent-mask-eroded)s' % {

            'seg-brain-dir'     : seg_brain_dir
            , 'vent-mask'       : vent_mask
            , 'vent-mask-eroded': vent_mask_eroded
        }

    submit_command(erode_vent_cmd)

    for each_file in vent_masks:

        file_to_remove = path.join(seg_brain_dir, each_file)

        if path.exists(file_to_remove):

            os.remove(file_to_remove)

    return path.join(seg_brain_dir, vent_mask_eroded)


# ~~~~~~~~~~~~~~~~ EXPECTED OUTPUTS FROM MASKING SECTION ~~~~~~~~~~~~~~~~ #
# Outputs (in $WD):
#         NB: all these images are in standard space
#             but at the specified resolution (to match the fMRI - i.e. low-res)
#     ${T1wImageFile}.${FinalfMRIResolution}
#     ${FreeSurferBrainMaskFile}.${FinalfMRIResolution}
#     ${BiasFieldFile}.${FinalfMRIResolution}
#     Scout_gdc_MNI_warp     : a warpfield from original (distorted) scout to low-res MNI
#
# Outputs (not in either of the above):
#     ${OutputTransform}  : the warpfield from fMRI to standard (low-res)
#     ${OutputfMRI}
#     ${JacobianOut}
#     ${ScoutOutput}
#          NB: last three images are all in low-res standard space

# ~~~~~~~~~~~~~~~~ END MAKE WM VENT MASKS SCRIPT ~~~~~~~~~~~~~~~~ #

# ~~~~~~~~~~~~~~~~ RETURN TO FNL_preproc.sh SCRIPT IN PROGRESS ~~~~~~~~~~~~~~~~ #

# ~~~~~~~~~~~~~~ MAKE FOLDERS

def make_output_dirs(desired_dirs):
    """
    Creates several output directories and ensures they are group-permitted (0775)

    :parameter desired_dirs: list of paths you want to create
    :return: list of paths created
    """

    output_paths_list = []

    for desired_dir in desired_dirs:

        output_dir = path.abspath(path.join(desired_dir))

        os.makedirs(output_dir, 0775)

        output_paths_list.append(output_dir)

    return output_paths_list


def calculate_wm_vent_means(epi_result_path, fmri_name, fnl_preproc_dir, eroded_vent_mask, eroded_wm_mask):
    """
    Takes eroded wm and vent-masks and calculates _mean.txt files for each.

    :parameter epi_result_path: path to current epi within main for-loop
    :parameter fmri_name: e.g. REST1
    :parameter fnl_preproc_dir: path to MNINonLinear/Results/REST1/FNL_preproc
    :parameter eroded_vent_mask: path to eroded ventricle mask
    :parameter eroded_wm_mask: path to eroded white matter mask
    :return: tuple (path to vent_mean, path to wm_mean)
    """
    vent_input_file = path.join(epi_result_path, fmri_name + '.nii.gz')
    vent_output_file = path.join(fnl_preproc_dir, fmri_name + '_vent_mean.txt')

    vent_mean_cmd = 'fslmeants -i %(vent-input-file)s -o %(vent-out-file)s -m %(eroded-vent-mask)s' % {
        'vent-input-file'        : vent_input_file
        , 'vent-out-file'        : vent_output_file
        , 'eroded-vent-mask'     : eroded_vent_mask
    }
    submit_command(vent_mean_cmd)

    wm_input_file = path.join(epi_result_path, fmri_name + '.nii.gz')
    wm_output_file = path.join(fnl_preproc_dir, fmri_name + '_wm_mean.txt')

    wm_mean_cmd = 'fslmeants -i %(wm-in-file)s -o %(wm-out-file)s -m %(eroded-wm-mask)s' % {
        'wm-in-file'        : wm_input_file
        , 'wm-out-file'     : wm_output_file
        , 'eroded-wm-mask'  : eroded_wm_mask
    }

    submit_command(wm_mean_cmd)

    return vent_output_file, wm_output_file


def write_ml_config_and_run_octave(fnl_preproc_dir, env_config, project_config, rest_seriesname,
                                   tr, summary_dir, cifti_out, epi_result_dir, fnl_preproc_cifti_name):
    """
    Takes several important variables from data, creates a script and runs it in a call to Octave. Per rsfMRI series.

    :parameter fnl_preproc_dir: path to MNINonLinear/Results/REST?/FNL_preproc
    :parameter env_config: binaries dict
    :parameter project_config: dictionary of project-specific params (formerly found in setup_env.sh)
    :parameter rest_seriesname: e.g. REST1
    :parameter tr: repetition time of the epi file
    :parameter summary_dir: path to /summary
    :parameter cifti_out: e.g. /path/to/REST1_Atlas.dtseries.nii
    :parameter epi_result_dir: path to MNINonLinear/Results/REST1
    :parameter fnl_preproc_cifti_name: REST1_FNL_preproc_Atlas.dtseries.nii

    :return: None
    """

    json_config_path = path.join(fnl_preproc_dir, 'FNL_preproc_mat_config.json')

    mean_wm_txt = path.join(fnl_preproc_dir, rest_seriesname + '_wm_mean.txt')
    mean_vent_txt = path.join(fnl_preproc_dir, rest_seriesname + '_vent_mean.txt')
    movement_regressors_txt = path.join(epi_result_dir, 'Movement_Regressors.txt')

    motion_filename = project_config['motion_filename']

    if path.exists(json_config_path):
        os.remove(json_config_path)

    json_file_contents = """
            {
                "path_wb_c"                       : "%(wb_command_path)s",
                "FNL_preproc_path"                : "%(path-to-this-program-dir)s",
                "HCP_Mat_Path"                    : "%(hcp-mat-path)s",
                "framewise_disp_path"             : "%(framewise_disp_path)s",
                "bp_order"                        : %(band-pass-filter-order)s,
                "lp_Hz"                           : %(low-pass-Hz)s,
                "hp_Hz"                           : %(high-pass-Hz)s,
                "TR"                              : %(TR)s,
                "fd_th"                           : %(fd-threshold)s,
                "path_cii"                        : "%(path-cifti)s",
                "path_ex_sum"                     : "%(ex_sum_dir)s",
                "FNL_preproc_CIFTI_name"          : "%(FNL_preproc_CIFTI_name)s",
                "file_wm"                         : "%(wm-mean-txt)s",
                "file_vent"                       : "%(vent-mean-txt)s",
                "file_mov_reg"                    : "%(movement-regressors-txt)s",
                "motion_filename"                 : "%(motion-filename)s",
                "skip_seconds"                    : %(skip_seconds)s,
                "brain_radius_in_mm"              : %(brain_radius_in_mm)s,
                "expected_contiguous_frame_count" : %(expected_contiguous_frame_count)s,
                "result_dir"                      : "%(fnl-preproc-dir)s"
            }
            """ % {

        'wb_command_path'                   : env_config['wb_command']
        , 'path-to-this-program-dir'        : path.dirname(sys.argv[0])
        , 'hcp-mat-path'                    : env_config['HCP_Mat_Path']
        , 'framewise_disp_path'             : env_config['framewise_disp_path']
        , 'band-pass-filter-order'          : project_config['bp_order']
        , 'low-pass-Hz'                     : project_config['lp_Hz']
        , 'high-pass-Hz'                    : project_config['hp_Hz']
        , 'TR'                              : tr
        , 'fd-threshold'                    : project_config['fd_th']
        , 'path-cifti'                      : cifti_out
        , 'ex_sum_dir'                      : summary_dir
        , 'FNL_preproc_CIFTI_name'          : path.basename(fnl_preproc_cifti_name)
        , 'wm-mean-txt'                     : mean_wm_txt
        , 'vent-mean-txt'                   : mean_vent_txt
        , 'movement-regressors-txt'         : movement_regressors_txt
        , 'motion-filename'                 : motion_filename
        , 'skip_seconds'                    : project_config['skip_seconds']
        , 'brain_radius_in_mm'              : project_config['brain_radius_in_mm']
        , 'expected_contiguous_frame_count' : project_config['expected_contiguous_frame_count']
        , 'fnl-preproc-dir'                 : fnl_preproc_dir
    }

    # open new file to write
    print '\nWriting new config...'

    with open(json_config_path, 'w') as f:

        # write config guts
        f.write(json_file_contents)

        f.close()

    # THIS SECTION IS NOT WORKING!
    # REFERENCE
        # single quotes are required inside the parens in octave call!
        # ${octave} --traditional --quiet --path `dirname $0` --eval  "FNL_preproc_Matlab('${UnwarpDir}/${config}')"

    # TODO: test whether we can add an exit and have this now work
    cmd = """%(octave-path)s --traditional --quiet --path %(this-program-dir)s --eval  "FNL_preproc_Matlab(%(config-path)s)"
        """ % {
        'octave-path'       : env_config['octave']
        , 'this-program-dir': path.dirname(sys.argv[0])
        , 'config-path'     : json_config_path}

    # WRITE OUT CMD FOR LATER REVIEW / DEBUGGING...

    cmd_file_path = path.join(fnl_preproc_dir, 'octave_cmd.txt')
    print '\nRunning Command through Octave, check the cmd-line at: \n%s' % cmd_file_path
    with open(cmd_file_path, 'w') as c:
        c.write(cmd)
        c.close()

    oc = Oct2Py(executable=env_config['octave'], timeout=120)
    oc.addpath(path.dirname(sys.argv[0]))
    oc.addpath(path.join(path.dirname(sys.argv[0])), 'scripts')

    try:

        oc.FNL_preproc_Matlab(json_config_path)

    except Exception, e:

        motion_filename_out = path.join(fnl_preproc_dir, motion_filename)

        if path.exists(motion_filename_out):
            print '\nOctave Timed out, HOWEVER we seem to have the necessary outputs \n%s' % motion_filename_out
        else:
            print "\nLet's try waiting another minute, then I'l exit..."
            time.sleep(60)
            oc.exit()


def pull_tr_from_raw_resting_state(nifti_path):
    """
    Uses flshd to pull a TR string from a given nifti path. Intended for epi-data here, but will handle any nii.

    :parameter nifti_path: path to NIFTI or .nii.gz file
    :return tr: repetition time (string) in whichever units that are stored in that file (originates in PATH_GUI
    """
    cmd = """fslhd %s | grep pixdim4 | gawk '{ print $2 }' """ % path.join(path.abspath(nifti_path))

    tr = submit_command(cmd)

    return float(tr)


def merge_ciftis(env_config, mni_results_dir, fnl_preproc_dir, rest_num, subj_ID, rest_prefix):
    """
    Should run once per REST to either create or merge a cifti, depending upon its series-num (merge if > 1)

    :param env_config: dict of binaries specific to the processing environment in which the code was called
    :param mni_results_dir: path to the output_folder(supplied by user)/MNINonLinear/Results
    :param fnl_preproc_dir: path to a given directory with pattern = MNINonLinear/Result/REST<series_num>/FNL_preproc
    :param rest_num: number (string) indicating which series of resting-state data we are working on
    :param subj_ID: subject code (also supplied by user)
    :param rest_prefix: e.g.  REST1
    :return: path to merged cifti file
    """

    merged_cifti = path.join(mni_results_dir, subj_ID + '_FNL_preproc_Atlas.dtseries.nii')
    # IF THE FIRST series, make a copy & remove source
    if int(rest_num) == 1:

        print '\nCopying first resting cifti to start the merging...Check for output: \n%s\n' % merged_cifti

        src = path.join(fnl_preproc_dir, 'REST1_FNL_preproc_Atlas.dtseries.nii')

        cp_cmd = 'cp %s %s' % (src, merged_cifti)

        submit_command(cp_cmd)

    elif int(rest_num) > 1:  # WB_COMMAND CIFTI MERGE if REST num > 1

        merge_cmd = "%(wb-command)s -cifti-merge %(merged-cifti)s -cifti %(merged-cifti)s " \
                    "-cifti %(fnl-preproc-cifti-name)s" % {

                        'wb-command'                : env_config['wb_command']
                        , 'merged-cifti'            : merged_cifti
                        , 'fnl-preproc-cifti-name'  : path.join(fnl_preproc_dir, rest_prefix + '_FNL_preproc_Atlas.dtseries.nii')
                    }

        submit_command(merge_cmd)

    return merged_cifti


# Make parcellated time courses
def dense_ts_to_spec(env_config, merged_cifti_path, spec_file_path):
    """
    Calls wb_command to create a .spec file from merged, dense time series cifti.

    :parameter config: environmental binaries config dictionary (specific to environment)
    :parameter merged_cifti_path: path to merged cifti file
    :parameter subject: subjID (user input)
    :parameter output_folder: path to processed data (user input)
    :return: path to .spec file output
    """

    cmd = '%(wb_command)s -add-to-spec-file %(spec-file)s INVALID %(all-cifti)s' % {
        'wb_command' : env_config['wb_command']
        , 'spec-file': spec_file_path
        , 'all-cifti': merged_cifti_path
    }

    submit_command(cmd)


def make_sym_links(links_dict):
    """
    Takes dictionary of location : target string pairs and creates sym-links. (key=path, value=link-label)

    :param links_dict:
    :return: None
    """

    for k, v in links_dict.items():
        cmd = 'ln -s %s %s' % (k, v)
        submit_command(cmd)


# GET THIS path_to_label_files FROM INITIAL CONFIG IMPORT

def make_subcort_and_surface_parcellations(env_config, mni_nonlinear_results_path, subj_code, merged_cifti_path, spec_file):
    """
    Produces the parcellations in the format: /MNINonLinear/Results/subjID_FNL_preproc_<parcel>_subcortical.psteries.nii

    :parameter env_config:
    :parameter mni_nonlinear_results_path:
    :parameter subj_code:
    :parameter merged_cifti_path:
    :parameter spec_file:
    :return: path to final-output file
    """
    path_to_label_files = path.join(env_config['path_to_label_files'])

    if not path.exists(path.join(path_to_label_files)):

        print '\nCould not locate the path_to_label_files needed from env_config\n'

        sys.exit(1)

    labels_list = os.listdir(path_to_label_files)

    parcellations_list = []

    for parcel in labels_list:

        print '\nCreating parcellations using: %s' % parcel

        surface_subcort_label = path.join(path_to_label_files, parcel, 'fsLR',
                                          parcel + '.subcortical.32k_fs_LR.dlabel.nii')

        if path.exists(surface_subcort_label):

            parcellation_time_series = path.join(mni_nonlinear_results_path,
                                            subj_code + '_FNL_preproc_' + parcel + '_subcortical.ptseries.nii')

            parcellation_cmd = '%(wb-command)s -cifti-parcellate %(merged-cifti-file)s %(surf-subcor-label)s ' \
                               'COLUMN %(file-out)s' % {

                                'wb-command'            : env_config['wb_command']
                                , 'merged-cifti-file'   : merged_cifti_path
                                , 'surf-subcor-label'   : surface_subcort_label
                                , 'file-out'            : parcellation_time_series
                                }
            print '\nAbout to run: \n%s' % parcellation_cmd

            submit_command(parcellation_cmd)

            print '\nAdding new parcellation to .spec...'

            add_to_spec_cmd = '%(wb-command)s -add-to-spec-file %(spec-file)s INVALID %(file-out)s' % {

                                'wb-command'            : env_config['wb_command']
                                , 'spec-file'           : spec_file
                                , 'file-out'            : parcellation_time_series
                                }

            submit_command(add_to_spec_cmd)

            parcellations_list.append(parcellation_time_series)
        else:
            print '\nMissing this parcel: \n%s' % parcel
            continue

# SUBCORT-ONLY PARCELLATION
def make_subcortical_only_parcellations(env_config, mni_nonlinear_results_path, subj_code, merged_cifti_path, spec_file):
    """
    Produces the parcellations in the format: /MNINonLinear/Results/subjID_FNL_preproc_<parcel>_subcortical.psteries.nii

    :parameter env_config:
    :parameter mni_nonlinear_results_path:
    :parameter subj_code:
    :parameter merged_cifti_path:
    :parameter spec_file:
    :return: path to final-output file
    """
    path_to_label_files = path.join(env_config['path_to_label_files'])

    if not path.exists(path_to_label_files):

        print '\nCould not locate the path_to_label_files needed from env_config\n'

        exit(1)

    for parcel in os.listdir(path_to_label_files):

        subcort_label = path.join(path_to_label_files, parcel, 'fsLR',
                                          parcel + '.subcortical.32k_fs_LR.dlabel.nii')

        if path.exists(subcort_label):

            super_cool_file_out = path.join(mni_nonlinear_results_path,
                                            subj_code + '_FNL_preproc_' + parcel + '.ptseries.nii')

            parcellation_cmd = '%(wb-command)s -cifti-parcellate %(merged-cifti-file)s %(subcor-label)s ' \
                               'COLUMN %(file-out)s' % {

                                'wb-command'            : env_config['wb_command']
                                , 'merged-cifti-file'   : merged_cifti_path
                                , 'subcor-label'        : subcort_label
                                , 'file-out'            : super_cool_file_out
                                }

            submit_command(parcellation_cmd)

            add_to_spec_cmd = '%(wb-command)s -add-to-spec-file %(spec-file)s INVALID %(file-out)s' % {

                                'wb-command'            : env_config['wb_command']
                                , 'spec-file'           : spec_file
                                , 'file-out'            : super_cool_file_out
                                }

            submit_command(add_to_spec_cmd)

        else:
            print '\nDo not have or cannot access the combined surface-subcort label you have requested: \n%s' % \
                  subcort_label
            continue


# START PREP
def concat_FD_text_files(summary_dir):

    rest_txt_files = [txt_file for txt_file in os.listdir(summary_dir) if 'FD_REST' in txt_file]
    print '\nconcatenating FD_REST?.txt files...\n'

    for rest_txt in rest_txt_files:
        with open(path.join(summary_dir, rest_txt), 'r') as f:
            file_text = f.read()
            f.close()
        with open(path.join(summary_dir, 'all_FD.txt'), 'a') as g:
            g.write(file_text)
            g.close()


def get_motion_numbers_list(mni_results_dir):

    file_pattern = path.join(mni_results_dir, 'REST*', 'FNL_preproc', 'motion_numbers.txt')

    motion_numbers_list = glob(file_pattern)

    print motion_numbers_list

    return motion_numbers_list


# PREP FOR ANALYSES SECTION
def cifti_to_txt(mni_results_dir):

    pass


# # CALL OUT TO OCTAVE
# ${octave} --traditional --quiet --path `dirname $0` --eval  "analyses_v2('${v2_config_path}')"
def write_analyses_config_and_run_octave(env_config, project_config, output_folder, tr, summary_dir, mni_results_path):

    json_file_path = path.join(output_folder, 'analyses_v2', 'matlab_code', 'analyses_v2_mat_config.json')

    with open(json_file_path, 'w') as f:

        json_file_contents = """
        {
            "path_wb_c"                       : "%(wb_command_path)s",
            "FNL_preproc_path"                : "%(path-to-this-program)s",
            "framewise_disp_path"             : "%(framewise_disp_path)s",
            "epi_TR"                          : %(TR)s,
            "summary_Dir"                     : "%(summary_Dir)s",
            "skip_seconds"                    : %(skip_seconds)s,
            "brain_radius_in_mm"              : %(brain_radius_in_mm)s,
            "expected_contiguous_frame_count" : %(expected_contiguous_frame_count)s,
            "result_dir"                      : "%(code_folder)s",
            "path_motion_numbers"             : "%(mni_nonlinear_results_path)s",
            "path_ciftis"                     : "%(ciftis_folder)s",
            "path_timecourses"                : "%(timecourses_folder)s"
        }
        """ % {
            'wb_command_path'                   : env_config['wb_command']
            , 'path-to-this-program'            : path.dirname(path.abspath(sys.argv[0]))
            , 'framewise_disp_path'             : env_config['framewise_disp_path']
            , 'TR'                              : tr
            , 'summary_Dir'                     : summary_dir
            , 'skip_seconds'                    : project_config['skip_seconds']
            , 'brain_radius_in_mm'              : project_config['brain_radius_in_mm']
            , 'expected_contiguous_frame_count' : project_config['expected_contiguous_frame_count']
            , 'code_folder'                     : path.join(output_folder, 'analyses_v2', 'matlab_code')
            , 'mni_nonlinear_results_path'      : mni_results_path
            , 'ciftis_folder'                   : path.join(output_folder, 'analyses_v2', 'workbench')
            , 'timecourses_folder'              : path.join(output_folder, 'analyses_v2', 'timecourses')
        }

        f.write(json_file_contents)

        f.close()

    print '\nTime Update: %s' % datetime.now()

    # TODO: try working inside a temp_dir -> try to avoid conversion to float?
    oc = Oct2Py(executable=env_config['octave'], timeout=800, temp_dir=path.join(output_folder, 'analyses_v2',
                                                                                 'matlab_code'), convert_to_float=False)
    oc.addpath(path.dirname(sys.argv[0]))
    oc.addpath(path.join(path.dirname(sys.argv[0])), 'scripts')

    # TODO: see if adding this path helps things along...
    oc.addpath(env_config['HCP_Mat_Path'])

    # TRY TO RUN .m FILE -> analyses_v2.m
    try:
        oc.analyses_v2(json_file_path)

    except Exception, e:

        final_output = path.join(summary_dir, 'FD_dist.png')

        if path.exists(final_output):
            print 'We have the final output from this octave section!\n%s' % final_output
        else:
            print "\nLet's try waiting another few minutes, then exit octave... \n%s" % e
            time.sleep(600)
            oc.exit()
            if not path.exists(final_output):

                print '\nBe sure to check your outputs, we may have missed something...\n'


def copy_motion_frames_matfile(src, dst):
    """
    Copies all *.mat files found in src to dst.

    :param src: source path where the .mat files can be found
    :param dst: destination path where you want the .mat files to go
    :return: None
    """

    copy_command = 'cp %s/*.mat %s' % (src, dst)

    submit_command(copy_command)


def write_frames_per_scan(mni_results_dir, summary_dir):
    """
    Makes a list of all MNI/Results/REST?/Movement_Regressors.txt files and reports line-counts to another .txt

    :param mni_results_dir: absolute path to MNINonLinear/Results
    :return: path to final output (frames_per_scan.txt)
    """

    regressor_pattern = path.join(mni_results_dir, 'REST*/Movement_Regressors.txt')

    # regressor_paths_list = glob(regressor_pattern)

    frames_per_scan_out = path.join(summary_dir, 'frames_per_scan.txt')

    # If it's already there (re-run), remove it
    if path.exists(frames_per_scan_out):

        os.remove(frames_per_scan_out)

    cmd = 'for mov_reg in `ls %s` ; do frames=`wc -l < ${mov_reg}`; echo ${frames} >> %s; done' % (
        regressor_pattern
        , frames_per_scan_out
    )
    submit_command(cmd)

    return frames_per_scan_out


def wait_another_min():
    time.sleep(60)


def main():

    # HANDLE ARGS
    parser = get_parser()

    args = parser.parse_args()

    # PULL INITIAL INFO FROM ARGS

    prog_path = path.dirname(sys.argv[0])
    subject = args.subject_code
    output_folder = path.abspath(args.output_path)

    environment = get_environment(output_folder)

    # SETUP ENVIRONMENT AND PROJECT VARIABLES

    project_name, visitID, pipeline = infer_project_details_from_path(output_folder, subject)

    if args.project_config:
        project_name = args.project_config

    environ_binaries, project_settings, image_names, mask_labels = get_configs(environment, project_name)
    raw_data_dir = path.abspath(path.join(output_folder, 'unprocessed', 'NIFTI'))

    # BEGIN PROCESSING ...
    print '\nStarting Summary and Prep Sections...\n'

    # check_complete_inputs(t1, regressors_path, t1_brain)

    # COUNT HOW MANY THINGS HAVE 'REST' in their file/directory strings
    # we presume that's how many REST there are to process
    try:
        num_epi, raw_epi_list = count_epi_series(raw_data_dir)
    except OSError:
        print 'Missing raw EPI-data! Please check your -o setting to make sure this exists?\n%s' % raw_data_dir
        exit(1)

    start_time = datetime.now()
    # TELL USER WHAT YOU'RE DOING
    # TODO: change this to report to logfile in addition to std.out?

    print '''
    subjectID is: \n\t%s
    output_folder (processing_dir) is: \n\t%s
    number of resting-state raw series is: \n\t%s
    Time is: \n\t%s
    ''' % (subject, output_folder, num_epi, start_time)

    # SETUP SOME DIRECTORIES TO MAKE

    dirs_to_make = ['FCmaps', 'motion', 'timecourses', 'matlab_code', 'workbench']

    analysis_dirs_to_make = [path.join(path.abspath(output_folder), 'analyses_v2', dir) for dir in dirs_to_make]

    summary_dir = path.join(output_folder, 'summary')

    mni_results_path = path.join(output_folder, 'MNINonLinear', 'Results')

    preproc_dirs_to_make = [summary_dir]

    rest_dirs_to_make = [path.join(mni_results_path, 'REST%s' % num, 'FNL_preproc') for num in range(1, num_epi+1)]

    # CONCAT DIRECTORY LISTS
    all_dirs_to_make = analysis_dirs_to_make + preproc_dirs_to_make

    # REMOVE EXISTING OUTPUT DIRS
    print '\nRemoving existing outputs...\n'

    remove_outputs(analysis_dirs_to_make)
    remove_outputs(preproc_dirs_to_make)
    remove_outputs(rest_dirs_to_make)

    # NOW MAKE NEW OUTPUT DIRS
    try:
        print 'Making output directories...\n'

        make_output_dirs(all_dirs_to_make)

        make_output_dirs(rest_dirs_to_make)

    except Exception, e:

        print e, '\n->(unable to make directories)'

        sys.exit(1)

    t1_brain = path.join(output_folder, 'MNINonLinear', 'T1w_restore_brain.nii.gz')

    atlas = path.join(prog_path, 'templates', 'MNI152_T1_1mm_brain.nii.gz')

    # MAKE T1 ON MNI & VICE VERSA GIFS

    print '\nCreating T1_atlas .gifs...\n'

    create_t1_atlas_gifs(atlas, t1_brain, summary_dir, subject)

    # REGISTER T1 TO MNI-2mm

    fsl_standard_path = path.join('%(fsl_dir_path)s/data/standard/MNI152_T1_2mm_brain' % {
        'fsl_dir_path': environ_binaries['FSL_DIR']})

    # FLIRT REG TO T1 MNI (2mm) SPACE -> from fsl_standards on beast
    print '\nRegistering T1 -> MNI_2mm-space (via fsl template)...\n'
    t1_2mm = flirt_t1_to_mni_2mm(t1_brain, fsl_standard_path)

    # SETUP VARS

    t1 = path.join(output_folder, 'MNINonLinear', 'T1w_restore.nii.gz')

    t2 = path.join(output_folder, 'MNINonLinear', 'T2w_restore.nii.gz')
    rw = path.join(output_folder, 'MNINonLinear', 'fsaverage_LR32k', subject + '.R.white.32k_fs_LR.surf.gii')
    rp = path.join(output_folder, 'MNINonLinear', 'fsaverage_LR32k', subject + '.R.pial.32k_fs_LR.surf.gii')
    lw = path.join(output_folder, 'MNINonLinear', 'fsaverage_LR32k', subject + '.L.white.32k_fs_LR.surf.gii')
    lp = path.join(output_folder, 'MNINonLinear', 'fsaverage_LR32k', subject + '.L.pial.32k_fs_LR.surf.gii')

    paths_for_scene = [t1, rw, rp, lw, lp]  # do not include t2 here since we have a method for handling that (below)

    missing_paths = []

    # CHECK FOR T2

    subject_has_t2_data = has_t2(output_folder)
    if subject_has_t2_data:

        t2 = t2

    else:

        t2 = t1

    for file_path in paths_for_scene:
        if path.exists(path.join(file_path)):
            continue
        else:
            missing_paths.append(path.join(file_path))
            raise 'Unable to locate these files: \n%s\nWill not be able to make .scene!\n' % missing_paths

    # BUILD SCENE FROM TEMPLATE
    # SETUP AND RUN SLICES (FSL) COMMAND TO MAKE .GIFS

    print 'Creating scene from template...'
    build_scene_from_template(t2, t1, rp, lp, rw, lw, output_folder)

    # OUTPUTS A BUNCH OF PNG FILES
    # for i in image_names; scenenum = i; if not has_t2 and 'T2' in i: print 'skip' && continue ;
    # else create_image_from_template

    print '\nMaking .png images from .scene...\n'

    # Count from i to max scenes number, check for t2, create_image_from_template on scene i
    for num, scene in enumerate(image_names):

        num += 1  # start your count at 1 instead of 0

        if not has_t2(output_folder):

            print '\nNo T2 image found, skipping this scene...\n'

            continue

        else:

            create_image_from_template(output_folder, num, scene, environ_binaries)

    # REMOVE TEMP.SCENE FILE USED ABOVE

    submit_command('rm -rf %s/image_template_temp.scene' % output_folder)

    # SETUP OUTPUT MASK LABELS TO BE USED

    segBrainDir = "%s/MNINonLinear/ROIs" % output_folder  # TODO: refactor this varibale

    segBrain = "wmparc.2.nii.gz"  # TODO: refactor this varibale

    # CREATE WM AND VENT MASKS
    print '\nMaking ventricle and WM masks...\n'

    eroded_wm_mask = make_wm_mask(segBrainDir, segBrain, project_settings, subject)

    eroded_vent_mask = make_vent_mask(segBrainDir, segBrain, project_settings, subject)

    print '\ndone making masks...\n'

    # REMOVE EXISTING merged cifti if present -> will be making a new one
    merged_cifti = path.join(mni_results_path, subject + '_FNL_preproc_Atlas.dtseries.nii')

    if path.exists(merged_cifti):
        print '\nRemoving existing merged cifti...\n%s' % merged_cifti
        os.remove(merged_cifti)

    # NOW LOOP THROUGH ALL OUR RESTing EPI

    for epi_file in raw_epi_list:

        # pull the REST? from file

        resting_series_name, rest_num = get_epi_series_info_from_file(epi_file, subject)

        # GET TR and PATHS
        print '\nGetting TR from %s\n' % resting_series_name
        epi_file_tr = pull_tr_from_raw_resting_state(epi_file)

        print '\nTR for %s is: %s\n' % (path.basename(epi_file), epi_file_tr)

        epi_result_path = path.join(mni_results_path, resting_series_name, resting_series_name + '.nii.gz')

        epi_result_dir = path.dirname(epi_result_path)

        fnl_preproc_dir = path.join(epi_result_dir, 'FNL_preproc')

        # CHECK REGRESSOR PATH VIA IN-HOUSE PYTHON SCRIPT (in config)
        # Makes an additional call out to fslhd, then uses data-munging to "validate" a text file, then returns Nothing?
        # TODO: refactor this script into my own function and keep local to this module
        regressors_path = path.join(mni_results_path, resting_series_name, 'Movement_Regressors.txt')

        if not check_regressors_valid(epi_file, epi_result_dir, environ_binaries):
            print 'UGH, that <expletive deleted> script is telling me that you have a ' \
                  'Missing or otherwise "invalid" regressor file. \n%s\nPlease confirm, Exiting for now...' % regressors_path
            sys.exit(1)
        else:
            print 'Regressor file valid for %s!' % epi_file

        # print epi_result_path
        # MAKE T1<->FUNCTIONAL REG GIFS
        print '\nMaking functional registration .gifs...\n'
        make_functional_registration_gifs(t1_2mm, subject, summary_dir, epi_result_path, resting_series_name)

        # CALCULATE AND WRITE _VENT and _WM_meant.txt files
        print '\ncalculating vent and wm_meant.txt...\n'
        calculate_wm_vent_means(epi_result_dir, resting_series_name, fnl_preproc_dir, eroded_vent_mask, eroded_wm_mask)

        # BEGIN CIFTI CREATION SECTION
        dt_series_suffix = '_Atlas.dtseries.nii'

        # COPY _Atlas.dtseries.nii to /FNL_preproc sub-dir
        print '\nCopying dtseries files to prep for Octave section...\n'
        # copy_source = path.join(epi_result_dir, resting_series_name + dt_series_suffix)
        fnl_preproc_cifti = path.join(fnl_preproc_dir, resting_series_name + '_FNL_preproc' + dt_series_suffix)

        # shutil.copyfile(copy_source, fnl_preproc_cifti)

        # We also need the REST_Atlas.dtseries.nii file from path above FNL_preproc directory
        cifti_out = path.join(epi_result_dir, resting_series_name + dt_series_suffix)
        cifti_out_dest = path.join(fnl_preproc_dir, resting_series_name + dt_series_suffix)

        print 'CIFTI OUT IS: \n\t%s \nCOPYING TO: \n\t%s\n' % (cifti_out, cifti_out_dest)
        shutil.copyfile(cifti_out, cifti_out_dest)

        fnl_preproc_cifti_name = path.basename(fnl_preproc_cifti)

        # BEGIN FIRST OCTAVE SECTION -> WRITE CONFIG.json for FNL_preproc_Matlab.m
        print '\nRunning FNL_preproc Octave Section...\n'

        print '\nRemoving existing, and creating config.json\n'

        try:
            write_ml_config_and_run_octave(fnl_preproc_dir, environ_binaries, project_settings, resting_series_name,
                                           epi_file_tr, summary_dir, cifti_out, epi_result_dir, fnl_preproc_cifti_name)

        except Exception, e:
            print 'something went wrong during OCTAVE, UGH>..\n\t%s' % e
            sys.exit()

        print 'Done with first Octave section...'

        # NOW CONCATENATE ALL THE CIFTIS WE JUST MADE

        # FNL_preproc_CIFTI_name="${fMRIName}_FNL_preproc_Atlas.dtseries.nii"
        print '\nMerging ciftis...\n'
        merge_ciftis(environ_binaries, mni_results_path, fnl_preproc_dir, rest_num, subject, resting_series_name)

    # NOW DO PARCELLATIONS FOR SURF+SUBCORT AND SUBCORT-ONLY
    merged_cifti = path.join(mni_results_path, subject + '_FNL_preproc_Atlas.dtseries.nii')

    spec_file = path.join(output_folder, 'MNINonLinear', 'fsaverage_LR32k', subject + '.32k_fs_LR.wb.spec')

    print '\nAdding merged cifti (dense_ts) to .spec (for Quality Assurance)...\n'
    dense_ts_to_spec(environ_binaries, merged_cifti, spec_file)

    workbench_ciftis_folder = path.join(output_folder, 'analyses_v2', 'workbench')

    # TODO: clean this up
    output_folder_parts = output_folder.split('/')[1:6]  # could be wrong -> [1:7] ?

    # TODO: find a better HACK!
    if 'win' not in sys.platform:
        starting_slash = '/'
    else:
        starting_slash = '\\'

    # GONNA ENFORCE THIS PATTERN FOR THIS SYM-LINKED STRUCTURE (for now)
    # /<share_name>/<study_root_dir>/analyses_v2/<pipe>/<subjID>+<visit>  # slightly different than old FNL_preproc
    analysis_folder = path.join(starting_slash + output_folder_parts[0]
                                , output_folder_parts[1]  # a share_name usually starts with a slash and has 2 paths
                                , output_folder_parts[2]
                                , output_folder_parts[3]
                                , output_folder_parts[4] # if len(output_folder_parts) is 5, this works... else adjust!
                                , 'analyses_v2'
                                , pipeline
                                , subject + '+' + visitID)

    if path.exists(analysis_folder):
        print '\nRemoving existing analysis output folder from previous run...\n%s' % analysis_folder
        shutil.rmtree(analysis_folder)

    if not path.exists(analysis_folder):
        os.makedirs(analysis_folder)

    links_to_make = {

        path.abspath(merged_cifti)                              : workbench_ciftis_folder
        , path.abspath(spec_file)                               : workbench_ciftis_folder
        , path.abspath(summary_dir)                             : analysis_folder
        , path.join(output_folder, 'analyses_v2', 'FCmaps')     : analysis_folder
        , path.join(output_folder, 'analyses_v2', 'motion')     : analysis_folder
        , path.join(output_folder, 'analyses_v2', 'timecourses'): analysis_folder
        , path.join(output_folder, 'analyses_v2', 'matlab_code'): analysis_folder
        , path.join(output_folder, 'analyses_v2', 'workbench')  : analysis_folder

    }

    # MAKE SYM-LINKS

    print '\nCreating sym links...'
    make_sym_links(links_to_make)

    # START MAKING PTSERIES DATA

    print '\nMaking subcort + surface parcellations...\n'

    try:

        make_subcort_and_surface_parcellations(environ_binaries, mni_results_path, subject, merged_cifti, spec_file)

    except Exception, e:

        print '\nProblem making parcellations...\n%s\nExiting or the next section will fail anyway...\n' % e

        sys.exit()

    # MAKE SUBCORTICAL PARCELLATIONS

    print '\nMaking subcort-ONLY parcellations...\n'

    make_subcortical_only_parcellations(environ_binaries, mni_results_path, subject, merged_cifti, spec_file)

    # ADD NEW METHODS TO HELP REDUCE ML DEPENDENCY
    concat_FD_text_files(summary_dir)


    # SECOND OCTAVE SECTION -> ANALYSES_V2.m

    print '\nRunning second octave stage (analyses_v2.m takes several minutes)...\n'

    # TODO: do we not need the TR from EACH file for this? OR can we just pick 1 ? Choose randomly?
    # TODO: Do we assume that any given TR will be the same across all?

    try:
        # epi_file_tr will = the last TR value from our epi_files_list
        # TODO: should that^ be the case?
        write_analyses_config_and_run_octave(environ_binaries, project_settings, output_folder,
                                             epi_file_tr, summary_dir, mni_results_path)
    except Exception, e:

        print 'Problem with analyses_v2.m to investigate... try running octave in a terminal to diagnose?'
        sys.exit()

    # COPY MAT FILES TO /motion -> used in downstream analysis by "GUI_environments".m"

    print '\nCopying .mat files to /analyses_v2/motion where they belong...'

    copy_motion_frames_matfile(path.join(output_folder, 'analyses_v2', 'matlab_code'),
                               path.join(output_folder, 'analyses_v2', 'motion'))

    print '\nWriting frames_per_scan file...\n'

    write_frames_per_scan(mni_results_path, summary_dir)

    if check_final_outputs(output_folder, subject):

        print '\n-->All Done with %s!' % subject

    end_time = datetime.now()

    print '\nTime is now: \n\t%s' % end_time

    print '\nElapsed Time: \n\t%s' % (end_time - start_time)

if __name__ == '__main__':

    main()
