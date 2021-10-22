from lib.conf.base.dtypes import null_dict, enrichment_dict, base_enrich


def batch(exp, en=None, ss=None, o=None, o_kws={},bm={}, as_entry=True, **kwargs):
    if en is None:
        enrichment = null_dict('enrichment')
    elif en == 'PI':
        enrichment = enrichment_dict(types=['PI'])
    elif en == 'source':
        enrichment = enrichment_dict(types=['angular', 'spatial', 'source'])
    else:
        enrichment=en

    if bm is None:
        bm_kws = {}
    elif bm == 'PI':
        bm_kws = {'run': 'odor_preference','post': 'null', 'final':'odor_preference'}
    elif bm == 'DEB':
        bm_kws = {'run': 'deb','post': 'null', 'final':'deb'}
    else :
        bm_kws = bm
    if ss is not None:
        ss = {p: null_dict('space_search_par', range=r, Ngrid=N) for p, (r, N) in ss.items()}
    conf = null_dict('batch_conf',
                     exp=exp,
                     exp_kws={'enrichment': enrichment, 'experiment' : exp},
                     optimization=null_dict("optimization", fit_par=o, **o_kws) if o is not None else None,
                     space_search=ss,
                     batch_methods=null_dict('batch_methods', **bm_kws),
                     **kwargs)
    if as_entry :
        return {exp: conf}
    else :
        return conf

batch_dict = {
    **batch('chemotaxis',
            ss={'Odor.mean': [(300.0, 1300.0), 3],'decay_coef': [(0.1, 0.5), 3]},
            o='final_dst_to_Source',
            en='source'),
    **batch('chemorbit',
            ss={'Odor.mean': [(300.0, 1300.0), 3],'decay_coef': [(0.1, 0.5), 3]},
            o='final_dst_to_Source',
            en='source'),
    **batch('PItest_off',
            ss={'odor_dict.CS.mean': [(-100.0, 100.0), 21],'odor_dict.UCS.mean': [(-100.0, 100.0), 21]},
            bm = 'PI',
            en='PI'),
    **batch('PItrain_mini',
            ss={'olfactor_noise': [(0.0, 0.4), 2],'decay_coef': [(0.1, 0.5), 2]},
             bm = 'PI',
            en='PI'),
    **batch('PItrain',
            ss={'olfactor_noise': [(0.0, 0.4), 2],'decay_coef': [(0.1, 0.5), 2]},
            bm = 'PI',
            en='PI'),
    **batch('patchy_food',
            ss={'EEB': [(0.0, 1.0), 3],'initial_freq': [(1.5, 2.5), 3]},
            o='ingested_food_volume'),
    **batch('food_grid',
            ss={'EEB': [(0.0, 1.0), 6],'EEB_decay': [(0.1, 2.0), 6]},
            o='ingested_food_volume'),
    **batch('growth',
            ss={'EEB': [(0.5, 0.8), 8],'hunger_gain': [(0.0, 0.0), 1]},
            o='deb_f_deviation', o_kws={'max_Nsims': 20, 'operations': {'mean': True, 'abs': True}}),
    # **batch('RvsS',
    #         ss={'substrate_quality': [(0.5, 0.8), 2], 'hours_as_larva': [(0, 100), 2]},
    #         bm = 'DEB'),
    **batch('imitation',
            ss={'activation_noise': [(0.0, 0.8), 3], 'base_activation': [(15.0, 25.0), 3]},
            o='sample_fit', o_kws={'threshold': 1.0, 'max_Nsims': 20, 'operations': {'mean': False, 'abs': False}},
            bm={'run':'exp_fit'}),
    **batch('tactile_detection',
            ss={'initial_gain': [(-20.0, -5.0), 5],'decay_coef': [(0.3, 0.7), 5]},
            o='cum_food_detected', o_kws={'threshold': 1000.0, 'max_Nsims': 80, 'minimize' : False, 'Nbest' : 8,
                                          'operations': {'mean': True, 'abs': False}}),
**batch('anemotaxis',
            ss={f'windsensor_params.weights.{m1}_{m2}': [(-10.0, 10.0), 3] for m1,m2 in zip(['bend','bend', 'hunch','hunch'], ['lin','ang', 'lin','ang'])},
            o='anemotaxis', o_kws={'threshold': 1000.0, 'max_Nsims': 50, 'minimize' : False, 'Nbest' : 8,
                                          'operations': {'mean': True, 'abs': False}}, en=enrichment_dict(types=['spatial', 'angular', 'wind'])),

}


def fit_tortuosity_batch(sample, model='explorer', exp='dish', idx=0, **kwargs):
    from lib.conf.stored.conf import imitation_exp
    conf=batch(exp=None,
               ss={'activation_noise': [(0.0, 2.0), 3],'base_activation': [(15.0, 25.0), 3]},
               o='tortuosity_20_mean', o_kws={'max_Nsims': 120, 'operations': {'mean': True}},
               en=enrichment_dict(types=['tortuosity']),
               as_entry=False
               )
    conf['exp'] = imitation_exp(sample, model=model, exp=exp, idx=idx, **kwargs)
    conf['batch_id'] = f'imitation_batchrun_{idx}'
    conf['batch_type'] = 'imitation'
    return conf

def fit_global_batch(sample, model='explorer', exp='dish', idx=0, **kwargs):
    from lib.conf.stored.conf import imitation_exp
    conf=batch(exp=None,
               ss={
                   'turner_params.initial_amp': [(25.0, 50.0), 4],
                   'turner_params.noise': [(0.0, 4.0), 4],
                   'turner_params.activation_noise': [(0.0, 4.0), 4],
               },
               o='sample_fit', o_kws={'threshold': 0.1, 'Nbest': 8, 'max_Nsims': 140, 'operations': {'mean': False, 'abs': False}},
               bm={'run': 'exp_fit'},
               en=enrichment_dict(types=['angular']),
               # en=base_enrich(fits=False),
               as_entry=False
               )
    conf['exp'] = imitation_exp(sample, model=model, exp=exp, idx=idx, **kwargs)
    conf['batch_id'] = f'imitation_batchrun_{idx}'
    conf['batch_type'] = 'imitation'
    return conf

def run_fit_global_batch(sample, **kwargs) :
    from run.exec_run import Exec
    from lib.anal.comparing import ExpFitter
    conf = fit_global_batch(sample=sample, **kwargs)
    conf['proc_kws']['exp_fitter'] = ExpFitter(sample, valid_fields=['angular motion'])
    # conf['proc_kws']['exp_fitter'] = ExpFitter(sample, valid_fields=['angular motion', 'reorientation', 'spatial motion'])
    k = Exec('batch', conf)
    return k.exec_run()

if __name__ == '__main__':
    from run.exec_run import Exec
    conf=fit_tortuosity_batch(sample='None.200_controls', model='explorer', exp='dish', idx=0)
    k = Exec('batch', conf)
    k.exec_run()