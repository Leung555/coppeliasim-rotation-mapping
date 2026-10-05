import math
import unittest
from main import Odometry, LandmarkMap, project_pixel


class GeometryTests(unittest.TestCase):
    def test_straight(self):
        odom = Odometry(0.1, 0.4)
        odom.update(0, 0)
        odom.update(1, 1)
        self.assertAlmostEqual(odom.x, 0.1)
        self.assertAlmostEqual(odom.y, 0)

    def test_wrap_and_full_rotation(self):
        odom = Odometry(0.1, 0.4)
        odom.update(0, 0)
        for i in range(1, 101):
            a = 4 * math.pi * i / 100
            odom.update(math.atan2(math.sin(-a), math.cos(-a)),
                        math.atan2(math.sin(a), math.cos(a)))
        self.assertAlmostEqual(odom.yaw, 2 * math.pi)
        self.assertAlmostEqual(odom.x, 0)
        self.assertAlmostEqual(odom.y, 0)

    def test_arc(self):
        odom = Odometry(0.1, 0.4)
        odom.update(0, 0)
        odom.update(0, 2)
        self.assertAlmostEqual(odom.x, 0.2 * math.sin(0.5))
        self.assertAlmostEqual(odom.y, 0.2 * (1 - math.cos(0.5)))

    def test_camera_rotation_and_offset(self):
        # Sensor +Z faces body +X, sensor +X faces body +Y.
        matrix = [0, 0, 1, 0.1, 1, 0, 0, 0, 0, 1, 0, 0.2]
        x, y = project_pixel(319.5, 239.5, 2, 640, 480, math.pi/2,
                             matrix, (1, 2, math.pi/2))
        self.assertAlmostEqual(x, 1)
        self.assertAlmostEqual(y, 4.1)
        _, left_y = project_pixel(159.5, 239.5, 2, 640, 480, math.pi/2,
                                 matrix, (0, 0, 0))
        self.assertAlmostEqual(left_y, 1)

    def test_instances_and_classes(self):
        m = LandmarkMap(0.3)
        m.observe('cube', 1, 0, .8)
        m.observe('cube', 1.1, 0, .9)
        m.observe('cube', 2, 0, .8)
        m.observe('sphere', 1, 0, .8)
        self.assertEqual(len(m.objects), 3)
        self.assertAlmostEqual(m.objects[0]['x'], 1.05)
        self.assertEqual(m.objects[0]['observations'], 2)


if __name__ == '__main__':
    unittest.main()
