from gym.envs.dart.dart_env import DartEnv
# ^^^^^ so that user gets the correct error
# message if Dart is not installed correctly
from gym.envs.dart.parameter_managers import *

from gym.envs.dart.cart_pole import DartCartPoleEnv
from gym.envs.dart.hopper import DartHopperEnv
#from gym.envs.dart.full_body import DartFullbodyEnv
#from gym.envs.dart.hopperRBF import DartHopperRBFEnv
#from gym.envs.dart.hopper_cont import DartHopperEnvCont
from gym.envs.dart.reacher import DartReacherEnv
from gym.envs.dart.robot_walk import DartRobotWalk
from gym.envs.dart.cart_pole_img import DartCartPoleImgEnv

#cloth:
from gym.envs.dart.sphere_tube import DartClothSphereTubeEnv
from gym.envs.dart.reacher_cloth import DartClothReacherEnv
from gym.envs.dart.reacher_cloth_1arm import DartClothReacherEnv2
from gym.envs.dart.reacher_cloth_sleeve import DartClothSleeveReacherEnv
from gym.envs.dart.reacher_cloth_shirt import DartClothShirtReacherEnv

from gym.envs.dart.walker2d import DartWalker2dEnv
from gym.envs.dart.walker3d import DartWalker3dEnv
from gym.envs.dart.walker3d_spd import DartWalker3dSPDEnv
from gym.envs.dart.inverted_double_pendulum import DartDoubleInvertedPendulumEnv
from gym.envs.dart.dog import DartDogEnv
from gym.envs.dart.reacher2d import DartReacher2dEnv

