import Box2D
import numpy as np
from shapely import affinity
from shapely.geometry import Polygon

import lib.aux.ang_aux


class BodySegment:
    def __init__(self, space, pos, orientation, seg_vertices, color):
        self.space = space
        self.color = color
        self.pos = pos
        self.orientation = orientation
        self.seg_vertices = seg_vertices
        # self.vertices = None

    def draw(self, viewer, color=None, filled=True):
        if color is None :
            color=self.color
        for vertices in self.vertices:
            viewer.draw_polygon(vertices, filled=filled, color=color)

    # @property
    def get_color(self):
        return self.color

    def get_position(self):
        return np.array(self.pos)

    def set_position(self, pos):
        self.pos = pos

    def set_orientation(self, orientation):
        self.orientation = orientation

    def set_pose(self, pos, orientation):
        self.set_position(pos)
        self.set_orientation(orientation)

    def get_orientation(self):
        return self.orientation

    def get_normalized_orientation(self):
        angle = self.get_orientation()
        # I normalize the angle_to_x_axis in [-pi,pi]
        angle %= 2 * np.pi
        # if angle > np.pi:
        #     angle -= 2 * np.pi
        return angle

    def get_shape(self, scale=1):
        p0 = Polygon(self.vertices[0])
        p = affinity.scale(p0, xfact=scale, yfact=scale)
        return p

    def set_color(self, color):
        color = np.asarray(color, dtype=np.int32)
        color = np.maximum(color, np.zeros_like(color, dtype=np.int32))
        color = np.minimum(color, np.full_like(color, 255, dtype=np.int32))
        self.color = color


class Box2DSegment(BodySegment):

    def __init__(self, space: Box2D.b2World, physics_pars, facing_axis, **kwargs):
        super().__init__(space=space, **kwargs)
        if self.__class__ == Box2DSegment:
            raise NotImplementedError('Abstract class Box2DSegment cannot be instantiated.')
        self.physics_pars = physics_pars
        self._body: Box2D.b2Body = self.space.CreateDynamicBody(
            position=Box2D.b2Vec2(*self.pos),
            angle=self.orientation,
            linearDamping=physics_pars['lin_damping'],
            angularDamping=physics_pars['ang_damping'])
        self._body.linearVelocity = Box2D.b2Vec2(*[.0, .0])
        self._body.angularVelocity = .0
        self._body.bullet = True

        # overriden by LarvaBody
        self.facing_axis = facing_axis

        # CAUTION
        # This sets the body'sigma origin (where pos, orientation is derived from)
        # self._body.localCenter = b2Vec2(0.0, 0.0)
        # this sets the body' center of mass (where velocity is set etc)
        # self._body.massData.center= self._body.localCenter
        # self._body.massData.center= b2Vec2(0.0, 0.0)
        # self._body.localCenter = self._body.massData.center

    # @property
    def get_position(self):
        # CAUTION CAUTION This took me a whole day.
        # worldCenter gets the point where the torque is applied
        # pos gets a point (tried to identify whether it is center of mass or origin, no luck) unknown how
        pos = self._body.worldCenter
        return np.asarray(pos)

    def set_position(self, position):
        self._body.position = position

    def get_orientation(self):
        return self._body.angle

    def get_angularvelocity(self):
        return self._body.angularVelocity

    def set_orientation(self, orientation):
        # orientation %= 2 * np.pi
        self._body.angle = orientation

    def get_pose(self):
        pos = np.asarray(self._body.position)
        return tuple((*pos, self._body.angle))

    def set_lin_vel(self, lin_vel, local=False):
        if local:
            lin_vel = self._body.GetWorldVector(np.asarray(lin_vel))
        self._body.linearVelocity = Box2D.b2Vec2(lin_vel)

    def set_ang_vel(self, ang_vel):
        self._body.angularVelocity = ang_vel

    def set_mass(self, mass):
        self._body.mass = mass

    def get_mass(self):
        return self._body.mass

    def add_mass(self, added_mass):
        self._body.mass += added_mass

    def set_massdata(self, massdata):
        self._body.massData = massdata

    def get_local_point(self, point):
        return np.asarray(self._body.GetLocalPoint(np.asarray(point)))

    def get_local_vector(self, vector):
        return np.asarray(self._body.GetLocalVector(vector))

    def get_local_orientation(self, angle):
        return angle - self._body.angle

    def get_local_pose(self, pose):
        return tuple((*self.get_local_point(pose[:2]), self.get_local_orientation(pose[2])))

    def get_world_point(self, point):
        return self._body.GetWorldPoint(np.asarray(point))

    def get_world_vector(self, vector):
        return np.asarray(self._body.GetWorldVector(vector))

    def get_world_facing_axis(self):
        return np.asarray(self._body.GetWorldVector(self.facing_axis))

    def collides_with(self, other):
        for contact_edge in self._body.contacts_gen:
            if contact_edge.other == other and contact_edge.contact.touching:
                return True


class Box2DPolygon(Box2DSegment):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # TODO: right now this assumes that all subpolygons have the same number of edges
        # TODO: rewrite such that arbitrary subpolygons can be used here
        vertices = self.seg_vertices

        centroid = np.zeros(2)
        area = .0
        for vs in vertices:
            # compute centroid of circle_to_polygon
            r0 = np.roll(vs[:, 0], 1)
            r1 = np.roll(vs[:, 1], 1)
            a = 0.5 * np.abs(np.dot(vs[:, 0], r1) - np.dot(vs[:, 1], r0))
            area += a
            # FIXME This changed in refactoring. It is wrong probably.
            # Find a way to use compute_centroid(points) function
            centroid += np.mean(vs, axis=0) * a

        centroid /= area

        self.__local_vertices = vertices - centroid
        self.__local_vertices.setflags(write=False)
        for v in self.__local_vertices:
            self._body.CreatePolygonFixture(
                shape=Box2D.b2PolygonShape(vertices=v.tolist()),
                density=self.physics_pars['density'],
                friction=self.physics_pars['friction'],
                restitution=self.physics_pars['restitution'],
                # radius=.00000001
            )

        self._fixtures = self._body.fixtures

        # FIXME for some reason this produces error
        # self._body.inertia = self.physics_pars['inertia']

    @property
    def vertices(self):
        return np.array([[self.get_world_point(v) for v in vertices] for vertices in self.__local_vertices])


class DefaultSegment(BodySegment):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # print(self.seg_vertices[0], self.pos)
        self.update_vertices(self.pos, self.orientation)
        # print(self.seg_vertices[0], self.pos)
        # print(self.vertices, self.pos)

        self.lin_vel = 0.0
        self.ang_vel = 0.0
        self.ang_acc = 0.0

    def update_vertices(self, pos, orient):
        self.vertices = [pos + lib.aux.ang_aux.rotate_around_center_multi(self.seg_vertices[0], -orient)]

    def get_pose(self):
        return np.array(self.pos), self.orientation

    def get_world_point(self, local_point):
        return self.get_position() + lib.aux.ang_aux.rotate_around_center(point=local_point, radians=-self.get_orientation())

    def get_angularvelocity(self):
        return self.ang_vel

    def set_lin_vel(self, lin_vel):
        self.lin_vel = lin_vel

    def set_ang_vel(self, ang_vel):
        self.ang_vel = ang_vel

