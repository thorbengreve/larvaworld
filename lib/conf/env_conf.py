import numpy as np

import lib.aux.functions as fun
import lib.conf.dtype_dicts as dtypes


def food_distro(N, mode='uniform', shape='circle', group='Food', **kwargs):
    if N > 0:
        return dtypes.get_dict('distro', class_name='Source', basic=False, group=group, as_entry=True,
                               N=N, mode=mode, shape=shape, **kwargs)
    else:
        return {}


def food_param_conf(distro={}, list={}, grid=None):
    return {'source_groups': distro,
            'food_grid': grid,
            'source_units': list}


def larva_distro(N=1, mode='uniform', shape='circle', group='Larva', **kwargs):
    if N > 0:
        return dtypes.get_dict('distro', class_name='Larva', basic=False, group=group, as_entry=True,
                               N=N, mode=mode, shape=shape, **kwargs)
    else:
        return {}


# set_on_xaxis_one_food = {'initial_num_flies': 1 * 8 * 20,
#                          'initial_fly_positions': {'mode': 'defined',
#                                                    'loc': fun.generate_positions_on_xaxis(num_identical=1 * 8,
#                                                                                           num_starting_points=20,
#                                                                                           step=0.05, starting_x=-0.5),
#                                                    'orientation_range': fun.generate_orientations(num_identical=1,
#                                                                                             circle_parsing=8,
#                                                                                             iterations=20)},
#                          'initial_num_food': 1,
#                          'initial_food_positions': {'mode': 'defined',
#                                                     'loc': np.array([(0.5, 0.0)])}}

food_patches = np.array([
    (0.70, 0.07), (0.50, -0.43),
    (0.04, -0.63), (-0.41, -0.46),
    (-0.66, 0.01), (-0.45, 0.50),
    (-0.00, 0.69), (0.45, 0.54)
])

one_diffusion_odor = {'odor_landscape': 'Diffusion',
                      'odor_layer_grid_resolution': [100, 100],
                      'odor_evaporation_rate': 0.9,
                      'odor_diffusion_rate': 0.8,
                      'odor_id_list': ['Default_odor_ID'],
                      'odor_carriers': 'food',
                      'odor_intensity_list': [1],
                      'odor_spread_list': [0.5],
                      'odor_source_allocation': 'iterative'
                      }


def dish(r):
    return {'arena_xdim': r,
            'arena_ydim': r,
            'arena_shape': 'circular'}


def arena(x, y):
    return {'arena_xdim': x,
            'arena_ydim': y,
            'arena_shape': 'rectangular'}


def maze(nx=15, ny=15, ix=0, iy=0, h=0.1, return_points=False):
    from lib.envs._maze import Maze
    m = Maze(nx, ny, ix, iy, height=h)
    m.make_maze()
    lines = m.maze_lines()
    if return_points:
        ps = []
        for l in lines:
            ps.append(l.coords[0])
            ps.append(l.coords[1])
        ps = [(np.round(x - h / 2, 3), np.round(y - h / 2, 3)) for x, y in ps]
        return ps
    else:
        return lines


def odor_source(id, pos=(0.0, 0.0), odor_id=None, odor_intensity=2.0, odor_spread=0.0002, **kwargs):
    if odor_id is None:
        odor_id = f'{id}_odor'
    return dtypes.get_dict('agent', class_name='Source', unique_id=id, as_entry=True, pos=pos,
                           odor_id=odor_id, odor_intensity=odor_intensity, odor_spread=odor_spread, **kwargs)


def foodNodor_source(id, pos=(0.0, 0.0), odor_id=None, odor_intensity=2.0, odor_spread=0.0002, amount=0.01, **kwargs):
    if odor_id is None:
        odor_id = f'{id}_odor'
    return dtypes.get_dict('agent', class_name='Source', unique_id=id, as_entry=True, pos=pos, amount=amount,
                           odor_id=odor_id, odor_intensity=odor_intensity, odor_spread=odor_spread, **kwargs)


CS_UCS_odors = {**odor_source(id='CS_source', pos=(-0.04, 0.0), odor_id='CS', default_color='red'),
                **odor_source(id='UCS_source', pos=(0.04, 0.0), odor_id='UCS', default_color='blue')}

CS_UCS_odors_RL = {
    **foodNodor_source(id='CS_source', pos=(-0.03, 0.0), odor_id='CS', default_color='red', odor_intensity=300.0,
                       r=0.015),
    **odor_source(id='UCS_source', pos=(0.03, 0.0), odor_id='UCS', default_color='blue', odor_intensity=300.0, r=0.015),
}


def gaussian_odor():
    return {'odorscape': 'Gaussian',
            'grid_dims': None,
            'evap_const': None,
            'gaussian_sigma': None
            }


def diffusion_odor():
    return {'odorscape': 'Diffusion',
            'grid_dims': [100, 100],
            'evap_const': 0.9,
            'gaussian_sigma': (7, 7)
            }


def game_env_conf(dim=0.1, N=10, x=0.4, y=0.0, mode='king'):
    x = np.round(x * dim, 3)
    y = np.round(y * dim, 3)
    if mode == 'king':
        modL, modR = 'gamer_L', 'gamer_R'
    elif mode == 'flag':
        modL, modR = 'gamer', 'gamer'
    env = {'arena_params': arena(dim, dim),
           'food_params': food_param_conf(list={
               **foodNodor_source('Flag', odor_intensity=8, odor_spread=0.0004, default_color='green',
                                  can_be_carried=True),
               **odor_source(id='Left_base', pos=(-x, y), default_color='blue'),
               **odor_source(id='Right_base', pos=(+x, y), default_color='red')}),
           'larva_params': {
               **larva_distro(N=N, loc=(-x, y), group='Left', model=modL, default_color='darkblue'),
               **larva_distro(N=N, loc=(+x, y), group='Right', model=modR, default_color='darkred')
           },
           'odorscape': gaussian_odor()
           }
    return env


king_env = game_env_conf(mode='king')
flag_env = game_env_conf(mode='flag')


def maze_conf(n, h):
    conf = {'arena_params': arena(h, h),
            'border_list': {
                'Maze': {
                    'points': maze(nx=n, ny=n, h=h, return_points=True),
                    'default_color': 'black',
                    'width': 0.001}
            },
            'food_params': food_param_conf(list={**odor_source('Target', odor_id='Odor', default_color='blue')}),
            'larva_params': larva_distro(N=5, loc=(-0.4 * h, 0.0), orientation_range=(-60.0, 60.0), model='navigator'),
            'odorscape': gaussian_odor()}
    return conf


pref_env = {'arena_params': dish(0.1),
            'food_params': food_param_conf(list=CS_UCS_odors),
            'larva_params': larva_distro(N=25, scale=(0.005, 0.02), model='navigator_x2'),
            'odorscape': gaussian_odor()}

pref_env_RL = {'arena_params': dish(0.1),
               'food_params': food_param_conf(list=CS_UCS_odors_RL),
               'larva_params': larva_distro(N=25, scale=(0.005, 0.02), model='RL_learner'),
               'odorscape': diffusion_odor()}

chemotax_env = {'arena_params': arena(0.1, 0.06),
                'food_params': food_param_conf(list={**odor_source(id='Odor_source', pos=(0.04, 0.0),
                                                                   odor_id='Odor', odor_intensity=8,
                                                                   odor_spread=0.0004, default_color='blue')}),
                'larva_params': larva_distro(N=30, loc=(-0.04, 0.0), scale=(0.005, 0.02),
                                             orientation_range=(-30.0, 30.0),
                                             model='navigator'),
                'odorscape': gaussian_odor()}

# print(chemotax_env['food_params']['source_units'])

chemorbit_env = {'arena_params': arena(0.1, 0.06),
                 'food_params': food_param_conf(list={**odor_source(id='Odor_source', odor_id='Odor',
                                                                    default_color='blue')}),
                 'larva_params': larva_distro(N=30, model='navigator'),
                 'odorscape': gaussian_odor()
                 }

chemorbit_diffusion_env = {'arena_params': arena(0.3, 0.3),
                           'food_params': food_param_conf(
                               list={**odor_source(id='Odor_source', odor_id='Odor',
                                                   odor_intensity=300.0, default_color='blue', r=0.03)}),
                           'larva_params': larva_distro(N=30, model='navigator'),
                           'odorscape': diffusion_odor()
                           }

RL_chemorbit_env = {'arena_params': dish(0.2),
                    'food_params': food_param_conf(
                        list={**foodNodor_source(id='Odor_source', odor_id='Odor',
                                                 odor_intensity=300.0, default_color='blue')}),
                    'larva_params': larva_distro(N=1, loc=(0.05, 0.05), model='RL_learner'),
                    'odorscape': diffusion_odor()
                    }

maze_env = maze_conf(15, 0.1)

dispersion_env = {'arena_params': dish(0.2),
                  'food_params': food_param_conf(),
                  'larva_params': larva_distro(N=30, model='explorer'),
                  'odorscape': None}

dish_env = {'arena_params': dish(0.1),
            'food_params': food_param_conf(),
            'larva_params': larva_distro(N=25, scale=(0.02, 0.02), model='explorer'),
            'odorscape': None}

reorientation_env = {'arena_params': dish(0.1),
                     'food_params': food_param_conf(
                         list={**odor_source(id='Odor_source', odor_id='Odor', default_color='blue')}),
                     'larva_params': larva_distro(N=200, scale=(0.05, 0.05), model='immobile'),
                     'odorscape': gaussian_odor()}

imitation_env_p = {'arena_params': dish(0.15),
                   'food_params': food_param_conf(),
                   'larva_params': larva_distro(N=25, model='imitation'),
                   'odorscape': None}

focus_env = {'arena_params': dish(0.01),
             'food_params': food_param_conf(),
             'larva_params': larva_distro(N=1, orientation_range=[90.0, 90.0], model='immobile'),
             'odorscape': None}

uniform_food_env = {'arena_params': dish(0.05),
                    'food_params': food_param_conf(
                        distro=food_distro(N=2000, scale=(0.025, 0.025), amount=0.01, radius=0.0001)),
                    'larva_params': larva_distro(N=5, scale=(0.005, 0.005), model='feeder'),
                    'odorscape': None}

patchy_food_env = {'arena_params': arena(0.2, 0.2),
                   'food_params': food_param_conf(
                       distro=food_distro(N=8, mode='periphery', scale=(0.07, 0.07), amount=0.001,
                                          odor_id='Odor', odor_intensity=8, odor_spread=0.0004)),
                   'larva_params': larva_distro(N=25, model='feeder-navigator'),
                   'odorscape': gaussian_odor()}

food_grid_env = {'arena_params': arena(0.03, 0.03),  # dish(0.006),
                 'food_params': food_param_conf(grid=dtypes.get_dict('food_grid')),
                 'larva_params': larva_distro(N=25, model='feeder'),
                 'odorscape': None}

growth_env = {'arena_params': arena(0.02, 0.02),  # dish(0.006),
              'food_params': food_param_conf(grid=dtypes.get_dict('food_grid')),
              'larva_params': larva_distro(N=5, model='sitter'),
              'odorscape': None}

# growth_env = {'arena_params': dish(0.01),  # dish(0.006),
#               'food_params': food_param_conf(list={**dtypes.get_dict('agent', class_name='Source', unique_id='Food',
#                                                                    as_entry=True, amount=1.0, radius=0.01)}),
#               'larva_params': larva_distro(N=5, model='sitter'),
#               'odorscape': None}

growth_2x_env = {'arena_params': arena(0.02, 0.02),  # dish(0.006),
                 'food_params': food_param_conf(grid=dtypes.get_dict('food_grid')),
                 'larva_params': {
                     **larva_distro(N=1, group='Rover', model='rover', default_color='blue'),
                     **larva_distro(N=1, group='Sitter', model='sitter', default_color='red')
                 },
                 'odorscape': None}

test_env = {'arena_params': dish(0.1),
            'food_params': {
                'source_groups': food_distro(N=8, mode='periphery', scale=(0.07, 0.07), amount=0.001,
                                             odor_id='Odor', odor_intensity=8, odor_spread=0.0004),
                'food_grid': dtypes.get_dict('food_grid'),
                'source_units': CS_UCS_odors
            },
            'larva_params': larva_distro(N=25, model='feeder'),
            'odorscape': diffusion_odor()}

catch_me_env = {'arena_params': dish(0.05),
                'food_params': food_param_conf(),
                'larva_params': {
                    **larva_distro(N=1, loc=(-0.01, 0.0), group='Left', model='follower_L', default_color='darkblue'),
                    **larva_distro(N=1, loc=(+0.01, 0.0), group='Right', model='follower_R', default_color='darkred')
                },
                'odorscape': diffusion_odor()
                }
