import numpy as np
from gym import utils
from gym.envs.dart import dart_env


class DartHopper4LinkSPDEnv(dart_env.DartEnv, utils.EzPickle):
    def __init__(self):
        self.control_bounds = np.array([[1.0, 1.0, 1.0],[-1.0, -1.0, -1.0]])
        self.action_scale = 200
        self.include_action_in_obs = False
        self.randomize_dynamics = False
        obs_dim = 11

        if self.include_action_in_obs:
            obs_dim += len(self.control_bounds[0])
            self.prev_a = np.zeros(len(self.control_bounds[0]))

        self.fwd_bwd_pass = False

        self.supp_input = False

        self.reverse_order = False

        self.feet_specialized = False

        if self.supp_input:
            obs_dim += 3*4 # [contact, local_x, local_y]

        dart_env.DartEnv.__init__(self, 'hopper_multilink/hopperid_4link.skel', 4, obs_dim, self.control_bounds, disableViewer=True)

        if self.randomize_dynamics:
            self.bodynode_original_masses = []
            self.bodynode_original_frictions = []
            for bn in self.robot_skeleton.bodynodes:
                self.bodynode_original_masses.append(bn.mass())
                self.bodynode_original_frictions.append(bn.friction_coeff())

        self.dart_world.set_collision_detector(3)

        self.initialize_articunet()

        kp_diag = np.array([0.0] * 3 + [100.0] * (3))
        self.Kp = np.diagflat(kp_diag)
        self.Kd = np.diagflat(kp_diag * 0.05)

        self.torque_limit = np.array([self.action_scale] * 3)

        utils.EzPickle.__init__(self)

    def initialize_articunet(self, supp_input = None, reverse_order = None, feet_specialized = None):
        self.supp_input = supp_input if supp_input is not None else self.supp_input
        self.reverse_order = reverse_order if reverse_order is not None else self.reverse_order
        self.feet_specialized = feet_specialized if feet_specialized is not None else self.feet_specialized
        # setups for controller articunet
        self.state_dim = 32
        self.enc_net = []
        self.act_net = []
        self.vf_net = []
        self.merg_net = []
        self.net_modules = []
        self.net_vf_modules = []
        if self.include_action_in_obs:
            self.enc_net.append([self.state_dim, 5, 64, 1, 'planar_enc'])
            self.enc_net.append([self.state_dim, 3, 64, 1, 'revolute_enc'])
        elif self.supp_input:
            self.enc_net.append([self.state_dim, 5 + 3, 64, 1, 'planar_enc'])
            self.enc_net.append([self.state_dim, 2 + 3, 64, 1, 'revolute_enc'])
        else:
            self.enc_net.append([self.state_dim, 5, 64, 1, 'planar_enc'])
            self.enc_net.append([self.state_dim, 2, 64, 1, 'revolute_enc'])

        self.enc_net.append([self.state_dim, 5, 64, 1, 'vf_planar_enc'])
        if not self.include_action_in_obs:
            self.enc_net.append([self.state_dim, 2, 64, 1, 'vf_revolute_enc'])
        else:
            self.enc_net.append([self.state_dim, 3, 64, 1, 'vf_revolute_enc'])

        # specialize ankle joint
        self.enc_net.append([self.state_dim, 2, 64, 1, 'ankle_enc'])

        self.act_net.append([self.state_dim, 1, 64, 1, 'revolute_act'])

        # specialize ankle joint
        self.act_net.append([self.state_dim, 1, 64, 1, 'ankle_act'])

        self.vf_net.append([self.state_dim, 1, 64, 1, 'vf_out'])
        self.merg_net.append([self.state_dim, 1, 64, 1, 'merger'])

        # value function modules
        if not self.include_action_in_obs:
            self.net_vf_modules.append([[4, 10], 3, None])
            self.net_vf_modules.append([[3, 9], 3, [0]])
            self.net_vf_modules.append([[2, 8], 3, [1]])
        else:
            self.net_vf_modules.append([[4, 10, 13], 3, None])
            self.net_vf_modules.append([[3, 9, 12], 3, [0]])
            self.net_vf_modules.append([[2, 8, 11], 3, [1]])
        self.net_vf_modules.append([[0, 1, 5, 6, 7], 2, [2]])
        self.net_vf_modules.append([[], 7, [3]])

        # policy modules
        if not self.reverse_order:
            self.net_modules.append([[4, 10], 1 if not self.feet_specialized else 4, None])
            self.net_modules.append([[3, 9], 1 if not self.feet_specialized else 4, [0]])
            self.net_modules.append([[2, 8], 1, [1]])
            self.net_modules.append([[0, 1, 5, 6, 7], 0, [2]])

            if self.include_action_in_obs:
                self.net_modules[0][0] += [13]
                self.net_modules[1][0] += [12]
                self.net_modules[2][0] += [11]
            elif self.supp_input:
                self.net_modules[0][0] += [20, 21, 22]
                self.net_modules[1][0] += [17, 18, 19]
                self.net_modules[2][0] += [14, 15, 16]
                self.net_modules[3][0] += [11, 12, 13]

            self.net_modules.append([[], 8, [3, 2], None, False])
            self.net_modules.append([[], 8, [3, 1], None, False])
            self.net_modules.append([[], 8, [3, 0], None, False])
            self.net_modules.append([[], 5, [4]])
            self.net_modules.append([[], 5 if not self.feet_specialized else 6, [5]])
            self.net_modules.append([[], 5 if not self.feet_specialized else 6, [6]])
            self.net_modules.append([[], None, [7, 8, 9], None, False])
        else:
            self.net_modules.append([[0, 1, 5, 6, 7], 0, None])
            self.net_modules.append([[2, 8], 1, [0]])
            self.net_modules.append([[3, 9], 1, [1]])
            self.net_modules.append([[4, 10], 1, [2]])

            self.net_modules.append([[], 8, [3, 1], None, False])
            self.net_modules.append([[], 8, [3, 2], None, False])

            self.net_modules.append([[], 5, [4]])
            self.net_modules.append([[], 5, [5]])
            self.net_modules.append([[], 5, [3]])
            self.net_modules.append([[], None, [6, 7, 8], None, False])

        # dynamics modules
        if self.fwd_bwd_pass:
            self.dyn_enc_net = []
            self.dyn_act_net = []  # using actor as decoder
            self.dyn_merg_net = []
            self.dyn_net_modules = []
            self.dyn_enc_net.append([self.state_dim, 6 + 1, 256, 1, 'dyn_planar_enc'])
            self.dyn_enc_net.append([self.state_dim, 3 + 1, 256, 1, 'dyn_revolute_enc'])
            self.dyn_act_net.append([self.state_dim, 2, 256, 1, 'dyn_planar_dec'])
            self.dyn_act_net.append([self.state_dim, 6, 256, 1, 'dyn_revolute_dec'])
            self.dyn_net_modules.append([[5, 11, 14, 15], 1, None])
            self.dyn_net_modules.append([[4, 10, 13, 15], 1, [0]])
            self.dyn_net_modules.append([[3, 9, 12, 15], 1, [1]])
            self.dyn_net_modules.append([[0, 1, 2, 6, 7, 8, 15], 0, [2]])

            self.dyn_net_modules.append([[3, 9, 12, 16], 1, [3]])
            self.dyn_net_modules.append([[4, 10, 13, 16], 1, [4]])
            self.dyn_net_modules.append([[5, 11, 14, 16], 1, [5]])

            self.dyn_net_modules.append([[], 2, [3]])
            self.dyn_net_modules.append([[], 3, [4]])
            self.dyn_net_modules.append([[], 3, [5]])
            self.dyn_net_modules.append([[], 3, [6]])
            self.dyn_net_modules.append([[], None, [7, 8, 9, 10], None, False])
            self.dyn_net_reorder = np.array([0, 1, 2, 6, 8, 10, 3, 4, 5, 7, 9, 11], dtype=np.int32)
        else:
            self.dyn_enc_net = []
            self.dyn_act_net = []  # using actor as decoder
            self.dyn_merg_net = []
            self.dyn_net_modules = []
            self.dyn_enc_net.append([self.state_dim, 6, 256, 1, 'dyn_planar_enc'])
            self.dyn_enc_net.append([self.state_dim, 3, 256, 1, 'dyn_revolute_enc'])
            self.dyn_act_net.append([self.state_dim, 2, 256, 1, 'dyn_planar_dec'])
            self.dyn_act_net.append([self.state_dim, 6, 256, 1, 'dyn_revolute_dec'])
            self.dyn_merg_net.append([self.state_dim, 1, 256, 1, 'dyn_merger'])
            self.dyn_net_modules.append([[5, 11, 14], 1, None])
            self.dyn_net_modules.append([[4, 10, 13], 1, [0]])
            self.dyn_net_modules.append([[3, 9, 12], 1, [1]])
            self.dyn_net_modules.append([[0, 1, 2, 6, 7, 8], 0, [2]])

            self.dyn_net_modules.append([[], 4, [3, 2], None, False])
            self.dyn_net_modules.append([[], 4, [3, 1], None, False])
            self.dyn_net_modules.append([[], 4, [3, 0], None, False])

            self.dyn_net_modules.append([[], 2, [3]])
            self.dyn_net_modules.append([[], 3, [4]])
            self.dyn_net_modules.append([[], 3, [5]])
            self.dyn_net_modules.append([[], 3, [6]])
            self.dyn_net_modules.append([[], None, [7, 8, 9, 10], None, False])
            self.dyn_net_reorder = np.array([0, 1, 2, 6, 8, 10, 3, 4, 5, 7, 9, 11], dtype=np.int32)

    def _fullspd(self, target_q):
        p = -self.Kp.dot(self.robot_skeleton.q + self.robot_skeleton.dq * self.dt - target_q)
        d = -self.Kd.dot(self.robot_skeleton.dq)
        qddot = np.linalg.solve(self.robot_skeleton.M + self.Kd * self.dt, -self.robot_skeleton.c + p + d + self.robot_skeleton.constraint_forces())
        tau = p + d - self.Kd.dot(qddot) * self.dt

        tau[0:3] = 0

        for i in range(len(self.torque_limit)):
            if abs(tau[i+3]) > self.torque_limit[i]:
                tau[i+3] = np.sign(tau[i+3]) * self.torque_limit[i]

        return tau

    def do_simulation_spd(self, target_q, n_frames):
        total_torque = np.zeros(len(target_q))
        for _ in range(n_frames):
            tau = self._fullspd(target_q)
            total_torque += tau
            self.robot_skeleton.set_forces(tau)
            self.dart_world.step()
            s = self.state_vector()
            if not (np.isfinite(s).all() and (np.abs(s[2:]) < 100).all()):
                break
        return total_torque

    def advance(self, a):
        clamped_control = np.array(a)
        for i in range(len(clamped_control)):
            if clamped_control[i] > self.control_bounds[0][i]:
                clamped_control[i] = self.control_bounds[0][i]
            if clamped_control[i] < self.control_bounds[1][i]:
                clamped_control[i] = self.control_bounds[1][i]
        if self.include_action_in_obs:
            self.prev_a = np.copy(clamped_control)

        target_q = np.zeros(self.robot_skeleton.ndofs)
        for i in range(len(self.control_bounds[0])):
            target_q[3 + i] = (clamped_control[i] + 1.0) / 2.0 * (
                    self.robot_skeleton.q_upper[i + 3] - self.robot_skeleton.q_lower[i + 3]) + \
                              self.robot_skeleton.q_lower[i + 3]

        return self.do_simulation_spd(target_q, self.frame_skip)

    def terminated(self):
        s = self.state_vector()
        posafter, ang = self.robot_skeleton.q[0, 2]
        height = self.robot_skeleton.bodynodes[2].com()[1]

        return not (np.isfinite(s).all() and (np.abs(s[2:]) < 100).all() and
             (height > self.init_height - 0.4) and (height < self.init_height + 0.5))

    def _step(self, a):
        pre_state = [self.state_vector()]

        posbefore = self.robot_skeleton.q[0]
        total_torque = self.advance(a)
        posafter,ang = self.robot_skeleton.q[0,2]
        height = self.robot_skeleton.bodynodes[2].com()[1]

        fall_on_ground = False
        contacts = self.dart_world.collision_result.contacts
        for contact in contacts:
            if contact.bodynode1 == self.robot_skeleton.bodynodes[2] or contact.bodynode2 == \
                    self.robot_skeleton.bodynodes[2]:
                fall_on_ground = True
            if self.supp_input:
                for bid, bn in enumerate(self.robot_skeleton.bodynodes):
                    if bid >= 2:
                        if contact.bodynode1 == bn or contact.bodynode2 == bn:
                            self.body_contact_list[bid-2] = 1.0
                        else:
                            self.body_contact_list[bid-2] = 0.0

        alive_bonus = 1.0
        reward = (posafter - posbefore) / self.dt
        reward += alive_bonus
        reward -= np.square(total_torque*1e-3).sum()
        s = self.state_vector()
        self.accumulated_rew += reward
        self.num_steps += 1.0
        #print(self.num_steps)
        done = self.terminated()
        if not (np.isfinite(s).all() and (np.abs(s[2:]) < 100).all()):
            reward = 0
        #if fall_on_ground:
        #    done = True
        ob = self._get_obs()

        return ob, reward, done, {}

    def _get_obs(self):
        state =  np.concatenate([
            self.robot_skeleton.q[1:],
            self.robot_skeleton.dq,
        ])
        state[0] = self.robot_skeleton.bodynodes[2].com()[1]

        if self.include_action_in_obs:
            state = np.concatenate([state, self.prev_a])

        if self.supp_input:
            for i, bn in enumerate(self.robot_skeleton.bodynodes):
                if i >= 2:
                    com_off = bn.C - self.robot_skeleton.C
                    state = np.concatenate([state, [self.body_contact_list[i-2], com_off[0], com_off[1]]])

        return state


    def reset_model(self):
        self.dart_world.reset()
        qpos = self.robot_skeleton.q + self.np_random.uniform(low=-.005, high=.005, size=self.robot_skeleton.ndofs)
        qvel = self.robot_skeleton.dq + self.np_random.uniform(low=-.005, high=.005, size=self.robot_skeleton.ndofs)
        self.set_state(qpos, qvel)

        if self.supp_input:
            self.body_contact_list = [0.0] * (len(self.robot_skeleton.bodynodes) - 2)

        state = self._get_obs()

        self.init_height = self.robot_skeleton.bodynodes[2].com()[1]

        if self.include_action_in_obs:
            self.prev_a = np.zeros(len(self.control_bounds[0]))

        self.accumulated_rew = 0.0
        self.num_steps = 0.0

        if self.randomize_dynamics:
            for i in range(len(self.robot_skeleton.bodynodes)):
                self.robot_skeleton.bodynodes[i].set_mass(
                    self.bodynode_original_masses[i] + np.random.uniform(-1.5, 1.5))
                self.robot_skeleton.bodynodes[i].set_friction_coeff(
                    self.bodynode_original_frictions[i] + np.random.uniform(-0.5, 0.5))

        return state

    def viewer_setup(self):
        self._get_viewer().scene.tb.trans[2] = -5.5


    def state_vector(self):
        if self.fwd_bwd_pass:
            return np.concatenate([
                self.robot_skeleton.q,
                self.robot_skeleton.dq/10.0,
                [0.0, 1.0]
            ])
        else:
            return np.concatenate([
                self.robot_skeleton.q,
                self.robot_skeleton.dq / 10.0,
            ])

    def set_state_vector(self, state):
        if self.fwd_bwd_pass:
            self.robot_skeleton.set_positions(state[0:int(len(state)/2)-1])
            self.robot_skeleton.set_velocities(state[int(len(state)/2)-1:-2]*10.0)
        else:
            self.robot_skeleton.set_positions(state[0:int(len(state) / 2)])
            self.robot_skeleton.set_velocities(state[int(len(state) / 2):] * 10.0)


