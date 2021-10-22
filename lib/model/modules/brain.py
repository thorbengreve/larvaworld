import numpy as np


from lib.model.modules.basic import Oscillator_coupling
from lib.model.modules.crawler import Crawler
from lib.model.modules.feeder import Feeder
from lib.model.modules.intermitter import Intermitter
from lib.model.modules.memory import RLOlfMemory, RLTouchMemory
from lib.model.modules.sensor import Olfactor, Toucher, WindSensor
from lib.model.modules.turner import Turner


class Brain():
    def __init__(self, agent, modules, conf):
        self.agent = agent
        self.modules = modules
        self.conf = conf
        self.olfactory_activation = 0
        self.touch_activation = 0
        self.wind_activation = 0
        self.crawler, self.turner, self.feeder, self.intermitter, self.olfactor, self.memory, self.touch_memory = [None] * 7

        dt = self.agent.model.dt
        m = self.modules
        c = self.conf
        self.windsensor = WindSensor(brain=self, dt=dt, gain_dict={'windsensor': 1.0},**c['windsensor_params'])
        if m['olfactor']:
            self.olfactor = Olfactor(brain=self, dt=dt, **c['olfactor_params'])

        # self.crawler, self.turner, self.feeder, self.olfactor, self.intermitter = None, None, None, None, None

    def sense_odors(self, pos):
        cons = {}
        for id, layer in self.agent.model.odor_layers.items():
            v = layer.get_value(pos)
            cons[id] = v + np.random.normal(scale=v * self.olfactor.noise)
        # print(self.agent.unique_id, cons)
        return cons

    def sense_food(self):
        a = self.agent
        sensors = a.get_sensors()
        return {s: int(a.detect_food(a.get_sensor_position(s)) is not None) for s in sensors}

    def sense_wind(self):
        from lib.aux.ang_aux import angle_dif
        a=self.agent
        w=a.model.windscape
        if w is None :
            v=0.0
        else :
            wo, wv=w['wind_direction'], w['wind_speed']
            o=np.rad2deg(a.head.get_orientation())
            v=np.abs(angle_dif(o,wo))/180*wv
        # sensors = a.get_sensors()
        return {'windsensor': v}
        # return {s: int(a.detect_wind(a.get_sensor_position(s)) is not None) for s in sensors}

class DefaultBrain(Brain):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        dt = self.agent.model.dt
        m = self.modules
        c = self.conf



        if m['crawler']:
            self.crawler = Crawler(dt=dt, **c['crawler_params'])
        if m['turner']:
            self.turner = Turner(dt=dt, **c['turner_params'])
        if m['feeder']:
            self.feeder = Feeder(dt=dt, model=self.agent.model, **c['feeder_params'])
        self.coupling = Oscillator_coupling(brain=self, **c['interference_params']) if m[
            'interference'] else Oscillator_coupling(brain=self)
        if m['intermitter']:
            self.intermitter = Intermitter(brain=self, dt=dt, **c['intermitter_params'])
        # if m['olfactor']:
        #     self.olfactor = Olfactor(brain=self, dt=dt, **c['olfactor_params'])
        if m['memory'] and c['memory_params']['mode'] == 'olf':
            self.memory = RLOlfMemory(brain=self, dt=dt, gain=self.olfactor.gain, **c['memory_params'])
        t = self.toucher = Toucher(brain=self, dt=dt, gain_dict={s: 0.0 for s in self.agent.get_sensors()})
        if m['memory'] and c['memory_params']['mode'] == 'touch':
            self.touch_memory = RLTouchMemory(brain=self, dt=dt, gain=t.gain, **c['memory_params'])

    def run(self, pos):
        lin, ang, feed_motion = 0, 0, False
        reward = self.agent.food_detected is not None
        if self.intermitter:
            self.intermitter.step()
        if self.feeder:
            feed_motion = self.feeder.step()
        if self.memory:
            self.olfactor.gain = self.memory.step(self.olfactor.get_dX(), reward)
        if self.crawler:
            lin = self.crawler.step(self.agent.sim_length)
        if self.olfactor:
            self.olfactory_activation = self.olfactor.step(self.sense_odors(pos))
        if self.touch_memory:
            self.toucher.gain = self.touch_memory.step(self.toucher.get_dX(), reward)
        if self.toucher:
            self.touch_activation = self.toucher.step(self.sense_food())
        if self.windsensor:
            self.wind_activation = self.windsensor.step(self.sense_wind())
        if self.turner:
            ang = self.turner.step(inhibited=self.coupling.step(),
                                   attenuation=self.coupling.attenuation,
                                   A_in=self.olfactory_activation + self.touch_activation)

        return lin, ang, feed_motion
