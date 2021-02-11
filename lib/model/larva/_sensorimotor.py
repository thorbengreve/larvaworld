import abc
import math

import numpy as np

from lib.model.larva._bodies import LarvaBody
from lib.aux.functions import restore_bend, inside_polygon, angle_dif, rotate_around_point, \
    restore_bend_2seg, rotate_around_center


class Agent(LarvaBody, abc.ABC):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # self._id = None
    # def set_id(self, id):
    #     self._id = id

    # @property
    # def id(self):
    #     return self._id

    @abc.abstractmethod
    def step(self, time_step):
        pass


class VelocityAgent(Agent, abc.ABC):
    def __init__(self, pos, orientation,
                 lin_vel_coef=1.0, ang_vel_coef=None, lin_force_coef=None, torque_coef=1.0, static_torque=0.0,
                 lin_mode='velocity', ang_mode='torque', body_spring_k=1.0, bend_correction_coef=1.0,
                 lin_damping=1.0, ang_damping=1.0, density=300.0,
                 friction_pars={'maxForce': 10 ** 0, 'maxTorque': 10 ** -1}, **kwargs):

        self.lin_damping = lin_damping
        self.ang_damping = ang_damping
        self.body_spring_k = body_spring_k
        self.bend_correction_coef = bend_correction_coef
        self.static_torque=static_torque
        self.density = density
        self.friction_pars = friction_pars

        self.head_contacts_ground = True
        super().__init__(model=self.model, pos=pos, orientation=orientation, **kwargs)
        self.lin_activity = 0
        self.ang_activity = 0
        self.ang_vel = 0
        self.body_bend=0
        self.body_bend_errors=0
        self.Nangles_b = int(self.Nangles + 1 / 2)
        self.compute_body_bend()
        self.torque = 0
        self.mid_seg_index = int(self.Nsegs / 2)

        self.sim_time = 0

        self.cum_dst = 0.0
        self.step_dst = 0.0
        self.initial_pos=self.get_position()
        self.current_pos=self.initial_pos
        self.trajectory = [self.current_pos]

        self.lin_mode = lin_mode
        self.ang_mode = ang_mode

        # Cheating calibration (this is to get a step_to_length around 0.3 for gaussian crawler with amp=1 and std=0.05
        # applied on TAIL of l3-sized larvae with interval -0.05.
        # Basically this means for a 7-timestep window only one value is 1 and all others nearly 0)
        # Will become obsolete when we have a definite answer to :
        # is relative_to_length displacement_per_contraction a constant? How much is it?
        # if self.Npoints == 6:
        #     self.lin_coef = 3.2  # 2.7 for tail, 3.2 for head applied velocity
        # elif self.Npoints == 1:
        #     self.lin_coef = 1.7
        # elif self.Npoints == 11:
        #     self.lin_coef = 4.2
        # else:
        #     self.lin_coef = 1.5 + self.Npoints / 4

        self.lin_vel_coef = lin_vel_coef
        self.ang_vel_coef = ang_vel_coef
        self.lin_force_coef = lin_force_coef
        self.torque_coef = torque_coef
        self.ground_contact=True

        k=0.95
        self.tank_vertices=self.model.tank_shape * k
        self.space_edges=self.model.space_edges_for_screen * k



    def step(self):
        self.restore_body_bend()

        # Trying restoration for any number of segments
        # if self.Nsegs == 1:
        # if self.Nsegs > 0:
        #     # Angular component
        #     # Restore body bend due to forward motion of the previous step
        #     # pass
        #     # ... apply the torque against the restorative powers to the body,
        #     # to update the angular velocity (for the physics engine) and the body_bend (for body state calculations) ...
        # else:
        #     # Default mode : apply torque
        #     # self.get_head()._body.ApplyTorque(self.torque, wake=True)
        #     pass

        if self.model.physics_engine:
            if self.ang_mode == 'velocity':
                ang_vel = self.ang_activity * self.ang_vel_coef
                ang_vel = self.compute_ang_vel(v=ang_vel, z=0)
                self.segs[0].set_ang_vel(ang_vel)
                if self.Nsegs > 1:
                    for i in np.arange(1, self.mid_seg_index, 1):
                        self.segs[i].set_ang_vel(ang_vel / i)
            elif self.ang_mode == 'torque':
                # unused_ang_vel = self.compute_ang_vel(ang_velocity=self.get_head().get_angularvelocity(),
                #                                                ang_damping=False)
                # TODO THis needs to be calibrated according to the real larva
                self.torque = self.ang_activity * self.torque_coef
                self.segs[0]._body.ApplyTorque(self.torque, wake=True)
                if self.Nsegs > 1:
                    for i in np.arange(1, self.mid_seg_index, 1):
                        self.segs[i]._body.ApplyTorque(self.torque / i, wake=True)
                # if self.Nsegs >= 4:
                #     self.segs[1]._body.ApplyTorque(torque * 3 / 4, wake=True)
                #     if self.Nsegs >= 8:
                #         self.segs[2]._body.ApplyTorque(torque * 2 / 3, wake=True)
                #         if self.Nsegs >= 12:
                #             self.segs[3]._body.ApplyTorque(torque / 2, wake=True)
            # self.segs[1]._body.ApplyTorque(self.torque*2/2, wake=True)
            # self.segs[2]._body.ApplyTorque(self.torque*2/3, wake=True)
            # self.segs[3]._body.ApplyTorque(self.torque*2/4, wake=True)

            # Linear component
            # Option : Apply to single body segment
            # We get the orientation of the front segment and compute the linear vector
            # target_segment = self.get_head()
            # lin_vec = self.compute_new_lin_vel_vector(target_segment)
            #
            # # From web : Impulse = Force x 1 Sec in Box2D
            # if self.mode == 'impulse':
            #     imp = lin_vec / target_segment.get_mass()
            #     target_segment._body.ApplyLinearImpulse(imp, target_segment._body.worldCenter, wake=True)
            # elif self.mode == 'force':
            #     target_segment._body.ApplyForceToCenter(lin_vec, wake=True)
            # elif self.mode == 'velocity':
            #     # lin_vec = lin_vec * target_segment.get_mass()
            #     # Use this with gaussian crawler
            #     # target_segment.set_lin_vel(lin_vec * self.lin_coef, local=False)
            #     # Use this with square crawler
            #     target_segment.set_lin_vel(lin_vec, local=False)
            #     # pass

            # Option : Apply to all body segments. This allows to control velocity for any Npoints. But it has the same shitty visualization as all options
            for seg in self.segs:
                if self.lin_mode == 'impulse':
                    temp_lin_vec_amp = self.lin_activity * self.lin_vel_coef
                    impulse = temp_lin_vec_amp * seg.get_world_facing_axis() / seg.get_mass()
                    seg._body.ApplyLinearImpulse(impulse, seg._body.worldCenter, wake=True)
                elif self.lin_mode == 'force':
                    lin_force_amp = self.lin_activity * self.lin_force_coef
                    force = lin_force_amp * seg.get_world_facing_axis()
                    seg._body.ApplyForceToCenter(force, wake=True)
                elif self.lin_mode == 'velocity':
                    lin_vel_amp = self.lin_activity * self.lin_vel_coef
                    vel = lin_vel_amp * seg.get_world_facing_axis()
                    seg.set_lin_vel(vel, local=False)
        else:
            if self.lin_mode == 'velocity' :
                lin_vel_amp = self.lin_activity * self.lin_vel_coef
            else :
                raise ValueError(f'Linear mode {self.lin_mode} not implemented for non-physics simulation')
            if self.ang_mode == 'torque':
                self.torque = self.ang_activity * self.torque_coef
                # The damping free mode is much closer to the experimental histogram of body bends (singlelarva_turns.ipynb)
                # On the other hand even a minor damping of 0.01 produces a two-top distribution at -20,20 (test_turner.py)
                # So I m gonna explore the no damping case.
                # TODO Attention, the experimental distribution is from a larva constantly striding but my findings are on stationary turner component
                #  I should explore whether interference corrects the dist even when damping is present
                # UPdate : 0 damping does not fix the two-pick (though makes it a bit better).Interference neither.
                # But maybe I cn raise the torque coef of 0.07 becuse two_osc reach -20,20 and interference drops it to -10,10.
                ang_vel = self.compute_ang_vel(torque=self.torque,
                                               v=self.get_head().get_angularvelocity(),
                                               z=self.ang_damping)
            elif self.ang_mode == 'velocity':
                ang_vel = self.ang_activity * self.ang_vel_coef
                ang_vel = self.compute_ang_vel(v=ang_vel, z=self.ang_damping)


            self.step_no_physics(linear_velocity=lin_vel_amp, angular_velocity=ang_vel)


        # Paint the body to visualize effector state
        if self.model.color_behavior:
            self.update_behavior_dict()
        # if self.model.draw_contour:
        #     self.set_contour()

    def compute_new_lin_vel_vector(self, target_segment):
        # Option 1 : Create the linear velocity from orientation.
        # This was the default. But it seems because of numerical issues it doesn't generate the expected vector,
        # which results in some angular velocity  when linear velocity is applied.
        # I haven't figured out when and why that happens
        # orientation = target_segment.get_normalized_orientation()
        # orientation = target_segment.get_orientation()
        # lin_vec = b2Vec2(self.lin_activity * np.cos(orientation),
        #                  self.lin_activity * np.sin(orientation))

        # Option 2 : Just retrieve the current lin_velocity vec
        # Update : Doesn't work because linear velocity can be zero
        # Trying to integrate the two options

        # if target_segment.get_linearvelocity_vec() != b2Vec2(0,0) :
        #     previous_lin_velocity_vec = target_segment.get_linearvelocity_vec()
        #     previous_lin_velocity_amp = target_segment.get_linearvelocity_amp()
        #     previous_lin_velocity_unit_vec = previous_lin_velocity_vec / previous_lin_velocity_amp
        #     lin_vec = self.lin_activity * previous_lin_velocity_unit_vec
        # else :
        #     orientation = target_segment.get_orientation()
        #     # orientation = target_segment.get_normalized_orientation()
        #     lin_vec = b2Vec2(self.lin_activity * np.cos(orientation),
        #                      self.lin_activity * np.sin(orientation))
        lin_vec = self.lin_activity * target_segment.get_world_facing_axis()

        return lin_vec

    def update_behavior_dict(self):
        behavior_dict=self.null_behavior_dict.copy()
        if self.brain.modules['crawler'] and self.brain.crawler.active():
            behavior_dict['stride_id'] = True
            if self.brain.crawler.complete_iteration:
                behavior_dict['stride_stop'] = True
        if self.brain.modules['intermitter'] and self.brain.intermitter.active():
            behavior_dict['pause_id'] = True
        if self.brain.modules['feeder'] and self.brain.feeder.active():
            behavior_dict['feed_id'] = True
        orvel=self.get_head().get_angularvelocity()
        if orvel > 0:
            behavior_dict['Lturn_id'] = True
        elif orvel < 0 :
            behavior_dict['Rturn_id'] = True
        color=self.update_color(self.default_color, behavior_dict)
        self.set_color([color for seg in self.segs])


    # Using the forward Euler method to compute the next theta and theta'

    '''Here we implement the lateral oscillator as described in Wystrach(2016) :
    We use a,b,c,d parameters to be able to generalize. In the paper a=1, b=2*z, c=k, d=0

    Quoting  : where z =n / (2* sqrt(k*g) defines the damping ratio, with n the damping force coefficient, 
    k the stiffness coefficient of a linear spring and g the muscle gain. We assume muscles on each side of the body 
    work against each other to change the heading and thus, in this two-dimensional model, the net torque produced is 
    taken to be the difference in spike rates of the premotor neurons E_L(t)-E_r(t) driving the muscles on each side. 

    Later : a level of damping, for which we have chosen an intermediate value z =0.5
    In the table of parameters  : k=1

    So a=1, b=1, c=n/4g=1, d=0 
    '''

    # Update 4.1.2020 : Setting b=0 because it is a substitute of the angular damping of the environment
    def compute_ang_vel(self, torque=0, v=0, z=0):
        # if self.ground_contact:
        #     new_ang_velocity=(- self.body_spring_k * self.body_bend + e * torque) * self.dt
        #     if np.abs(new_ang_velocity)<vel_friction :
        #         new_ang_velocity=0
        #     else :
        #         self.ground_contact=False
        # else :
        #     new_ang_velocity = ang_velocity+ (-b * ang_velocity - self.body_spring_k * self.body_bend + e * torque) * self.dt / a
        #     if new_ang_velocity*ang_velocity<0 :
        #         self.ground_contact=True
        #         new_ang_velocity=0
        # # print(new_ang_velocity, ang_velocity)
        # return new_ang_velocity
        # print(torque)
        k=self.body_spring_k
        c=self.torque_coef
        Tst=self.static_torque
        b=self.body_bend

        # dif=(-z * v - k * b)* self.dt
        # if abs(dif)<abs(v) :
        #     v += dif
        # else :
        #     v=0
        # new_v = v + (e * torque) * self.dt
        new_v = v + (-z * v - k * b + torque) * self.model.dt
        # print(v, new_v, v-new_v)
        if new_v * v<0 and np.abs(torque)<Tst * c:
            return 0.0
        else:
            return new_v
        # if np.abs(ang_velocity) <= 1.0:
        #     self.head_contacts_ground = True
        # if np.abs(e*torque)>=Tst * c :
        #     self.head_contacts_ground=False
        # # print(torque, ang_velocity, self.head_contacts_ground)
        # if not self.head_contacts_ground :
        #     new_ang_velocity = ang_velocity + (-z * ang_velocity - k * b + e * torque) * self.dt
        #     return new_ang_velocity
        # else :
        #     return 0.0

    def restore_body_bend(self):
        self.compute_spineangles()
        # More formal mathematical solution based on the restoration of the bending angle_to_x_axis of two segments attached to a point
        # See functions.py
        d,l = self.step_dst, self.get_sim_length()
        # First attempt. Complex. Does not solve problems
        # self.set_body_bend(restored_angle(self.body_bend, d, self.get_sim_length()))
        # Second attempt. Multiple angles (Npoints-2). Critical spinepoint carries the bend resistance
        # state = np.zeros(self.Nsegs)
        # critical_point = int(self.Npoints / 2)
        # critical_point = 0
        # state[critical_point] = b
        # a = self.angles[0]
        if not self.model.physics_engine :
            if self.Nsegs ==2 :
                self.spineangles[0] = restore_bend_2seg(self.spineangles[0], d, l, correction_coef=self.bend_correction_coef)
            else :
                self.spineangles = restore_bend(self.spineangles, d, l, self.Nsegs, correction_coef=self.bend_correction_coef)
        # print(self.physics_engine)
        # print(np.abs(a)-np.abs(self.angles[0]))

        self.compute_body_bend()

    def set_torque(self, value):
        self.torque = value

    def set_lin_activity(self, value):
        self.lin_activity = value

    def set_ang_activity(self, value):
        self.ang_activity = value
        # print(value, self.ang_activity)

    def get_body_bend(self):
        return self.body_bend

    def set_body_bend(self, value):
        self.body_bend = value

    def get_position(self):
        if self.model.physics_engine:
            return self.get_global_midspine_of_body()
        else:
            return self.pos
            # return self.get_global_midspine_of_body()

    def update_trajectory(self):
        pos = self.get_position()
        self.step_dst = np.sqrt(np.sum((pos-self.current_pos)**2))
        self.cum_dst += self.step_dst
        self.current_pos=pos
        self.trajectory.append(pos)

    def set_head_contacts_ground(self, value):
        self.head_contacts_ground = value

    def step_no_physics(self, linear_velocity, angular_velocity):
        # self.body_bend += self.dt * ang_velocity
        # self.body_bend = np.clip(self.body_bend, a_min=-np.pi, a_max=np.pi)

        # BIO : Translate motor signal to behavior (how much to turn, how much to move)
        # distance = motor_vector[0] * self.max_speed
        # self.header = (self.header + motor_vector[1] * math.pi / 2) % (2 * math.pi)

        # COUNTER
        # self.total_distance += distance

        # TECH : Move the agent
        # Compute orientation
        dt=self.model.dt
        pos_old, or_old = self.get_head().get_pose()
        head_rear_old = self.get_global_rear_end_of_head()


        d_or = angular_velocity * dt
        or_new = or_old + d_or
        k=np.array([math.cos(or_new), math.sin(or_new)])

        d=linear_velocity * dt
        head_rear_new = head_rear_old + k * d
        pos_new = head_rear_new + k* self.seg_lengths[0]/2


        # head_front_local_p = self.get_local_front_end_of_seg(seg_index=0)
        # head_front_global_p = self.get_head().get_world_point(head_front_local_p)
        # front_pos_temp = rotate_around_point(origin=head_rear_global_p, point=head_front_global_p, radians=-d_or)
        # front_pos_new = (front_pos_temp[0] + dx, front_pos_temp[1] + dy)

        # points=[pos_new]
        # points=[pos_new, front_pos_new]
        temp_bool = inside_polygon(points=[pos_new], space_edges_for_screen=self.space_edges,vertices=self.tank_vertices)
        if not temp_bool :
            linear_velocity=0
            d=0
            pos_new = pos_old
            head_rear_new = head_rear_old
            angular_velocity += np.pi / 2
            d_or = angular_velocity * dt
            or_new = or_old + d_or
        self.get_head().set_pose(pos_new, or_new, linear_velocity, angular_velocity)
        self.get_head().update_vertices(pos_new, or_new)
        self.position_rest_of_body(d_or, head_rear_pos=head_rear_new, head_or=or_new)

        self.step_dst = d
        self.cum_dst += d
        if self.Nsegs==2:
            self.current_pos = head_rear_new
        else :
            self.current_pos = self.get_global_midspine_of_body()
        self.model.space.move_agent(self, self.current_pos)
        self.trajectory.append(self.current_pos)

    def position_rest_of_body(self, d_orientation, head_rear_pos, head_or):
        if self.Nsegs == 1:
            pass
        else:
            bend_per_spineangle = d_orientation / (self.Nsegs / 2)
            for i, (seg,l) in enumerate(zip(self.segs[1:], self.seg_lengths[1:])):
                if i==0 :
                    global_p=head_rear_pos
                    previous_seg_or=head_or
                else :
                    global_p = self.get_global_rear_end_of_seg(seg_index=i)
                    previous_seg_or = self.segs[i].get_orientation()
                if i + 1 <= self.Nsegs / 2:
                    self.spineangles[i] += bend_per_spineangle
                new_or = previous_seg_or - self.spineangles[i]
                seg.set_orientation(new_or)
                new_p = global_p +np.array([-np.cos(new_or), -np.sin(new_or)])* l / 2
                seg.set_position(new_p)
                seg.update_vertices(new_p, new_or)
            self.compute_body_bend()


    def compute_spineangles(self):
        seg_ors = [seg.get_orientation() for seg in self.segs]
        self.spineangles = [angle_dif(seg_ors[i], seg_ors[i + 1], in_deg=False) for i in range(self.Nangles)]

    def compute_body_bend(self):
        prev = self.body_bend
        curr= np.sum(self.spineangles[:self.Nangles_b])
        if np.abs(prev)>2 and np.abs(curr)>2 and prev*curr<0 :
            self.body_bend_errors+=1
            # curr=np.sign(curr)*np.pi
            # print('Illegal bend over rear axis')
        self.body_bend=curr
