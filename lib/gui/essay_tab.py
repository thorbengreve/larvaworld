import copy
import os

import PySimpleGUI as sg
import numpy as np

import lib.conf.dtype_dicts as dtypes

from lib.aux.collecting import output_keys
from lib.gui.gui_lib import CollapsibleDict, Collapsible, \
    named_bool_button, GraphList, graphic_button, t10_kws, col_kws, col_size, t24_kws, \
    t8_kws, \
    t16_kws, t11_kws, t6_kws, t12_kws, t14_kws, t13_kws, t9_kws, named_list_layout
from lib.gui.tab import GuiTab, SelectionList
from lib.sim.single_run import run_sim, run_essay
from lib.sim.analysis import sim_analysis, essay_analysis
from lib.conf.conf import loadConfDict, loadConf, next_idx
from lib.stor import paths


class EssayTab(GuiTab):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.essay_exps_key='Essay_exps'
        self.exp_figures_key='Essay_exp_figures'

    def build(self):
        l_essay = SelectionList(tab=self, conftype='Essay', actions=['load', 'save', 'delete', 'run'],
                              # progress=True,
                              # sublists={'env_params': l_env, 'life_params' : l_life}
                              )
        next_to_header=[graphic_button('play', f'RUN_{self.essay_exps_key}', tooltip='Run the selected essay experiment.')]
        l_exps=named_list_layout(text='Experiments', key=self.essay_exps_key, choices=[], drop_down=False,
                          single_line=False, next_to_header=next_to_header)

        self.selectionlists = [l_essay]

        # print(temp)

        g1 = GraphList(self.name, list_header='Simulation results', canvas_size=(1000, 500))
        g2 = GraphList(self.exp_figures_key, list_header='Experiment data',canvas_size=(1000, 500),
                       fig_dict={})
        l_conf = [[sg.Col([
            *[i.get_layout() for i in [l_essay]],
            [l_exps]
        ])]]
        gg=sg.Col([
            [g1.canvas, g1.get_layout()],
            [g2.canvas, g2.get_layout()]
        ],
            size=col_size(0.8), **col_kws)
        l = [[sg.Col(l_conf, **col_kws, size=col_size(0.2)),
              gg
              ]]

        c = {}
        # for i in [s1]:
        #     c.update(i.get_subdicts())
        g = {g1.name: g1, g2.name:g2}
        d = {}
        d['essay_results'] = {'fig_dict': {}}
        return l, c, g, d

    def run(self, v, w, c, d, g, conf, id):
        conf = loadConf(id, 'Essay')
        for essay_exp in list(conf.keys()):
            d, g = self.run_essay_exp(v, w, c, d, g, essay_exp)
        return d, g

    def update(self, w, c, conf, id):
        exps=list(conf.keys())
        w.Element(self.essay_exps_key).Update(values=exps)
        if id=='roversVSsitters' :
            exp_figs=paths.RoverSitterFigFolder
            temp = {f.split('.')[0]: f'{exp_figs}/{f}' for f in os.listdir(exp_figs)}
            self.gui.graph_lists[self.exp_figures_key].update(w, temp)


    def get(self, w, v, c, as_entry=True):
        conf = {
            # 'exp_types' :
            # 'essay_params': c['essay_params'].get_dict(v, w),
            # # 'sim_params': sim,
            # 'collections': [k for k in output_keys if c['Output'].get_dict(v, w)[k]],
            # # 'life_params': c['life'].get_dict(v, w),
            # 'enrichment': loadConf(v[self.selectionlists[0].k], 'Exp')['enrichment'],
        }
        return conf

    def eval(self, e, v, w, c, d, g):
        if e == f'RUN_{self.essay_exps_key}':
            essay_exp=v[self.essay_exps_key][0]
            if essay_exp not in [None, '']:
                d, g = self.run_essay_exp(v, w, c, d, g, essay_exp)
        return d, g

    def run_essay_exp(self, v, w, c, d, g, essay_exp):
        essay_type = v[self.selectionlists[0].k]
        conf=loadConf(essay_type, 'Essay')
        essay = conf[essay_exp]
        kws = {
            # **conf,
            'id' : f'{essay_type}_{essay_exp}',
            'vis_kwargs': c['Visualization'].get_dict(v, w) if 'Visualization' in list(
                c.keys()) else dtypes.get_dict('visualization'),
            'exp_types': essay['exp_types'],
            'durations': essay['durations']
            # 'progress_bar' : w[p.k]
        }
        ds0 = run_essay(**kws)
        if ds0 is not None:
            fig_dict, results = essay_analysis(essay_type, essay_exp, ds0)
            d['essay_results'][essay_exp] = {'exp_fig_dict' : fig_dict, 'results':results}
            d['essay_results']['fig_dict'].update(fig_dict)
            g[self.name].update(w, d['essay_results']['fig_dict'])
        return d, g



if __name__ == "__main__":
    from lib.gui.gui import LarvaworldGui

    larvaworld_gui = LarvaworldGui(tabs=['essay'])
    larvaworld_gui.run()
