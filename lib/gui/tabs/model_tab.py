import copy
import os

from lib.gui.aux.elements import CollapsibleDict, Collapsible, CollapsibleTable, GraphList, SelectionList, \
    CollapsibleTable2
from lib.gui.aux.functions import col_size, col_kws, gui_col
import lib.conf.dtype_dicts as dtypes
from lib.gui.tabs.tab import GuiTab
from lib.stor import paths

class ModelTab(GuiTab):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fields=['physics', 'energetics', 'body', 'odor']
        self.module_keys = list(dtypes.get_dict('modules').keys())

    def update(self, w, c, conf, id=None):
        for n in self.fields:
            c[n].update(w, conf[n])
        module_dict = conf['brain']['modules']
        for k, v in module_dict.items():
            dic = conf['brain'][f'{k}_params']
            if k == 'olfactor':
                if dic is not None:
                    odor_gains = dic['odor_dict']
                    dic.pop('odor_dict')
                else:
                    odor_gains = {}
                c['odor_gains'].update(w, odor_gains)
            c[k].update(w, dic)
        c['Brain'].update(w, module_dict, use_prefix=False)

    def get(self, w, v, c, as_entry=True):
        module_dict = dict(zip(self.module_keys, [w[f'TOGGLE_{k}'].get_state() for k in self.module_keys]))
        m = {}
        for n in self.fields:
            m[n] = None if c[n].state is None else c[n].get_dict(v, w)

        b = {}
        b['modules'] = module_dict
        for k in module_dict.keys():
            b[f'{k}_params'] = c[k].get_dict(v, w)
        if b['olfactor_params'] is not None:
            b['olfactor_params']['odor_dict'] = c['odor_gains'].dict
        b['nengo'] = False
        m['brain'] = b
        return copy.deepcopy(m)

    def build(self):
        l0 = SelectionList(tab=self, buttons=['load', 'save', 'delete'])
        c1 = [CollapsibleDict(n, default=True, **kwargs) for n, kwargs in zip(self.fields, [{}, {'toggle': True}, {}, {}])]
        s1 = CollapsibleTable2('odor_gains', headings=['id', 'mean', 'std'])
        c2 = [CollapsibleDict(k, default=True, toggle=True) for k in self.module_keys]
        l2 = [i.get_layout() for i in c2]
        b = Collapsible('Brain', content=l2, state=True)

        fdir=paths.ModelFigFolder
        fig_dict= {f: f'{fdir}/{f}' for f in os.listdir(fdir)}
        g1 = GraphList(self.name, tab=self,list_header='Model', fig_dict=fig_dict, subsample=3, canvas_size=col_size(x_frac=0.6*0.9, y_frac=0.9))
        g = {g1.name: g1}

        l = [[
            gui_col([l0, b, s1], 0.25),
            gui_col([*c1, g1], 0.25),
            gui_col([g1.canvas], 0.5),
            # gui_col([g1], 0.2)
        ]]

        c = {}
        for s in c2 + c1 + [s1, b]:
            c.update(s.get_subdicts())

        return l, c, g, {}


if __name__ == "__main__":
    from lib.gui.tabs.gui import LarvaworldGui
    larvaworld_gui = LarvaworldGui(tabs=['larva-model'])
    larvaworld_gui.run()
