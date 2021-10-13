import subprocess
import sys
import argparse

from lib.sim.batch.batch import _batch_run

sys.path.insert(0, '..')
from lib.sim.single.analysis import sim_analysis
from lib.stor.larva_dataset import LarvaDataset
from lib.sim.batch.functions import retrieve_results
from lib.conf.base import paths
import lib.aux.dictsNlists

class Exec:
    def __init__(self, mode, conf, run_externally=True, progressbar=None, w_progressbar=None, **kwargs):
        self.run_externally = run_externally
        self.mode = mode
        self.conf = conf
        self.progressbar = progressbar
        self.w_progressbar = w_progressbar
        self.type = self.conf['batch_type'] if mode == 'batch' else self.conf['experiment']
        self.done = False

    def terminate(self):
        if self.process is not None:
            self.process.terminate()

    def run(self, **kwargs):
        f0, f1 = paths.path('EXECONF'), paths.path('EXEC')
        if self.run_externally:
            lib.aux.dictsNlists.save_dict(self.conf, f0)
            self.process = subprocess.Popen(['python', f1, self.mode, f0], **kwargs)
        else:
            res = self.exec_run()
            self.results = self.retrieve(res)
            self.done = True

    def check(self):
        if not self.done:
            if self.run_externally:
                if self.process.poll() is not None:
                    self.results = self.retrieve()
                    self.done = True
                    return True
            return False
        else:
            return True

    def retrieve(self, res=None):
        if self.mode == 'batch':
            if res is None and self.run_externally:
                args = {'batch_type': self.type, 'batch_id': self.conf['batch_id']}
                res = retrieve_results(**args)
            return res
        elif self.mode == 'sim':
            if res is None and self.run_externally:
                sim_id = self.conf['sim_params']['sim_ID']
                dir = f"{paths.path('SIM')}/{self.conf['sim_params']['path']}/{sim_id}"
                res = [LarvaDataset(dir)]
            if res is not None:
                fig_dict, results = sim_analysis(res, self.type)
                entry = {res[0].id: {'dataset': res[0], 'figs': fig_dict}}
            else:
                entry, fig_dict = None, None
            return entry, fig_dict

    def exec_run(self):
        from lib.sim.single.single_run import SingleRun
        from lib.sim.batch.batch import batch_run
        from lib.sim.batch.functions import prepare_batch
        if self.mode == 'sim':
            self.process = SingleRun(**self.conf, progress_bar=self.w_progressbar)
            res = self.process.run()
        elif self.mode == 'batch':
            self.process = None
            batch_kwargs = prepare_batch(self.conf)
            res = _batch_run(**batch_kwargs)
        return res


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run given batch-run/simulation")
    parser.add_argument('mode', choices=['sim', 'batch'],
                        help='Whether we are running a single simulation or a batch-run')
    parser.add_argument('conf_file', type=str, help='The configuration file of the batch-run/simulation')
    args = parser.parse_args()
    conf = lib.aux.dictsNlists.load_dict(args.conf_file)
    k = Exec(args.mode, conf)
    k.exec_run()

