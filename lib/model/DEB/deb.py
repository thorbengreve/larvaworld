'''
DEB pipeline from literature
'''
import json
import os
import numpy as np
from scipy.integrate import quad, solve_ivp

from lib.model.DEB.deb_aux import beta0, simplex
from lib.conf.base.dtypes import null_dict, substrate_dict
from lib.conf.stored.conf import loadConf
import lib.aux.naming as nam
from lib.model.DEB.gut import Gut
from lib.conf.base import paths

'''
Standard culture medium
50g Baker’s yeast; 100g sucrose; 16g agar; 0.1gKPO4; 8gKNaC4H4O6·4H2O; 0.5gNaCl; 0.5gMgCl2; and 0.5gFe2(SO4)3 per liter of tap water. 
Larvae were reared from egg-hatch to mid- third-instar (96±2h post-hatch) in 25°C at densities of 100 larvae per 35ml of medium in 100mm⫻15mm Petri dishes


[1] K. R. Kaun, M. Chakaborty-Chatterjee, and M. B. Sokolowski, “Natural variation in plasticity of glucose homeostasis and food intake,” J. Exp. Biol., vol. 211, no. 19, pp. 3160–3166, 2008.

--> 0.35 ml medium per larva for the 4 days
'''
class Substrate:
    def __init__(self, type='standard', quality=1.0):
        self.d_water = 1
        self.d_yeast_drop = 0.125 #g/cm**3 https://www.google.com/url?sa=t&rct=j&q=&esrc=s&source=web&cd=&ved=2ahUKEwi3iaeqipLxAhVPyYUKHTmpCqMQFjAAegQIAxAD&url=https%3A%2F%2Fwww.mdpi.com%2F2077-0375%2F11%2F3%2F182%2Fpdf&usg=AOvVaw1qDlMHxBPu73W8B1vZWn76
        self.V_drop = 0.05 # cm**3
        self.quality = quality # cm**3
        # Molecular weights (g/mol)
        self.w_dict={
            'glucose' : 180.18,
            'dextrose' : 198.17,
            'saccharose' : 342.30,
            'yeast' : 274.3, # Baker's yeast
            'agar' : 336.33,
            'cornmeal' : 359.33,
            'water' : 18.01528,
        }
        self.d_dict= substrate_dict[type]
        self.d = self.d_water + sum(list(self.d_dict.values()))
        self.C=self.get_C()
        self.X=self.get_X()
        self.X_ratio=self.get_X_ratio()

    def get_X(self, quality=None, compounds = ['glucose', 'dextrose', 'yeast', 'cornmeal', 'saccharose'], return_sum=True):
        if quality is None :
            quality=self.quality
        Xs=[self.d_dict[c]/self.w_dict[c]*quality for c in compounds]
        return sum(Xs) if return_sum else Xs

    def get_mol(self, V, **kwargs):
        return self.get_X(**kwargs)*V

    def get_f(self, K,**kwargs):
        X=self.get_X(**kwargs)
        return X/(K+X)

    def get_C(self, quality=None):
        C=self.d_water / self.w_dict['water'] + self.get_X(quality, compounds=list(self.d_dict.keys()))
        return C

    def get_X_ratio(self, quality=None):
        X=self.get_X(quality = quality)
        C=self.get_C(quality = quality)
        return X/C


class DEB:
    def __init__(self, id='DEB model', species='default', steps_per_day=24*60, cv=0, T=298.15, eb=1.0, substrate=None,
                 aging=False, print_output=False, starvation_strategy=False, assimilation_mode='deb', save_dict=True, save_to=None,
                 V_bite=0.001, absorption=None, base_hunger=0.5, hunger_gain=0,hunger_as_EEB=False, hours_as_larva=0, simulation=True, use_gut=True,
                 intermitter=None):

        # Drosophila model by default
        self.species=species
        with open(paths.path('DEB_MODS')[species]) as tfp:
            self.species_dict = json.load(tfp)
        self.__dict__.update(self.species_dict)

        # DEB methods enabled
        self.starvation_strategy = starvation_strategy
        self.aging = aging

        # Hunger drive parameters
        self.hunger_gain = hunger_gain
        self.hunger_as_EEB = hunger_as_EEB
        self.intermitter = intermitter

        if self.hunger_as_EEB and self.intermitter is not None:
            base_hunger=self.intermitter.base_EEB
        self.base_hunger = base_hunger
        self.T = T
        self.L0 = 10 ** -10
        self.hours_as_larva = hours_as_larva
        self.sim_start = hours_as_larva
        self.id = id
        self.cv = cv
        self.eb = eb

        self.save_to=save_to
        self.print_output = print_output
        self.simulation = simulation
        self.assimilation_mode = assimilation_mode
        self.absorption = absorption

        # if y_E_X is not None :
        #     self.y_E_X = y_E_X
        self.epochs = []
        self.epoch_fs = []
        self.epoch_qs = []
        self.dict_file = None

        # Larva stage flags
        self.stage = 'embryo'
        self.alive = True

        # Stage duration parameters
        self.age = 0
        self.birth_time_in_hours = np.nan
        self.pupation_time_in_hours = np.nan
        self.emergence_time_in_hours = np.nan
        self.death_time_in_hours = np.nan
        self.derived_pars()

        self.E = self.E0
        self.E_H = 0
        self.E_R = 0
        self.V = self.L0 ** 3
        self.deb_p_A = 0
        self.sim_p_A = 0
        self.gut_p_A = 0
        if substrate is None :
            substrate=null_dict('substrate')
        if type(substrate)==dict :
            self.substrate = Substrate(type=substrate['type'], quality=substrate['quality'])
        else :
            self.substrate=substrate
        self.base_f = self.substrate.get_f(K=self.K)
        self.f = self.base_f
        self.V_bite = V_bite

        self.steps_per_day = steps_per_day
        self.dt = 1 / steps_per_day

        self.gut = Gut(deb=self, V_bite=self.V_bite, save_dict=save_dict) if use_gut else None
        self.set_steps_per_day(steps_per_day)
        self.run_embryo_stage()
        self.predict_larva_stage(f=self.base_f)

        self.dict = self.init_dict() if save_dict else None

    @ property
    def Lw(self):
        return self.L / self.del_M

    @property
    def L(self):
        return self.V ** (1 / 3)

    def scale_time(self):
        dt = self.dt * self.T_factor
        self.F_m_dt = self.F_m * dt
        self.v_dt = self.v * dt
        self.p_M_dt = self.p_M * dt
        self.p_T_dt = self.p_T * dt if self.p_T != 0.0 else 0.0
        self.k_J_dt = self.k_J * dt
        self.h_a_dt = self.h_a * dt ** 2

        self.p_Am_dt = self.p_Am * dt
        self.p_Amm_dt = self.p_Amm * dt
        self.J_X_Amm_dt = self.J_X_Amm * dt
        self.J_E_Amm_dt = self.J_E_Amm * dt
        self.k_E_dt = self.k_E * dt

        if self.gut is not None :
            self.gut.get_Nticks(dt)
            self.J_X_A_array = np.ones(self.gut.gut_Nticks)*self.J_X_A

    def set_steps_per_day(self, steps_per_day):
        self.steps_per_day = steps_per_day
        self.dt = 1 / steps_per_day
        # print(steps_per_day/24/60)
        # raise
        self.scale_time()

    def derived_pars(self):
        kap = self.kap
        v = self.v
        p_Am = self.p_Am = self.z * self.p_M / kap
        self.J_E_Am = p_Am/self.mu_E
        self.J_X_Am = self.J_E_Am / self.y_E_X
        self.p_Xm=p_Am/self.kap_X
        self.K=self.J_X_Am/self.F_m

        self.E_M = p_Am / v
        self.E_V = self.mu_V * self.d_V / self.w_V
        k_M = self.k_M = self.p_M / self.E_G
        g = self.g = self.E_G / (kap * self.E_M)
        ii = g ** 2 * k_M ** 3 / ((1 - kap) * v ** 2)
        self.k = self.k_J / k_M
        self.U_Hb = self.E_Hb / p_Am
        self.vHb = self.U_Hb * ii
        self.U_He = self.E_He / p_Am
        self.vHe = self.U_He * ii
        self.Lm = v / (g * k_M)
        self.T_factor = np.exp(self.T_A / self.T_ref - self.T_A / self.T);  # Arrhenius factor

        lb = self.lb = self.get_length_at_birth(eb=self.eb)
        Lb = self.Lb = lb * self.Lm
        self.Lwb = Lb / self.del_M
        self.tau_b = self.get_tau_b(eb=self.eb)
        self.t_b = self.tau_b / k_M / self.T_factor

        self.k_E = v / Lb

        # For the larva the volume specific max assimilation rate p_Amm is used instead of the surface-specific p_Am
        self.p_Amm = p_Am / Lb
        self.J_X_Amm = self.J_X_Am / Lb
        self.J_E_Amm = self.J_E_Am / Lb
        self.F_mm = self.F_m / Lb



        # DEB textbook p.91
        # self.y_VE = (self.d_V / self.w_V)*self.mu_E/E_G
        # self.J_E_Am = self.p_Am/self.mu_E

        self.uE0 = self.get_initial_reserve(eb=self.eb)
        self.U0 = self.uE0 * v ** 2 / g ** 2 / k_M ** 3
        self.E0 = self.U0 * p_Am
        self.Ww0 = self.E0 * self.w_E / self.mu_E  # g, initial wet weight

        self.v_Rm = (1 + lb / g) / (1 - lb)  # scaled max reprod buffer density
        self.v_Rj = self.s_j * self.v_Rm  # scaled reprod buffer density at pupation

        if self.print_output:
            print('------------------Egg------------------')
            print(f'Reserve energy  (mJ) :       {int(1000 * self.E0)}')
            print(f'Wet weight      (mg) :       {np.round(1000 * self.Ww0, 5)}')

    def hex_model(self):
        # p.161    [1] S. a. L. M. Kooijman, “Comments on Dynamic Energy Budget theory,” Changes, 2010.
        # For the larva stage
        # self.r = self.g * self.k_M * (self.e/self.lb -1)/(self.e+self.g) # growth rate at  constant food where e=f
        # self.k_E = self.v/self.Lb # Reserve turnover
        pass

    def get_tau_b(self, eb=1.0):
        def get_tb(x, ab, xb):
            return x ** (-2 / 3) / (1 - x) / (ab - beta0(x, xb))

        g = self.g
        xb = g / (eb + g)
        ab = 3 * g * xb ** (1 / 3) / self.lb
        return 3 * quad(func=get_tb, a=1e-15, b=xb, args=(ab, xb))[0]

    def get_length_at_birth(self, eb=1.0):
        g = self.g
        k = self.k
        vHb = self.vHb

        n = 1000 + round(1000 * max(0, k - 1))
        xb = g / (g + eb)
        xb3 = xb ** (1 / 3)
        x = np.linspace(10 ** -5, xb, n)
        dx = xb / n
        x3 = x ** (1 / 3)

        b = beta0(x, xb) / (3 * g)

        t0 = xb * g * vHb
        i = 0
        norm = 1
        ni = 100

        lb = vHb ** (1 / 3)

        while i < ni and norm > 1e-18:
            l = x3 / (xb3 / lb - b)
            s = (k - x) / (1 - x) * l / g / x
            vv = np.exp(- dx * np.cumsum(s))
            vb = vv[- 1]
            r = (g + l)
            rv = r / vv
            t = t0 / lb ** 3 / vb - dx * np.sum(rv)
            dl = xb3 / lb ** 2 * l ** 2. / x3
            dlnv = np.exp(- dx * np.cumsum(s * dl / l))
            dlnvb = dlnv[- 1]
            dt = - t0 / lb ** 3 / vb * (3 / lb + dlnvb) - dx * np.sum((dl / r - dlnv) * rv)
            lb -= t / dt  # Newton Raphson step
            norm = t ** 2
            i += 1
        return lb

    def get_initial_reserve(self, eb=1.0):
        g = self.g
        xb = g / (g + eb)
        return np.real((3 * g / (3 * g * xb ** (1 / 3) / self.lb - beta0(0, xb))) ** 3)

    def predict_larva_stage(self, f=1.0):
        g = self.g
        lb = self.lb
        c1 = f / g * (g + lb) / (f - lb)
        c2 = self.k * self.vHb / lb ** 3
        self.rho_j = (f / lb - 1) / (f / g + 1)  # scaled specific growth rate of larva

        def get_tj(tau_j):
            ert = np.exp(- tau_j * self.rho_j)
            return np.abs(self.v_Rj - c1 * (1 - ert) + c2 * tau_j * ert)

        self.tau_j = simplex(get_tj, 1)
        self.lj = lb * np.exp(self.tau_j * self.rho_j / 3)
        self.t_j = self.tau_j / self.k_M / self.T_factor
        self.Lj = self.lj * self.Lm
        self.Lwj = self.Lj / self.del_M
        self.E_Rm = self.v_Rm * (1 - self.kap) * g * self.E_M * self.Lj ** 3
        self.E_Rj = self.E_Rm * self.s_j
        self.E_eggs = self.E_Rm * self.kap_R

    def predict_pupa_stage(self):
        g = self.g
        k_M = self.k_M

        def emergence(t, luEvH, terminal=True, direction=0):
            return self.vHe - luEvH[2]

        def get_te(t, luEvH):
            l = luEvH[0]
            u_E = max(1e-6, luEvH[1])
            ii = u_E + l ** 3
            dl = (g * u_E - l ** 4) / ii / 3
            du_E = - u_E * l ** 2 * (g + l) / ii
            dv_H = - du_E - self.k * luEvH[2]
            return [dl, du_E, dv_H]  # pack output

        sol = solve_ivp(fun=get_te, t_span=(0, 1000), y0=[0, self.uEj, 0], events=emergence)
        self.tau_e = sol.t_events[0][0]
        self.le, self.uEe = sol.y_events[0][0][:2]
        self.t_e = self.tau_e / k_M / self.T_factor
        self.Le = self.le * self.Lm
        self.Lwe = self.Le / self.del_M
        self.Ue = self.uEe * self.v ** 2 / g ** 2 / k_M ** 3
        self.Ee = self.Ue * self.p_Am
        self.Wwe = self.compute_Ww(V=self.Le ** 3, E=self.Ee + self.E_Rj)  # g, wet weight at emergence

        self.V = self.Le ** 3
        self.E = self.Ee
        self.E_H = self.E_He
        self.update()

        self.emergence_time_in_hours = self.pupation_time_in_hours + np.round(self.t_e * 24, 1)
        self.stage = 'imago'
        self.age = self.t_e
        if self.print_output:
            print('-------------Pupa stage-------------')
            print(f'Duration         (d) :      {np.round(self.t_e, 3)}')
            print('-------------Emergence--------------')
            print(f'Wet weight      (mg) :      {np.round(self.Wwe * 1000, 5)}')
            print(f'Physical length (mm) :      {np.round(self.Lwe * 10, 3)}')

    def predict_imago_stage(self, f=1.0):
        # if np.abs(self.sG) < 1e-10:
        #     self.sG = 1e-10
        # self.uh_a =self.h_a/ self.k_M ** 2 # scaled Weibull aging coefficient
        self.lT = self.p_T/(self.p_M*self.Lm)# scaled heating length {p_T}/[p_M]Lm
        self.li = f - self.lT;
        # self.hW3 = self.ha * f * self.g/ 6/ self.li
        # self.hW = self.hW3**(1/3) # scaled Weibull aging rate
        # self.hG = self.sG * f * self.g * self.li**2
        # self.hG3 = self.hG**3;     # scaled Gompertz aging rate
        # self.tG = self.hG/ self.hW
        # self.tG3 = self.hG3/ self.hW3 # scaled Gompertz aging rate
        # # self.tau_m = sol.t_events[0][0]
        # # self.lm, self.uEm=sol.y_events[0][0][:2]
        # self.t_m = self.tau_m / self.k_M / self.T_factor
        self.Li = self.li * self.Lm
        self.Lwi = self.Li / self.del_M
        self.Ui = self.uEi * self.v ** 2 / self.g ** 2 / self.k_M ** 3
        self.Ei = self.Ui * self.p_Am
        self.Wwi = self.compute_Ww(V=self.Li ** 3, E=self.Ei + self.E_Rj)  # g, imago wet weight
        # self.age = self.t_m

        self.V = self.Li ** 3
        self.E = self.Ei

        if self.print_output:
            print('-------------Imago stage-------------')
            print(f'Duration         (d) :      {np.round(self.t_i_cor, 3)}')
            print('---------------Emergence---------------')
            print(f'Wet weight      (mg) :      {np.round(self.Wwi * 1000, 5)}')
            print(f'Physical length (mm) :      {np.round(self.Lwi * 10, 3)}')

    def run_embryo_stage(self, dt=None):
        if dt is None:
            dt = self.dt

        kap = self.kap
        E_G = self.E_G

        t = 0

        while self.E_H < self.E_Hb:
            p_S = self.p_M_dt * self.V + self.p_T_dt * self.V ** (
                    2 / 3)  # This is in e/t and below needs to be volume-specific
            p_C = self.E * (E_G * self.v_dt / self.V ** (1 / 3) + p_S / self.V) / (kap * self.E / self.V + E_G)
            p_G = kap * p_C - p_S
            p_J = self.k_J_dt * self.E_H
            p_R = (1 - kap) * p_C - p_J

            self.E -= p_C
            self.V += p_G / E_G
            self.E_H += p_R
            t += dt
        self.Eb = self.E
        L_b = self.V ** (1 / 3)
        Lw_b = L_b / self.del_M

        self.Wwb = self.compute_Ww(V=self.Lb ** 3, E=self.Eb)  # g, wet weight at birth
        self.birth_time_in_hours = np.round(self.t_b * 24, 2)
        self.sim_start+=self.birth_time_in_hours
        self.stage = 'larva'
        self.age = self.t_b
        if self.print_output:
            print('-------------Embryo stage-------------')
            print(f'Duration         (d) :      predicted {np.round(self.t_b, 3)} VS computed {np.round(t, 3)}')
            print('----------------Birth----------------')
            print(f'Wet weight      (mg) :      {np.round(self.Wwb * 1000, 5)}')
            print(
                f'Physical length (mm) :      predicted {np.round(self.Lwb * 10, 3)} VS computed {np.round(Lw_b * 10, 3)}')

    def run_larva_stage(self, f=1.0, dt=None):
        if dt is None:
            dt = self.dt
        kap = self.kap
        E_G = self.E_G
        g = self.g
        del_M = self.del_M

        t = 0

        while self.E_R < self.E_Rj:
            p_A = self.p_Amm_dt * f * self.V
            p_S = self.p_M_dt * self.V
            p_C = self.E * (E_G * self.k_E_dt + p_S / self.V) / (kap * self.E / self.V + E_G)
            p_G = kap * p_C - p_S
            p_J = self.k_J_dt * self.E_Hb
            p_R = (1 - kap) * p_C - p_J

            self.E += (p_A - p_C)
            self.V += p_G / E_G
            self.E_R += p_R
            t += dt
        Lw_j = self.V ** (1 / 3) / del_M
        Ej = self.Ej = self.E
        self.Uj = Ej / self.p_Am
        self.uEj = self.lj ** 3 * (self.kap * self.kap_V + f / g)
        self.Wwj = self.compute_Ww(V=self.Lj ** 3,
                                   E=Ej + self.E_Rj)  # g, wet weight at pupation, including reprod buffer
        # self.Wwj = self.Lj**3 * (1 + f * self.w_V) # g, wet weight at pupation, excluding reprod buffer at pupation
        # self.Wwj += self.E_Rj * self.w_E/ self.mu_E/ self.d_E # g, wet weight including reprod buffer
        self.pupation_time_in_hours = self.birth_time_in_hours + np.round(t * 24, 1)
        self.stage = 'pupa'
        if self.print_output:
            print('-------------Larva stage-------------')
            print(f'Duration         (d) :      predicted {np.round(self.t_j, 3)} VS computed {np.round(t, 3)}')
            print('---------------Pupation---------------')
            print(f'Wet weight      (mg) :      {np.round(self.Wwj * 1000, 5)}')
            print(
                f'Physical length (mm) :      predicted {np.round(self.Lwj * 10, 3)} VS computed {np.round(Lw_j * 10, 3)}')

    def compute_hunger(self):
        h= np.clip(self.base_hunger + self.hunger_gain * (1 - self.e), a_min=0, a_max=1)

        return h

    def run(self, f=None, X_V=0, assimilation_mode=None):
        if f is None:
            f = self.base_f
        if assimilation_mode is None:
            assimilation_mode = self.assimilation_mode
        self.f = f
        self.age += self.dt
        # print(self.dt*24*60*60, self.age)
        kap = self.kap
        E_G = self.E_G

        if self.E_R < self.E_Rj:
            if self.gut is not None:
                self.gut.update(X_V)
            p_A = self.get_p_A(f=f, assimilation_mode=assimilation_mode)
            p_S = self.p_M_dt * self.V
            p_C = self.E * (E_G * self.k_E_dt + p_S / self.V) / (kap * self.E / self.V + E_G)
            p_G = kap * p_C - p_S
            p_J = self.k_J_dt * self.E_Hb
            p_R = (1 - kap) * p_C - p_J
            self.E += (p_A - p_C)
            self.V += p_G / E_G
            self.E_R += p_R
            self.update_hunger()
        elif self.stage == 'larva':
            self.pupation_time_in_hours = np.round(self.age * 24, 1)
            self.stage = 'pupa'
        if self.dict is not None:
            self.update_dict()

    def update_hunger(self):
        self.hunger = self.compute_hunger()
        if self.hunger_as_EEB and self.intermitter is not None:
            self.intermitter.base_EEB = self.hunger

    def die(self):
        self.alive = False
        self.death_time_in_hours = self.age * 24
        if self.print_output:
            print(f'Dead after {self.age} days')

    @ property
    def J_X_A(self):
        return self.J_X_Amm*self.V*self.base_f

    @property
    def F(self): # Vol specific filtering rate (cm**3/(d*cm**3) -> vol of environment/vol of individual*day
        # F = self.F_mm * self.K/(self.K + self.substrate.X)
        F = (self.F_mm ** -1 + self.substrate.X * self.J_X_Amm ** -1) ** -1
        # F = (self.F_mm ** -1 + self.substrate.X * self.J_X_Amm ** -1) ** -1
        return F

    @property
    def fr_feed(self):
        freq = self.F / self.V_bite * self.T_factor
        freq /= (24 * 60 * 60)
        return freq

    def compute_Ww(self, V=None, E=None):
        if V is None:
            V = self.V
        if E is None:
            E = self.E + self.E_R
        return V * self.d_V + E * self.w_E / self.mu_E

    @property
    def Ww(self):
        return self.V * self.d_V + (self.E + self.E_R) * self.w_E / self.mu_E

    @ property
    def e(self):
        return self.E / self.V / self.E_M

    @ property
    def Vw(self):
        Em=self.p_Am/self.v
        omegaV=Em*self.w_E/self.d_E/self.mu_E
        return self.V*(1+omegaV*self.e)

    # @property
    # def Ww(self):
    #     Em = self.p_Am / self.v
    #     omegaW = Em * self.w_E / self.d_V / self.mu_E
    #     return self.d_V*self.V * (1 + omegaW * self.e)
    def grow_larva(self, epochs, **kwargs):
        tb=self.birth_time_in_hours
        self.epoch_fs =[]
        self.epoch_qs =[]
        self.epochs = []
        for idx, ep in epochs.items() :
            q=ep['substrate']['quality']
            f=Substrate(**ep['substrate']).get_f(K=self.K)
            c = {'assimilation_mode': 'sim', 'f' : f}
            if ep['stop'] is None:
                while self.stage == 'larva':
                    self.run(**c)
            else :
                N = int(self.steps_per_day / 24 * (ep['stop']-ep['start']))
                for i in range(N):
                    if self.stage == 'larva':
                        self.run(**c)
            self.epoch_fs.append(f)
            self.epoch_qs.append(q)
            self.epochs.append([ep['start']+tb, ep['stop']+tb if ep['stop'] is not None else self.pupation_time_in_hours])
        self.hours_as_larva = self.age*24 - tb

    @ property
    def pupation_buffer(self):
        return self.E_R / self.E_Rj

    @property
    def EEB(self):
        if self.intermitter is None :
            return None
        else :
            return self.intermitter.EEB

    def init_dict(self):
        self.dict_keys = [
            'age',
            'mass',
            'length',
            'reserve',
            'reserve_density',
            'hunger',
            'pupation_buffer',
            'f',
            'deb_p_A',
            'sim_p_A',
            'EEB'
        ]
        d = {k: [] for k in self.dict_keys}
        return d

    def update_dict(self):
        dict_values = [
            self.age * 24,
            self.Ww * 1000,
            self.Lw * 10,
            self.E,
            self.e,
            self.hunger,
            self.pupation_buffer,
            self.f,
            self.deb_p_A / self.V,
            self.sim_p_A / self.V,
            self.EEB
        ]
        for k, v in zip(self.dict_keys, dict_values):
            self.dict[k].append(v)
        if self.gut is not None :
            self.gut.update_dict()

    def finalize_dict(self, path=None):
        if self.dict is not None :
            d = self.dict
            d['birth'] = self.birth_time_in_hours
            d['pupation'] = self.pupation_time_in_hours
            d['emergence'] = self.emergence_time_in_hours
            d['death'] = self.death_time_in_hours
            d['id'] = self.id
            d['simulation'] = self.simulation
            d['hours_as_larva'] = self.hours_as_larva
            d['sim_start'] = self.sim_start
            d['epochs'] = self.epochs
            d['epoch_fs'] = self.epoch_fs
            d['epoch_qs'] = self.epoch_qs
            d['fr'] = 1 / (self.dt * 24 * 60 * 60)
            d['feed_freq_estimate'] = self.fr_feed
            d['f_mean'] = np.mean(d['f'])
            d['f_deviation_mean'] = np.mean(np.array(d['f'])-1)

            if self.gut is not None :
                d['Nfeeds'] = self.gut.Nfeeds
                d['mean_feed_freq'] = self.gut.Nfeeds/(self.age-self.birth_time_in_hours)/(60*60)
            
        self.save_dict(path)
        return d



    def return_dict(self):
        if self.gut is None :
            return self.dict
        else :
            return {**self.dict, **self.gut.dict}

    def store_epochs(self, epochs, fs):
        t0 = self.birth_time_in_hours
        t1 = self.pupation_time_in_hours
        t2 = self.death_time_in_hours
        epochs = [[s0 + t0, s1 + t0] for [s0, s1] in epochs]
        # print(t0,t1,t2,epochs, fs)
        for t in [t1, t2]:
            if not np.isnan(t):
                f_epochs = [[(s0, np.clip(s1, a_min=s0, a_max=t)),f] for [s0, s1], f in zip(epochs,fs) if s0 <= t]
            else :
                f_epochs = [[(s0, s1), f] for [s0, s1], f in zip(epochs, fs)]
        epochs=[(s0,s1) for (s0,s1),f in f_epochs]
        fs=[f for (s0,s1),f in f_epochs]
        return epochs,fs

    def save_dict(self, path=None):
        if path is None :
            if self.save_to is not None :
                path=self.save_to
            else :
                return
                # raise ValueError ('No path to save DEB dict')
        if self.dict is not None:
            # self.finalize_dict()
            self.dict_file = f'{path}/{self.id}.txt'
            # self.deb_dict_file = f'{path}/deb_{self.id}.txt'
            # self.gut_dict_file = f'{path}/gut_{self.id}.txt'
            if self.gut is not None :
                d={**self.dict, **self.gut.dict}
            else :
                d=self.dict
            if not os.path.exists(path):
                os.makedirs(path)
            for f,d in zip([self.dict_file], [d]) :
            # for f,d in zip([self.dict_file,self.deb_dict_file,self.gut_dict_file], [self.dict, self.deb_dict, self.gut_dict]) :
                with open(f, "w") as fp:
                    json.dump(d, fp)

    def get_p_A(self, f, assimilation_mode):
        self.deb_p_A = self.p_Amm_dt * self.base_f * self.V
        self.sim_p_A = self.p_Amm_dt * f * self.V

        if assimilation_mode == 'sim':
            return self.sim_p_A
        elif assimilation_mode == 'gut':
            self.gut_p_A = self.gut.p_A
            # print(int(100*self.gut_p_A/ self.deb_p_A))
            return self.gut.p_A
        elif assimilation_mode == 'deb':
            return self.deb_p_A

    @property
    def deb_f_mean(self):
        return np.mean(self.dict['f'])

    # @property
    # def gut_occupancy(self):
    #     return self.gut.occupancy

    @property
    def ingested_body_mass_ratio(self):
        return self.gut.ingested_mass() / self.Ww * 100

    @property
    def ingested_body_volume_ratio(self):
        return self.gut.ingested_volume / self.V * 100

    @property
    def ingested_gut_volume_ratio(self):
        return self.gut.ingested_volume / (self.V * self.gut.V_gm) * 100

    @property
    def ingested_body_area_ratio(self):
        return (self.gut.ingested_volume / self.V) ** (1 / 2) * 100

    @property
    def amount_absorbed(self):
        return self.gut.absorbed_mass('mg')

    @property
    def deb_f_deviation(self):
        return self.f - 1

    @property
    def deb_f_deviation_mean(self):
        return np.mean(np.array(self.dict['f']) - 1)


# p.257 in S. a. L. M. Kooijman, “Dynamic Energy Budget theory for metabolic organisation : Summary of concepts of the third edition,” Water, vol. 365, p. 68, 2010.


def deb_default(id='DEB model', epochs={}, age=None, **kwargs):
    # print(epochs)
    deb = DEB(id=id, simulation=False, use_gut=False, **kwargs)
    N=len(epochs)
    if N==0 :
        epochs={0:null_dict('epoch', start=0.0, stop=None)}
    elif epochs[str(N-1)]['stop'] is not None:
        epochs.update({N : null_dict('epoch', start=epochs[str(N-1)]['stop'], stop=None)})
    deb.grow_larva(epochs=epochs, age=age)
    deb.finalize_dict()
    d = deb.return_dict()
    return d

def deb_sim(id='DEB sim', EEB=None, deb_dt=None, dt=None,  sample=None, use_hunger=False,model_id=None,save_dict=True, **kwargs) :
    from lib.model.modules.intermitter import OfflineIntermitter, get_best_EEB
    sample=loadConf(sample, 'Ref')
    kws2=sample['intermitter']
    if dt is None:
        dt=kws2['dt']
    else :
        kws2.update({'dt': dt})

    if deb_dt is None:
        deb_dt = dt
    steps_per_day=np.round(24 * 60 * 60 / deb_dt).astype(int)
    deb = DEB(id=id, assimilation_mode='gut', save_dict=save_dict,**kwargs)
    if EEB is None :
        EEB=get_best_EEB(deb, sample)
    deb.set_steps_per_day(steps_per_day=steps_per_day)
    deb.base_hunger=EEB
    Nticks=np.round(deb_dt / dt).astype(int)
    inter=OfflineIntermitter(**kws2, EEB=EEB)
    counter=0
    feeds=0
    cum_feeds=0
    feed_dict=[]
    while (deb.stage!='pupa' and deb.alive) :
        inter.step()
        if inter.feed_counter>cum_feeds :
            feeds += 1
            cum_feeds += 1
        if inter.total_ticks%Nticks==0 :
            feed_dict.append(feeds)
            X_V = deb.V_bite * deb.V * feeds
            deb.run(X_V=X_V)
            feeds = 0
            if use_hunger :
                inter.EEB=deb.hunger
                if inter.feeder_reocurrence_as_EEB :
                    inter.feeder_reoccurence_rate=inter.EEB
            # if deb.age * 24>counter :
            #     print(counter, int(deb.pupation_buffer*100))
            #     counter+=24
    deb.finalize_dict()
    d_sim= deb.return_dict()
    d_inter = inter.build_dict()
    mini_dic={
        'DEB model' : deb.species,
        'EEB' : np.round(EEB,2),
        **{f'{q} ratio' : np.round(d_inter[nam.dur_ratio(p)],2) for p,q in zip(['stridechain', 'pause','feedchain'], ['crawl', 'pause','feed'])},
    f"{nam.freq('feed')}_exp" :  np.round(inter.get_mean_feed_freq(),2),
    f"{nam.freq('feed')}_est" :  np.round(deb.fr_feed,2)
    }
    d_sim.update(mini_dic)
    if model_id is None :
        return d_sim
    else :
        d_mod = deb_default(id=model_id,save_dict=save_dict,**kwargs)
        return d_sim, d_mod



if __name__ == '__main__':
    deb=DEB(print_output=True)
    print(deb.age, deb.stage)
    # deb.run_larva_stage()
    # print(deb.age, deb.stage)
    deb.grow_larva(epochs={'0':{'start':0.0, 'stop':80.0, 'substrate':{'quality':1.0, 'type': 'standard'}}})
    print(deb.age, deb.stage)
    raise
    from lib.model.modules.intermitter import OfflineIntermitter, get_best_EEB,get_EEB_poly1d
    ffrs=np.round(np.arange(0.2, 2.2, 0.2), 1)
    sample = loadConf('None.200_controls', 'Ref')
    z=np.poly1d(sample['EEB_poly1d'])
    print(np.round(z(ffrs),2))
    z=get_EEB_poly1d(sample=sample)
    print(np.round(z(ffrs),2))
    raise
    ds=[]
    # for q in np.round(np.arange(0.02,1.02,0.02),2) :
    for ffr in np.round(np.arange(0.2, 2.2, 0.2), 1):
        d=deb_sim(sample='None.200_controls', dt=0.1, EEB=z(ffr),deb_dt=60)
        ds.append(d)
        # deb=DEB(substrate={'quality':q, 'type':'standard'})
        print(ffr, d[f"{nam.freq('feed')}_exp"], d[f"{nam.freq('feed')}_est"],d['EEB'])
        # for
    import pandas as pd
    df=pd.DataFrame.from_records(ds)
    # d_sim=deb_sim(sample='None.200_controls', dt=0.1, deb_dt=1.0)
    # print(d_sim)
    # deb.run_larva_stage()
    raise
    # print(deb.K)
    # print(deb.V*deb.J_E_Amm)
    # print(deb.substrate.X/(deb.substrate.X+ deb.K))
    # print(deb.substrate.X_ratio)
    # print(10**6*deb.V*deb.J_E_Amm/deb.k_E/deb.y_E_X)
    # for EEB in [0.57,0.95] :
    #     d=deb_sim(EEB=EEB, dt=0.1, deb_dt=60)
        # print(EEB, d['pupation'])
    from lib.model.modules.intermitter import get_best_EEB

    sample = loadConf('None.200_controls', 'Ref')
    for sp in ['default', 'rover', 'sitter'] :
        deb = DEB(species=sp)
        print(sp, deb.fr_feed, deb.K, deb.base_f, deb.kap_X, get_best_EEB(deb, sample))
    raise

    dt_bite=1/(24*60*60)*2
    # for s in ['standard'] :
    for s in ['standard', 'cornmeal', 'PED_tracker'] :
        q=1
        V_bite=0.0005
        deb=DEB(substrate_quality=q, assimilation_mode='sim', steps_per_day=24*60, V_bite=V_bite, substrate_type=s)

        print([[q, deb.substrate.get_f(K=deb.K, quality=q)] for q in np.arange(0,1.01,0.5)])
        continue
        th_F=0.01
        th_X=deb.gut.V_gm


        counter=0
        while (deb.stage != 'pupa' and deb.alive):
            deb.run()
            if deb.age * 24 > counter:
                print(counter, int(deb.pupation_buffer * 100), deb.fr_feed)
                # print(deb.hunger, inter.EEB)
                counter += 5
    # a=Substrate()
    # print(F)


