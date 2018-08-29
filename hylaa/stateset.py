'''
Generalized Star and other Star data structures
Stanley Bak
Aug 2016
'''

import numpy as np

from hylaa import lputil

from hylaa.hybrid_automaton import Mode
from hylaa.timerutil import Timers
from hylaa.util import Freezable
from hylaa.lpinstance import LpInstance
from hylaa.predecessor import TransitionPredecessor, AggregationPredecessor

from hylaa import lpplot

class StateSet(Freezable):
    '''
    A set of states with a common mode.
    '''

    next_computation_path_id = 0 # a unique counter for computation path nodes

    def __init__(self, lpi, mode, cur_steps_since_start=None, predecessor=None, computation_path_id=None):
        assert isinstance(lpi, LpInstance)
        assert isinstance(mode, Mode)

        self.mode = mode
        self.lpi = lpi

        # computation_path_id can check two StateSets are clones at different steps in the same continuous post sequence
        if computation_path_id is None:
            self.computation_path_id = self.__class__.next_computation_path_id
            self.__class__.next_computation_path_id += 1
        else:
            self.computation_path_id = computation_path_id

        self.cur_step_in_mode = 0

        if cur_steps_since_start is not None:
            assert len(cur_steps_since_start) == 2 # needs to be an interval in case this stateset is an aggregation
            self.cur_steps_since_start = cur_steps_since_start.copy()
        else:
            self.cur_steps_since_start = [0, 0]

        # the predecessor to this StateSet
        assert isinstance(predecessor, (type(None), AggregationPredecessor, TransitionPredecessor))
        self.predecessor = predecessor

        self.is_concrete = self._is_concrete_state()
        
        # the LP row of the strongest constraint for each invariant condition
        # this is used to eliminate redundant constraints as the lpi is intersected with the invariant at each step
        self.invariant_constraint_rows = None 

        self.basis_matrix = np.identity(mode.a_csr.shape[0])
        self.input_effects_list = None if mode.b_csr is None else [] # list of input effects at each step

        # used for plotting
        self._verts = None # cached vertices at the current step
        self.assigned_plot_dim = False # set to True on first call to verts()
        self.xdim = None # set on first call to verts()
        self.ydim = None # set on first call to verts()

        self.freeze_attrs()

    def clone(self, keep_computation_path_id=False):
        'deep copy this StateSet'

        i = None if not keep_computation_path_id else self.computation_path_id

        rv = StateSet(self.lpi.clone(), self.mode, self.cur_steps_since_start, self.predecessor, i)

        rv.cur_step_in_mode = self.cur_step_in_mode
        rv.invariant_constraint_rows = self.invariant_constraint_rows.copy()
        rv.basis_matrix = self.basis_matrix.copy()

        return rv

    def __str__(self):
        'short string representation of this state set'

        return "[StateSet in '{}']".format(self.mode.name)

    def _is_concrete_state(self):
        '''is this a concrete state (no aggregation along computation path)

        this is used to compute self.is_concrete
        '''

        rv = True

        if self.predecessor is not None:
            if isinstance(self.predecessor, AggregationPredecessor):
                rv = False
            elif isinstance(self.predecessor, TransitionPredecessor):
                rv = self.predecessor.state.is_concrete
            else:
                raise RuntimeError("Unknown predecessor type: {}".format(type(self.predecessor)))

        return rv
            
    def step(self):
        'update the star based on values from a new simulation time instant'

        Timers.tic("step")

        self.cur_step_in_mode += 1
        self.cur_steps_since_start[0] += 1
        self.cur_steps_since_start[1] += 1

        Timers.tic('get_bm')
        self.basis_matrix, input_effects_matrix = self.mode.time_elapse.get_basis_matrix(self.cur_step_in_mode)
        Timers.toc('get_bm')

        Timers.tic('set_bm')
        lputil.set_basis_matrix(self.lpi, self.basis_matrix)
        Timers.toc('set_bm')

        if input_effects_matrix is not None:
            self.input_effects_list.append(input_effects_matrix)
            
            Timers.tic('add_input_effects')
            lputil.add_input_effects_matrix(self.lpi, input_effects_matrix, self.mode)
            Timers.toc('add_input_effects')

        self._verts = None # cached vertices no longer valid

        Timers.toc("step")

    def verts(self, plotman, subplot=0):
        'get the vertices for plotting this state set, wraps around so rv[0] == rv[-1]'

        Timers.tic('verts')

        if self._verts is None:
            self._verts = [None] * plotman.num_subplots

        if self._verts[subplot] is None:
            min_time = self.cur_steps_since_start[0] * plotman.core.settings.step_size
            max_time = self.cur_steps_since_start[1] * plotman.core.settings.step_size
            time_interval = (min_time, max_time)

            if not self.assigned_plot_dim:
                self.assigned_plot_dim = True

                self.xdim = []
                self.ydim = []

                for i in range(plotman.num_subplots):
                    self.xdim.append(plotman.settings.xdim_dir[i])
                    self.ydim.append(plotman.settings.ydim_dir[i])

                    if isinstance(self.xdim[i], dict):
                        assert self.mode.name in self.xdim[i], "mode {} not in xdim plot direction dict".format(
                            self.mode.name)
                        self.xdim[i] = self.xdim[i][self.mode.name]

                    if isinstance(self.ydim[i], dict):
                        assert self.mode.name in self.ydim[i], "mode {} not in ydim plot direction dict".format(
                            self.mode.name)
                        self.ydim[i] = self.ydim[i][self.mode.name]

            self._verts[subplot] = lpplot.get_verts(self.lpi, xdim=self.xdim[subplot], ydim=self.ydim[subplot], \
                                           plot_vecs=plotman.plot_vec_list[subplot], cur_time=time_interval)
            assert self._verts[subplot] is not None, "verts() was unsat"
            
        Timers.toc('verts')

        return self._verts[subplot]

    def intersect_invariant(self):
        '''intersect the current state set with the mode invariant

        returns whether the state set is still feasbile after intersection'''

        Timers.tic("intersect_invariant")

        has_intersection = False

        if self.invariant_constraint_rows is None:
            self.invariant_constraint_rows = [None] * len(self.mode.inv_list)

        for invariant_index, lc in enumerate(self.mode.inv_list):
            if lputil.check_intersection(self.lpi, lc.negate()):
                has_intersection = True
                old_row = self.invariant_constraint_rows[invariant_index]
                vec = lc.csr.toarray()[0]
                rhs = lc.rhs

                if old_row is None:
                    # new constriant
                    row = lputil.add_init_constraint(self.lpi, vec, rhs, self.basis_matrix, self.input_effects_list)
                    self.invariant_constraint_rows[invariant_index] = row
                else:
                    # strengthen existing constraint possibly
                    row = lputil.try_replace_init_constraint(self.lpi, old_row, vec, rhs, self.basis_matrix, \
                                                             self.input_effects_list)
                    self.invariant_constraint_rows[invariant_index] = row

                # adding the invariant condition may make the lp infeasible
                if not self.lpi.is_feasible():
                    break

        is_feasible = True if not has_intersection else self.lpi.is_feasible()

        Timers.toc("intersect_invariant")

        return is_feasible
