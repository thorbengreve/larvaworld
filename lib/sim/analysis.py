import numpy as np

from lib.anal.comparing import ExpFitter
from lib.anal.plotting import plot_endpoint_scatter, plot_turn_Dbearing, plot_turn_amp, plot_turns, plot_timeplot, \
    plot_navigation_index, plot_debs, plot_food_amount, plot_gut, plot_pathlength, plot_endpoint_params, barplot, \
    comparative_analysis, plot_marked_turns, plot_chunk_Dorient2source, plot_marked_strides, targeted_analysis, \
    plot_stridesNpauses, plot_ang_pars, plot_interference, lineplot
from lib.aux import functions as fun
from lib.conf import dtype_dicts as dtypes
from lib.conf.conf import loadConf
from lib.conf.par import getPar
from lib.model.DEB.deb import deb_default
from lib.sim.single_run import load_reference_dataset
from lib.stor import paths
from lib.stor.larva_dataset import LarvaDataset


def sim_analysis(d: LarvaDataset, exp_type, show_output=False):

    if d is None:
        return
    if not type(d)==list :
        d=[d]
    ccc = {'show': False,
           'save_to': d[0].config['parent_plot_dir']}
    cc = {'datasets': d,
          'subfolder': None,
          **ccc}
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

        # fig_dict['angular'] = plot_ang_pars(datasets=[d], **ccc)
        # fig_dict['bouts'] = plot_stridesNpauses(datasets=[d], plot_fits=None, only_fit_one=False, test_detection=True,
        #                                         **ccc)

        fig_dict['scatter_x4'] = plot_endpoint_scatter(keys=['cum_sd', 'f_am', 'str_tr', 'pau_tr'], **cc)
        fig_dict['scatter_x2'] = plot_endpoint_scatter(keys=['cum_sd', 'f_am'], **cc)

    elif exp_type in ['food_at_bottom']:
        # ds = d.split_dataset(is_last=False, show_output=show_output)


        fig_dict['bearing correction VS Y pos'] = plot_turn_amp(par_short='tur_y0', mode='hist', ref_angle=270, **cc)
        fig_dict['turn angle VS Y pos (hist)'] = plot_turn_amp(par_short='tur_y0', mode='hist', **cc)
        fig_dict['turn angle VS Y pos (scatter)'] = plot_turn_amp(par_short='tur_y0', mode='scatter', **cc)
        fig_dict['turn duration'] = plot_turn_amp(par_short='tur_t', mode='scatter', absolute=True, **cc)
        fig_dict['turn amplitude'] = plot_turns(**cc)
        fig_dict['Y position'] = plot_timeplot(['y'], show_first=False, legend_loc='lower left', **cc)
        fig_dict['navigation index'] = plot_navigation_index(**cc)
        fig_dict['orientation to center'] = plot_turn_Dbearing(min_angle=5.0, ref_angle=None, **cc)
        fig_dict['bearing to 270deg'] = plot_turn_Dbearing(min_angle=5.0, ref_angle=270, par=None, **cc)

    elif exp_type in ['rovers_sitters_on_standard', 'rovers_sitters_on_agar']:
        s = exp_type.split('_')[-1]
        # ds = d.split_dataset(groups=['Rover', 'Sitter'], show_output=show_output)
        debs = fun.flatten_list([dd.load_deb_dicts(use_pickle=False) for dd in d])
        # d.delete(show_output=show_output)
        fig_dict[f'RS hunger on {s} '] = plot_debs(deb_dicts=debs, save_as=f'deb_on_{s}.pdf',
                                                   mode='hunger', sim_only=True, roversVSsitters=True, **cc)

    elif exp_type in ['growth', 'rovers_sitters']:
        deb_model = deb_default(epochs=d[0].config['epochs'], substrate_quality=d[0].config['substrate_quality'])
        if exp_type == 'rovers_sitters':
            roversVSsitters = True
            # ds = d.split_dataset(groups=['Sitter', 'Rover'], show_output=show_output)
            labels = ['Sitters', 'Rovers']
        else:
            roversVSsitters = False
            # ds = [d]
            labels = [dd.id for dd in d]

        deb_dicts = fun.flatten_list([dd.load_deb_dicts(use_pickle=False) for dd in d]) + [deb_model]
        # deb_dicts = d.load_deb_dicts() + [deb_model]
        c = {'roversVSsitters': roversVSsitters}
        c1 = {'deb_dicts': deb_dicts[:-1],
              'sim_only': True}

        for m in ['feeding', 'reserve_density', 'fs', 'assimilation', 'food_ratio_1', 'food_ratio_2', 'food_mass_1',
                  'food_mass_2']:
            for t in ['hours']:
                save_as = f'{m}_in_{t}.pdf'
                fig_dict[f'{m} ({t})'] = plot_debs(save_as=save_as, mode=m, time_unit=t, **c, **c1, **cc)

        for m in ['energy', 'growth', 'full']:
            save_as = f'{m}_vs_model.pdf'
            fig_dict[f'{m} vs model'] = plot_debs(deb_dicts=deb_dicts, save_as=save_as, mode=m, **c, **cc)

        if exp_type == 'rovers_sitters':
            # cc = {'datasets': ds,
            #       'labels': labels,
            #       'save_to': d.plot_dir,
            #       **ccc}
            cc1 = {'show_first': False, 'legend_loc': 'upper_left', **cc}

            fig_dict['faeces ratio'] = plot_timeplot(['f_out_r'], **cc1)
            fig_dict['faeces amount'] = plot_timeplot(['f_out'], **cc1)
            fig_dict['food absorption efficiency'] = plot_timeplot(['abs_r'], **cc1)
            fig_dict['food absorbed'] = plot_timeplot(['f_ab'], **cc1)
            fig_dict['food intake (timeplot)'] = plot_timeplot(['f_am'], **cc1)

            fig_dict['food intake'] = plot_food_amount(**cc)
            fig_dict['food intake (filt)'] = plot_food_amount(filt_amount=True, **cc)
            fig_dict['gut occupancy'] = plot_gut(**cc)
            fig_dict['pathlength'] = plot_pathlength(scaled=False, **cc)
            fig_dict['endpoint'] = plot_endpoint_params(mode='deb', **cc)
            try:
                fig_dict['food intake (barplot)'] = barplot(par_shorts=['f_am'], **cc)
            except:
                pass

    elif exp_type == 'dispersion_x2':
        samples=fun.unique_list([dd.config['sample'] for dd in d])
        targets=[LarvaDataset(loadConf(sd, 'Ref')['dir'])for sd in samples]
        dic0 = comparative_analysis(datasets=d+targets,**ccc)
        fig_dict.update(dic0)
        for dd in d :
            dd.delete()

    # elif exp_type == 'dispersion':
    #     target_dataset = load_reference_dataset(dataset_id=d.config['sample_dataset'])
    #     ds = [d, target_dataset]
    #     labels = ['simulated', 'empirical']
    #     # targeted_analysis(ds)
    #     dic0 = comparative_analysis(datasets=ds, labels=labels, simVSexp=True, save_to=None, **ccc)
    #     fig_dict.update(dic0)
    #     dic1 = {f'marked_strides_idx_0_slice_{s0}-{s1}': plot_marked_strides(datasets=[d], agent_idx=0,
    #                                                                          slice=[s0, s1], **ccc) for (s0, s1) in
    #             [(10, 50), (60, 100)]}
    #     # dic1 = plot_marked_strides(dataset=d, agent_ids=d.agent_ids[:3], title=' ', slices=[[10, 50], [60, 100]])
    #     fig_dict.update(dic1)
    #     dic2 = plot_marked_turns(dataset=d, agent_ids=d.agent_ids[:3], min_turn_angle=20, **ccc)
    #     fig_dict.update(dic2)

    elif exp_type in ['chemotaxis_approach', 'chemotaxis_local', 'chemotaxis_diffusion']:
        if exp_type in ['chemotaxis_local', 'chemotaxis_diffusion']:
            ps = ['o_cent', 'sd_cent', 'd_cent']
            source = (0.0, 0.0)
        elif exp_type in ['chemotaxis_approach']:
            ps = ['o_chem', 'sd_chem', 'd_chem']
            source = (0.04, 0.0)
        for p in ps:
            fig_dict[p] = plot_timeplot([p], show_first=True, **cc)
        for p in ['c_odor1', 'dc_odor1', 'A_olf', 'A_tur', 'Act_tur']:
            fig_dict[p] = plot_timeplot([p], **cc)
        for chunk in ['turn', 'stride', 'pause']:
            for dur in [0.0, 0.5, 1.0]:
                try:
                    fig_dict[f'{chunk}_bearing2source_min_{dur}_sec'] = plot_chunk_Dorient2source(chunk=chunk,
                                                                                                  source=source,
                                                                                                  min_dur=dur, **cc)
                except:
                    pass
        vis_kwargs = dtypes.get_dict('visualization', mode='image', image_mode='final', show_display=False,
                                     random_colors=True, trajectories=True,
                                     visible_clock=False, visible_scale=False, media_name='single_trajectory')
        d[0].visualize(agent_ids=[d[0].agent_ids[0]], vis_kwargs=vis_kwargs)

    if 'odor_pref' in exp_type:
        ind = d[0].compute_preference_index()
        print(f'Preference for left odor : {np.round(ind, 3)}')
        results['PI'] = ind

    if exp_type in ['odor_pref_RL', 'chemotaxis_RL']:
        c = {
            'show_first': False,
            'table': 'best_gains',
            **cc
        }

        g_keys = ['g_odor1'] if exp_type == 'chemotaxis_RL' else ['g_odor1', 'g_odor2']
        fig_dict['best_gains_table'] = plot_timeplot(g_keys, save_as='best_gains.pdf', **c)
        fig_dict['olfactor_decay_table'] = plot_timeplot(['D_olf'], save_as='olfactor_decay.pdf', **c)
        fig_dict['olfactor_decay_table_inds'] = plot_timeplot(['D_olf'], save_as='olfactor_decay_inds.pdf',
                                                              individuals=True, **c)
        fig_dict['reward_table'] = plot_timeplot(['cum_reward'], save_as='reward.pdf', **c)
    elif exp_type == 'realistic_imitation':
        d[0].save_agents(pars=fun.flatten_list(d[0].points_xy) + fun.flatten_list(d[0].contour_xy), header=True)
    if exp_type == 'dish':
        targeted_analysis(d)
        fig_dict = {f'stride_track_idx_0_in_{s0}-{s1}': plot_marked_strides(agent_idx=0,
                                                                            slice=[s0, s1], **cc) for (s0, s1) in
                    [(0, 60)]}
    if exp_type == 'imitation':
        f = ExpFitter(d[0].config['env_params']['larva_groups']['ImitationGroup']['sample'])
        results['sample_fit'] = f.compare(d[0], save_to_config=True)
        print(results['sample_fit'])
    print(f'    Analysis complete!')
    return fig_dict, results


def essay_analysis(essay_type, exp, ds0, all_figs=False, path=None):
    if path is None :
        parent_dir = f'essays/{essay_type}/global_test'
        plot_dir = f'{paths.SimFolder}/{parent_dir}/plots'
    else :
        plot_dir=f'{path}/plots'
    ccc = {'show': False}
    if len(ds0) == 0 or any([d0 is None for d0 in ds0]):
        return {}, {}
    figs = {}
    results = {}

    if essay_type in ['roversVSsitters', 'RvsS']:
        RS_leg_cols = ['black', 'white']
        markers = ['D', 's']
        ls = [r'$for^{R}$', r'$for^{S}$']
        shorts = ['f_am', 'sf_am_Vg', 'sf_am_V', 'sf_am_A', 'sf_am_M']

        def dsNls(ds0, lls=None):
            if lls is None:
                lls = fun.flatten_list([ls] * len(ds0))
            dds = []
            deb_dicts = []
            for d in ds0:
                ds, debs = split_rovers_sitters(d)
                dds += ds
                deb_dicts += debs

            return {'datasets': dds,
                    'labels': lls,
                    'deb_dicts': deb_dicts,
                    'save_to': plot_dir,
                    'leg_cols': RS_leg_cols,
                    'markers': markers,
                    **ccc
                    }

        if exp == 'pathlength':
            lls = fun.flatten_list([[rf'{s} $for^{"R"}$', rf'{s} $for^{"S"}$'] for s in ['Agar', 'Yeast']])
            kwargs = {
                ** dsNls(ds0, lls),
                'xlabel': r'time on substrate_type $(min)$',
            }
            figs['1_pathlength'] = plot_pathlength(scaled=False, save_as=f'1_PATHLENGTH.pdf', unit='cm', **kwargs)

        elif exp == 'intake':
            kwargs = {**dsNls(ds0),
                      'coupled_labels': [10, 15, 20],
                      'xlabel': r'Time spent on food $(min)$'}
            figs['2_intake'] = barplot(par_shorts=['sf_am_V'], save_as=f'2_AD_LIBITUM_INTAKE.pdf', **kwargs)
            if all_figs:
                for s in shorts:
                    p = getPar(s, to_return=['d'])[0]
                    figs[f'intake {p}'] = barplot(par_shorts=[s], save_as=f'2_AD_LIBITUM_{p}.pdf', **kwargs)

        elif exp == 'starvation':
            hs = [0, 1, 2, 3, 4]
            kwargs = {**dsNls(ds0),
                      'coupled_labels': hs,
                      'xlabel': r'Food deprivation $(h)$'}
            figs['3_starvation'] = lineplot(par_shorts=['f_am_V'], save_as='3_POST-STARVATION_INTAKE.pdf',
                                            ylabel='Food intake', scale=1000, **kwargs)
            if all_figs:
                for ii in ['feeding']:
                    figs[ii] = plot_debs(mode=ii, save_as=f'3_POST-STARVATION_{ii}.pdf', include_egg=False,
                                         label_epochs=False, **kwargs)
                for s in shorts:
                    p = getPar(s, to_return=['d'])[0]
                    figs[f'post-starvation {p}'] = lineplot(par_shorts=[s], save_as=f'3_POST-STARVATION_{p}.pdf',
                                                            **kwargs)

        elif exp == 'quality':
            qs = [1.0, 0.75, 0.5, 0.25, 0.15]
            qs_labels = [int(q * 100) for q in qs]
            kwargs = {**dsNls(ds0),
                      'coupled_labels': qs_labels,
                      'xlabel': 'Food quality (%)'
                      }
            figs['4_quality'] = barplot(par_shorts=['sf_am_V'], save_as='4_REARING-DEPENDENT_INTAKE.pdf', **kwargs)
            if all_figs:
                for s in shorts:
                    p = getPar(s, to_return=['d'])[0]
                    figs[f'rearing-quality {p}'] = barplot(par_shorts=[s], save_as=f'4_REARING_{p}.pdf', **kwargs)

        elif exp == 'refeeding':
            h = 3
            n = f'5_REFEEDING_after_{h}h_starvation_'
            kwargs = dsNls(ds0)
            figs['5_refeeding'] = plot_food_amount(scaled=True, filt_amount=True, save_as='5_REFEEDING_INTAKE.pdf',
                                                   **kwargs)

            if all_figs:
                figs[f'refeeding food-intake'] = plot_food_amount(scaled=True, save_as=f'{n}scaled_intake.pdf',**kwargs)
                figs[f'refeeding food-intake(filt)'] = plot_food_amount(scaled=True, filt_amount=True,
                                                                        save_as=f'{n}scaled_intake_filt.pdf', **kwargs)
                for s in shorts:
                    p = getPar(s, to_return=['d'])[0]
                    figs[f'refeeding {p}'] = plot_timeplot(par_shorts=[s], show_first=False, subfolder=None,
                                                           save_as=f'{n}{p}.pdf', **kwargs)
        # for d in kwargs['datasets'] :
        #     d.delete()
    print(f'    Analysis complete!')
    return figs, results


def split_rovers_sitters(d):
    ds = d.split_dataset()
    debs = d.load_deb_dicts(use_pickle=False)
    d.delete(show_output=False)
    return ds, debs
