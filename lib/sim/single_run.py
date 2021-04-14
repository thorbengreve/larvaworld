""" Run a simulation and save the parameters and data to files."""
import copy
import datetime
import time
import pickle

import lib.aux.functions as fun
import lib.conf.data_conf as dat
import lib.stor.paths as paths
from lib.anal.plotting import *
from lib.aux.collecting import output, midline_xy_pars
from lib.conf.dtype_dicts import get_vis_kwargs_dict
from lib.envs._larvaworld import LarvaWorldSim
from lib.model.deb import deb_dict, deb_default
from lib.conf.conf import loadConf
from lib.stor.larva_dataset import LarvaDataset


def sim_enrichment(d, experiment):
    d.build_dirs()
    if experiment in ['growth', 'rovers_sitters']:
        d.deb_analysis(is_last=False)
    elif experiment == 'focus':
        d.angular_analysis(is_last=False)
        d.detect_turns(is_last=False)
    elif experiment == 'dispersion':
        d.enrich(length_and_centroid=False, is_last=False)
    return d


def sim_analysis(d, exp_type):
    if d is None:
        return
    s, e = d.step_data, d.endpoint_data
    fig_dict = {}
    results = {}
    if exp_type in ['patchy_food', 'uniform_food', 'food_grid']:
        # am = e['amount_eaten'].values
        # print(am)
        # cr,pr,fr=e['stride_dur_ratio'].values, e['pause_dur_ratio'].values, e['feed_dur_ratio'].values
        # print(cr+pr+fr)
        # cN, pN, fN = e['num_strides'].values, e['num_pauses'].values, e['num_feeds'].values
        # print(cN, pN, fN)
        # cum_sd, f_success=e['cum_scaled_dst'].values, e['feed_success_rate'].values
        # print(cum_sd, f_success)
        fig_dict['scatter_x4'] =plot_endpoint_scatter(datasets=[d], labels=[d.id], par_shorts=['cum_sd', 'f_am', 'str_tr', 'fee_tr'])
        fig_dict['scatter_x2'] =plot_endpoint_scatter(datasets=[d], labels=[d.id], par_shorts=['cum_sd', 'f_am'])

    elif exp_type in ['growth', 'rovers_sitters']:
        starvation_hours = d.config['starvation_hours']
        f = d.config['deb_base_f']
        deb_model = deb_default(starvation_hours=starvation_hours, base_f=f)
        if exp_type == 'rovers_sitters':
            roversVSsitters = True
            datasets = d.split_dataset(larva_id_prefixes=['Sitter', 'Rover'])
            labels = ['Sitters', 'Rovers']
        else:
            roversVSsitters = False
            datasets = [d]
            labels = [d.id]


        cc = {'datasets': datasets,
              'labels': labels,
              'save_to': d.plot_dir}

        fig_dict['gut'] =plot_gut(**cc)
        fig_dict['food_amount'] =plot_food_amount(**cc)
        fig_dict['food_amount_filt'] =plot_food_amount(filt_amount=True, **cc)
        # raise
        fig_dict['pathlength'] = plot_pathlength(scaled=False, **cc)
        fig_dict['endpoint'] = plot_endpoint_params(mode='deb', **cc)
        try:
            fig_dict['food_amount_barplot'] =  barplot(par_shorts=['f_am'], **cc)
        except:
            pass

        deb_dicts = [deb_dict(d, id, starvation_hours=starvation_hours) for id in d.agent_ids] + [deb_model]
        c = {'save_to': d.plot_dir,
             'roversVSsitters': roversVSsitters}
        c1={'deb_dicts' : deb_dicts[:-1],
            'sim_only' : True}

        for m in ['f', 'hunger', 'minimal', 'full', 'complete'] :
            for t in ['hours', 'seconds'] :
                for i,s in enumerate([True, False]) :
                    l=f'{m}_{t}_{i}'
                    save_as=f'{l}.pdf'
                    fig_dict[l] = plot_debs(save_as=save_as, mode=m, time_unit=t,start_at_sim_start=s, **c, **c1)

        for m in ['minimal', 'full', 'complete']:
            l = f'{m}_comp'
            save_as = f'{l}.pdf'
            fig_dict[l] = plot_debs(deb_dicts=deb_dicts, save_as=save_as, mode=m, **c)





    elif exp_type == 'dispersion':
        target_dataset = load_reference_dataset()
        datasets = [d, target_dataset]
        labels = ['simulated', 'empirical']
        dic0=comparative_analysis(datasets=datasets, labels=labels, simVSexp=True, save_to=None)
        fig_dict.update(dic0)
        dic1=plot_marked_strides(dataset=d, agent_ids=d.agent_ids[:3], title=' ', slices=[[10, 50], [60, 100]])
        fig_dict.update(dic1)
        dic2=plot_marked_turns(dataset=d, agent_ids=d.agent_ids[:3], min_turn_angle=20)
        fig_dict.update(dic2)


    elif exp_type in ['chemotaxis_approach', 'chemotaxis_local', 'chemotaxis_diffusion']:
        for p in ['c_odor1', 'dc_odor1', 'A_olf', 'A_tur', 'Act_tur'] :
            fig_dict[p] =plot_timeplot(p, datasets=[d])
        dic = plot_distance_to_source(dataset=d, exp_type=exp_type)
        fig_dict.update(dic)
        d.visualize(agent_ids=[d.agent_ids[0]], mode='image', image_mode='final',
                    contours=False, centroid=False, spinepoints=False,
                    random_colors=True, trajectories=True, trajectory_dt=0,
                    save_as='single_trajectory', show_display=False)
    elif exp_type == 'odor_preference':
        ind = d.compute_preference_index(arena_diameter_in_mm=100)
        print(ind)
        results['PI'] = ind
        # return ind
    elif exp_type == 'realistic_imitation':
        d.save_agent(pars=fun.flatten_list(d.points_xy) + fun.flatten_list(d.contour_xy), header=True)
    return fig_dict, results

def init_sim(env_params):
    env = LarvaWorldSim(env_params=env_params, vis_kwargs=get_vis_kwargs_dict(visible_clock=False))
    env.allow_clicks = True
    env.is_running = True
    return env


def configure_sim(env_params):
    env = init_sim(env_params)
    while env.is_running:
        env.step()
        env.render()
    food_list = env.get_agent_list(class_name='Food')
    border_list = env.get_agent_list(class_name='Border')
    return food_list, border_list


def run_sim_basic(
        vis_kwargs,
        sim_params,
        env_params,
        life_params={},
        collections=None,
        save_to=None,
        media_name=None,
        save_data_flag=True,
        enrich=False,
        experiment=None,
        par_config=dat.SimParConf,
        seed=1,
        **kwargs):
    if collections is None:
        collections = ['pose']
    np.random.seed(seed)
    id = sim_params['sim_id']
    dt = sim_params['dt']
    Nsec = sim_params['sim_dur'] * 60
    path = sim_params['path']
    Box2D = sim_params['Box2D']

    if save_to is None:
        save_to = paths.SimFolder
    if path is not None:
        save_to = os.path.join(save_to, path)
    dir_path = os.path.join(save_to, id)

    # Store the parameters so that we can save them in the results folder
    sim_date = datetime.datetime.now()
    param_dict = locals()
    start = time.time()
    Nsteps = int(Nsec / dt)
    # # FIXME This only takes the first configuration into account
    # print(env_params['larva_params'].values())
    Npoints = list(env_params['larva_params'].values())[0]['model']['body_params']['Nsegs'] + 1

    d = LarvaDataset(dir=dir_path, id=id, fr=int(1 / dt),
                     Npoints=Npoints, Ncontour=0,
                     arena_pars=env_params['arena_params'],
                     par_conf=par_config, save_data_flag=save_data_flag, load_data=False,
                     life_params=life_params
                     )

    collected_pars = collection_conf(dataset=d, collections=collections)
    env = LarvaWorldSim(id=id, dt=dt, Box2D=Box2D,
                        # larva_pars=larva_pars,
                        env_params=env_params, collected_pars=collected_pars,
                        life_params=life_params, Nsteps=Nsteps,
                        media_name=media_name, save_to=d.vis_dir, experiment=experiment,
                        **kwargs, vis_kwargs=vis_kwargs)
    # Prepare the odor layer for a number of timesteps
    odor_prep_time = 0.0
    larva_prep_time = 0.5
    env.prepare_odor_layer(int(odor_prep_time * 60 / env.dt))
    # Prepare the flies for a number of timesteps
    env.prepare_flies(int(larva_prep_time * 60 / env.dt))
    print(f'Initialized simulation {id}!')

    # Run the simulation
    completed = env.run()

    if not completed:
        d.delete()
        print(f'Simulation not completed!')
        res = None
    else:
        # Read the data collected during the simulation
        env.larva_end_col.collect(env)
        env.food_end_col.collect(env)

        d.set_step_data(env.larva_step_col.get_agent_vars_dataframe())
        d.set_end_data(env.larva_end_col.get_agent_vars_dataframe().droplevel('Step'))
        d.set_food_end_data(env.food_end_col.get_agent_vars_dataframe().droplevel('Step'))

        end = time.time()
        dur = end - start
        param_dict['duration'] = np.round(dur, 2)

        # Save simulation data and parameters
        if save_data_flag:
            if enrich and experiment is not None:
                d = sim_enrichment(d, experiment)
            d.save()
            fun.dict_to_file(param_dict, d.sim_pars_file_path)
            # Save the odor layer
            if env.Nodors > 0:
                env.plot_odorscape(save_to=d.plot_dir)
        print(f'Simulation completed in {dur} seconds!')
        res = d
    env.close()
    return res


ser = pickle.dumps(run_sim_basic)
run_sim = pickle.loads(ser)


def collection_conf(dataset, collections):
    d = dataset
    step_pars = []
    end_pars = []
    for c in collections:
        if c == 'midline':
            step_pars += list(midline_xy_pars(N=d.Nsegs).keys())
            # step_pars += fun.flatten_list(d.points_xy)
        elif c == 'contour':
            step_pars += fun.flatten_list(d.contour_xy)
        else:
            step_pars += output[c]['step']
            end_pars += output[c]['endpoint']

    collected_pars = {'step': fun.unique_list(step_pars),
                      'endpoint': fun.unique_list(end_pars)}
    return collected_pars


def load_reference_dataset():
    reference_dataset = LarvaDataset(dir=paths.RefFolder, load_data=False)
    reference_dataset.load(step_data=False)
    return reference_dataset


# def generate_config(exp, sim_params, Nagents=None, life_params={}):
#     config = copy.deepcopy(exp_types[exp])
#     config['experiment'] = exp
#     config['sim_params'] = sim_params
#     config['life_params'] = life_params
#
#     if type(config['env_params']) == str:
#         config['env_params'] = loadConf(config['env_params'], 'Env')
#
#     if Nagents is not None:
#         config['env_params']['larva_params']['Larva']['N'] = Nagents
#     for k, v in config['env_params']['larva_params'].items():
#         if type(v['model']) == str:
#             v['model'] = loadConf(v['model'], 'Model')
#     # print(config['env_params']['larva_params']['Larva']['model'])
#     # raise
#     return config


def get_exp_conf(exp_type, sim_params, life_params=None, enrich=True, N=None):
    if life_params is None:
        life_params = {'starvation_hours': None,
                       'hours_as_larva': 0.0,
                       'deb_base_f': 1.0}
    exp_conf = loadConf(exp_type, 'Exp')
    env = exp_conf['env_params']
    if type(env) == str:
        env = loadConf(env, 'Env')
    for k, v in env['larva_params'].items():
        if type(v['model']) == str:
            v['model'] = loadConf(v['model'], 'Model')
    if N is not None :
        for k in list(env['larva_params'].keys()) :
            env['larva_params'][k]['N'] = N
    exp_conf['env_params'] = env
    exp_conf['life_params'] = life_params
    exp_conf['sim_params'] = sim_params
    exp_conf['experiment'] = exp_type
    exp_conf['enrich'] = enrich
    return exp_conf
