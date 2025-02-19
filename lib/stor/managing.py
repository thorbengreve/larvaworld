import os
import warnings
from itertools import product
import pandas as pd

import lib.aux.dictsNlists
from lib.stor.building import build_Jovanic, build_Schleyer, build_Berni
from lib.conf.stored.conf import *
from lib.stor.larva_dataset import LarvaDataset


def build_dataset(datagroup_id,id,target_dir, source_dir=None,source_files=None, **kwargs):
    warnings.filterwarnings('ignore')
    g = loadConf(datagroup_id, 'Group')
    build_conf = g['tracker']['filesystem']
    data_conf = g['tracker']['resolution']
    par_conf = g['parameterization']
    arena_pars = g['tracker']['arena']
    env_params=null_dict('env_conf', arena=arena_pars)


    try:
        shutil.rmtree(target_dir)
    except:
        pass

    d = LarvaDataset(dir=target_dir, id=id, par_conf=par_conf, env_params=env_params,
                     load_data=False, **data_conf)


    if datagroup_id in [ 'Jovanic lab']:
        step, end = build_Jovanic(d, build_conf, source_dir=source_dir, **kwargs)
    elif datagroup_id in [ 'Berni lab']:
        step, end = build_Berni(d, build_conf, source_files=source_files, **kwargs)
    elif datagroup_id in ['Schleyer lab']:
        step, end = build_Schleyer(d, build_conf, raw_folders=source_dir, **kwargs)
    else:
        raise ValueError(f'Configuration for {datagroup_id} is not supported for building new datasets')
    if step is not None:
        step.sort_index(level=['Step', 'AgentID'], inplace=True)
        end.sort_index(inplace=True)
        d.set_data(step=step, end=end)
        d.save(food=False)
        d.agent_ids = d.step_data.index.unique('AgentID').values
        d.num_ticks = d.step_data.index.unique('Step').size
        # d.starting_tick = d.step_data.index.unique('Step')[0]
        print(f'--- Dataset {d.id} created with {len(d.agent_ids)} larvae! ---')
    else:
        print(f'--- Failed to create dataset {d.id}! ---')
        d.delete()
    return d


def build_datasets_old(datagroup_id, raw_folders, folders=None, suffixes=None,
                       ids=None, names=['raw'], group_ids=None, **kwargs):
    warnings.filterwarnings('ignore')
    g = loadConf(datagroup_id, 'Group')
    build_conf = g['tracker']['filesystem']
    group_dir=f'{paths.path("DATA")}/{g["path"]}'
    raw_dir=f'{group_dir}/raw'

    ds = get_datasets(datagroup_id=datagroup_id, last_common='processed', names=names,
                      folders=folders, suffixes=suffixes, mode='initialize', ids=ids)
    if group_ids in [None, '']:
        group_ids = [d.id for d in ds]
    elif type(group_ids) == str:
        group_ids = [group_ids] * len(ds)
    elif len(group_ids) != len(ds):
        raise ValueError(
            f'Number of datasets ({len(ds)}) does not match number of provided group-IDs ({len(group_ids)})')
    for d, raw, group_id in zip(ds, raw_folders, group_ids):
        if datagroup_id in [ 'Jovanic lab']:
            step, end = build_Jovanic(d, build_conf, source_dir=f'{raw_dir}/{raw}', **kwargs)
        elif datagroup_id in [ 'Berni lab']:
            step, end = build_Berni(d, build_conf, source_dir=f'{raw_dir}/{raw}', **kwargs)
        elif datagroup_id in ['Schleyer lab']:

            if type(raw) == str:
                temp = [f'{raw_dir}/{raw}']
            elif type(raw) == list:
                temp = [f'{raw_dir}/{r}' for r in raw]
            step, end = build_Schleyer(d, build_conf, raw_folders=temp, **kwargs)
        else:
            raise ValueError(f'Configuration for {datagroup_id} is not supported for building new datasets')
        if step is not None:
            step.sort_index(level=['Step', 'AgentID'], inplace=True)
            end.sort_index(inplace=True)
            d.set_data(step=step, end=end)
            d.config['group_id'] = group_id
            d.save(food=False)
            d.agent_ids = d.step_data.index.unique('AgentID').values
            d.num_ticks = d.step_data.index.unique('Step').size
            d.starting_tick = d.step_data.index.unique('Step')[0]
            print(f'--- Dataset {d.id} created with {len(d.agent_ids)} larvae! ---')
        else:
            print(f'--- Failed to create dataset {d.id}! ---')
            d.delete()
    return ds


def get_datasets(datagroup_id, names, last_common='processed', folders=None, suffixes=None,
                 mode='load', load_data=True, ids=None, **kwargs):
    g = loadConf(datagroup_id, 'Group')
    data_conf = g['tracker']['resolution']
    par_conf = g['parameterization']
    arena_pars = g['tracker']['arena']
    group_dir = f'{paths.path("DATA")}/{g["path"]}'

    last_common = f'{group_dir}/{last_common}'
    if folders is None:
        new_ids = ['']
        folders = [last_common]
    else:
        new_ids = folders
        folders = [f'{last_common}/{f}' for f in folders]
    if suffixes is not None:
        names = [f'{n}_{s}' for (n, s) in list(product(names, suffixes))]
    new_ids = [f'{id}{n}' for (id, n) in list(product(new_ids, names))]
    if ids is None:
        ids = new_ids
    dirs = [f'{f}/{n}' for (f, n) in list(product(folders, names))]
    ds = []
    for dir, id in zip(dirs, ids):
        if mode == 'load':
            if not os.path.exists(dir):
                print(f'No dataset found at {dir}')
                continue
            d = LarvaDataset(dir=dir, load_data=load_data)
        elif mode == 'initialize':
            try:
                shutil.rmtree(dir)
            except:
                pass

            d = LarvaDataset(dir=dir, id=id, par_conf=par_conf, arena_pars=arena_pars,
                             load_data=False, **data_conf)
        ds.append(d)
    return ds


def enrich_datasets(datagroup_id, datasets=None, names=None, enrich_conf=None, **kwargs):
    warnings.filterwarnings('ignore')

    if datasets is None and names is not None:
        datasets = get_datasets(datagroup_id, last_common='processed', names=names, mode='load', **kwargs)
    if enrich_conf is None:
        g = loadConf(datagroup_id, 'Group')
        enrich_conf = g['enrichment']
    print()
    print(f'------ Enriching {len(datasets)} datasets ------')
    print()
    ds = [d.enrich(**enrich_conf, **kwargs) for d in datasets]
    # print()
    print(f'------ {len(ds)} datasets enriched ------')
    print()
    return ds


def analyse_datasets(datagroup_id, save_to=None, **kwargs):
    from lib.sim.single.analysis import comparative_analysis
    ds = get_datasets(datagroup_id=datagroup_id, **kwargs)
    if save_to is None and len(ds) > 1:
        g = loadConf(datagroup_id, 'Group')
        save_to = f'{paths.path("DATA")}/{g["path"]}/plots'
    fig_dict = comparative_analysis(datasets=ds, labels=[d.id for d in ds], save_to=save_to)
    return fig_dict


def visualize_datasets(datagroup_id, save_to=None, save_as=None, vis_kwargs={}, replay_kwargs={}, **kwargs):
    warnings.filterwarnings('ignore')
    ds = get_datasets(datagroup_id=datagroup_id, **kwargs)
    if save_to is None and len(ds) > 1:
        g = loadConf(datagroup_id, 'Group')
        save_to = f'{paths.path("DATA")}/{g["path"]}/visuals'
    if save_as is None:
        save_as = [d.id for d in ds]
    for d, n in zip(ds, save_as):
        vis_kwargs['media_name'] = n
        d.visualize(save_to=save_to, vis_kwargs=vis_kwargs, **replay_kwargs)



def detect_dataset(datagroup_id=None, folder_path=None, raw=True, **kwargs):
    dic = {}
    if folder_path in ['', None]:
        return dic
    if raw:
        conf = loadConf(datagroup_id, 'Group')['tracker']['filesystem']
        if 'detect' in conf.keys():
            d = conf['detect']
            dF, df = d['folder'], d['file']
            dFp, dFs = dF['pref'], dF['suf']
            dfp, dfs, df_ = df['pref'], df['suf'], df['sep']

            fn = folder_path.split('/')[-1]
            if dFp is not None:
                if fn.startswith(dFp):
                    dic[fn] = folder_path
                else:
                    ids, dirs = detect_dataset_in_subdirs(datagroup_id, folder_path, fn, **kwargs)
                    for id, dr in zip(ids, dirs):
                        dic[id] = dr
            elif dFs is not None:
                if fn.startswith(dFs):
                    dic[fn] = folder_path
                else:
                    ids, dirs = detect_dataset_in_subdirs(datagroup_id, folder_path, fn, **kwargs)
                    for id, dr in zip(ids, dirs):
                        dic[id] = dr
            elif dfp is not None:
                fs = os.listdir(folder_path)
                ids, dirs = [f.split(df_)[1:][0] for f in fs if f.startswith(dfp)], [folder_path]
                for id, dr in zip(ids, dirs):
                    dic[id] = dr
            elif dfs is not None:
                fs = os.listdir(folder_path)
                ids = [f.split(df_)[:-1][0] for f in fs if f.endswith(dfs)]
                for id in ids:
                    dic[id] = folder_path
            elif df_ is not None:
                fs = os.listdir(folder_path)
                ids = lib.aux.dictsNlists.unique_list([f.split(df_)[0] for f in fs if df_ in f])
                for id in ids:
                    dic[id] = folder_path
        return dic
    else:
        if os.path.exists(f'{folder_path}/data'):
            dd = LarvaDataset(dir=folder_path)
            dic[dd.id] = dd
        else:
            for ddr in [x[0] for x in os.walk(folder_path)]:
                if os.path.exists(f'{ddr}/data'):
                    dd = LarvaDataset(dir=ddr)
                    dic[dd.id] = dd
        return dic


def detect_dataset_in_subdirs(datagroup_id, folder_path, last_dir, full_ID=False):
    fn = last_dir
    ids, dirs = [], []
    if os.path.isdir(folder_path):
        fs = os.listdir(folder_path)
        for f in fs:
            dic = detect_dataset(datagroup_id, f'{folder_path}/{f}', full_ID=full_ID, raw=True)
            # id, dir = detect_dataset(datagroup_id, f'{folder_path}/{f}', full_ID=full_ID)
            for id, dr in dic.items():
                if full_ID:
                    ids += [f'{fn}/{id0}' for id0 in id]
                else:
                    ids.append(id)
                dirs.append(dr)
    return ids, dirs


if __name__ == '__main__':
    # dds=[[f'/home/panos/nawrot_larvaworld/larvaworld/data/JovanicGroup/processed/3_conditions/AttP{g}@UAS_TNT/{c}' for g in ['2', '240']] for c in ['Fed', 'Deprived', 'Starved']]
    # dds=fun.flatten_list(dds)
    # dr = '/home/panos/nawrot_larvaworld/larvaworld/data/SchleyerGroup/FRUvsQUI/Naive->PUR/EM/control'
    dr1='/home/panos/nawrot_larvaworld/larvaworld/data/SimGroup/single_runs/dispersion_x2/dispersion_x2_3.Levy'
    dr2='/home/panos/nawrot_larvaworld/larvaworld/data/SimGroup/single_runs/dispersion_x2/dispersion_x2_3.Oscillatory'

