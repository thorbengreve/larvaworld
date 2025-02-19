import itertools
import random

import numpy as np

from lib.aux.dictsNlists import flatten_tuple
from lib.model.modules.basic import Effector


class RLmemory(Effector):
    def __init__(self, brain, gain_space, gain, Delta=0.1, state_spacePerSide=0, update_dt=2, train_dur=30, alpha=0.05,
                 gamma=0.6, epsilon=0.15, state_specific_best=True, **kwargs):
        super().__init__(**kwargs)
        self.state_specific_best=state_specific_best
        self.brain = brain
        self.effector = True
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon
        self.Delta = Delta
        self.gain_space = gain_space
        self.gain = gain
        self.best_gain = gain
        self.gain_ids = list(gain.keys())
        self.Ngains = len(self.gain_ids)
        self.state_spacePerSide = state_spacePerSide
        self.state_space = np.array(
            [ii for ii in itertools.product(range(2*self.state_spacePerSide + 1), repeat=self.Ngains)])
        self.actions = [ii for ii in itertools.product(self.gain_space, repeat=self.Ngains)]
        self.q_table = np.zeros((self.state_space.shape[0], len(self.actions)))

        self.train_dur = train_dur
        # self.update_dt = update_dt
        self.lastAction = 0
        self.lastState = 0
        self.Niters = int(update_dt * 60 / self.dt)
        self.iterator = self.Niters
        self.table = False
        self.rewardSum = 0
        # print(self.state_space[13])
        # raise

    def state_collapse(self, dx):
        k = self.state_spacePerSide
        if len(dx) > 0:
            dx = [dx]
        stateV = []
        for index in range(len(dx)):
            for i in dx[index]:

                dxI = dx[index][i]
                stateIntermitt = np.zeros(k)
                for ii in range(k):
                    stateIntermitt[ii] = np.abs(dxI) > (ii + 1) * self.Delta
            stateV.append(int(np.sign(dxI) * (np.sum(stateIntermitt)) + k))
        state = np.where((self.state_space == stateV).all(axis=1))[0][0]
        return state

    def step(self, dx, reward):
        if self.table == False:
            temp = self.brain.agent.model.table_collector
            if temp is not None:
                self.table = temp.tables['best_gains'] if 'best_gains' in list(temp.tables.keys()) else None

        self.count_time()
        if self.effector and self.total_t > self.train_dur * 60:
            self.effector = False
            print(f'Best gain : {self.best_gain}')
            print(np.array(self.q_table*100).astype(int))
        if self.effector:
            self.add_reward(reward)
            if self.condition(dx):
                state = self.state_collapse(dx)
                actionID=self.select_action(state)
                self.update_q_table(actionID, state,  self.rewardSum)
                self.best_gain = self.get_best_combo()

                if self.table:
                    for col in list(self.table.keys()):
                        try:
                            self.table[col].append(getattr(self.brain.agent, col))
                        except:
                            self.table[col].append(np.nan)
                self.rewardSum = 0
                self.iterator = 0
            self.iterator += 1

            return self.gain
        else:
            if not self.state_specific_best :
                return self.best_gain
            else :
                state = self.state_collapse(dx)
                actionID = np.argmax(self.q_table[state])
                action = self.actions[actionID]
                for ii, id in enumerate(self.gain_ids):
                    self.gain[id] = action[ii]
                # print(self.gain, self.best_gain, self.q_table)
                return self.gain

    def add_reward(self, reward):
        self.rewardSum += int(reward) - 0.01

    def get_best_combo(self):
        return dict(zip(self.gain_ids, self.actions[np.argmax(np.mean(self.q_table, axis=0))]))

    def condition(self,dx):
        return self.iterator >= self.Niters

    def update_q_table(self, actionID, state, reward):
        old_value = self.q_table[self.lastState, self.lastAction]
        new_value = (1 - self.alpha) * old_value + self.alpha * (reward + self.gamma * np.max(self.q_table[state]))
        # print(old_value, new_value, self.rewardSum, next_max)
        self.q_table[self.lastState, self.lastAction] = new_value
        self.lastAction = actionID
        self.lastState = state

    def select_action(self, state):
        if random.uniform(0, 1) < self.epsilon:
            actionID = random.randrange(len(self.actions))
        else:
            actionID = np.argmax(self.q_table[state])  # Exploit learned values
        # print(np.array(self.q_table*100).astype(int))
        for ii, id in enumerate(self.gain_ids):
            self.gain[id] = self.actions[actionID][ii]
        return actionID

    # @property
    # def cum_reward(self):
    #     return self.rewardSum


class RLOlfMemory(RLmemory):
    def __init__(self, mode='olf', **kwargs):
        super().__init__(**kwargs)

    @property
    def first_odor_best_gain(self):
        return list(self.best_gain.values())[0]

    @property
    def second_odor_best_gain(self):
        return list(self.best_gain.values())[1]




class RLTouchMemory(RLmemory):
    def __init__(self, mode='touch', **kwargs):
        # gain = {s: 0.0 for s in brain.agent.get_sensors()}
        super().__init__(**kwargs)


    def condition(self,dx):
        if 1 in dx.values() or -1 in dx.values():
            if 1 in dx.values():
                self.rewardSum = 1/self.iterator
            elif -1 in dx.values():
                self.rewardSum = self.iterator
            return True
        else :
            return False



