import os
import PySimpleGUI as sg

from lib.gui.aux.buttons import ClickableImage
from lib.gui.aux.functions import window_size
from lib.gui.tabs.tab import GuiTab
from lib.conf.base.paths import path


class VideoTab(GuiTab):

    def build(self):
        link0 = "http://computational-systems-neuroscience.de/wp-content/uploads/2021/04/"
        f0 = path('videos')
        fs = [f for f in os.listdir(f0) if f.endswith('png')]
        ns=[f.split(".")[0] for f in fs]
        ffs=[os.path.join(f0, f) for f in fs]
        bl = [ClickableImage(name=n, link=f'{link0}{n}.mp4',image_filename=ff,
                             image_subsample=5, pad=(25, 40)) for ff,n in zip(ffs, ns)]

        n = 3
        bl = [bl[i * n:(i + 1) * n] for i in range((len(bl) + n - 1) // n)]
        l = [[sg.Col(bl, vertical_scroll_only=True, scrollable=True, size=window_size)]]

        return l, {}, {}, {}

    def eval(self, e, v, w, c, d, g):
        if 'ClickableImage' in e:
            w[e].eval()

if __name__ == "__main__":
    from lib.gui.tabs.gui import LarvaworldGui

    larvaworld_gui = LarvaworldGui(tabs=['videos'])
    larvaworld_gui.run()
