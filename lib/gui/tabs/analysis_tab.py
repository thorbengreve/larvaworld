from lib.gui.aux.elements import ButtonGraphList, DataList
from lib.gui.aux.functions import col_size, col_kws, gui_col
from lib.gui.tabs.tab import GuiTab
from lib.anal.plotting import graph_dict



class AnalysisTab(GuiTab):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        col_frac = 0.25
        self.canvas_size = col_size(x_frac=1 - 2 * col_frac, y_frac=0.8)
        self.canvas_col_size = col_size(x_frac=1 - 2 * col_frac)
        self.col_size = col_size(col_frac)
        self.data_key = 'Datasets'

    # def change_dataset_id(self,w, v, dic, k0):
    #     # k0 = 'DATASET_IDS'
    #     v0 = v[k0]
    #     # data=self.base_dict
    #     if len(v0) > 0:
    #         old_id = v0[0]
    #         l = [[sg.Text('Enter new dataset ID', size=(20, 1)), sg.In(k='NEW_ID', size=(10, 1))],
    #              [sg.Button('Store'), sg.Ok(), sg.Cancel()]]
    #         e1, v1 = sg.Window('Change dataset ID', l).read(close=True)
    #         new_id=v1['NEW_ID']
    #         if e1 == 'Ok':
    #             dic[new_id] = dic.pop(old_id)
    #             w.Element(k0).Update(values=list(dic.keys()))
    #         elif e1 == 'Store':
    #             d = dic[old_id]
    #             d.set_id(new_id)
    #             dic[new_id] = dic.pop(old_id)
    #             w.Element(k0).Update(values=list(dic.keys()))
    # return data

    def build(self):
        d = {self.name: {}}
        dl1 = DataList(name=self.data_key, tab=self, dict=d[self.name],
                      buttons=['replay', 'add_ref', 'select_all', 'remove', 'change_ID', 'browse'],
                       aux_cols=['N', 'duration', 'quality'], size=(30,5)
                       )
        g1 = ButtonGraphList(name=self.name, tab=self, fig_dict=graph_dict, canvas_size=self.canvas_size)


        l = [[
            gui_col([dl1], 0.25),
            gui_col([g1.canvas], 0.55),
            gui_col([g1], 0.2),

        ]]
        g = {g1.name: g1}
        return l, {}, g, d

    def eval(self, e, v, w, c, d, g):
        return d, g


if __name__ == "__main__":
    from lib.gui.tabs.gui import LarvaworldGui

    larvaworld_gui = LarvaworldGui(tabs=['analysis'])
    larvaworld_gui.run()
