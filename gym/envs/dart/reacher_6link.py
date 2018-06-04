import numpy as np
from gym import utils
from gym.envs.dart import dart_env


class DartReacher6LinkEnv(dart_env.DartEnv, utils.EzPickle):
    def __init__(self):
        self.target = np.array([0.8, -0.6, 0.6])
        self.action_scale = np.array([10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10])
        self.control_bounds = np.array([[1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
                                        [-1.0, -1.0, -1.0, -1.0, -1.0, -1.0, -1.0, -1.0, -1.0, -1.0, -1.0, -1.0]])
        obs_dim = 30
        self.include_task = False
        if not self.include_task:
            obs_dim -= 6
        dart_env.DartEnv.__init__(self, 'reacher_multilink/reacher_6link.skel', 4, obs_dim, self.control_bounds, disableViewer=True)
        self.initialize_articunet()
        utils.EzPickle.__init__(self)

    def initialize_articunet(self, reverse_order = None):
        # setups for articunet
        self.state_dim = 32
        self.task_dim = 6 if self.include_task else 0
        self.enc_net = []
        self.act_net = []
        self.vf_net = []
        self.merg_net = []
        self.net_modules = []
        self.net_vf_modules = []
        self.enc_net.append([self.state_dim, 4, 64, 1, 'universal_enc'])
        self.enc_net.append([self.state_dim, 4, 64, 1, 'vf_universal_enc'])
        self.act_net.append([self.state_dim+self.task_dim, 2, 64, 1, 'universal_act'])
        self.vf_net.append([self.state_dim+self.task_dim, 1, 64, 1, 'vf_out'])
        self.merg_net.append([self.state_dim, 1, 64, 1, 'merger'])

        # value function modules
        self.net_vf_modules.append([[10, 11, 22, 23], 1, None])
        self.net_vf_modules.append([[8, 9, 20, 21], 1, [0]])
        self.net_vf_modules.append([[6, 7, 18, 19], 1, [1]])
        self.net_vf_modules.append([[4, 5, 16, 17], 1, [2]])
        self.net_vf_modules.append([[2, 3, 14, 15], 1, [3]])
        self.net_vf_modules.append([[0, 1, 12, 13], 1, [4]])
        self.net_vf_modules.append([[], None, [5], [24, 25, 26, 27, 28, 29] if self.include_task else None])
        self.net_vf_modules.append([[], 3, [6]])

        # policy modules
        self.net_modules.append([[10, 11, 22, 23], 0, None])
        self.net_modules.append([[8, 9, 20, 21], 0, [0]])
        self.net_modules.append([[6, 7, 18, 19], 0, [1]])
        self.net_modules.append([[4, 5, 16, 17], 0, [2]])
        self.net_modules.append([[2, 3, 14, 15], 0, [3]])
        self.net_modules.append([[0, 1, 12, 13], 0, [4]])
        self.net_modules.append([[], 4, [5, 4], None, False])
        self.net_modules.append([[], 4, [5, 3], None, False])
        self.net_modules.append([[], 4, [5, 2], None, False])
        self.net_modules.append([[], 4, [5, 1], None, False])
        self.net_modules.append([[], 4, [5, 0], None, False])
        self.net_modules.append([[], None, [5], [24, 25, 26, 27, 28, 29] if self.include_task else None])
        self.net_modules.append([[], None, [6], [24, 25, 26, 27, 28, 29] if self.include_task else None])
        self.net_modules.append([[], None, [7], [24, 25, 26, 27, 28, 29] if self.include_task else None])
        self.net_modules.append([[], None, [8], [24, 25, 26, 27, 28, 29] if self.include_task else None])
        self.net_modules.append([[], None, [9], [24, 25, 26, 27, 28, 29] if self.include_task else None])
        self.net_modules.append([[], None, [10], [24, 25, 26, 27, 28, 29] if self.include_task else None])

        self.net_modules.append([[], 2, [11]])
        self.net_modules.append([[], 2, [12]])
        self.net_modules.append([[], 2, [13]])
        self.net_modules.append([[], 2, [14]])
        self.net_modules.append([[], 2, [15]])
        self.net_modules.append([[], 2, [16]])

        self.net_modules.append([[], None, [17, 18, 19, 20, 21, 22], None, False])

    def _step(self, a):
        clamped_control = np.array(a)
        for i in range(len(clamped_control)):
            if clamped_control[i] > self.control_bounds[0][i]:
                clamped_control[i] = self.control_bounds[0][i]
            if clamped_control[i] < self.control_bounds[1][i]:
                clamped_control[i] = self.control_bounds[1][i]
        tau = np.multiply(clamped_control, self.action_scale)

        fingertip = np.array([0.0, -0.25, 0.0])
        vec = self.robot_skeleton.bodynodes[-1].to_world(fingertip) - self.target
        reward_dist = - np.linalg.norm(vec)
        reward_ctrl = - np.square(tau).sum() * 0.002
        alive_bonus = 0
        reward = reward_dist + reward_ctrl + alive_bonus

        self.do_simulation(tau, self.frame_skip)
        ob = self._get_obs()

        s = self.state_vector()

        self.num_steps += 1

        done = not (np.isfinite(s).all())

        if (-reward_dist < 0.1):
            reward += 2.0

        return ob, reward, done, {}

    def _get_obs(self):
        theta = self.robot_skeleton.q
        fingertip = np.array([0.0, -0.25, 0.0])
        vec = self.robot_skeleton.bodynodes[-1].to_world(fingertip) - self.target
        if self.include_task:
            return np.concatenate([self.robot_skeleton.q, self.robot_skeleton.dq, self.target, vec]).ravel()
        else:
            return np.concatenate([self.robot_skeleton.q, self.robot_skeleton.dq]).ravel()

    def reset_model(self):
        self.dart_world.reset()
        qpos = self.robot_skeleton.q + self.np_random.uniform(low=-.01, high=.01, size=self.robot_skeleton.ndofs)
        qvel = self.robot_skeleton.dq + self.np_random.uniform(low=-.01, high=.01, size=self.robot_skeleton.ndofs)
        self.set_state(qpos, qvel)
        while True:
            self.target = self.np_random.uniform(low=-1, high=1, size=3)
            if np.linalg.norm(self.target) < 1.5: break
        self.target = np.array([0.7, -0.4, 0.2])

        self.dart_world.skeletons[0].q = [0, 0, 0, self.target[0], self.target[1], self.target[2]]

        self.num_steps = 0

        return self._get_obs()

    def viewer_setup(self):
        self._get_viewer().scene.tb.trans[2] = -3.5
        self._get_viewer().scene.tb._set_theta(0)
        self.track_skeleton_id = 0