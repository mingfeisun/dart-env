import numpy as np
from gym import utils
from gym.envs.dart import dart_env
from gym.envs.dart.parameter_managers import *
from gym.envs.dart.sub_tasks import *
import copy


class DartWalker2dEnv(dart_env.DartEnv, utils.EzPickle):
    def __init__(self):
        self.control_bounds = np.array([[1.0]*6,[-1.0]*6])
        #self.control_bounds[1][1] = -0.3
        #self.control_bounds[1][4] = -0.3
        self.action_scale = np.array([100, 100, 20, 100, 100, 20]) *0.01
        obs_dim = 17
        self.param_manager = hopperContactMassManager(self)

        self.avg_div = 0
        self.target_vel = 0.9
        self.split_task_test = False
        self.tasks = TaskList(2)
        self.tasks.add_world_choice_tasks([0, 0])
        self.learn_forwardbackward = False
        self.task_expand_flag = False
        self.state_index = 0

        if self.split_task_test:
            obs_dim += self.tasks.task_input_dim()
        if self.avg_div > 1:
            obs_dim += self.avg_div

        dart_env.DartEnv.__init__(self, ['walker2d.skel', 'walker2d_variation1.skel'\
                                         , 'walker2d_variation2.skel'], 4, obs_dim, self.control_bounds, disableViewer=True)

        self.dart_worlds[0].set_collision_detector(3)
        self.dart_worlds[1].set_collision_detector(0)
        self.dart_worlds[2].set_collision_detector(1)

        self.dart_world=self.dart_worlds[0]
        self.robot_skeleton=self.dart_world.skeletons[-1]
        if not self.disableViewer:
            self._get_viewer().sim = self.dart_world

        # info for building gnn for dynamics
        self.ignore_joint_list = []
        self.ignore_body_list = [0, 1]
        self.joint_property = ['limit']  # what to include in the joint property part
        self.bodynode_property = ['mass']
        self.root_type = 'None'
        self.root_id = 0

        # no joint limit
        for world in self.dart_worlds:
            for skeleton in world.skeletons:
                for jt in range(0, len(skeleton.joints)):
                    for dof in range(len(skeleton.joints[jt].dofs)):
                        if skeleton.joints[jt].has_position_limit(dof):
                            skeleton.joints[jt].set_position_limit_enforced(False)


        utils.EzPickle.__init__(self)

    def about_to_contact(self):
        return False

    def pad_action(self, a):
        full_ac = np.zeros(len(self.robot_skeleton.q))
        full_ac[3:] = a
        return full_ac

    def terminated(self):
        s = self.state_vector()
        height = self.robot_skeleton.bodynodes[2].com()[1]
        ang = self.robot_skeleton.q[2]
        done = not (np.isfinite(s).all() and (np.abs(s[2:]) < 100).all())# and
                   # (height > .8) and (height < 2.0) and (abs(ang) < 1.0))
        return done

    def reward_func(self, a):
        posafter, ang = self.robot_skeleton.q[0, 2]
        height = self.robot_skeleton.bodynodes[2].com()[1]

        alive_bonus = 1.0
        vel = (posafter - self.posbefore) / self.dt
        reward = vel
        reward += alive_bonus
        reward -= 1e-1 * np.square(a).sum()
        joint_limit_penalty = 0
        for j in [-2, -5]:
            if (self.robot_skeleton.q_lower[j] - self.robot_skeleton.q[j]) > -0.05:
                joint_limit_penalty += abs(1.5)
            if (self.robot_skeleton.q_upper[j] - self.robot_skeleton.q[j]) < 0.05:
                joint_limit_penalty += abs(1.5)

        reward -= 5e-1 * joint_limit_penalty

        return reward

    def advance(self, a):
        clamped_control = np.array(a)
        #print(clamped_control)
        for i in range(len(clamped_control)):
            if clamped_control[i] > self.control_bounds[0][i]:
                clamped_control[i] = self.control_bounds[0][i]
            if clamped_control[i] < self.control_bounds[1][i]:
                clamped_control[i] = self.control_bounds[1][i]
        tau = np.zeros(self.robot_skeleton.ndofs)
        tau[3:] = clamped_control * self.action_scale
        self.posbefore = self.robot_skeleton.q[0]

        # compensate for gravity
        tau[1] = self.robot_skeleton.mass() * 9.81

        self.do_simulation(tau, self.frame_skip)



    def _step(self, a):
        self.advance(a)
        reward = self.reward_func(a)

        done = self.terminated()

        ob = self._get_obs()

        return ob, reward, done, {'dyn_model_id':0, 'state_index':self.state_index}

    def _get_obs(self):
        state =  np.concatenate([
            self.robot_skeleton.q[1:],
            np.clip(self.robot_skeleton.dq,-10,10)
        ])
        state[0] = self.robot_skeleton.bodynodes[2].com()[1]

        if self.split_task_test:
            state = np.concatenate([state, self.tasks.get_task_inputs(self.state_index)])

        if self.avg_div > 1:
            return_state = np.zeros(len(state) + self.avg_div)
            return_state[0:len(state)] = state
            return_state[len(state) + self.state_index] = 1
            return return_state

        return state

    def reset_model(self):
        self.dart_world.reset()
        qpos = self.robot_skeleton.q + self.np_random.uniform(low=-.005, high=.005, size=self.robot_skeleton.ndofs)
        qvel = self.robot_skeleton.dq + self.np_random.uniform(low=-.005, high=.005, size=self.robot_skeleton.ndofs)
        self.set_state(qpos, qvel)

        if self.split_task_test:
            if self.task_expand_flag:
                self.tasks.expand_range_param_tasks()
                self.task_expand_flag = False
            self.state_index = np.random.randint(self.tasks.task_num)
            world_choice, pm_id, pm_val, jt_id, jt_val = self.tasks.resample_task(self.state_index)
            if self.dart_world != self.dart_worlds[world_choice]:
                self.dart_world = self.dart_worlds[world_choice]
                self.robot_skeleton = self.dart_world.skeletons[-1]
                qpos = self.robot_skeleton.q + self.np_random.uniform(low=-.005, high=.005, size=self.robot_skeleton.ndofs)
                qvel = self.robot_skeleton.dq + self.np_random.uniform(low=-.005, high=.005, size=self.robot_skeleton.ndofs)
                self.set_state(qpos, qvel)
                if not self.disableViewer:
                    self._get_viewer().sim = self.dart_world
            self.param_manager.controllable_param = pm_id
            self.param_manager.set_simulator_parameters(np.array(pm_val))
            for ind, jtid in enumerate(jt_id):
                self.robot_skeleton.joints[jtid].set_position_upper_limit(0, jt_val[ind][1])
                self.robot_skeleton.joints[jtid].set_position_lower_limit(0, jt_val[ind][0])

        return self._get_obs()

    def viewer_setup(self):
        self._get_viewer().scene.tb.trans[2] = -5.5
