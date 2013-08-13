#
# Copyright 2009 - 2012, Alex Fraser <alex@phatcore.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import sys
import logging
import math

import bge
import aud
import mathutils

import bat.utils
import bat.bmath
import bat.bats
import bat.containers
import bat.event
import bat.render

import Scripts.director
import bat.store

def hasLineOfSight(ob, other):
    hitOb, _, _ = bat.bmath.ray_cast_p2p(other, ob, prop = 'Ray')
    return (hitOb is None)

class AutoCamera(metaclass=bat.bats.Singleton):
    '''Manages the transform of the camera, and provides transitions between
    camera locations. To transition to a new location, call PushGoal. The
    reverse transition can be performed by calling PopGoal.
    '''
    _prefix = 'AC_'

    log = logging.getLogger(__name__ + '.AutoCamera')

    COLLISION_BIAS = 1.0
    MIN_FOCAL_DIST = 3.0
    FOCAL_FAC = 0.1
    BLUR_MULT_ACCEL = 0.001
    BLUR_MULT_MAX = 10.0
    BLUR_MULT_DAMP = 0.1
    # Blur settings vary based on camera type.
    MAX_BLUR = {
            'FIRST': 0,
            'THIRD_SHOULDER': 0.02,
            'THIRD_STATIC': 0.1
            }

    camera = bat.containers.weakprop('camera')
    lastGoal = bat.containers.weakprop('lastGoal')

    def __init__(self):
        '''Create an uninitialised AutoCamera. Call SetCamera to bind it to a
        camera.
        '''
        self.camera = None
        self.defaultLens = 22.0
        self.blurMultiplier = 1.0
        self.blurMultVelocity = 0.0
        self.queue = bat.containers.SafePriorityStack()
        self.focusQueue = bat.containers.SafePriorityStack()
        self.observers = bat.containers.SafeSet()
        self.lastGoal = None
        self.instantCut = False
        self.errorReported = False

        bat.event.EventBus().add_listener(self)
        bat.event.EventBus().replay_last(self, 'TeleportSnail')

    def on_event(self, evt):
        if evt.message == 'TeleportSnail':
            self.on_teleport(evt.body)
        elif evt.message == 'AddCameraGoal':
            self.add_goal(evt.body)
        elif evt.message == 'RemoveCameraGoal':
            self.remove_goal(evt.body)
        elif evt.message == 'AddFocusPoint':
            self.add_focus_point(evt.body)
        elif evt.message == 'RemoveFocusPoint':
            self.remove_focus_point(evt.body)
        elif evt.message == 'BlurAdd':
            self.blurMultVelocity += evt.body

    @bat.bats.expose
    @bat.utils.owner_cls
    def set_camera(self, camera):
        '''Bind to a camera.'''

        AutoCamera.log.info('Setting actual camera to %s', camera)
        self.camera = camera
        self.defaultLens = camera.lens
        bat.utils.get_scene(camera).active_camera = camera

    @bat.bats.expose
    @bat.utils.controller_cls
    def init_filters(self, c):
        '''Initialise filters.'''
        if bat.store.get('/opt/depthOfField', True):
            c.activate(c.actuators['aDof'])

    @bat.bats.expose
    def update(self):
        '''Update the location of the camera. observers will be notified. The
        camera should have a controller set up to call this once per frame.
        '''

        if not self.camera:
            return

        if AutoCamera.log.isEnabledFor(10):
            # Write entire queue when in DEBUG
            sys.stdout.write("\rCamera: {} Focus: {}".format(self.queue, self.focusQueue))
            sys.stdout.flush()

        currentGoal = None
        try:
            currentGoal = self.queue.top()
        except IndexError:
            if not self.errorReported:
                AutoCamera.log.warn('Queue is empty')
                self.errorReported = True
            return

        max_blur = AutoCamera.MAX_BLUR[currentGoal['CameraType']]

        # Keeping track of goals being added and removed it very
        # difficult, so we just consider the last action when deciding
        # whether or not to cut instantly.
        if not self.instantCut:
            # ... but if there's an object in the way, teleport to the nearest
            # safe position.
            ob, hitPoint, _ = self.camera.rayCast(currentGoal, self.camera, 0.0,
                'Ray', True, True, False)
            if ob is not None:
                vectTo = hitPoint - currentGoal.worldPosition
                vectTo *= AutoCamera.COLLISION_BIAS
                self.camera.worldPosition = currentGoal.worldPosition + vectTo

        if self.instantCut:
            self.camera.worldPosition = currentGoal.worldPosition
            self.camera.worldOrientation = currentGoal.worldOrientation
            if hasattr(currentGoal, 'lens'):
                self.camera.lens = currentGoal.lens
            self._update_focal_depth(True, max_blur)
            self.instantCut = False
        else:
            bat.bmath.slow_copy_loc(self.camera, currentGoal, currentGoal['LocFac'])
            bat.bmath.slow_copy_rot(self.camera, currentGoal, currentGoal['RotFac'])

        # Update focal length.
        targetLens = self.defaultLens
        if hasattr(currentGoal, 'lens'):
            targetLens = currentGoal.lens
        # Interpolate FOV, not focal length - the latter is non-linear.
        fov = 1.0 / self.camera.lens
        target_fov = 1.0 / targetLens
        fov = bat.bmath.lerp(fov, target_fov, currentGoal['RotFac'])
        self.camera.lens = 1.0 / fov

        self.lastGoal = currentGoal

        # Update depth of field (blur).
        self._update_focal_depth(False, max_blur)

        try:
            dev = aud.device()
            dev.listener_location = self.camera.worldPosition
            dev.listener_orientation = self.camera.worldOrientation.to_quaternion()
            dev.listener_velocity = (0.0, 0.0, 0.0)
        except aud.error:
            #AutoCamera.log.warn("Can't set audio listener location: %s", e)
            pass

        for ob in self.observers:
            ob.on_camera_moved(self)

    def _update_focal_depth(self, instant, max_blur):
        focalPoint = None
        try:
            focalPoint = self.focusQueue.top()
        except IndexError:
            focalPoint = Scripts.director.Director().mainCharacter
            if focalPoint is None:
                return

        if hasattr(focalPoint, 'get_focal_points'):
            # Pick the point that is closest to the camera.
            points = focalPoint.get_focal_points()
            if len(points) > 0:
                key = bat.bmath.DistanceKey(self.camera)
                points.sort(key=key)
                focalPoint = points[0]

        cam = bge.logic.getCurrentScene().active_camera

        # Convert to depth; assume very large zFar
        # http://www.sjbaker.org/steve/omniv/love_your_z_buffer.html
        vecTo = focalPoint.worldPosition - cam.worldPosition
        z = vecTo.project(cam.getAxisVect((0.0, 0.0, 1.0))).magnitude
        z = max(z, AutoCamera.MIN_FOCAL_DIST)
        depth = 1.0 - cam.near / z
        if instant:
            cam['focalDepth'] = depth
        else:
            cam['focalDepth'] = bat.bmath.lerp(cam['focalDepth'], depth,
                    AutoCamera.FOCAL_FAC)

        # This bit doesn't need to be interpolated; the lens value is already
        # interpolated in 'update'.
        cam['blurRadius'] = min(max_blur,
                cam['baseBlurRadius'] * pow((cam.lens / self.defaultLens), 2))
        cam['blurRadius'] *= self.blurMultiplier

        diff = 1.0 - self.blurMultiplier
        accel = diff * AutoCamera.BLUR_MULT_ACCEL
        if abs(diff) > 0.01 or abs(self.blurMultVelocity) > 0.01:
            self.blurMultiplier, self.blurMultVelocity = bat.bmath.integrate(
                    self.blurMultiplier, self.blurMultVelocity,
                    accel, AutoCamera.BLUR_MULT_DAMP)
            self.blurMultiplier = bat.bmath.clamp(0.0, AutoCamera.BLUR_MULT_MAX,
                    self.blurMultiplier)

    @bat.bats.expose
    @bat.utils.owner_cls
    def add_goal(self, goal):
        '''Give the camera a new goal, and remember the last one. Call
        RemoveGoal to restore the previous relationship. The camera position
        isn't changed until update is called.
        '''
        if isinstance(goal, str):
            try:
                sce = bat.utils.get_scene(goal)
                goal = sce.objects[goal]
            except KeyError or ValueError:
                AutoCamera.log.warn("Can't find goal %s.", goal)
                return
        # Set some defaults for properties.
        bat.utils.set_default_prop(goal, 'LocFac', 0.1)
        bat.utils.set_default_prop(goal, 'RotFac', 0.1)
        bat.utils.set_default_prop(goal, 'InstantCut', False)
        bat.utils.set_default_prop(goal, 'Priority', 1)
        # {'FIRST', 'THIRD_SHOULDER', 'THIRD_STATIC'}
        bat.utils.set_default_prop(goal, 'CameraType', 'THIRD_STATIC')

        # Add the goal to the queue.
        self.queue.push(goal, goal['Priority'])

        if self.queue.top() == goal and goal['InstantCut']:
            # Goal is on top of the stack: it will be switched to next
            if goal['InstantCut'] in (True, 'IN', 'BOTH'):
                AutoCamera.log.info(
                        "Cutting instantly to '%s' because InstantCut = %s",
                        goal.name, goal['InstantCut'])
                self.instantCut = True

        if self.instantCut:
            self.update()
        self.errorReported = False

    @bat.bats.expose
    @bat.utils.owner_cls
    def remove_goal(self, goal):
        '''Remove a goal from the stack. If it was currently in use, the camera
        will switch to follow the next one on the stack. The transform isn't
        changed until update is called.
        '''
        if isinstance(goal, str):
            try:
                sce = bat.utils.get_scene(goal)
                goal = sce.objects[goal]
            except KeyError or ValueError:
                AutoCamera.log.warn("Warning: can't find goal %s.", goal)
                return
        if not goal in self.queue:
            return

        if self.queue.top() == goal:
            # Goal is on top of the stack: it's in use!
            if goal['InstantCut'] in (True, 'OUT', 'BOTH'):
                AutoCamera.log.info(
                        "Cutting instantly to '%s' because InstantCut = %s",
                        goal.name, goal['InstantCut'])
                self.instantCut = True

        self.queue.discard(goal)
        if self.instantCut:
            self.update()

    @bat.bats.expose
    @bat.utils.owner_cls
    def add_focus_point(self, target):
        if isinstance(target, str):
            try:
                sce = bat.utils.get_scene(target)
                target = sce.objects[target]
            except KeyError or ValueError:
                AutoCamera.log.warn("Can't find focus point %s.", target)
                return
        bat.utils.set_default_prop(target, 'FocusPriority', 1)
        self.focusQueue.push(target, target['FocusPriority'])

    @bat.bats.expose
    @bat.utils.owner_cls
    def remove_focus_point(self, target):
        if isinstance(target, str):
            try:
                sce = bat.utils.get_scene(target)
                target = sce.objects[target]
            except KeyError or ValueError:
                AutoCamera.log.warn("Can't find focus point %s.", target)
                return
        self.focusQueue.discard(target)

    def add_observer(self, observer):
        # No need to have remove_observer; that happens automatically when the
        # observer dies.
        self.observers.add(observer)

    def on_teleport(self, spawn_point):
        if isinstance(spawn_point, str):
            try:
                sce = bat.utils.get_scene(spawn_point)
                spawn_point = sce.objects[spawn_point]
            except KeyError:
                AutoCamera.log.warn("Can't find spawn point %s", spawn_point)
                return
        if len(spawn_point.children) <= 0:
            return

        spawn_camera = spawn_point.children[0]
        pos = spawn_camera.worldPosition
        orn = spawn_camera.worldOrientation
        bat.event.Event('RelocatePlayerCamera', (pos, orn)).send(0)

        bat.utils.set_default_prop(spawn_camera, 'InstantCut', 'IN')
        self.add_goal(spawn_camera)
        bat.event.WeakEvent('RemoveCameraGoal', spawn_camera).send(60)


class MainCharSwitcher(bat.bats.BX_GameObject, bge.types.KX_Camera):
    '''Adds self as a goal when an attached sensor is touched by the main
    character.'''
    _prefix = 'MCS_'

    def __init__(self, old_owner):
        self.attached = False

    @bat.bats.expose
    @bat.utils.controller_cls
    def on_touched(self, c):
        mainChar = Scripts.director.Director().mainCharacter
        shouldAttach = False
        for s in c.sensors:
            if mainChar in s.hitObjectList:
                shouldAttach = True
                break

        if shouldAttach and not self.attached:
            AutoCamera().add_goal(self)
        elif not shouldAttach and self.attached:
            AutoCamera().remove_goal(self)
        self.attached = shouldAttach

class MainGoalManager(bat.bats.BX_GameObject, bge.types.KX_GameObject):
    '''Creates cameras that follow the player in response to SetCameraType
    messages. The body of the message should be the name of the camera to
    create (i.e. the name of the objects that embodies that camera).'''

    currentCamera = bat.containers.weakprop('currentCamera')

    log = logging.getLogger(__name__ + '.MainGoalManager')

    def __init__(self, old_owner):
        self.cameraType = None
        bat.event.EventBus().add_listener(self)
        bat.event.EventBus().replay_last(self, 'SetCameraType')

    def on_event(self, evt):
        if evt.message == 'SetCameraType':
            self.set_camera_type(evt.body)

    def set_camera_type(self, name):
        if self.currentCamera is None or self.cameraType != name:
            sce = self.scene
            MainGoalManager.log.info("Switching to camera %s in %s",
                    name, sce)
            oldCamera = self.currentCamera
            self.currentCamera = bat.bats.add_and_mutate_object(sce, name, self)

            ac = AutoCamera().camera
            if ac is not None:
                bat.event.Event('RelocatePlayerCamera',
                        (ac.worldPosition, ac.worldOrientation)).send()
            self.cameraType = name
            if oldCamera is not None:
                oldCamera.endObject()

class OrbitCameraAlignment:
    '''
    Defines how the camera aligns with its target; use with OrbitCamera.

    This class gives the classic 3rd-person adventure camera. It looks towards
    the character, but does not always sit behind. Imagine a circle in the
    air above the character: on each frame, the camera moves the shortest
    distance possible to remain on that circle, unless it is blocked by a wall.
    '''

    def get_home_axes(self, camera, target):
        '''
        Get an alignment that represents the 'natural' view of the target, e.g.
        behind the shoulder.

        @return: forwardVector, upVector
        '''
        upDir = target.getAxisVect(bat.bmath.ZAXIS)
        self.upDir = upDir.copy()
        fwdDir = target.getAxisVect(bat.bmath.YAXIS)
        fwdDir.negate()
        return fwdDir, upDir

    def get_axes(self, camera, target):
        '''
        Get an alignment that is a progression from the previous alignment.

        @return: forwardVector, upVector
        '''
        rawUpDir = target.getAxisVect(bat.bmath.ZAXIS)
        try:
            rawUpDir = bat.bmath.lerp(self.upDir, rawUpDir,
                    OrbitCamera.ZALIGN_FAC)
            rawUpDir.normalize()
        except AttributeError:
            pass
        self.upDir = rawUpDir.copy()

        vectTo = camera.worldPosition - target.worldPosition
        upDir = vectTo.project(rawUpDir)
        fwdDir = vectTo - upDir
        fwdDir.normalize()

        return fwdDir, rawUpDir

class OrbitCamera(bat.impulse.Handler, bat.bats.BX_GameObject, bge.types.KX_GameObject):
    '''A 3rd-person camera that stays a constant distance from its target.'''

    _prefix = 'Orb_'

    UP_DIST = 8.0
    BACK_DIST = 25.0
    DIST_BIAS = 0.5
    EXPAND_FAC = 0.01
    ZALIGN_FAC = 0.025

    HROT_STEP = math.radians(5)
    VROT_MAX = math.radians(45)
    VROT_SPEED = 0.2
    VROT_RESET_RATE = 0.05

    def __init__(self, old_owner):
        self.reset = False

        # These must be members. This information can't be computed from the
        # current state of the frame: they would become smaller when going over
        # a convex surface.
        self.distUp = None
        self.distBack = None

        self.alignment = None

        self.cam_shift = mathutils.Vector((0, 0))
        bat.impulse.Input().add_handler(self)

        AutoCamera().add_goal(self)
        bat.event.EventBus().add_listener(self)
        bat.event.EventBus().replay_last(self, 'RelocatePlayerCamera')
        bat.event.EventBus().replay_last(self, 'SetCameraAlignment')

    @bat.bats.expose
    def update(self):
        if self.alignment is None:
            return

        mainChar = Scripts.director.Director().mainCharacter
        if mainChar is None:
            return
        target = mainChar.get_camera_tracking_point()

        # Find directions to project along
        fwdDir, upDir = self.alignment.get_axes(self, target)

        # Adjust based on user camera movement input. Transform is:
        # 1. Rotate around up-axis by horizontal movement.
        # 2. Rotate around right-axis by vertical movement.
        if abs(self.cam_shift.x) > 0.0001 or abs(self.cam_shift.y) > 0.0001:
            rightDir = fwdDir.cross(upDir)
            yrot = mathutils.Quaternion(upDir, self.cam_shift.x * OrbitCamera.HROT_STEP)
            xrot = mathutils.Quaternion(rightDir, self.cam_shift.y * OrbitCamera.VROT_MAX)
            transform = yrot * xrot

            fwdDir = transform * fwdDir
            upDir = transform * upDir

        if self.distUp is None:
            # The first time this is run (after creation), distUp and distBack
            # are not known - so calculate them. On subsequent frames, the
            # cached values will be used.
            relPos = self.worldPosition - target.worldPosition
            relUpPos = relPos.project(upDir)
            relFwdPos = relPos - relUpPos
            self.distUp = relUpPos.magnitude
            self.distBack = relFwdPos.magnitude

        # Look for the ceiling above the target.
        upPos, self.distUp = self.cast_ray(target.worldPosition, upDir,
                self.distUp, OrbitCamera.UP_DIST)

        # Search backwards for a wall.
        backDir = fwdDir.copy()
        backPos, self.distBack = self.cast_ray(upPos, backDir, self.distBack,
                OrbitCamera.BACK_DIST)
        self.worldPosition = backPos
        # Set linv to something very small; zero would be ignored.
        self.worldLinearVelocity = (0, 0, 0.0001)

        # Orient the camera towards the target.
        self.alignAxisToVect(upDir, 1)
        self.alignAxisToVect(fwdDir, 2)

        self.reset = False

    def cast_ray(self, origin, direction, lastDist, maxDist):
        through = origin + direction

        hitOb, hitPoint, hitNorm = self.rayCast(
            through,        # obTo
            origin,            # obFrom
            maxDist,        # dist
            'Ray',            # prop
            1,                # face normal
            1                # x-ray
        )

        targetDist = maxDist
        if hitOb and (hitNorm.dot(direction) < 0):
            #
            # If dot > 0, the tracking object is inside another mesh.
            # It's not perfect, but better not bring the camera forward
            # in that case, or the camera will be inside too.
            #
            targetDist = (hitPoint - origin).magnitude

        targetDist = targetDist * OrbitCamera.DIST_BIAS

        if targetDist < lastDist:
            dist = targetDist
        else:
            dist = bat.bmath.lerp(lastDist, targetDist,
                    OrbitCamera.EXPAND_FAC)

        pos = origin + (direction * dist)
        return pos, dist

    def can_handle_input(self, state):
        return state.name in {'CameraMovement', 'CameraReset'}

    def handle_input(self, state):
        if state.name == 'CameraMovement':
            self.handle_cam_movement(state)
        elif state.name == 'CameraReset':
            self.handle_reset(state)

    def handle_cam_movement(self, state):
        if self.reset:
            # Don't allow shifting when position is being reset.
            return
        self.cam_shift.x = state.direction.x
        yoffset = self.cam_shift.y + (state.direction.y * OrbitCamera.VROT_SPEED)
        self.cam_shift.y = bat.bmath.clamp(-1, 1, yoffset)

    def handle_reset(self, state):
        if not state.positive:
            return

        mainChar = Scripts.director.Director().mainCharacter
        if mainChar is None:
            return
        target = mainChar.get_camera_tracking_point()
        target_fwd_dir, target_up_dir = self.alignment.get_home_axes(self, target)

        fwdDir = self.getAxisVect(bat.bmath.ZAXIS)

        yrot_diff = fwdDir.angle(target_fwd_dir, 0)
        RESET_MIN_ROT = math.radians(2)
        if abs(yrot_diff) < RESET_MIN_ROT:
            return

        # Find sign of rotation
        target_right_dir = target_fwd_dir.cross(target_up_dir)
        right_component = fwdDir.project(target_right_dir)
        clockwise = right_component.dot(target_right_dir) > 0

        yrot = min(OrbitCamera.HROT_STEP, yrot_diff)
        yrot /= OrbitCamera.HROT_STEP
        if not clockwise:
            yrot = -yrot

        self.cam_shift.x = yrot

        if self.cam_shift.y > OrbitCamera.VROT_RESET_RATE:
            self.cam_shift.y -= OrbitCamera.VROT_RESET_RATE
        elif self.cam_shift.y < -OrbitCamera.VROT_RESET_RATE:
            self.cam_shift.y += OrbitCamera.VROT_RESET_RATE
        else:
            self.cam_shift.y = 0

        self.reset = True

    def on_event(self, evt):
        if evt.message == 'RelocatePlayerCamera':
            pos, orn = evt.body
            self.worldPosition = pos
            if orn is not None:
                self.worldOrientation = orn
        elif evt.message == 'SetCameraAlignment':
            self.alignment = evt.body

class PathCamera(bat.bats.BX_GameObject, bge.types.KX_GameObject):
    '''A camera goal that follows the active player. It tries to follow the same
    path as the player, so that it avoids static scenery.
    '''

    _prefix = 'PC_'

    log = logging.getLogger(__name__ + '.PathCamera')

    # The maximum number of nodes to track. Once this number is reached, the
    # oldest nodes will be removed.
    MAX_NODES = 50
    # The minimum distance to leave between nodes. 
    MIN_DIST = 2

    ACCELERATION = 0.05
    DAMPING = 0.2

    # The preferred distance from the target (a point above the actor).
    # Note that this mill change depending on the situation; e.g. it becomes
    # lower when the ceiling is low.
    REST_DISTANCE = 5.0
    # The amount to expand the radius when it is safe to do so.
    EXPAND_FACTOR = 4.0
    # The amount to expand the radius when no other factors are at play. Ideally
    # REST_DISTANCE would just be increased, but in practice the contraction
    # factor is never below about 1.5 - so a similar value is used for
    # continuity.
    REST_FACTOR = 1.5

    # The distance above the actor that the camera should aim for. Actually, the
    # camera will aim for a point ZOFFSET * CEILING_AVOIDANCE_BIAS away from the
    # actor.
    ZOFFSET = 5.0
    CEILING_AVOIDANCE_BIAS = 0.5
    # The maximum height difference between two consecutive targets. This
    # smoothes off the path as the actor goes under a ceiling.
    ZOFFSET_INCREMENT = MIN_DIST * 0.5

    # The number of consecutive nodes that must be seen before being accepted.
    # If this is too low, the camera will clip through sharp corners. 
    NODE_DELAY = 2
    # The number of frames to wait before deciding that the predictive node is
    # obscured.
    EXPAND_ON_WAIT = 10
    EXPAND_OFF_WAIT = 5
    # Responsiveness of the radius adjustment.
    RADIUS_SPEED = 0.1
    # Responsiveness of the camera orientation.
    ALIGN_Y_SPEED = 0.15
    ALIGN_Z_SPEED = 0.5
    # Distance to project predictive node.
    PREDICT_FWD = 20.0
    PREDICT_UP = 50.0

    class CameraNode:
        '''A single point in a path used by the CameraPathGoal. These act as
        way points for the camera to follow.'''

        log = logging.getLogger(__name__ + '.PathCamera.CameraNode')

        # Note: This class uses strong references, so it will hang around even
        # when the associated game object dies. But that's OK, because the only
        # class that uses this one is PathCamera, which should end with its
        # object, thus releasing this one.

        def __init__(self):
            # Defines the location of the way point. Using a way point allows the
            # node to parented to an object.
            self.owner = bat.utils.add_object('PointMarker')
            if not PathCamera.CameraNode.log.isEnabledFor(10):
                self.owner.visible = False
            else:
                self.marker = bat.utils.add_object("PointMarker")
                self.marker.color = bat.render.BLUE
                self.marker.visible = True
                self.owner.visible = True

            # It is an error to access these next two before calling update().
            self.ceilingHeight = None
            self.target = None

        def update(self):
            self.target = bat.bmath.ZAXIS.copy()
            self.target *= PathCamera.ZOFFSET
            self.target = bat.bmath.to_world(self.owner, self.target)
            hitOb, hitPoint, _ = bat.bmath.ray_cast_p2p(
                    self.target, # objto
                    self.owner.worldPosition, # objfrom
                    prop = 'Ray')

            if hitOb:
                vec = hitPoint - self.owner.worldPosition
                self.setCeilingHeight(vec.magnitude)
            else:
                self.setCeilingHeight(PathCamera.ZOFFSET)

        def get_target(self):
            bias = self.ceilingHeight / PathCamera.ZOFFSET
            bias *= PathCamera.CEILING_AVOIDANCE_BIAS
            return bat.bmath.lerp(self.owner.worldPosition, self.target, bias)

        def destroy(self):
            self.owner.endObject()
            if PathCamera.CameraNode.log.isEnabledFor(10):
                self.marker.endObject()

        def setCeilingHeight(self, height):
            self.ceilingHeight = height
            if PathCamera.CameraNode.log.isEnabledFor(10):
                self.marker.worldPosition = self.get_target()

    target = bat.containers.weakprop('target')

    def __init__(self, old_owner):
        # A list of CameraNodes. Must use a safe list here, because the nodes
        # attach themselves to nearby objects as children - and if one of those
        # objects is deleted, the node will be too.
        self.path = bat.containers.SafeList()
        self.pathHead = PathCamera.CameraNode()
        self.linV = bat.bmath.ZEROVEC.copy()

        self.radMult = 1.0
        self.expand = bat.bats.FuzzySwitch(PathCamera.EXPAND_ON_WAIT,
                                        PathCamera.EXPAND_OFF_WAIT, True)
        self.target = None

        AutoCamera().add_goal(self)
        bat.event.EventBus().add_listener(self)
        bat.event.EventBus().replay_last(self, 'MainCharacterSet')
        bat.event.EventBus().replay_last(self, 'RelocatePlayerCamera')

        if PathCamera.log.isEnabledFor(10):
            self.targetVis = bat.utils.add_object('DebugReticule')
            self.predictVis = bat.utils.add_object('DebugReticule')

    def on_event(self, event):
        if event.message == 'MainCharacterSet':
            self.target = event.body
        elif event.message == 'RelocatePlayerCamera':
            pos, orn = event.body
            self.worldPosition = pos
            if orn is not None:
                self.worldOrientation = orn

    @bat.bats.expose
    def update(self):
        self.updateWayPoints()
        self.advanceGoal()

    def advanceGoal(self):
        '''Move the camera to follow the main character. This will either follow
        the path or the character, depending on which is closest. Don't worry
        about interpolation; the AutoCamera will smooth out the motion later.'''
        #
        # Get the vector from the camera to the target.
        #
        actor = self.target
        if actor is None:
            return

        # Get the vector from the camera to the next way point.
        node, pathLength = self._getNextWayPoint()
        target = node.get_target()
        dirWay = target - self.worldPosition
        dirWay.normalize()

        # Adjust preferred distance from actor based on current conditions.
        contract = False
        if node.ceilingHeight < PathCamera.ZOFFSET:
            # Bring the camera closer when under a low ceiling or in a tunnel.
            contract = True

        if self._canSeeFuture():
            # Otherwise, relax the camera if the predicted point is visible.
            self.expand.turn_on()
        else:
            self.expand.turn_off()

        radMult = 1.0
        if contract:
            radMult = 1.0 + (node.ceilingHeight / PathCamera.ZOFFSET)
        elif self.expand.is_on():
            radMult = PathCamera.EXPAND_FACTOR
        else:
            radMult = PathCamera.REST_FACTOR
        self.radMult = bat.bmath.lerp(self.radMult, radMult,
                                    PathCamera.RADIUS_SPEED)
        restNear = self.REST_DISTANCE
        restFar = self.REST_DISTANCE * self.radMult

        # Determine the acceleration, based on the distance from the actor.
        dist = self.getDistanceTo(node.owner) + pathLength
        acceleration = 0.0
        if dist < restNear:
            acceleration = (dist - restNear) * self.ACCELERATION
        elif dist > restFar:
            acceleration = (dist - restFar) * self.ACCELERATION

        # Apply the (fake) acceleration.
        self.linV = self.linV + (dirWay * acceleration)
        self.linV = self.linV * (1.0 - self.DAMPING)
        self.worldPosition = self.worldPosition + self.linV
        # Nullify actual acceleration.
        self.worldLinearVelocity = (0, 0, 0.0001)

        # Align the camera's Y-axis with the global Z, and align
        # its Z-axis with the direction to the target. The alignment with Y is
        # modulated by how horizontal the camera is right now - this prevents
        # the camera from spinning too rapidly when pointing up.
        look = dirWay.copy()
        look.negate()
        yfac = 1 - abs(self.getAxisVect(bat.bmath.ZAXIS).dot(bat.bmath.ZAXIS))
        yfac = (yfac * 0.5) + 0.5
        yfac *= PathCamera.ALIGN_Y_SPEED

        if actor.localCoordinates:
            axis = node.owner.getAxisVect(bat.bmath.ZAXIS)
            self.alignAxisToVect(axis, 1, yfac)
        else:
            self.alignAxisToVect(bat.bmath.ZAXIS, 1, yfac)
        self.alignAxisToVect(look, 2, PathCamera.ALIGN_Z_SPEED)

        if PathCamera.log.isEnabledFor(10):
            self.targetVis.worldPosition = target

    def _canSeeFuture(self):
        # TODO: Make a DEBUG function decorator that runs stuff before and after
        ok, projectedPoint = self._canSeeFuture_()
        if PathCamera.log.isEnabledFor(10):
            self.predictVis.worldPosition = projectedPoint
            if ok:
                self.predictVis.color = bat.render.BLACK
            else:
                self.predictVis.color = bat.render.RED
        return ok

    def _canSeeFuture_(self):
        if len(self.path) < 2:
            # Can't determine direction. Return True if actor is visible.
            projectedPoint = self.pathHead.owner.worldPosition
            return hasLineOfSight(self, projectedPoint), projectedPoint

        # Try a point ahead of the actor. If the path is curving, project the
        # point 'down' in anticipation of the motion.
        a, b = self.path[0], self.path[1]
        ba = a.owner.worldPosition - b.owner.worldPosition
        ba.normalize()
        projectedPoint = a.owner.worldPosition + (ba * PathCamera.PREDICT_FWD)

        hitOb, hitPoint, _ = bat.bmath.ray_cast_p2p(
                projectedPoint, a.owner, prop = 'Ray')
        if hitOb is not None:
            vect = hitPoint - a.owner.worldPosition
            vect.magnitude = vect.magnitude * 0.9
            projectedPoint = a.owner.worldPosition + vect

        # Check the difference in direction of consecutive line segments.
        dot = 1.0
        cb = ba.copy()
        for i, c in enumerate(self.path):#[2:7]:
            if i < 2:
                continue
            if i > 7:
                break
            cb = b.owner.worldPosition - c.owner.worldPosition
            cb.normalize()

            dot = ba.dot(cb)
            if dot < 0.999:
                break

        if dot < 0.999:
            # The path is bent; project the point in the direction of the
            # curvature. The cross product gives the axis of rotation.
            rotAxis = ba.cross(cb)
            upAxis = rotAxis.cross(ba)
            pp2 = projectedPoint - (upAxis * PathCamera.PREDICT_FWD)

            hitOb, hitPoint, _ = bat.bmath.ray_cast_p2p(
                    pp2, projectedPoint, prop = 'Ray')
            if hitOb is not None:
                vect = hitPoint - projectedPoint
                vect.magnitude = vect.magnitude * 0.9
                pp2 = projectedPoint + vect
            projectedPoint = pp2

        if hasLineOfSight(self, projectedPoint):
            return True, projectedPoint
        else:
            return False, projectedPoint

    def _getNextWayPoint(self):
        node, pathLength = self._getNextWayPoint_()
        if PathCamera.log.isEnabledFor(10):
            # Colour nodes.
            found = False

            if node == self.pathHead:
                found = True
                node.owner.color = bat.render.RED
            else:
                node.owner.color = bat.render.WHITE

            for n in self.path:
                if node == n:
                    n.owner.color = bat.render.RED
                    found = True
                elif found:
                    n.owner.color = bat.render.BLACK
                else:
                    n.owner.color = bat.render.WHITE

        return node, pathLength

    def _getNextWayPoint_(self):
        '''Find the next point that the camera should advance towards.'''

        # Try to go straight to the actor.
        nFound = 0
        node = self.pathHead
        target = node.get_target()
        if (hasLineOfSight(self, node.owner) and
            hasLineOfSight(self, target)):
            return node, 0.0

        # Actor is obscured; find a good way point.
        nSearched = 0
        for currentNode in self.path:
            nSearched += 1

            currentTarget = currentNode.get_target()

            if (not hasLineOfSight(self, currentNode.owner) or
                not hasLineOfSight(self, currentTarget)):
                nFound = 0
                continue

            nFound += 1
            if nFound >= self.NODE_DELAY:
                node = currentNode
                break

        distance = nSearched * self.MIN_DIST
        if len(self.path) > 0:
            distance += self.pathHead.owner.getDistanceTo(self.path[0].owner)
        return node, distance

    def updateWayPoints(self):
        actor = self.target
        if actor is None:
            return

        if actor.localCoordinates:
            bat.bmath.copy_transform(actor, self.pathHead.owner)
        else:
            self.pathHead.owner.worldPosition = actor.worldPosition
            bat.bmath.reset_orientation(self.pathHead.owner)

        # Add a new node if the actor has moved far enough.
        addNew = False
        if len(self.path) == 0:
            addNew = True
        else:
            currentPos = actor.worldPosition
            vec = currentPos - self.path[0].owner.worldPosition
            if vec.magnitude > self.MIN_DIST:
                addNew = True

        if addNew:
            node = PathCamera.CameraNode()

            if actor.localCoordinates:
                bat.bmath.copy_transform(actor, node.owner)
            else:
                node.owner.worldPosition = actor.worldPosition
            node.owner.worldPosition = actor.worldPosition
            self.path.insert(0, node)
            if actor.touchedObject is not None:
                node.owner.setParent(actor.touchedObject, False)
            if len(self.path) > self.MAX_NODES:
                # Delete the oldest node.
                self.path.pop().destroy()

        # Update the ceiling height for each node, ensuring a smooth transition
        # between consecutive z-offsets.
        self.pathHead.update()
        for node in self.path:
            node.update()

        def pingPong(iterable):
            # pingPong('ABC') --> A B C C B A
            for element in iterable:
                yield element
            for element in reversed(iterable):
                yield element

        def marginMin(current, nxt, margin):
            return min(current + margin, nxt)

        currentOffset = self.pathHead.ceilingHeight
        for node in pingPong(self.path):
            node.setCeilingHeight(marginMin(currentOffset, node.ceilingHeight,
                                self.ZOFFSET_INCREMENT))
            currentOffset = node.ceilingHeight
        self.pathHead.setCeilingHeight(marginMin(currentOffset,
                                        self.pathHead.ceilingHeight,
                                        self.ZOFFSET_INCREMENT))
    def endObject(self):
        for node in self.path:
            node.destroy()
        if PathCamera.log.isEnabledFor(10):
            self.targetVis.endObject()
            self.predictVis.endObject()
        self.pathHead.destroy()
        bge.types.KX_GameObject.endObject(self)

#
# Helper for sensing when camera is inside something.
#

class CameraCollider(bat.bats.BX_GameObject, bge.types.KX_GameObject):
    '''Senses when the camera is inside something. This senses when the
    camera touches a volumetric object, and then tracks to see when the camera
    enters and leaves that object, adjusting the screen filter appropriately.'''

    MAX_DIST = 1000.0

    def __init__(self, old_owner):
        AutoCamera().add_observer(self)
        self.set_filter_colour(None)

    def on_camera_moved(self, ac):
        self.worldPosition = ac.camera.worldPosition
        pos = ac.camera.worldPosition.copy()

        direction = bat.bmath.ZAXIS.copy()
        ob = self.cast_for_water(pos, direction)
        if ob is not None:
            # Double check - works around bug with rays that strike a glancing
            # blow on an edge.
            direction.x = direction.y = 0.1
            direction.normalize()
            ob = self.cast_for_water(pos, direction)

        if ob is not None:
            self.set_filter_colour(ob['VolumeCol'])
        else:
            self.set_filter_colour(None)

    def set_filter_colour(self, colour):
        try:
            if colour == self.last_colour:
                return
        except AttributeError:
            pass
        self.last_colour = colour
        bat.event.Event('ShowFilter', colour).send()

    def cast_for_water(self, pos, direction):
        through = pos + direction * CameraCollider.MAX_DIST
        ob, _, normal = bat.bmath.ray_cast_p2p(through, pos, prop='VolumeCol')
        if ob is not None and normal.dot(direction) > 0.0:
            return ob
        else:
            return None

#
# camera for viewing the background scene
#

class SkyBox(bat.bats.BX_GameObject, bge.types.KX_Camera):
    '''Sticks to the camera to prevent lens distortion.'''

    def __init__(self, old_owner):
        AutoCamera().add_observer(self)

    def on_camera_moved(self, ac):
        self.worldPosition = ac.camera.worldPosition
