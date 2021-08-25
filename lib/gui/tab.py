import os
import webbrowser

import PySimpleGUI as sg
import numpy as np
from lib.conf.conf import loadConfDict, saveConf, deleteConf, loadConf, expandConf
from lib.gui.gui_lib import ClickableImage, window_size, t10_kws, graphic_button, t24_kws, named_list_layout, t8_kws, \
    save_conf_window, CollapsibleDict
import lib.stor.paths as paths
import lib.conf.dtype_dicts as dtypes

class ProgressBarLayout :
    def __init__(self, list):
        self.list=list
        n=self.list.disp
        self.k=f'{n}_PROGRESSBAR'
        self.k_complete=f'{n}_COMPLETE'
        self.l = [sg.Text('Progress :', **t8_kws),
                  sg.ProgressBar(100, orientation='h', size=(8.8, 20), key=self.k,
                                 bar_color=('green', 'lightgrey'), border_width=3),
                  graphic_button('check', self.k_complete, visible=False,
                                 tooltip='Whether the current {n} was completed.')]

    def reset(self, w):
        w[self.k].update(0)
        w[self.k_complete].update(visible=False)

    def run(self, w, min=0, max=100):
        w[self.k_complete].update(visible=False)
        w[self.k].update(0, max=max)


class SelectionList:
    def __init__(self, tab, conftype=None, disp=None, actions=[], sublists={},idx=None, progress=False,
                 width=24,with_dict=False, **kwargs):
        self.with_dict = with_dict
        self.width = width
        self.tab = tab
        self.conftype = conftype if conftype is not None else tab.conftype
        self.actions = actions

        if disp is None:
            disps = [k for k, v in self.tab.gui.tab_dict.items() if v[1] == self.conftype]
            if len(disps) == 1:
                disp = disps[0]
            elif len(disps) > 1:
                raise ValueError('Each selectionList is associated with a single configuration type')
        self.disp = disp

        if not progress :
            self.progressbar=None
        else :
            self.progressbar = ProgressBarLayout(self)
        self.k0 = f'{self.conftype}_CONF'
        if idx is not None :
            self.k=f'{self.k0}{idx}'
        else :
            self.k = self.get_next(self.k0)

        self.l = self.build(**kwargs)
        self.sublists = sublists



    def w(self):
        if not hasattr(self.tab.gui, 'window'):
            return None
        else:
            return self.tab.gui.window

    def c(self):
        return self.tab.gui.collapsibles

    def d(self):
        return self.tab.gui.dicts

    def g(self):
        return self.tab.gui.graph_lists

    def set_g(self, g):
        self.tab.gui.graph_lists =g

    def set_d(self, d):
        self.tab.gui.dicts =d

    def build(self, append=[],as_col=True,**kwargs):

        acts = self.actions
        n = self.disp
        bs = []
        if self.progressbar is not None :
            append+=self.progressbar.l


        if 'load' in acts:
            bs.append(graphic_button('load', f'LOAD_{n}', tooltip=f'Load the configuration for a {n}.'))
        if 'edit' in acts:
            bs.append(graphic_button('edit', f'EDIT_{n}', tooltip=f'Configure an existing or create a new {n}.')),
        if 'save' in acts:
            bs.append(graphic_button('data_add', f'SAVE_{n}', tooltip=f'Save a new {n} configuration.'))
        if 'delete' in acts:
            bs.append(graphic_button('data_remove', f'DELETE_{n}',
                                     tooltip=f'Delete an existing {n} configuration.'))
        if 'run' in acts:
            bs.append(graphic_button('play', f'RUN_{n}', tooltip=f'Run the selected {n}.'))
        if 'search' in acts:
            bs.append(graphic_button('search_add', f'SEARCH_{n}', initial_folder=paths.DataFolder, change_submits=True,
                           enable_events=True, target=(0, -1), button_type=sg.BUTTON_TYPE_BROWSE_FOLDER,
                           tooltip='Browse to add datasets to the list.\n Either directly select a dataset directory or a parent directory containing multiple datasets.'))

        if self.with_dict :
            nn=self.tab.gui.tab_dict[n][2]
            self.collapsible = CollapsibleDict(n, True, dict=dtypes.get_dict(nn),type_dict=dtypes.get_dict_dtypes(nn),
                                               header_list_width=self.width, header_dict=loadConfDict(self.conftype),next_to_header=bs,header_key=self.k,
                              header_list_kws={'tooltip' : f'The currently loaded {n}.'},**kwargs)


            temp=self.collapsible.get_layout(as_col=False)

        else :
            self.collapsible =None
            temp = named_list_layout(text=n.capitalize(), key=self.k, choices=self.confs, default_value=None,
                                 drop_down=True,list_width=self.width,single_line=False, next_to_header=bs, as_col=False,
                                 list_kws={'tooltip' : f'The currently loaded {n}.'})

        if self.progressbar is not None :
            temp.append(self.progressbar.l)
        if as_col :
            return [sg.Col(temp)]
        else :
            return temp
        # l = [sg.Col(temp)]
        # return l

    def eval(self, e, v):
        w = self.w()
        c = self.c()
        n = self.disp
        id = v[self.k]
        k0 = self.conftype
        g=self.g()
        d=self.d()

        if e == f'LOAD_{n}' and id != '':
            conf = loadConf(id, k0)
            self.tab.update(w, c, conf, id)
            if self.progressbar is not None :
                self.progressbar.reset(w)
            for kk, vv in self.sublists.items():
                vv.update(w, conf[kk])

        elif e == f'SAVE_{n}':
            conf = self.tab.get(w, v, c, as_entry=True)
            for kk, vv in self.sublists.items():
                conf[kk] = v[vv.k]
            id = self.save(conf)
            if id is not None :
                self.update(w, id)
        elif e == f'DELETE_{n}' and id != '':
            deleteConf(id, k0)
            self.update(w)
        elif e == f'RUN_{n}' and id != '':
            conf = self.tab.get(w, v, c, as_entry=False)
            for kk, vv in self.sublists.items():
                conf[kk] = expandConf(id=v[vv.k], conf_type=vv.conftype)
            d,g=self.tab.run(v,w,c,d,g, conf, id)
            self.set_d(d)
            self.set_g(g)
        elif e == f'EDIT_{n}':
            conf = self.tab.get(w, v, c, as_entry=False)
            new_conf = self.tab.edit(conf)
            self.tab.update(w, c, new_conf, id=None)
        elif self.collapsible is not None and e == self.collapsible.header_key :
            self.collapsible.update_header(w,id)

    def update(self, w, id='', all=False):
        w.Element(self.k).Update(values=self.confs, value=id, size=(self.width, self.Nconfs))
        if self.collapsible is not None :
            self.collapsible.update_header(w,id)
        if all:
            for i in range(5):
                k = f'{self.k0}{i}'
                if k in w.AllKeysDict.keys():
                    w[k].update(values=self.confs, value=id)

    def save(self, conf):
        return save_conf_window(conf, self.conftype, disp=self.disp)

        # for i in range(3):
        #     k = f'{self.conf_k}{i}'
        #     w.Element(k, silent_on_error=True).Update(values=list(loadConfDict(k).keys()),value=id)

    def get_next(self, k0):
        w = self.w()
        if w is None:
            idx = 0
        else:
            idx = int(np.min([i for i in range(5) if f'{k0}{i}' not in w.AllKeysDict.keys()]))
        return f'{k0}{idx}'

    def get_layout(self):
        return self.l

    def get_subdicts(self):
        if self.collapsible is not None :
            return self.collapsible.get_subdicts()
        else :
            return {}

    @property
    def confs(self):
        return list(loadConfDict(self.conftype).keys())

    @property
    def Nconfs(self):
        return len(self.confs)





class GuiTab:
    def __init__(self, name, gui, conftype=None):
        self.name = name
        self.gui = gui
        self.conftype = conftype
        self.selectionlists = {}
        # self.graph_list=None

    @property
    def graph_list(self):
        gs = self.gui.graph_lists
        n = self.name
        if n in list(gs.keys()):
            return gs[n]
        else:
            return None

    @property
    def canvas_k(self):
        g=self.graph_list
        return g.canvas_key if g is not None else None

    @property
    def graphlist_k(self):
        g = self.graph_list
        return g.list_key if g is not None else None

    @property
    def base_list(self):
        return self.selectionlists[self.conftype] if self.conftype is not None else None

    @property
    def base_dict(self):
        ds=self.gui.dicts
        n=self.name
        if n in list(ds.keys()) :
            return ds[n]
        else :
            return None

    def current_ID(self, v):
        l=self.base_list
        return v[l.k] if l is not None else None

    def current_conf(self, v):
        id=self.current_ID(v)
        return loadConf(id, self.conftype) if id is not None else None

    def build(self):
        return None, {}, {}, {}

    def eval0(self, e, v):
        for sl_name,sl in self.selectionlists.items():
            sl.eval(e, v)
        w = self.gui.window
        c = self.gui.collapsibles
        g = self.gui.graph_lists
        d = self.gui.dicts
        self.eval(e, v, w, c, d, g)

    def run(self, v, w,c, d, g, conf, id):
        pass
        # return d, g

    def eval(self, e, v, w, c, d, g):
        pass

    def get(self, w, v, c):
        return None

    def update(self, w, c, conf, id):
        pass

    def fork(self, func, kwargs):
        import os
        import signal
        import sys
        def handle_signal(signum, frame):
            print('Caught signal "%s"' % signum)
            if signum == signal.SIGTERM:
                print('SIGTERM. Exiting!')
                sys.exit(1)
            elif signum == signal.SIGHUP:
                print('SIGHUP')
            elif signum == signal.SIGUSR1:
                print('SIGUSR1 Calling wait()')
                pid, status = os.wait()
                print('PID was: %s.' % pid)

        print('Starting..')
        signal.signal(signal.SIGCHLD, handle_signal)
        signal.signal(signal.SIGHUP, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)
        signal.signal(signal.SIGUSR1, handle_signal)

        try:
            ff_pid = os.fork()
        except OSError as err:
            print('Unable to fork: %s' % err)
        if ff_pid > 0:
            # Parent.
            print('First fork.')
            print('Child PID: %d' % ff_pid)
        elif ff_pid == 0:
            res=func(**kwargs)
            # return res
            # sys.exit(0)




class IntroTab(GuiTab):
    # def __init__(self, **kwargs):
    #     super().__init__(**kwargs)

    def build(self):
        c = {'size': (80, 1),
             'pad': (20, 5),
             'justification': 'center'
             }

        filenames = os.listdir(paths.IntroSlideFolder)
        filenames.sort()

        b_list = [
            sg.B(image_filename=os.path.join(paths.IntroSlideFolder, f), image_subsample=3,
                 pad=(15, 70)) for f in filenames]
        l_title = sg.Col([[sg.T('', size=(5, 5))],
                          [sg.T('Larvaworld', font=("Cursive", 40, "italic"), **c)],
                          b_list,
                          [sg.T('Behavioral analysis and simulation platform', font=("Lobster", 15, "bold"), **c)],
                          [sg.T('for Drosophila larva', font=("Lobster", 15, "bold"), **c)]],
                         element_justification='center',
                         )

        l_intro = [[l_title]]

        return l_intro, {}, {}, {}


class VideoTab(GuiTab):
    # def __init__(self, **kwargs):
    #     super().__init__(**kwargs)

    def build(self):
        link_pref = "http://computational-systems-neuroscience.de/wp-content/uploads/2021/04/"
        files = [f for f in os.listdir(paths.VideoSlideFolder) if f.endswith('png')]
        b_list = [ClickableImage(name=f.split(".")[0], link=f'{link_pref}{f.split(".")[0]}.mp4',
                                 image_filename=os.path.join(paths.VideoSlideFolder, f),
                                 image_subsample=5, pad=(25, 40)) for f in files]

        n = 3
        b_list = [b_list[i * n:(i + 1) * n] for i in range((len(b_list) + n - 1) // n)]
        l = [[sg.Col(b_list, vertical_scroll_only=True, scrollable=True, size=window_size)]]

        return l, {}, {}, {}

    def eval(self, e, v, w, c, d, g):
        if 'ClickableImage' in e:
            w[e].eval()

        # return d, g

class TutorialTab(GuiTab):

    def build(self):
        c2 = {'size': (80, 1),
              'pad': (20, 5),
              'justification': 'left'
              }
        c1 = {'size': (70, 1),
              'pad': (10, 35)
              }

        col1 = [[sg.B(image_filename=os.path.join(paths.TutorialSlideFolder, '1.png'), key='BUTTON 1',
                      image_subsample=2, image_size=(70, 70), pad=(20, 10))],
                [sg.B(image_filename=os.path.join(paths.TutorialSlideFolder, '2.png'), key='BUTTON 2',
                      image_subsample=3, image_size=(70, 70), pad=(20, 10))],
                [sg.B(image_filename=os.path.join(paths.TutorialSlideFolder, '3.png'), key='BUTTON 3',
                      image_subsample=3, image_size=(70, 70), pad=(20, 10))],
                [sg.B(image_filename=os.path.join(paths.TutorialSlideFolder, '4.png'), key='BUTTON 4',
                      image_subsample=2, image_size=(70, 70), pad=(20, 10))]]
        col2 = [
            [sg.T('1. Run and analyze a single run experiment with selected larva model and environment',
                  font='Lobster 12', **c1)],
            [sg.T('2. Run and analyze a batch run experiment with selected larva model and environment',
                  font='Lobster 12', **c1)],
            [sg.T('3. Create your own experimental environment', font='Lobster 12', **c1)],
            [sg.T('4. Change settings and shortcuts', font='Lobster 12', **c1)],
        ]
        l_tut = [
            [sg.T('')],
            [sg.T('Tutorials', font=("Cursive", 40, "italic"), **c2)],
            [sg.T('Choose between following video tutorials:', font=("Lobster", 15, "bold"), **c2)],
            [sg.T('')],
            [sg.Column(col1), sg.Column(col2)],
            [sg.T('')],
            [sg.T('Further information:', font=("Lobster", 15, "bold"), **c2)],
            [sg.T('')],
            [sg.B(image_filename=os.path.join(paths.TutorialSlideFolder, 'Glossary.png'), key='GLOSSARY', image_subsample=3,
                  image_size=(70, 70), pad=(25, 10)),
             sg.T('Here you find a glossary explaining all variables in Larvaworld', font='Lobster 12', **c1)]

        ]

        return l_tut, {}, {}, {}

    def eval(self, event, values, window, collapsibles, dicts, graph_lists):
        if 'BUTTON 1' in event:
            webbrowser.open_new(paths.TutorialSlideFolder + "/1.mp4")
        if 'BUTTON 2' in event:
            webbrowser.open_new(paths.TutorialSlideFolder + "/2.mp4")
        if 'BUTTON 3' in event:
            webbrowser.open_new(paths.TutorialSlideFolder + "/3.mp4")
        if 'BUTTON 4' in event:
            webbrowser.open_new(paths.TutorialSlideFolder + "/4.mp4")
        if 'GLOSSARY' in event:
            webbrowser.open_new(paths.TutorialSlideFolder + "/Glossary.pdf")
        return dicts, graph_lists


if __name__ == "__main__":
    pass
    # sg.theme('LightGreen')
    # n = 'intro'
    # l, c, g, d = build_intro_tab()
    # w = sg.Window(f'{n} gui', l, size=(1800, 1200), **w_kws, location=(300, 100))
    #
    # while True:
    #     e, v = w.read()
    #     if e in (None, 'Exit'):
    #         break
    #     default_run_window(w, e, v, c, g)
    #     d, g = eval_intro_tab(e, v, w, collapsibles=c, dicts=d, graph_lists=g)
    # w.close()
