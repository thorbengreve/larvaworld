import os

def get_parent_dir():
    p=os.path.abspath(__file__)
    p = os.path.dirname(p)
    p = os.path.dirname(p)
    p = os.path.dirname(p)
    p = os.path.dirname(p)
    # p = os.path.join(p, '../..')
    return p


def path(n) :
    F0 = get_parent_dir()
    RF = f'{F0}/run'
    GF = f'{F0}/lib/gui'
    CF = f'{F0}/lib/conf/stored/conf_dicts'
    MF = f'{F0}/lib/media'

    exp_paths = {
        'RvsS': f'{MF}/exp_figures/roversVSsitters',
        'odor_pref': f'{MF}/exp_figures/odor_preference',
    }

    media_paths = {
        'videos': f'{MF}/video_slides',
        'intro': f'{MF}/intro_slides',
        'tutorials': f'{MF}/tutorial_slides',
        'model': f'{MF}/model_figures',
        'exp_figs': f'{MF}/exp_figures',
    }

    par_paths = {
        'ParDb': f'{CF}/ParDatabase.csv',
        'ParShelve': f'{CF}/ParShelve',
        'ParDict': f'{CF}/ParDict.csv',
        'ParDf': f'{CF}/ParDf.csv',
        'ParPdf': f'{CF}/ParPdf.pdf',
        'Unit': f'{CF}/UnitDict.csv',
        'ParRef': f'{CF}/RefPars.txt',
    }

    conf_paths = {
        'Group': f'{CF}/DataGroups.txt',
        'Env': f'{CF}/EnvConfs.txt',
        'Par': f'{CF}/ParConfs.txt',
        'Exp': f'{CF}/ExpConfs.txt',
        'ExpGroup': f'{CF}/ExpGroupConfs.txt',
        'Essay': f'{CF}/EssayConfs.txt',
        'Model': f'{CF}/ModelConfs.txt',
        'Batch': f'{CF}/BatchConfs.txt',
        'Settings': f'{CF}/SetConfs.txt',
        'Ref': f"{CF}/ReferenceDatasets.txt",
        'Life': f"{CF}/LifeConfs.txt",
        'SimIdx': f'{CF}/SimIdx.txt',
    }

    data_paths = {
        'DEB': f'{F0}/data/SimGroup/deb_runs',
        'DEB_MODS': {n: f'{F0}/lib/model/DEB/models/deb_{n}.csv' for n in ['rover', 'sitter', 'default']},
        'REF': f'{F0}/data/SampleGroup',
        'EXEC': f'{RF}/exec_run.py',
        'EXECONF': f'{RF}/exec_conf.txt',
        'BATCH': f'{F0}/data/SimGroup/batch_runs',
        'ESSAY': f'{F0}/data/SimGroup/essays',
        'RUN': f'{F0}/data/SimGroup/single_runs',
        'SIM': f'{F0}/data/SimGroup',
        'DATA': f'{F0}/data',
        'GUITEST': f'{GF}/gui_speed_test.csv',
    }

    paths={**par_paths, **conf_paths, **exp_paths, **media_paths, **data_paths}
    return paths[n]
