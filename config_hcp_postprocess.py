#!/usr/bin/env python
"""
__author__ = 'Shannon Buckley', 5/8/16

"""

# paths to shared dependencies #
configured_environments = {
    'airc': {

        'path_to_label_files':
            '/group_shares/PSYCH/ROI_sets/Surface_schemes/Human',
        'path_to_movement_regressor_check':
            '/group_shares/PSYCH/code/development/utilities/movmnt_regressor_check/movmnt_regressor_check.py',
        'FSL_DIR':
            '/usr/share/fsl/5.0',
        'octave':
            '/group_shares/PSYCH/code/external/utilities/octave3.8/bin/octave',
        'wb_command':
            '/group_shares/PSYCH/code/external/utilities/workbench/bin_linux64/wb_command',
        'framewise_disp_path':
            '/group_shares/PSYCH/code/development/utilities/framewise_displacement',
        'HCP_Mat_Path':
            '/group_shares/PSYCH/code/development/utilities/HCP_Matlab',
        'matlab_template':
            'FNL_preproc_Matlab.m'
    },

    # TODO: change these into exacloud-paths!

    'exacloud': {

        'path_to_label_files':
            '/group_shares/PSYCH/ROI_sets/Surface_schemes/Human',
        'path_to_movement_regressor_check':
            '/group_shares/PSYCH/code/development/utilities/movmnt_regressor_check/movmnt_regressor_check.py',
        'FSL_DIR':
            '/usr/share/fsl/5.0',
        'octave':
            '/group_shares/PSYCH/code/external/utilities/octave3.8/bin/octave',
        'wb_command':
            '/group_shares/PSYCH/code/external/utilities/workbench/bin_linux64/wb_command',
        'framewise_disp_path':
            '/group_shares/PSYCH/code/development/utilities/framewise_displacement',
        'HCP_Mat_Path':
            '/group_shares/PSYCH/code/development/utilities/HCP_Matlab'
    },
    'rushmore': {

            'path_to_label_files':
                '/mnt/max/shared/ROI_sets/Surface_schemes/Human',
            'path_to_movement_regressor_check':
                '/mnt/max/shared/utilities/movmnt_regressor_check/movmnt_regressor_check.py',
            'FSL_DIR':
                '/usr/share/fsl/5.0',
            'octave':
                '/usr/bin/octave',  # apt installed 4.0 ... has issues ugh -> need 3.8.2?->installed signal, statistics
                # '/mnt/airc/PSYCH/code/external/utilities/octave3.8/bin/octave',
            'wb_command':
                '/usr/bin/wb_command',
            'framewise_disp_path':
                '/mnt/max/shared/utilities/framewise_displacement',  # from PSYC/dev
            'HCP_Mat_Path':
                '/mnt/max/shared/utilities/HCP_Matlab'  # from PSYC/dev
        }
    }
# print configured_environments
mask_threshold_values_dict = {

    # TODO: do these change ever? Specific to human atlases?

    'vent_lt_L' : 4,     # ventricles lower threshold Right
    'vent_ut_L' : 4,     # ventricles upper threshold Right
    'vent_lt_R' : 43,    # ventricles lower threshold Left
    'vent_ut_R' : 43,    # ventricles upper threshold Left
    'wm_lt_R'   : 2950,  # white matter lower threshold Right
    'wm_ut_R'   : 3050,  # white matter upper threshold Right
    'wm_lt_L'   : 3950,  # white matter lower threshold Left
    'wm_ut_L'   : 4050   # white matter upper threshold Left
}
# developed for humans, un-tested for primates
image_names = [
    'T1-Axial-InferiorTemporal-Cerebellum',
    'T2-Axial-InferiorTemporal-Cerebellum',
    'T1-Axial-BasalGangila-Putamen',
    'T2-Axial-BasalGangila-Putamen',
    'T1-Axial-SuperiorFrontal',
    'T2-Axial-SuperiorFrontal',
    'T1-Coronal-PosteriorParietal-Lingual',
    'T2-Coronal-PosteriorParietal-Lingual',
    'T1-Coronal-Caudate-Amygdala',
    'T2-Coronal-Caudate-Amygdala',
    'T1-Coronal-OrbitoFrontal',
    'T2-Coronal-OrbitoFrontal',
    'T1-Sagittal-Insula-FrontoTemporal',
    'T2-Sagittal-Insula-FrontoTemporal',
    'T1-Sagittal-CorpusCallosum',
    'T2-Sagittal-CorpusCallosum',
    'T1-Sagittal-Insula-Temporal-HippocampalSulcus',
    'T2-Sagittal-Insula-Temporal-HippocampalSulcus'
]

# HUMAN PROJECT CONFIGURATIONS (formerly found within setup_env.sh in previous verions)
configured_projects = {

    'ASD': {

        'expected_contiguous_frame_count'   : 5,
        'skip_seconds'                      : 5,
        'brain_radius_in_mm'                : 50,
        'motion_filename'                   : "motion_numbers.txt",

        # frame displacement threshold to calculate beta coefficients for regression
        'fd_th'                             : 0.2,
        'bp_order'  : 2,  # band pass filter order
        'lp_Hz'     : 0.009,  # low pass frequency, in Hz
        'hp_Hz'     : 0.080,  # high pass frequency, in Hz

        'vent_lt_L' : 4,  # white matter lower threshold Left (per Freesurfer)
        'vent_ut_L' : 4,  # white matter upper threshold Left
        'vent_lt_R' : 43,  # white matter lower threshold Right
        'vent_ut_R' : 43,  # white matter upper threshold Right
        'wm_lt_R'   : 2950,  # ventricles lower threshold Right
        'wm_ut_R'   : 3050,  # ventricles upper threshold Right
        'wm_lt_L'   : 3950,  # ventricles lower threshold Left
        'wm_ut_L'   : 4050,  # ventricles upper threshold Left
    },

    'ADHD': {

        'expected_contiguous_frame_count'   : 5,
        'skip_seconds'                      : 5,
        'brain_radius_in_mm'                : 50,
        'motion_filename'                   : "motion_numbers.txt",
        'fd_th'                             : 0.2,

        'bp_order'  : 2,  # band pass filter order
        'lp_Hz'     : 0.009,  # low pass frequency, Hz
        'hp_Hz'     : 0.080,  # high pass frequency, Hz

        'vent_lt_L' : 4,  # white matter lower threshold Left
        'vent_ut_L' : 4,  # white matter upper threshold Left
        'vent_lt_R' : 43,  # white matter lower threshold Right
        'vent_ut_R' : 43,  # white matter upper threshold Right
        'wm_lt_R'   : 2950,  # ventricles lower threshold Right
        'wm_ut_R'   : 3050,  # ventricles upper threshold Right
        'wm_lt_L'   : 3950,  # ventricles lower threshold Left
        'wm_ut_L'   : 4050,  # ventricles upper threshold Left
    },

    # PRIMATE STUDY CONFIGURATIONS
    'NHP_Fezcko_config': {

        'expected_contiguous_frame_count'   : 5,
        'skip_seconds'                      : 5,

        # params from Feczko email: 6-28-16
        'brain_radius_in_mm'                : 30,

        'motion_filename'                   : "motion_numbers.txt",
        # Frame Displacement Threshold for calculating beta coefficients for regression
        'fd_th'                             : 0.2,

        'bp_order'  : 2,  # band pass filter order
        'lp_Hz'     : 0.009,  # low pass frequency, Hz
        'hp_Hz'     : 0.080,  # high pass frequency, Hz

        'vent_lt_L' : 4,  # white matter lower threshold Left  # TODO: same atlas labels as humans?
        'vent_ut_L' : 4,  # white matter upper threshold Left
        'vent_lt_R' : 43,  # white matter lower threshold Right
        'vent_ut_R' : 43,  # white matter upper threshold Right
        'wm_lt_R'   : 2950,  # ventricles lower threshold Right
        'wm_ut_R'   : 3050,  # ventricles upper threshold Right
        'wm_lt_L'   : 3950,  # ventricles lower threshold Left
        'wm_ut_L'   : 4050,  # ventricles upper threshold Left
    },

    'NHP_HFD': {

        'expected_contiguous_frame_count': 5,
        'skip_seconds': 5,
        'brain_radius_in_mm': 30,
        'motion_filename': "motion_numbers.txt",
        'fd_th': 0.2,  # frame displacement th to calculate beta coefficients for regression

        'bp_order': 2,  # band pass filter order
        'lp_Hz': 0.009,  # low pass frequency, Hz
        'hp_Hz': 0.080,  # high pass frequency, Hz

        'vent_lt_L': 4,  # white matter lower threshold Left
        'vent_ut_L': 4,  # white matter upper threshold Left
        'vent_lt_R': 43,  # white matter lower threshold Right
        'vent_ut_R': 43,  # white matter upper threshold Right
        'wm_lt_R': 2950,  # ventricles lower threshold Right
        'wm_ut_R': 3050,  # ventricles upper threshold Right
        'wm_lt_L': 3950,  # ventricles lower threshold Left
        'wm_ut_L': 4050,  # ventricles upper threshold Left
    },

    'NHP_Sam': {

        'expected_contiguous_frame_count'   : 5,
        'skip_seconds'                      : 5,
        'brain_radius_in_mm'                : 30,
        'fd_th'                             : 0.2,
        'motion_filename'                   : "motion_numbers.txt",

        'bp_order'  : 2,  # band pass filter order
        'lp_Hz'     : 0.009,  # low pass frequency, Hz
        'hp_Hz'     : 0.080,  # high pass frequency, Hz

        'vent_lt_L' : 4,  # white matter lower threshold Left
        'vent_ut_L' : 4,  # white matter upper threshold Left
        'vent_lt_R' : 43,  # white matter lower threshold Right
        'vent_ut_R' : 43,  # white matter upper threshold Right
        'wm_lt_R'   : 2950,  # ventricles lower threshold Right
        'wm_ut_R'   : 3050,  # ventricles upper threshold Right
        'wm_lt_L'   : 3950,  # ventricles lower threshold Left
        'wm_ut_L'   : 4050,  # ventricles upper threshold Left
    }
}
