import copy
import json
import shutil

from lib.conf.base.dtypes import null_dict, base_enrich
from lib.conf.base import paths


def loadConf(id, conf_type):
    try:
        conf_dict = loadConfDict(conf_type)
        conf = conf_dict[id]
        return conf
    except:
        raise ValueError(f'{conf_type} Configuration {id} does not exist')


def expandConf(id, conf_type):
    conf = loadConf(id, conf_type)
    # print(conf.keys(), id)
    try:
        if conf_type == 'Batch':
            conf['exp'] = expandConf(conf['exp'], 'Exp')
        elif conf_type == 'Exp':
            conf['experiment'] = id
            conf['env_params'] = expandConf(conf['env_params'], 'Env')
            conf['trials'] = loadConf(conf['trials'], 'Trial')
            for k, v in conf['larva_groups'].items():
                if type(v['model']) == str:
                    v['model'] = loadConf(v['model'], 'Model')
    except:
        pass
    return conf


def loadConfDict(conf_type):
    try:
        with open(paths.path(conf_type)) as f:
            d = json.load(f)
        return d
    except:
        return {}


def saveConf(conf, conf_type, id=None, mode='overwrite'):
    try:
        d = loadConfDict(conf_type)
    except:
        d = {}
    if id is None:
        id = conf['id']

    if id in list(d.keys()):
        for k, v in conf.items():
            if type(k) == dict and k in list(d[id].keys()) and mode == 'update':
                d[id][k].update(conf[k])
            else:
                d[id][k] = v
    else:
        d[id] = conf
    saveConfDict(d, conf_type)
    print(f'{conf_type} Configuration saved under the id : {id}')


def saveConfDict(ConfDict, conf_type):
    with open(paths.path(conf_type), "w") as f:
        json.dump(ConfDict, f)


def deleteConf(id, conf_type):
    if conf_type == 'Data':
        DataGroup = loadConf(id, conf_type)
        path = DataGroup['path']
        try:
            shutil.rmtree(path)
        except:
            pass
    d = loadConfDict(conf_type)
    try:
        d.pop(id, None)
        saveConfDict(d, conf_type)
        print(f'Deleted {conf_type} configuration under the id : {id}')
    except:
        pass


def next_idx(exp, type='single'):
    F0 = paths.path('SimIdx')
    try:
        with open(F0) as f:
            d = json.load(f)
    except:
        ksExp = list(loadConfDict('Exp').keys())
        ksBatch = list(loadConfDict('Batch').keys())
        ksEssay = list(loadConfDict('Essay').keys())
        dExp = dict(zip(ksExp, [0] * len(ksExp)))
        dBatch = dict(zip(ksBatch, [0] * len(ksBatch)))
        dEssay = dict(zip(ksEssay, [0] * len(ksEssay)))
        # batch_idx_dict.update(loadConfDict('Batch'))
        d = {'single': dExp,
             'batch': dBatch,
             'essay': dEssay}
    if not exp in d[type].keys():
        d[type][exp] = 0
    d[type][exp] += 1
    with open(F0, "w") as fp:
        json.dump(d, fp)
    return d[type][exp]


def store_reference_data_confs():
    from lib.stor.larva_dataset import LarvaDataset
    from lib.aux.dictsNlists import flatten_list

    DATA = paths.path('DATA')

    dds = [
        [f'{DATA}/JovanicGroup/processed/3_conditions/AttP{g}@UAS_TNT/{c}' for g
         in ['2', '240']] for c in ['Fed', 'Deprived', 'Starved']]
    dds = flatten_list(dds)
    dds.append(f'{DATA}/SchleyerGroup/processed/FRUvsQUI/Naive->PUR/EM/exploration')
    dds.append(f'{DATA}/SchleyerGroup/processed/no_odor/200_controls')
    dds.append(f'{DATA}/SchleyerGroup/processed/no_odor/10_controls')
    for dr in dds:
        d = LarvaDataset(dr, load_data=False)
        d.save_config(add_reference=True)


def store_confs(keys=None):
    if keys is None:
        keys = ['Ref', 'Data', 'Model', 'Env', 'Exp', 'Life']
    if 'Life' in keys:
        from lib.conf.stored.trial_conf import trial_dict, life_dict
        for k, v in trial_dict.items():
            saveConf(v, 'Trial', k)
        for k, v in life_dict.items():
            saveConf(v, 'Life', k)
    if 'Data' in keys:
        from lib.conf.stored.data_conf import importformats, import_par_confs
        for k, v in import_par_confs.items():
            saveConf(v, 'Par', k)
        for g in importformats:
            saveConf(g, 'Group')
    if 'Ref' in keys:
        store_reference_data_confs()
    if 'Model' in keys:
        from lib.conf.stored.larva_conf import mod_dict
        for k, v in mod_dict.items():
            saveConf(v, 'Model', k)
    if 'Env' in keys:
        from lib.conf.stored.env_conf import env_dict
        for k, v in env_dict.items():
            saveConf(v, 'Env', k)
    if 'Exp' in keys:
        import lib.conf.stored.exp_conf as exp
        import lib.conf.stored.essay_conf as essay
        import lib.conf.stored.batch_conf as bat
        from lib.aux.dictsNlists import merge_dicts

        d = exp.grouped_exp_dict
        exp_dict = merge_dicts(list(d.values()))
        exp_group_dict = {k: {'simulations': list(v.keys())} for k, v in d.items()}
        for k, v in exp_dict.items():
            saveConf(v, 'Exp', k)
        for k, v in exp_group_dict.items():
            saveConf(v, 'ExpGroup', k)

        for k, v in essay.essay_dict.items():
            saveConf(v, 'Essay', k)

        for k, v in bat.batch_dict.items():
            saveConf(v, 'Batch', k)


def imitation_exp(sample, model='explorer', idx=0, N=None,duration=None, **kwargs):
    sample_conf = loadConf(sample, 'Ref')
    id = sample_conf['id']
    base_larva = expandConf(model, 'Model')
    if duration is None :
        duration = sample_conf['duration'] / 60
    sim_params = null_dict('sim_params', timestep=1 / sample_conf['fr'], duration=duration,
                           path='single_runs/imitation', sim_ID=f'{id}_imitation_{idx}')
    env_params = null_dict('env_conf', arena=sample_conf['env_params']['arena'])
    larva_groups = {
        'ImitationGroup': null_dict('LarvaGroup', sample=sample, model=base_larva, default_color='blue', imitation=True,
                                    distribution={'N': N})}

    exp_conf = null_dict('exp_conf', sim_params=sim_params, env_params=env_params, larva_groups=larva_groups,
                         trials={}, enrichment=base_enrich())
    exp_conf['experiment'] = 'imitation'
    exp_conf.update(**kwargs)
    return exp_conf


# def get_exp_conf(exp_type, sim_params, life_params=None, N=None, larva_model=None):
#     conf = copy.deepcopy(expandConf(exp_type, 'Exp'))
#     for k in list(conf['env_params']['larva_groups'].keys()):
#         if N is not None:
#             conf['env_params']['larva_groups'][k]['N'] = N
#         if larva_model is not None:
#             conf['env_params']['larva_groups'][k]['model'] = loadConf(larva_model, 'Model')
#     if life_params is not None:
#         conf['life_params'] = life_params
#
#     if sim_params['sim_ID'] is None:
#         idx = next_idx(exp_type)
#         sim_params['sim_ID'] = f'{exp_type}_{idx}'
#     if sim_params['path'] is None:
#         sim_params['path'] = f'single_runs/{exp_type}'
#     if sim_params['duration'] is None:
#         sim_params['duration'] = conf['sim_params']['duration']
#     conf['sim_params'] = sim_params
#     conf['experiment'] = exp_type
#
#     return conf

if __name__ == '__main__':
    store_confs()
