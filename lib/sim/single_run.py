""" Run a simulation and save the parameters and data to files."""
import copy
import datetime
import json
import time

import lib.aux.functions as fun
import lib.conf.data_modes as conf
import lib.conf.sim_modes
import lib.stor.paths as paths
from lib.anal.plotting import *
from lib.aux.collecting import effector_collection
from lib.conf import exp_types
from lib.model.envs._larvaworld import LarvaWorldSim
from lib.model.agents.deb import deb_dict, deb_default
from lib.stor.larva_dataset import LarvaDataset
import lib.sim.gui_lib as gui
import pickle


def sim_enrichment(d, experiment):
    d.build_dirs()
    if experiment in ['growth', 'growth_2x']:
        d.deb_analysis(is_last=False)
    elif experiment == 'focus':
        d.angular_analysis(is_last=False)
        d.detect_turns(is_last=False)
    elif experiment == 'dispersion':
        d.enrich(length_and_centroid=False, is_last=False)
    return d


def sim_analysis(d, experiment):
    if d is None:
        return
    s, e = d.step_data, d.endpoint_data
    if experiment in ['feed_patchy', 'feed_scatter', 'feed_grid']:
        # am = e['amount_eaten'].values
        # print(am)
        # cr,pr,fr=e['stride_dur_ratio'].values, e['pause_dur_ratio'].values, e['feed_dur_ratio'].values
        # print(cr+pr+fr)
        # cN, pN, fN = e['num_strides'].values, e['num_pauses'].values, e['num_feeds'].values
        # print(cN, pN, fN)
        # cum_sd, f_success=e['cum_scaled_dst'].values, e['feed_success_rate'].values
        # print(cum_sd, f_success)
        plot_endpoint_scatter(datasets=[d], labels=[d.id], par_shorts=['cum_sd', 'f_am', 'str_tr', 'fee_tr'])
        plot_endpoint_scatter(datasets=[d], labels=[d.id], par_shorts=['cum_sd', 'f_am'])

    elif experiment in ['growth', 'growth_2x']:
        starvation_hours = d.config['starvation_hours']
        f = d.config['deb_base_f']
        deb_model = deb_default(starvation_hours=starvation_hours, base_f=f)
        if experiment == 'growth_2x':
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

        plot_gut(**cc)
        plot_food_amount(**cc)
        plot_food_amount(filt_amount=True, **cc)
        # raise
        plot_pathlength(scaled=False, **cc)
        plot_endpoint_params(mode='deb', **cc)
        try:
            barplot(par_shorts=['f_am'], **cc)
        except:
            pass

        deb_dicts = [deb_dict(d, id, starvation_hours=starvation_hours) for id in d.agent_ids] + [deb_model]
        c = {'save_to': d.plot_dir,
             'roversVSsitters': roversVSsitters}

        plot_debs(deb_dicts=deb_dicts[:-1], save_as='deb_hunger_sim_start.pdf', mode='hunger', sim_only=True,
                  start_at_sim_start=True, **c)

        plot_debs(deb_dicts=deb_dicts[:-1], save_as='deb_f_sec.pdf', mode='f', sim_only=True,
                  time_unit='seconds', start_at_sim_start=True, **c)

        plot_debs(deb_dicts=deb_dicts[:-1], save_as='deb_f.pdf', mode='f', sim_only=True, **c)
        plot_debs(deb_dicts=deb_dicts[:-1], save_as='deb_hunger.pdf', mode='hunger', sim_only=True, **c)
        plot_debs(deb_dicts=deb_dicts, save_as='comparative_deb_complete.pdf', mode='complete', **c)
        # raise
        plot_debs(deb_dicts=deb_dicts, save_as='comparative_deb.pdf', **c)

        plot_debs(deb_dicts=deb_dicts, save_as='comparative_deb_minimal.pdf', mode='minimal', **c)

        plot_debs(deb_dicts=deb_dicts[:-1], save_as='deb.pdf', sim_only=True, **c)
        plot_debs(deb_dicts=deb_dicts[:-1], save_as='deb_minimal.pdf', mode='minimal', sim_only=True, **c)
        plot_debs(deb_dicts=deb_dicts[:-1], save_as='deb_complete.pdf', mode='complete', sim_only=True, **c)
        plot_debs(deb_dicts=[deb_dicts[-1]], save_as='default_deb.pdf', **c)

        plot_debs(deb_dicts=deb_dicts[:-1], save_as='deb_f_sec.pdf', mode='f', sim_only=True,
                  time_unit='seconds', start_at_sim_start=True, **c)
        plot_debs(deb_dicts=deb_dicts[:-1], save_as='deb_f.pdf', mode='f', sim_only=True, **c)

        plot_debs(deb_dicts=deb_dicts[:-1], save_as='deb_hunger_sim_start.pdf', mode='hunger', sim_only=True,
                  start_at_sim_start=True, **c)

    elif experiment == 'dispersion':
        target_dataset = load_reference_dataset()
        datasets = [d, target_dataset]
        labels = ['simulated', 'empirical']
        comparative_analysis(datasets=datasets, labels=labels, simVSexp=True, save_to=None)
        plot_marked_strides(dataset=d, agent_ids=d.agent_ids[:3], title=' ', slices=[[10, 50], [60, 100]])
        plot_marked_turns(dataset=d, agent_ids=d.agent_ids[:3], min_turn_angle=20)


    elif experiment in ['chemorbit', 'chemotax']:
        plot_timeplot('c_odor1', datasets=[d])
        plot_timeplot('A_olf', datasets=[d])
        plot_timeplot('A_tur', datasets=[d])
        plot_timeplot('Act_tur', datasets=[d])
        plot_distance_to_source(dataset=d, experiment=experiment)
        d.visualize(agent_ids=[d.agent_ids[0]], mode='image', image_mode='final',
                    contours=False, centroid=False, spinepoints=False,
                    random_colors=True, trajectories=True, trajectory_dt=0,
                    save_as='single_trajectory')
    elif experiment == 'odor_pref':
        ind = d.compute_preference_index(arena_diameter_in_mm=100)
        print(ind)
        return ind
    elif experiment == 'imitation':
        d.save_agent(pars=fun.flatten_list(d.points_xy) + fun.flatten_list(d.contour_xy), header=True)


def init_sim(env_params, fly_params):
    env = LarvaWorldSim(fly_params=fly_params, env_params=env_params, mode='video')
    env.allow_clicks = True
    env.visible_clock = False
    env.is_running = True
    return env


def configure_sim(env_params, fly_params):
    env = init_sim(env_params, fly_params)
    while env.is_running:
        env.step()
        env.render()
    food_list = env.get_agent_list(class_name='Food')
    border_list = env.get_agent_list(class_name='Border')
    return food_list, border_list


def run_sim_basic(
        sim_params,
        env_params,
        fly_params,
        life_params={},
        collections=None,
        save_to=None,
        # common_folder=None,
        media_name=None,
        save_data_flag=True,
        enrich=False,
        experiment=None,
        par_config=conf.SimParConf,
        # starvation_hours=[],
        # deb_base_f=1,
        preview=False,
        **kwargs):
    if collections is None:
        collections = ['pose']
    np.random.seed(1)
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


    # current_date = date.today()
    # Store the parameters so that we can save them in the results folder
    sim_date = datetime.datetime.now()
    param_dict = locals()
    start = time.time()

    Nsteps = int(Nsec / dt)
    # FIXME This only takes the first configuration into account
    if not type(fly_params) == list:
        Npoints = fly_params['body_params']['Nsegs'] + 1
    else:
        Npoints = fly_params[0]['body_params']['Nsegs'] + 1

    # Build the environment
    # try :
    d = LarvaDataset(dir=dir_path, id=id, fr=int(1 / dt),
                     Npoints=Npoints, Ncontour=0,
                     arena_pars=env_params['arena_params'],
                     par_conf=par_config, save_data_flag=save_data_flag, load_data=False,
                     life_params=life_params
                     # starvation_hours=starvation_hours, deb_base_f=deb_base_f
                     )

    collected_pars = data_collection_config(dataset=d, collections=collections)
    env = LarvaWorldSim(fly_params=fly_params, id=id, env_params=env_params, dt=dt, Nsteps=Nsteps,
                        collected_pars=collected_pars, Box2D=Box2D,
                        media_name=media_name,
                        save_to=d.vis_dir,
                        life_params=life_params,
                        experiment=experiment,
                                    # starvation_hours=starvation_hours, deb_base_f=deb_base_f,
                                    ** kwargs)
    # Prepare the odor layer for a number of timesteps
    odor_prep_time = 0.0
    larva_prep_time = 0.5
    env.prepare_odor_layer(int(odor_prep_time * 60 / env.dt))
    # Prepare the flies for a number of timesteps
    env.prepare_flies(int(larva_prep_time * 60 / env.dt))
    print(f'Initialized simulation {id}!')
    # if preview :
    #     env.step()
    #     env.render()
    #
    #     im = env.get_image_path()
    #     env.close()
    #     return im

    # Run the simulation
    completed = env.run()

    if not completed:
        d.delete()
        print(f'Simulation not completed!')
        return None
    else:
        # Read the data collected during the simulation
        larva_step_data = env.larva_step_collector.get_agent_vars_dataframe()

        env.larva_endpoint_collector.collect(env)
        env.food_endpoint_collector.collect(env)
        larva_endpoint_data = env.larva_endpoint_collector.get_agent_vars_dataframe()
        food_endpoint_data = env.food_endpoint_collector.get_agent_vars_dataframe()
        env.close()

        larva_endpoint_data = larva_endpoint_data.droplevel('Step')
        food_endpoint_data = food_endpoint_data.droplevel('Step')
        # if 'cum_dur' in sim_params['end_pars']:
        #     larva_endpoint_data['cum_dur'] = larva_step_data.index.unique('Step').size*d.dt
        # if 'num_ticks' in sim_params['end_pars']:
        #     larva_endpoint_data['num_ticks'] = larva_step_data.index.unique('Step').size

        d.set_step_data(larva_step_data)
        d.set_endpoint_data(larva_endpoint_data)
        d.set_food_endpoint_data(food_endpoint_data)

        end = time.time()
        dur = end - start
        param_dict['duration'] = np.round(dur, 2)

        # Save simulation data and parameters
        if save_data_flag:
            if enrich and experiment is not None:
                d = sim_enrichment(d, experiment)
            d.save()
            fun.dict_to_file(param_dict, d.sim_pars_file_path)
            # Show the odor layer
            if env.Nodors > 0:
                env.plot_odorscape(save_to=d.plot_dir)
        print(f'Simulation completed in {dur} seconds!')
        return d


ser = pickle.dumps(run_sim_basic)
run_sim = pickle.loads(ser)


def data_collection_config(dataset, collections):
    d = dataset
    step_pars = []
    end_pars = []
    for c in collections:
        if c == 'midline':
            step_pars += fun.flatten_list(d.points_xy)
        elif c == 'contour':
            step_pars += fun.flatten_list(d.contour_xy)
        else:
            step_pars += effector_collection[c]['step']
            end_pars += effector_collection[c]['endpoint']

    collected_pars = {'step': fun.unique_list(step_pars),
                      'endpoint': fun.unique_list(end_pars)}
    return collected_pars


def load_reference_dataset():
    reference_dataset = LarvaDataset(dir=paths.RefFolder, load_data=False)
    reference_dataset.load(step_data=False)
    return reference_dataset


def next_idx(exp, type='single'):
    from lib.conf.batch_modes import batch_types
    try:
        with open(paths.SimIdx_path) as tfp:
            idx_dict = json.load(tfp)
    except:
        exp_names = exp_types.keys()
        batch_names = batch_types.keys()
        exp_idx_dict = dict(zip(exp_names, [0] * len(exp_names)))
        batch_idx_dict = dict(zip(batch_names, [0] * len(batch_names)))
        idx_dict = {'single': exp_idx_dict,
                    'batch': batch_idx_dict}
    if not exp in idx_dict[type].keys():
        idx_dict[type][exp] = 0
    idx_dict[type][exp] += 1
    with open(paths.SimIdx_path, "w") as fp:
        json.dump(idx_dict, fp)
    return idx_dict[type][exp]


def generate_config(exp, sim_params, Nagents=None, life_params={}):
    config = copy.deepcopy(exp_types[exp])
    config['experiment'] = exp
    # config.update(**exp_kwargs)

    # if 'sim_params' not in config.keys():
    #     config['sim_params'] = copy.deepcopy(default_sim)
    config['sim_params'] = sim_params
    config['life_params'] = life_params
    if Nagents is not None:
        config['env_params']['place_params']['']['N'] = Nagents
    # if sim_time is not None:
    #     config['sim_params']['sim_time_in_min'] = sim_time
    # if dt is not None:
    #     config['sim_params']['dt'] = dt
    # if Box2D:
    #     config['env_params']['space_params'] = box2d_space
    return config
